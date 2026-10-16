use bounded_request_model::{
    CacheState, CommandKind, Completion, Effect, Engine, EngineConfig, Event, LowerOutcome,
    Operation, ParentId, PrepareResult, Reject, Status, Token,
};
use std::collections::{HashMap, HashSet};

fn config(slots: usize, lower_depth: usize) -> EngineConfig {
    EngineConfig {
        slots,
        lower_depth,
        cache: CacheState::Enabled,
    }
}

#[derive(Default)]
struct RunLog {
    completions: Vec<Completion>,
    submits: Vec<(u64, CommandKind)>,
    max_lower: usize,
    max_resident: usize,
    retired: HashSet<Token>,
}

fn run_fair(engine: &mut Engine, inline: bool, log: &mut RunLog) {
    let mut steps = 0usize;
    while let Some(effect) = engine.poll_effect() {
        steps += 1;
        assert!(steps < 100_000, "fair run failed to quiesce");
        assert!(!engine.snapshot().lock_held, "callback effect escaped under lock");
        log.max_lower = log.max_lower.max(engine.snapshot().lower_occupied);
        log.max_resident = log.max_resident.max(engine.snapshot().resident_parents);
        match effect {
            Effect::MarkPending { .. } | Effect::StaleIgnored { .. } => {}
            Effect::Prepare { token, .. } => {
                engine.notify(Event::PrepareFinished {
                    token,
                    result: PrepareResult::Ready,
                });
            }
            Effect::Submit { token, parent, .. } => {
                log.submits.push((parent.0, token.kind));
                if inline {
                    engine.notify(Event::LowerCompleted {
                        token,
                        outcome: LowerOutcome::success(token.bytes),
                    });
                    engine.notify(Event::SubmitReturned { token });
                } else {
                    engine.notify(Event::SubmitReturned { token });
                    engine.notify(Event::LowerCompleted {
                        token,
                        outcome: LowerOutcome::success(token.bytes),
                    });
                }
            }
            Effect::CancelLower { token, .. } => {
                engine.notify(Event::LowerCompleted {
                    token,
                    outcome: LowerOutcome::error(Status::IoError, 0),
                });
            }
            Effect::Retire { token, .. } => {
                assert!(log.retired.insert(token), "token retired twice: {token:?}");
                engine.notify(Event::Retired { token });
            }
            Effect::Complete(completion) => {
                let parent = completion.parent;
                log.completions.push(completion);
                engine.notify(Event::ParentDelivered { parent });
            }
        }
    }
    engine.check_invariants().unwrap();
}

#[test]
fn delayed_single_active_lower_completion_keeps_pump_live() {
    let mut engine = Engine::new(config(12, 1)).unwrap();
    for _ in 0..12 {
        engine.admit(Operation::read(1, 512)).unwrap();
    }

    let mut log = RunLog::default();
    run_fair(&mut engine, false, &mut log);

    assert_eq!(log.completions.len(), 12);
    assert!(log.completions.iter().all(|c| c.status == Status::Ok));
    assert_eq!(log.max_lower, 1);
    assert_eq!(engine.snapshot().resident_parents, 0);
}

#[test]
fn round_robin_fairness_prevents_a_read_stream_from_starving_a_write() {
    let mut engine = Engine::new(config(2, 1)).unwrap();
    let write = engine.admit(Operation::write(1, 512)).unwrap();
    engine.admit(Operation::read(1, 512)).unwrap();
    let mut write_submitted = false;
    let mut reads_completed = 0;
    let mut steps = 0;

    while reads_completed < 20 && !write_submitted {
        steps += 1;
        assert!(steps < 1_000);
        let effect = engine.poll_effect().expect("pump stalled with resident work");
        match effect {
            Effect::MarkPending { .. } | Effect::StaleIgnored { .. } => {}
            Effect::Prepare { token, .. } => engine.notify(Event::PrepareFinished {
                token,
                result: PrepareResult::Ready,
            }),
            Effect::Submit { token, parent, .. } if parent == write => {
                write_submitted = true;
                engine.notify(Event::SubmitReturned { token });
                engine.notify(Event::LowerCompleted {
                    token,
                    outcome: LowerOutcome::success(token.bytes),
                });
            }
            Effect::Submit { token, .. } => {
                engine.notify(Event::SubmitReturned { token });
                engine.notify(Event::LowerCompleted {
                    token,
                    outcome: LowerOutcome::success(token.bytes),
                });
            }
            Effect::Retire { token, .. } => engine.notify(Event::Retired { token }),
            Effect::Complete(c) if c.parent != write => {
                reads_completed += 1;
                engine.notify(Event::ParentDelivered { parent: c.parent });
                engine.admit(Operation::read(1, 512)).unwrap();
            }
            Effect::Complete(c) => engine.notify(Event::ParentDelivered { parent: c.parent }),
            Effect::CancelLower { .. } => panic!("unexpected cancellation"),
        }
    }
    assert!(write_submitted, "eligible write starved behind a read stream");
}

#[test]
fn inline_completion_waits_for_submit_return_before_retirement() {
    let mut engine = Engine::new(config(2, 1)).unwrap();
    let parent = engine.admit(Operation::read(1, 512)).unwrap();

    assert!(matches!(engine.poll_effect(), Some(Effect::MarkPending { .. })));
    let token = match engine.poll_effect().unwrap() {
        Effect::Prepare { token, .. } => token,
        other => panic!("expected prepare, got {other:?}"),
    };
    engine.notify(Event::PrepareFinished {
        token,
        result: PrepareResult::Ready,
    });
    let submit = engine.poll_effect().unwrap();
    assert!(matches!(submit, Effect::Submit { token: t, .. } if t == token));

    engine.notify(Event::LowerCompleted {
        token,
        outcome: LowerOutcome::success(512),
    });
    assert!(!matches!(engine.poll_effect(), Some(Effect::Retire { .. })));
    engine.notify(Event::SubmitReturned { token });
    assert!(matches!(engine.poll_effect(), Some(Effect::Retire { token: t, .. }) if t == token));
    engine.notify(Event::Retired { token });
    assert!(matches!(engine.poll_effect(), Some(Effect::Complete(c)) if c.parent == parent));
}

#[test]
fn zero_byte_parent_completes_without_prepare_or_submit() {
    let mut engine = Engine::new(config(2, 1)).unwrap();
    let parent = engine.admit(Operation::read(0, 512)).unwrap();
    assert!(matches!(
        engine.poll_effect(),
        Some(Effect::MarkPending { parent: p }) if p == parent
    ));
    assert!(matches!(
        engine.poll_effect(),
        Some(Effect::Complete(c)) if c.parent == parent && c.status == Status::Ok && c.bytes == 0
    ));
}

#[test]
fn callback_reentry_sets_rescan_and_does_not_recursively_submit() {
    let mut engine = Engine::new(config(3, 1)).unwrap();
    let first = engine.admit(Operation::read(1, 512)).unwrap();
    let second = engine.admit(Operation::read(1, 512)).unwrap();

    let mut first_token = None;
    while let Some(effect) = engine.poll_effect() {
        match effect {
            Effect::MarkPending { .. } => {}
            Effect::Prepare { token, parent, .. } if parent == first => {
                engine.notify(Event::PrepareFinished {
                    token,
                    result: PrepareResult::Ready,
                });
            }
            Effect::Submit { token, parent, .. } if parent == first => {
                first_token = Some(token);
                engine.notify(Event::LowerCompleted {
                    token,
                    outcome: LowerOutcome::success(512),
                });
                engine.notify(Event::Cancel { parent: second });
                assert_eq!(engine.snapshot().lower_occupied, 1);
                engine.notify(Event::SubmitReturned { token });
            }
            Effect::Retire { token, .. } => engine.notify(Event::Retired { token }),
            Effect::Complete(c) => engine.notify(Event::ParentDelivered { parent: c.parent }),
            other => panic!("unexpected reentrant effect: {other:?}"),
        }
    }
    assert!(first_token.is_some());
    assert_eq!(engine.snapshot().resident_parents, 0);
    engine.check_invariants().unwrap();
}

#[test]
fn cancellation_races_preserve_ownership_and_cancel_once() {
    // Precommit cancellation: prepared storage retires, submit never occurs.
    let mut pre = Engine::new(config(1, 1)).unwrap();
    let p = pre.admit(Operation::read(1, 512)).unwrap();
    assert!(matches!(pre.poll_effect(), Some(Effect::MarkPending { .. })));
    let t = match pre.poll_effect().unwrap() {
        Effect::Prepare { token, .. } => token,
        other => panic!("expected prepare, got {other:?}"),
    };
    pre.notify(Event::Cancel { parent: p });
    pre.notify(Event::PrepareFinished {
        token: t,
        result: PrepareResult::Ready,
    });
    assert!(matches!(pre.poll_effect(), Some(Effect::Retire { token, .. }) if token == t));
    pre.notify(Event::Retired { token: t });
    assert!(matches!(pre.poll_effect(), Some(Effect::Complete(c)) if c.status == Status::Cancelled));

    // Postcommit cancellation: wait for submit return, then issue one cancel.
    let mut post = Engine::new(config(1, 1)).unwrap();
    let p = post.admit(Operation::read(1, 512)).unwrap();
    post.poll_effect(); // MarkPending
    let t = match post.poll_effect().unwrap() {
        Effect::Prepare { token, .. } => token,
        other => panic!("expected prepare, got {other:?}"),
    };
    post.notify(Event::PrepareFinished {
        token: t,
        result: PrepareResult::Ready,
    });
    assert!(matches!(post.poll_effect(), Some(Effect::Submit { .. })));
    post.notify(Event::Cancel { parent: p });
    assert!(!matches!(post.poll_effect(), Some(Effect::CancelLower { .. })));
    post.notify(Event::SubmitReturned { token: t });
    assert!(matches!(post.poll_effect(), Some(Effect::CancelLower { token, .. }) if token == t));
    post.notify(Event::Cancel { parent: p });
    assert!(!matches!(post.poll_effect(), Some(Effect::CancelLower { .. })));
    post.notify(Event::LowerCompleted {
        token: t,
        outcome: LowerOutcome::error(Status::IoError, 128),
    });
    assert!(matches!(post.poll_effect(), Some(Effect::Retire { .. })));
    post.notify(Event::Retired { token: t });
    assert!(matches!(post.poll_effect(), Some(Effect::Complete(c)) if c.status == Status::Cancelled && c.bytes == 128));
}

#[test]
fn stale_callback_after_slot_reuse_cannot_touch_new_parent() {
    let mut engine = Engine::new(config(1, 1)).unwrap();
    let first = engine.admit(Operation::read(1, 512)).unwrap();
    let mut log = RunLog::default();
    run_fair(&mut engine, false, &mut log);
    let old = *log.retired.iter().next().unwrap();
    assert_eq!(log.completions[0].parent, first);

    let second = engine.admit(Operation::read(1, 512)).unwrap();
    engine.notify(Event::LowerCompleted {
        token: old,
        outcome: LowerOutcome::success(512),
    });
    assert!(matches!(engine.poll_effect(), Some(Effect::MarkPending { parent }) if parent == second));
    assert!(matches!(engine.poll_effect(), Some(Effect::StaleIgnored { token }) if token == old));
    run_fair(&mut engine, false, &mut log);
    assert_eq!(log.completions.len(), 2);
    assert_eq!(log.completions[1].parent, second);
    assert!(log.retired.iter().any(|t| t.generation > old.generation));
}

#[test]
fn write_flush_and_write_through_barriers_are_admission_ordered() {
    let mut engine = Engine::new(config(8, 2)).unwrap();
    let w1 = engine.admit(Operation::write(1, 512)).unwrap();
    let flush = engine.admit(Operation::Flush).unwrap();
    let w2 = engine.admit(Operation::write(1, 512)).unwrap();
    let read = engine.admit(Operation::read(1, 512)).unwrap();
    let wt = engine.admit(Operation::write_through(1, 512)).unwrap();
    let w3 = engine.admit(Operation::write(1, 512)).unwrap();

    let mut log = RunLog::default();
    for _ in 0..6 {
        assert!(matches!(engine.poll_effect(), Some(Effect::MarkPending { .. })));
    }
    let w1_token = match engine.poll_effect().unwrap() {
        Effect::Prepare { token, parent, .. } if parent == w1 => token,
        other => panic!("expected first write prepare, got {other:?}"),
    };
    engine.notify(Event::PrepareFinished {
        token: w1_token,
        result: PrepareResult::Ready,
    });
    assert!(matches!(
        engine.poll_effect(),
        Some(Effect::Submit { token, parent, .. }) if token == w1_token && parent == w1
    ));
    log.submits.push((w1.0, CommandKind::Data));
    engine.notify(Event::SubmitReturned { token: w1_token });

    let read_token = match engine.poll_effect().unwrap() {
        Effect::Prepare { token, parent, .. } if parent == read => token,
        other => panic!("read did not cross blocked flush: {other:?}"),
    };
    engine.notify(Event::PrepareFinished {
        token: read_token,
        result: PrepareResult::Ready,
    });
    assert!(matches!(
        engine.poll_effect(),
        Some(Effect::Submit { token, parent, .. }) if token == read_token && parent == read
    ));
    log.submits.push((read.0, CommandKind::Data));
    engine.notify(Event::SubmitReturned { token: read_token });
    engine.notify(Event::LowerCompleted {
        token: read_token,
        outcome: LowerOutcome::success(read_token.bytes),
    });
    engine.notify(Event::LowerCompleted {
        token: w1_token,
        outcome: LowerOutcome::success(w1_token.bytes),
    });
    run_fair(&mut engine, false, &mut log);
    let position = |p: ParentId| log.submits.iter().position(|(id, _)| *id == p.0).unwrap();
    assert!(position(w1) < position(flush));
    assert!(position(flush) < position(w2));
    assert!(position(read) < position(flush), "read must cross the flush barrier");
    let wt_sync = log
        .submits
        .iter()
        .position(|(id, kind)| *id == wt.0 && *kind == CommandKind::Sync)
        .unwrap();
    assert!(position(w2) < wt_sync);
    assert!(wt_sync < position(w3));
}

#[test]
fn failed_queue_release_quarantines_and_drains_live_work() {
    let mut engine = Engine::new(config(3, 2)).unwrap();
    let frozen_parent = engine.admit(Operation::read(1, 512)).unwrap();
    let live_parent = engine.admit(Operation::read(1, 512)).unwrap();
    let waiting_parent = engine.admit(Operation::read(1, 512)).unwrap();

    let mut submitted = HashMap::new();
    let mut completions = Vec::new();
    let mut cancel_count = 0;
    let mut steps = 0;
    while let Some(effect) = engine.poll_effect() {
        steps += 1;
        assert!(steps < 200);
        match effect {
            Effect::MarkPending { .. } | Effect::StaleIgnored { .. } => {}
            Effect::Prepare { token, .. } => engine.notify(Event::PrepareFinished {
                token,
                result: PrepareResult::Ready,
            }),
            Effect::Submit { token, parent, .. } => {
                submitted.insert(parent, token);
                engine.notify(Event::SubmitReturned { token });
                if token.kind == CommandKind::ReleaseQueue {
                    engine.notify(Event::LowerCompleted {
                        token,
                        outcome: LowerOutcome::error(Status::IoError, 0),
                    });
                } else if parent == live_parent {
                    let frozen_token = submitted[&frozen_parent];
                    engine.notify(Event::LowerCompleted {
                        token: frozen_token,
                        outcome: LowerOutcome::frozen_error(Status::IoError, 0),
                    });
                }
            }
            Effect::CancelLower { token, .. } => {
                cancel_count += 1;
                engine.notify(Event::LowerCompleted {
                    token,
                    outcome: LowerOutcome::error(Status::IoError, 0),
                });
            }
            Effect::Retire { token, .. } => engine.notify(Event::Retired { token }),
            Effect::Complete(c) => {
                let parent = c.parent;
                completions.push(c);
                engine.notify(Event::ParentDelivered { parent });
            }
        }
    }
    assert!(engine.snapshot().quarantined);
    assert_eq!(cancel_count, 1, "only the live peer needs lower cancellation");
    assert_eq!(completions.len(), 3);
    assert!(completions.iter().any(|c| c.parent == frozen_parent));
    assert!(completions.iter().any(|c| c.parent == live_parent && c.status == Status::IoError));
    assert!(completions.iter().any(|c| c.parent == waiting_parent && c.status == Status::IoError));
    assert_eq!(engine.admit(Operation::read(1, 512)), Err(Reject::Quarantined));
}

#[test]
fn qd12_stream_of_1024_async_reads_never_stalls_after_warmup() {
    let mut engine = Engine::new(config(12, 1)).unwrap();
    let mut admitted = 0usize;
    let mut completed = 0usize;
    let mut log = RunLog::default();

    while completed < 1024 {
        while admitted < 1024 && engine.snapshot().resident_parents < 12 {
            engine.admit(Operation::read(1, 2048)).unwrap();
            admitted += 1;
        }
        let before = log.completions.len();
        run_fair(&mut engine, false, &mut log);
        completed += log.completions.len() - before;
        assert!(admitted >= completed);
    }

    assert_eq!(admitted, 1024);
    assert_eq!(completed, 1024);
    assert!(engine.snapshot().accepted_total >= 16);
    assert_eq!(log.max_lower, 1);
    assert!(log.max_resident <= 12);
    assert_eq!(engine.snapshot().resident_parents, 0);
}

#[test]
fn randomized_fair_schedules_preserve_safety_and_eventual_completion() {
    let mut seed = 0x9e37_79b9_7f4a_7c15u64;
    for _case in 0..64 {
        let mut engine = Engine::new(config(12, 1)).unwrap();
        let mut expected = HashSet::new();
        let mut completed = HashSet::new();
        let mut outstanding_tokens = Vec::new();
        let mut steps = 0usize;

        for _ in 0..48 {
            let chunks = 1 + (next_u64(&mut seed) % 3) as u32;
            let op = if next_u64(&mut seed) % 5 == 0 {
                Operation::write(chunks, 512)
            } else {
                Operation::read(chunks, 512)
            };
            if let Ok(parent) = engine.admit(op) {
                expected.insert(parent);
            }

            for _ in 0..(1 + next_u64(&mut seed) % 9) {
                steps += 1;
                let Some(effect) = engine.poll_effect() else { break };
                assert!(!engine.snapshot().lock_held);
                match effect {
                    Effect::MarkPending { parent } => {
                        if next_u64(&mut seed) % 13 == 0 {
                            engine.notify(Event::Cancel { parent });
                        }
                    }
                    Effect::Prepare { token, .. } => {
                        engine.notify(Event::PrepareFinished {
                            token,
                            result: PrepareResult::Ready,
                        });
                    }
                    Effect::Submit { token, .. } => {
                        outstanding_tokens.push(token);
                        if next_u64(&mut seed) & 1 == 0 {
                            engine.notify(Event::LowerCompleted {
                                token,
                                outcome: LowerOutcome::success(token.bytes),
                            });
                            engine.notify(Event::SubmitReturned { token });
                        } else {
                            engine.notify(Event::SubmitReturned { token });
                            engine.notify(Event::LowerCompleted {
                                token,
                                outcome: LowerOutcome::success(token.bytes),
                            });
                        }
                        if next_u64(&mut seed) % 11 == 0 {
                            engine.notify(Event::LowerCompleted {
                                token,
                                outcome: LowerOutcome::success(token.bytes),
                            });
                        }
                    }
                    Effect::CancelLower { token, .. } => engine.notify(Event::LowerCompleted {
                        token,
                        outcome: LowerOutcome::error(Status::IoError, 0),
                    }),
                    Effect::Retire { token, .. } => engine.notify(Event::Retired { token }),
                    Effect::Complete(c) => {
                        assert!(completed.insert(c.parent));
                        engine.notify(Event::ParentDelivered { parent: c.parent });
                    }
                    Effect::StaleIgnored { .. } => {}
                }
                engine.check_invariants().unwrap();
                assert!(engine.snapshot().lower_occupied <= 1);
                assert!(engine.snapshot().resident_parents <= 12);
            }
        }

        // Fair tail: acknowledge every remaining effect and lower operation.
        let mut log = RunLog::default();
        run_fair(&mut engine, next_u64(&mut seed) & 1 == 0, &mut log);
        for c in log.completions {
            assert!(completed.insert(c.parent));
        }
        assert!(!expected.is_empty(), "random schedule admitted no work");
        assert_eq!(completed, expected);
        assert_eq!(engine.snapshot().resident_parents, 0);

        // Every remembered old token is harmless after the run.
        for token in outstanding_tokens.into_iter().take(4) {
            engine.notify(Event::LowerCompleted {
                token,
                outcome: LowerOutcome::success(token.bytes),
            });
        }
        while engine.poll_effect().is_some() {}
        engine.check_invariants().unwrap();
        assert!(steps < 100_000);
    }
}

fn next_u64(state: &mut u64) -> u64 {
    *state ^= *state << 13;
    *state ^= *state >> 7;
    *state ^= *state << 17;
    *state
}

