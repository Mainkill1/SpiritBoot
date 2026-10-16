//! Executable state-machine model for a bounded storage request pump.
//!
//! The environment drives the model in two steps. `notify` records an event
//! under the modeled state lock. `poll_effect` advances the iterative pump by
//! at most one outside-lock action. The environment may call `notify` while
//! executing that action, which models callback reentry without recursion.

use std::collections::{HashSet, VecDeque};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum CacheState {
    Enabled,
    Disabled,
    Unqualified,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct EngineConfig {
    pub slots: usize,
    pub lower_depth: usize,
    pub cache: CacheState,
}

#[derive(Clone, Copy, Debug, Eq, Hash, Ord, PartialEq, PartialOrd)]
pub struct ParentId(pub u64);

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Operation {
    Read { chunks: u32, bytes_per_chunk: u32 },
    Write { chunks: u32, bytes_per_chunk: u32 },
    WriteThrough { chunks: u32, bytes_per_chunk: u32 },
    Flush,
}

impl Operation {
    pub fn read(chunks: u32, bytes_per_chunk: u32) -> Self {
        Self::Read { chunks, bytes_per_chunk }
    }

    pub fn write(chunks: u32, bytes_per_chunk: u32) -> Self {
        Self::Write { chunks, bytes_per_chunk }
    }

    pub fn write_through(chunks: u32, bytes_per_chunk: u32) -> Self {
        Self::WriteThrough { chunks, bytes_per_chunk }
    }

    fn requested_bytes(self) -> u64 {
        match self {
            Self::Read { chunks, bytes_per_chunk }
            | Self::Write { chunks, bytes_per_chunk }
            | Self::WriteThrough { chunks, bytes_per_chunk } => {
                u64::from(chunks) * u64::from(bytes_per_chunk)
            }
            Self::Flush => 0,
        }
    }

    fn is_read(self) -> bool {
        matches!(self, Self::Read { .. })
    }

    fn is_write(self) -> bool {
        matches!(self, Self::Write { .. } | Self::WriteThrough { .. })
    }

    fn is_barrier(self) -> bool {
        matches!(self, Self::Flush | Self::WriteThrough { .. })
    }
}

#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
pub enum CommandKind {
    Data,
    Sync,
    ReleaseQueue,
}

#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
pub struct Token {
    pub slot: usize,
    pub generation: u64,
    pub sequence: u64,
    pub kind: CommandKind,
    pub bytes: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Status {
    Ok,
    Cancelled,
    ShortTransfer,
    IoError,
    ProtocolError,
    PrepareFailed,
    DurabilityUnsupported,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Reject {
    Busy,
    Quarantined,
    Invalid,
    DurabilityUnsupported,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum PrepareResult {
    Ready,
    Failed(Status),
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct LowerOutcome {
    pub status: Status,
    pub bytes: u32,
    pub queue_frozen: bool,
}

impl LowerOutcome {
    pub fn success(bytes: u32) -> Self {
        Self {
            status: Status::Ok,
            bytes,
            queue_frozen: false,
        }
    }

    pub fn error(status: Status, bytes: u32) -> Self {
        Self {
            status,
            bytes,
            queue_frozen: false,
        }
    }

    pub fn frozen_error(status: Status, bytes: u32) -> Self {
        Self {
            status,
            bytes,
            queue_frozen: true,
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Completion {
    pub parent: ParentId,
    pub status: Status,
    pub bytes: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Event {
    PrepareFinished {
        token: Token,
        result: PrepareResult,
    },
    SubmitReturned {
        token: Token,
    },
    LowerCompleted {
        token: Token,
        outcome: LowerOutcome,
    },
    Retired {
        token: Token,
    },
    ParentDelivered {
        parent: ParentId,
    },
    Cancel {
        parent: ParentId,
    },
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Effect {
    MarkPending {
        parent: ParentId,
    },
    Prepare {
        token: Token,
        parent: ParentId,
        kind: CommandKind,
        bytes: u32,
    },
    Submit {
        token: Token,
        parent: ParentId,
        kind: CommandKind,
        bytes: u32,
    },
    CancelLower {
        token: Token,
        parent: ParentId,
    },
    Retire {
        token: Token,
        parent: ParentId,
    },
    Complete(Completion),
    StaleIgnored {
        token: Token,
    },
}

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct Snapshot {
    pub lock_held: bool,
    pub lower_occupied: usize,
    pub resident_parents: usize,
    pub accepted_total: u64,
    pub quarantined: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum Health {
    Healthy,
    Quarantined,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum RetireReason {
    PreparedCancelled,
    Terminal(LowerOutcome),
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum Phase {
    Idle,
    Waiting,
    Preparing(Token),
    Submitting {
        token: Token,
        terminal: Option<LowerOutcome>,
    },
    LowerOwned(Token),
    Retiring {
        token: Token,
        reason: RetireReason,
    },
    WaitingRecovery {
        original_token: Token,
        original: LowerOutcome,
    },
    Completing {
        completion: Completion,
        emitted: bool,
    },
}

#[derive(Clone, Debug)]
struct Slot {
    generation: u64,
    next_sequence: u64,
    parent: Option<ParentId>,
    admission: u64,
    operation: Operation,
    chunks_done: u32,
    credited_bytes: u64,
    caller_cancelled: bool,
    internal_abort: bool,
    cancel_sent: bool,
    recovery_saved: Option<(Token, LowerOutcome)>,
    phase: Phase,
}

impl Slot {
    fn idle() -> Self {
        Self {
            generation: 0,
            next_sequence: 0,
            parent: None,
            admission: 0,
            operation: Operation::Flush,
            chunks_done: 0,
            credited_bytes: 0,
            caller_cancelled: false,
            internal_abort: false,
            cancel_sent: false,
            recovery_saved: None,
            phase: Phase::Idle,
        }
    }

    fn is_resident(&self) -> bool {
        !matches!(self.phase, Phase::Idle)
    }

    fn parent(&self) -> ParentId {
        self.parent.expect("resident slot has a parent")
    }
}

#[derive(Debug)]
pub struct Engine {
    config: EngineConfig,
    slots: Vec<Slot>,
    health: Health,
    next_parent: u64,
    next_admission: u64,
    accepted_total: u64,
    scan_cursor: usize,
    pump_owned: bool,
    rescan_requested: bool,
    lock_held: bool,
    effects: VecDeque<Effect>,
}

impl Engine {
    pub fn new(config: EngineConfig) -> Result<Self, Reject> {
        if config.slots == 0 || config.lower_depth == 0 {
            return Err(Reject::Invalid);
        }
        Ok(Self {
            config,
            slots: vec![Slot::idle(); config.slots],
            health: Health::Healthy,
            next_parent: 1,
            next_admission: 1,
            accepted_total: 0,
            scan_cursor: 0,
            pump_owned: false,
            rescan_requested: false,
            lock_held: false,
            effects: VecDeque::new(),
        })
    }

    pub fn admit(&mut self, operation: Operation) -> Result<ParentId, Reject> {
        self.enter();
        let result = self.admit_locked(operation);
        self.leave();
        result
    }

    fn admit_locked(&mut self, operation: Operation) -> Result<ParentId, Reject> {
        if self.health == Health::Quarantined {
            return Err(Reject::Quarantined);
        }
        if matches!(operation, Operation::Flush | Operation::WriteThrough { .. })
            && self.config.cache == CacheState::Unqualified
        {
            return Err(Reject::DurabilityUnsupported);
        }
        match operation {
            Operation::Read {
                chunks,
                bytes_per_chunk,
            }
            | Operation::Write {
                chunks,
                bytes_per_chunk,
            }
            | Operation::WriteThrough {
                chunks,
                bytes_per_chunk,
            } if chunks > 0 && bytes_per_chunk == 0 => return Err(Reject::Invalid),
            _ => {}
        }

        let Some(index) = self.slots.iter().position(|slot| !slot.is_resident()) else {
            return Err(Reject::Busy);
        };
        let parent = ParentId(self.next_parent);
        self.next_parent = self.next_parent.checked_add(1).expect("parent id overflow");
        let admission = self.next_admission;
        self.next_admission = self
            .next_admission
            .checked_add(1)
            .expect("admission id overflow");

        let generation = self.slots[index]
            .generation
            .checked_add(1)
            .expect("generation overflow");
        self.slots[index] = Slot {
            generation,
            next_sequence: self.slots[index].next_sequence,
            parent: Some(parent),
            admission,
            operation,
            chunks_done: 0,
            credited_bytes: 0,
            caller_cancelled: false,
            internal_abort: false,
            cancel_sent: false,
            recovery_saved: None,
            phase: Phase::Waiting,
        };
        self.accepted_total += 1;
        self.effects.push_back(Effect::MarkPending { parent });
        if matches!(
            operation,
            Operation::Read { chunks: 0, .. }
                | Operation::Write { chunks: 0, .. }
                | Operation::WriteThrough { chunks: 0, .. }
        ) {
            self.finish(index, Status::Ok);
        }
        self.request_rescan();
        Ok(parent)
    }

    pub fn notify(&mut self, event: Event) {
        self.enter();
        match event {
            Event::PrepareFinished { token, result } => self.on_prepare(token, result),
            Event::SubmitReturned { token } => self.on_submit_returned(token),
            Event::LowerCompleted { token, outcome } => self.on_lower_complete(token, outcome),
            Event::Retired { token } => self.on_retired(token),
            Event::ParentDelivered { parent } => self.on_parent_delivered(parent),
            Event::Cancel { parent } => self.on_cancel(parent),
        }
        self.request_rescan();
        self.leave();
    }

    pub fn poll_effect(&mut self) -> Option<Effect> {
        self.enter();
        let effect = self.poll_effect_locked();
        self.leave();
        effect
    }

    fn poll_effect_locked(&mut self) -> Option<Effect> {
        if let Some(effect) = self.effects.pop_front() {
            return Some(effect);
        }

        if !self.pump_owned {
            if !self.rescan_requested {
                return None;
            }
            self.pump_owned = true;
        }
        self.rescan_requested = false;

        if let Some(effect) = self.next_completion_effect() {
            return Some(effect);
        }
        if self.transport_reservations() < self.config.lower_depth {
            if let Some(index) = self.select_recovery() {
                return Some(self.begin_prepare(index, CommandKind::ReleaseQueue, 0));
            }
            if let Some(index) = self.select_eligible() {
                return self.begin_normal_or_finish_disabled(index);
            }
        }

        self.pump_owned = false;
        None
    }

    fn next_completion_effect(&mut self) -> Option<Effect> {
        for offset in 0..self.slots.len() {
            let index = (self.scan_cursor + offset) % self.slots.len();
            if let Phase::Completing {
                completion,
                emitted: false,
            } = self.slots[index].phase
            {
                self.slots[index].phase = Phase::Completing {
                    completion,
                    emitted: true,
                };
                self.scan_cursor = (index + 1) % self.slots.len();
                return Some(Effect::Complete(completion));
            }
        }
        None
    }

    fn select_recovery(&self) -> Option<usize> {
        if self.recovery_active() {
            return None;
        }
        (0..self.slots.len())
            .map(|offset| (self.scan_cursor + offset) % self.slots.len())
            .filter(|&index| matches!(self.slots[index].phase, Phase::WaitingRecovery { .. }))
            .min_by_key(|&index| self.slots[index].admission)
    }

    fn select_eligible(&self) -> Option<usize> {
        for offset in 0..self.slots.len() {
            let index = (self.scan_cursor + offset) % self.slots.len();
            let slot = &self.slots[index];
            if !matches!(slot.phase, Phase::Waiting) {
                continue;
            }
            if self.normal_eligible(index) {
                return Some(index);
            }
        }
        None
    }

    fn begin_normal_or_finish_disabled(&mut self, index: usize) -> Option<Effect> {
        let kind = self.next_normal_kind(index);
        if kind == CommandKind::Sync && self.config.cache == CacheState::Disabled {
            self.finish(index, Status::Ok);
            self.scan_cursor = (index + 1) % self.slots.len();
            self.rescan_requested = true;
            return self.next_completion_effect();
        }
        let bytes = match kind {
            CommandKind::Data => match self.slots[index].operation {
                Operation::Read { bytes_per_chunk, .. }
                | Operation::Write { bytes_per_chunk, .. }
                | Operation::WriteThrough { bytes_per_chunk, .. } => bytes_per_chunk,
                Operation::Flush => 0,
            },
            CommandKind::Sync | CommandKind::ReleaseQueue => 0,
        };
        Some(self.begin_prepare(index, kind, bytes))
    }

    fn begin_prepare(&mut self, index: usize, kind: CommandKind, bytes: u32) -> Effect {
        let slot_count = self.slots.len();
        let slot = &mut self.slots[index];
        slot.next_sequence = slot
            .next_sequence
            .checked_add(1)
            .expect("command sequence overflow");
        slot.cancel_sent = false;
        let token = Token {
            slot: index,
            generation: slot.generation,
            sequence: slot.next_sequence,
            kind,
            bytes,
        };
        slot.phase = Phase::Preparing(token);
        let parent = slot.parent();
        self.scan_cursor = (index + 1) % slot_count;
        Effect::Prepare {
            token,
            parent,
            kind,
            bytes,
        }
    }

    fn on_prepare(&mut self, token: Token, result: PrepareResult) {
        let Some(index) = self.matching_phase(token, |phase| matches!(phase, Phase::Preparing(t) if *t == token)) else {
            self.stale(token);
            return;
        };
        let parent = self.slots[index].parent();
        match result {
            PrepareResult::Failed(status) => {
                if token.kind == CommandKind::ReleaseQueue {
                    self.quarantine_after_recovery_failure(index, status);
                } else {
                    let final_status = if self.slots[index].caller_cancelled {
                        Status::Cancelled
                    } else if self.slots[index].internal_abort {
                        Status::IoError
                    } else {
                        status
                    };
                    self.finish(index, final_status);
                }
            }
            PrepareResult::Ready
                if token.kind != CommandKind::ReleaseQueue
                    && (self.slots[index].caller_cancelled
                        || self.slots[index].internal_abort) =>
            {
                self.slots[index].phase = Phase::Retiring {
                    token,
                    reason: RetireReason::PreparedCancelled,
                };
                self.effects.push_back(Effect::Retire { token, parent });
            }
            PrepareResult::Ready => {
                self.slots[index].phase = Phase::Submitting {
                    token,
                    terminal: None,
                };
                self.effects.push_back(Effect::Submit {
                    token,
                    parent,
                    kind: token.kind,
                    bytes: token.bytes,
                });
            }
        }
    }

    fn on_submit_returned(&mut self, token: Token) {
        let Some(index) = self.matching_phase(token, |phase| {
            matches!(phase, Phase::Submitting { token: active, .. } if *active == token)
        }) else {
            self.stale(token);
            return;
        };
        let parent = self.slots[index].parent();
        let terminal = match self.slots[index].phase {
            Phase::Submitting { terminal, .. } => terminal,
            _ => unreachable!(),
        };
        if let Some(outcome) = terminal {
            self.slots[index].phase = Phase::Retiring {
                token,
                reason: RetireReason::Terminal(outcome),
            };
            self.effects.push_back(Effect::Retire { token, parent });
        } else {
            self.slots[index].phase = Phase::LowerOwned(token);
            self.maybe_request_lower_cancel(index);
        }
    }

    fn on_lower_complete(&mut self, token: Token, outcome: LowerOutcome) {
        let Some(index) = self.token_slot(token) else {
            self.stale(token);
            return;
        };
        let parent = self.slots[index].parent();
        match self.slots[index].phase {
            Phase::Submitting {
                token: active,
                terminal: None,
            } if active == token => {
                self.slots[index].phase = Phase::Submitting {
                    token,
                    terminal: Some(outcome),
                };
            }
            Phase::LowerOwned(active) if active == token => {
                self.slots[index].phase = Phase::Retiring {
                    token,
                    reason: RetireReason::Terminal(outcome),
                };
                self.effects.push_back(Effect::Retire { token, parent });
            }
            _ => self.stale(token),
        }
    }

    fn on_retired(&mut self, token: Token) {
        let Some(index) = self.matching_phase(token, |phase| {
            matches!(phase, Phase::Retiring { token: active, .. } if *active == token)
        }) else {
            self.stale(token);
            return;
        };
        let reason = match self.slots[index].phase {
            Phase::Retiring { reason, .. } => reason,
            _ => unreachable!(),
        };
        match reason {
            RetireReason::PreparedCancelled => {
                let status = if self.slots[index].caller_cancelled {
                    Status::Cancelled
                } else {
                    Status::IoError
                };
                self.finish(index, status);
            }
            RetireReason::Terminal(outcome) if token.kind == CommandKind::ReleaseQueue => {
                if outcome.status == Status::Ok && outcome.bytes == 0 {
                    self.finish_recovered_parent(index);
                } else {
                    self.quarantine_after_recovery_failure(index, outcome.status);
                }
            }
            RetireReason::Terminal(outcome) if outcome.queue_frozen => {
                self.slots[index].recovery_saved = Some((
                    token,
                    LowerOutcome {
                        queue_frozen: false,
                        ..outcome
                    },
                ));
                self.slots[index].phase = Phase::WaitingRecovery {
                    original_token: token,
                    original: LowerOutcome {
                        queue_frozen: false,
                        ..outcome
                    },
                };
            }
            RetireReason::Terminal(outcome) => self.apply_terminal(index, token, outcome),
        }
    }

    fn finish_recovered_parent(&mut self, index: usize) {
        let (token, outcome) = match self.slots[index].phase {
            Phase::Retiring { token, .. } if token.kind == CommandKind::ReleaseQueue => {
                match self.recovery_original(index) {
                    Some(pair) => pair,
                    None => {
                        self.finish(index, Status::IoError);
                        return;
                    }
                }
            }
            _ => unreachable!(),
        };
        self.apply_terminal(index, token, outcome);
    }

    fn recovery_original(&self, index: usize) -> Option<(Token, LowerOutcome)> {
        self.slots[index].recovery_saved
    }

    fn apply_terminal(&mut self, index: usize, token: Token, outcome: LowerOutcome) {
        let over_report = outcome.bytes > token.bytes;
        if token.kind == CommandKind::Data && !over_report {
            self.slots[index].credited_bytes += u64::from(outcome.bytes);
        }

        if self.slots[index].caller_cancelled {
            self.finish(index, Status::Cancelled);
            return;
        }
        if self.slots[index].internal_abort {
            self.finish(index, Status::IoError);
            return;
        }
        if over_report {
            self.finish(index, Status::ProtocolError);
            return;
        }
        if outcome.status != Status::Ok {
            self.finish(index, outcome.status);
            return;
        }
        if token.kind == CommandKind::Data && outcome.bytes < token.bytes {
            self.finish(index, Status::ShortTransfer);
            return;
        }

        match token.kind {
            CommandKind::Data => {
                self.slots[index].chunks_done += 1;
                let complete = match self.slots[index].operation {
                    Operation::Read { chunks, .. }
                    | Operation::Write { chunks, .. }
                    | Operation::WriteThrough { chunks, .. } => {
                        self.slots[index].chunks_done >= chunks
                    }
                    Operation::Flush => true,
                };
                if complete {
                    if matches!(self.slots[index].operation, Operation::WriteThrough { .. }) {
                        if self.config.cache == CacheState::Disabled {
                            self.finish(index, Status::Ok);
                        } else {
                            self.slots[index].phase = Phase::Waiting;
                        }
                    } else {
                        self.finish(index, Status::Ok);
                    }
                } else {
                    self.slots[index].phase = Phase::Waiting;
                }
            }
            CommandKind::Sync => self.finish(index, Status::Ok),
            CommandKind::ReleaseQueue => unreachable!(),
        }
    }

    fn on_parent_delivered(&mut self, parent: ParentId) {
        let Some(index) = self.slots.iter().position(|slot| {
            slot.parent == Some(parent)
                && matches!(slot.phase, Phase::Completing { emitted: true, .. })
        }) else {
            return;
        };
        let generation = self.slots[index].generation;
        let next_sequence = self.slots[index].next_sequence;
        self.slots[index] = Slot::idle();
        self.slots[index].generation = generation;
        self.slots[index].next_sequence = next_sequence;
    }

    fn on_cancel(&mut self, parent: ParentId) {
        let Some(index) = self.slots.iter().position(|slot| slot.parent == Some(parent)) else {
            return;
        };
        if matches!(self.slots[index].phase, Phase::Completing { .. } | Phase::Idle) {
            return;
        }
        self.slots[index].caller_cancelled = true;
        match self.slots[index].phase {
            Phase::Waiting => self.finish(index, Status::Cancelled),
            Phase::LowerOwned(_) => self.maybe_request_lower_cancel(index),
            Phase::WaitingRecovery { .. } => {
                // Queue release still runs; cancellation wins after recovery.
            }
            _ => {}
        }
    }

    fn maybe_request_lower_cancel(&mut self, index: usize) {
        if self.slots[index].cancel_sent {
            return;
        }
        let token = match self.slots[index].phase {
            Phase::LowerOwned(token) if token.kind != CommandKind::ReleaseQueue => token,
            _ => return,
        };
        if !(self.slots[index].caller_cancelled || self.slots[index].internal_abort) {
            return;
        }
        self.slots[index].cancel_sent = true;
        self.effects.push_back(Effect::CancelLower {
            token,
            parent: self.slots[index].parent(),
        });
    }

    fn finish(&mut self, index: usize, status: Status) {
        let completion = Completion {
            parent: self.slots[index].parent(),
            status,
            bytes: self.slots[index].credited_bytes,
        };
        self.slots[index].phase = Phase::Completing {
            completion,
            emitted: false,
        };
        self.rescan_requested = true;
    }

    fn quarantine_after_recovery_failure(&mut self, owner: usize, _recovery_status: Status) {
        self.health = Health::Quarantined;
        let owner_status = if self.slots[owner].caller_cancelled {
            Status::Cancelled
        } else {
            match self.slots[owner].recovery_saved {
                Some((_, original)) if original.status != Status::Ok => original.status,
                _ => Status::IoError,
            }
        };
        self.credit_recovery_original(owner);
        self.finish(owner, owner_status);

        for index in 0..self.slots.len() {
            if index == owner || !self.slots[index].is_resident() {
                continue;
            }
            self.slots[index].internal_abort = true;
            match self.slots[index].phase {
                Phase::Waiting | Phase::WaitingRecovery { .. } => {
                    let status = if self.slots[index].caller_cancelled {
                        Status::Cancelled
                    } else {
                        Status::IoError
                    };
                    self.finish(index, status);
                }
                Phase::LowerOwned(_) => self.maybe_request_lower_cancel(index),
                Phase::Completing { .. }
                | Phase::Preparing(_)
                | Phase::Submitting { .. }
                | Phase::Retiring { .. }
                | Phase::Idle => {}
            }
        }
    }

    fn credit_recovery_original(&mut self, index: usize) {
        if let Some((token, original)) = self.slots[index].recovery_saved {
            if token.kind == CommandKind::Data && original.bytes <= token.bytes {
                self.slots[index].credited_bytes += u64::from(original.bytes);
            }
        }
    }

    fn normal_eligible(&self, index: usize) -> bool {
        let slot = &self.slots[index];
        if slot.caller_cancelled || slot.internal_abort {
            return false;
        }
        if slot.operation.is_read() {
            return true;
        }
        let prior_barrier = self.slots.iter().any(|other| {
            other.is_resident()
                && other.admission < slot.admission
                && other.operation.is_barrier()
        });
        match self.next_normal_kind(index) {
            CommandKind::Data => !prior_barrier,
            CommandKind::Sync => {
                !prior_barrier
                    && !self.slots.iter().any(|other| {
                        other.is_resident()
                            && other.admission < slot.admission
                            && other.operation.is_write()
                    })
            }
            CommandKind::ReleaseQueue => false,
        }
    }

    fn next_normal_kind(&self, index: usize) -> CommandKind {
        match self.slots[index].operation {
            Operation::Read { .. } | Operation::Write { .. } => CommandKind::Data,
            Operation::WriteThrough { chunks, .. }
                if self.slots[index].chunks_done < chunks =>
            {
                CommandKind::Data
            }
            Operation::WriteThrough { .. } | Operation::Flush => CommandKind::Sync,
        }
    }

    fn matching_phase<F>(&self, token: Token, predicate: F) -> Option<usize>
    where
        F: FnOnce(&Phase) -> bool,
    {
        let index = self.token_slot(token)?;
        predicate(&self.slots[index].phase).then_some(index)
    }

    fn token_slot(&self, token: Token) -> Option<usize> {
        let slot = self.slots.get(token.slot)?;
        (slot.is_resident() && slot.generation == token.generation).then_some(token.slot)
    }

    fn stale(&mut self, token: Token) {
        self.effects.push_back(Effect::StaleIgnored { token });
    }

    fn transport_reservations(&self) -> usize {
        self.slots
            .iter()
            .filter(|slot| {
                matches!(
                    slot.phase,
                    Phase::Preparing(_) | Phase::Submitting { .. } | Phase::LowerOwned(_)
                )
            })
            .count()
    }

    fn lower_occupied(&self) -> usize {
        self.slots
            .iter()
            .filter(|slot| matches!(slot.phase, Phase::Submitting { .. } | Phase::LowerOwned(_)))
            .count()
    }

    fn recovery_active(&self) -> bool {
        self.slots.iter().any(|slot| match slot.phase {
            Phase::Preparing(token)
            | Phase::LowerOwned(token)
            | Phase::Retiring { token, .. } => token.kind == CommandKind::ReleaseQueue,
            Phase::Submitting { token, .. } => token.kind == CommandKind::ReleaseQueue,
            _ => false,
        })
    }

    fn request_rescan(&mut self) {
        self.rescan_requested = true;
    }

    fn enter(&mut self) {
        assert!(!self.lock_held, "modeled state lock recursively acquired");
        self.lock_held = true;
    }

    fn leave(&mut self) {
        assert!(self.lock_held, "modeled state lock not held");
        self.lock_held = false;
    }

    pub fn snapshot(&self) -> Snapshot {
        Snapshot {
            lock_held: self.lock_held,
            lower_occupied: self.lower_occupied(),
            resident_parents: self.slots.iter().filter(|slot| slot.is_resident()).count(),
            accepted_total: self.accepted_total,
            quarantined: self.health == Health::Quarantined,
        }
    }

    pub fn check_invariants(&self) -> Result<(), String> {
        if self.lock_held {
            return Err("public boundary retains state lock".into());
        }
        if self.lower_occupied() > self.config.lower_depth {
            return Err("lower occupancy exceeds configured depth".into());
        }
        if self.transport_reservations() > self.config.lower_depth {
            return Err("prepared/committed transport reservations exceed depth".into());
        }
        let mut parents = HashSet::new();
        let mut tokens = HashSet::new();
        for slot in &self.slots {
            if !slot.is_resident() {
                if slot.parent.is_some() {
                    return Err("idle slot retains a parent".into());
                }
                continue;
            }
            let parent = slot.parent.ok_or("resident slot lacks a parent")?;
            if !parents.insert(parent) {
                return Err("parent appears in multiple slots".into());
            }
            if slot.credited_bytes > slot.operation.requested_bytes() {
                return Err("credited bytes exceed request".into());
            }
            let token = match slot.phase {
                Phase::Preparing(token)
                | Phase::LowerOwned(token)
                | Phase::Retiring { token, .. } => Some(token),
                Phase::Submitting { token, .. } => Some(token),
                _ => None,
            };
            if let Some(token) = token {
                if token.slot >= self.slots.len() || token.generation != slot.generation {
                    return Err("active token does not identify its slot generation".into());
                }
                if !tokens.insert(token) {
                    return Err("duplicate active command token".into());
                }
            }
        }
        Ok(())
    }
}

