# Clean-room bounded request pump model

This document is the frozen, implementation-independent specification for the
Rust model in this directory. It describes observable transitions and
ownership. It does not describe or translate a C implementation. Every rule is
marked with its evidence class:

- **[contract]** is taken from the allowed behavioral prose under
  `docs/storage-replacement/independent-implementation/request-engine/`.
- **[observation]** is supplied directly in the task.
- **[inference]** is an independently chosen model rule needed to make the
  public behavior precise or testable. It is a candidate for validation, not a
  claim about historical implementation.

## Boundary and purpose

1. **[contract]** The engine has fixed resident request slots. It allocates no
   request-time heap object, worker, timer, retry buffer, or bounce buffer.
2. **[contract]** A parent owns at most one live lower command. More than one
   parent may be admitted and more than one lower command may exist when the
   lower transport permits it.
3. **[observation]** The target workload has upper queue depth 12, issues 1,024
   asynchronous reads, and reaches a PATA lower path with effective depth one.
4. **[observation]** Two optimized pumps stall after warm-up with respectively
   six and five requests still outstanding. The original pump completes. A
   qualification run must accept at least sixteen parents over time.
5. **[inference]** The model defaults to 12 resident parent slots and lower
   depth one. It counts cumulative admissions separately from simultaneous
   residency; slot reuse must allow far more than twelve total parents.

## State and ownership

6. **[inference]** Device health is `Healthy`, `Recovering`, or `Quarantined`.
   Quarantine is sticky for the modeled device lifetime.
7. **[inference]** A slot is one of `Idle`, `Waiting`, `Preparing`,
   `Submitting`, `LowerOwned`, `Retiring`, `WaitingRecovery`, or `Completing`.
   These names are neutral model vocabulary.
8. **[contract]** The parent request, its buffer/MDL domain, and its upper lease
   remain borrowed until terminal parent delivery. The model represents that
   lease with a resident slot and releases it only after `ParentDelivered`.
9. **[contract]** Prepared child resources are adapter-owned and retire exactly
   once, after a terminal lower report and after the submit call returns.
10. **[contract]** The lower owns an active command until one terminal report.
    A cancel request asks the lower to finish; it does not release ownership.
11. **[contract]** A command token contains slot, admission generation, and
    command sequence by value. Reports with a mismatched token or an already
    consumed token change no request state.
12. **[inference]** Admission increments a slot generation and each prepare
    increments its command sequence. Neither counter is reset on slot reuse.

## Lock and pump protocol

13. **[contract]** State transitions are short and serialized. Prepare, submit,
    lower cancel, retire, and parent-complete callbacks run outside the state
    lock. Only the pending-mark leaf may execute while locked; this model emits
    it as an effect as well, making the stronger outside-lock property visible.
14. **[inference]** `notify(event)` is one serialized transition and
    `poll_effect()` is the iterative pump. Both return with `lock_held == false`.
    The consumer executes one effect and may call `notify` reentrantly before
    polling again.
15. **[contract]** Inline completion publishes a terminal result; it cannot
    recursively submit another segment.
16. **[inference]** Every event that may enable work sets a durable rescan bit.
    The outer poll loop owns pumping, consumes the bit only after scanning all
    slots, and continues until a full scan emits no effect and no event requested
    another scan. This is the liveness rule aimed at the observed warm-up stall.
17. **[inference]** The slot scan is round-robin. It is a fairness choice, not a
    parity claim. No eligible resident request may be skipped forever while
    lower capacity repeatedly becomes available.

### Wake-event interpretation

The Rust model uses one durable rescan bit because every enabling condition is
also represented as persistent slot/device state. A count is not required to
remember how many callbacks occurred; one complete scan observes their combined
state. **[inference]** A saturating event count is equivalent for liveness only
when increments are atomic, the pump consumes or snapshots the count without a
later blind store to zero, and idle entry follows a complete bounded scan plus
an atomic final event check.

**[inference]** Counterexample for an unsafe counted implementation: the pump
samples count one and starts a scan; an inline completion reenters and increments
the count; after returning, the outer frame stores zero based on its old sample
and exits. A waiting parent remains eligible with no future edge to wake it.
Saturation does not repair that overwrite. Consuming the prior event before the
scan, or using an exchange/compare-and-swap protocol that cannot erase a later
increment, closes this trace. No counterexample was found against an atomic
saturating count combined with a full scan and atomic final check.

## Submission, completion, cancellation, and reuse

18. **[contract]** `PrepareOk` followed by the final cancellation check commits
    a command. Submit then runs outside the lock and may complete inline.
19. **[contract]** Cancellation accepted before commit prevents submission.
    Prepared resources still retire once.
20. **[contract]** Cancellation after commit may race with submit. If submit has
    returned and the command remains lower-owned, exactly one lower cancel is
    requested. An inline-terminal command is not canceled afterward.
21. **[contract]** Accepted cancellation wins terminal parent status. Bounded
    verified data bytes remain visible. Cancellation does not undo writes.
22. **[contract]** Lower completion bytes are authoritative. A full successful
    data command advances the parent. A short success stops with `ShortTransfer`.
    An error stops with its error while retaining bounded bytes. An over-report
    is `ProtocolError` and credits no bytes for that command.
23. **[contract]** A parent completes once, outside the lock, only after its last
    child retires. Parent delivery may reenter, admit new work, and allow the
    just-freed slot to be reused only after `ParentDelivered` acknowledges the
    delivery effect.
24. **[inference]** `ParentDelivered` is explicit so tests can pause completion,
    prove the slot is not reused early, and then observe generation change.

## Ordering barriers

25. **[contract]** Reads may use available lower capacity across write and flush
    barriers.
26. **[contract]** A flush waits for all earlier writes. Later writes wait for
    that flush. A cache-enabled flush uses a real synchronization command; an
    independently established disabled cache preserves ordering without a lower
    command; unqualified durability fails.
27. **[contract]** Write-through keeps one parent and slot across data chunks and
    synchronization. Its sync waits for earlier writes; later writes wait for
    the write-through parent; reads retain concurrency.
28. **[inference]** Admission order is a monotonic ordinal. Barrier predicates
    consult unfinished resident writes/barriers by ordinal, avoiding dependence
    on physical slot position or slot reuse.

## Freeze recovery and quarantine

29. **[contract]** A queue-frozen terminal outcome schedules exactly one
    `ReleaseQueue` command using the failed parent's reserved resources before
    parent delivery.
30. **[inference]** Recovery commands are serialized. Additional frozen parents
    wait in `WaitingRecovery`; this keeps recovery bounded under lower depth one.
31. **[contract]** Recovery success preserves the original command outcome and
    then completes the parent. Recovery failure quarantines the device, fails
    waiting/admitted work, and requests one cancellation for every live command.
32. **[contract]** Internally canceled live work ends as `IoError` unless caller
    cancellation was independently accepted. Resources remain owned until the
    actual terminal lower report.
33. **[contract]** Quarantine rejects new admissions. There is no retry of queue
    release or uncertain writes.

## Neutral transition table

`T` denotes the current command token. “Effect” means an outside-lock action
the environment must acknowledge with a later event.

| Current state | Event or guard | Next state | Effect / invariant | Evidence |
| --- | --- | --- | --- | --- |
| Idle | admit, healthy, slot available | Waiting | MarkPending; retain parent lease; new generation | contract + inference |
| any | admit, quarantined | unchanged | Reject(Quarantined) | contract |
| all slots resident | admit | unchanged | Reject(Busy) | inference |
| Waiting | canceled | Completing | Complete(Cancelled, 0) | contract |
| Waiting, eligible, lower capacity | pump scan | Preparing(T) | Prepare(T) | contract + inference |
| Preparing(T) | PrepareFailed(T, e) | Completing | Complete(e, credited bytes) | contract |
| Preparing(T) | PrepareOk(T), canceled | Retiring(T) | Retire(T); never Submit | contract |
| Preparing(T) | PrepareOk(T), not canceled | Submitting(T) | Submit(T); commit established | contract |
| Submitting(T) | LowerComplete(T, result) | Submitting(T, latched result) | no recursive submit | contract |
| Submitting(T) | SubmitReturned(T), no result | LowerOwned(T) | CancelLower(T) once if canceled/quarantining | contract |
| Submitting(T) | SubmitReturned(T), latched result | Retiring(T) | Retire(T) | contract |
| LowerOwned(T) | cancel | LowerOwned(T) | CancelLower(T) once | contract |
| LowerOwned(T) | LowerComplete(T, result) | Retiring(T) | Retire(T) | contract |
| Retiring(T) | Retired(T) | Waiting / WaitingRecovery / Completing | advance one full data chunk; otherwise stop | contract |
| WaitingRecovery | recovery is next and lower free | Preparing(recovery T) | Prepare(T) | contract + inference |
| recovery Retiring(T) | Retired success | Completing | Complete(original result) | contract |
| recovery Retiring(T) | Retired failure | Completing + Quarantined device | Complete(original or I/O error); cancel/fail peers | contract |
| Completing | Complete effect emitted | Completing | parent cannot yet be reused | inference |
| Completing | ParentDelivered | Idle | release lease; slot reusable with next generation | contract + inference |
| any active state | stale/duplicate token | unchanged | StaleIgnored(token) | contract |

## Acceptance properties

34. **[observation]** With lower depth one and twelve resident slots, a stream of
    1,024 one-command reads completes, cumulative admissions exceed sixteen,
    no point has more than twelve residents, and no point has more than one
    lower-owned/committed command.
35. **[contract]** The same safety invariants hold for delayed completion,
    completion before submit returns, completion callback reentry, cancellation
    at every ownership boundary, stale callbacks after reuse, recovery failure,
    and parent-completion reentry.
36. **[inference]** Random event schedules must preserve: lower occupancy bound;
    unique live token; exactly one retirement and parent completion; no effect
    emitted under lock; no reuse before delivery; monotonic credited bytes not
    exceeding requested bytes; and eventual quiescence under a fair environment
    that acknowledges every emitted effect and terminally completes every
    submitted command.

## Deliberate limits

- **[contract]** This is a host model, not a kernel adapter. It does not claim
  native IRQL, MDL, SRB, cancel-spin-lock, DMA, cache durability, or teardown
  qualification.
- **[inference]** Status names and event/effect vocabulary are model-local and
  deliberately avoid source-shaped private identifiers.
- **[inference]** A fair environment is assumed for liveness: prepare, submit,
  retire, completion delivery, and lower cancellation eventually respond.

