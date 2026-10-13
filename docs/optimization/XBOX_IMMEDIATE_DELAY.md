# Xbox immediate-delay scheduling

## Problem and resulting behavior

An alertable zero-length `KeDelayExecutionThread` call can occur repeatedly
while a title pumps read-completion APCs. The previous implementation reused
`NtYieldExecution`: it could hand an entire quantum to any ready thread,
including one below the caller's base priority, and returned
`STATUS_NO_YIELD_PERFORMED` when no thread was ready.

An owned public API fixture establishes different reference behavior for a
delay whose deadline has already passed. The caller returns success, restores
its dynamic priority to base, then considers an equal-or-higher priority peer.
Real-time priorities remain unchanged. The fix implements this only for Xbox
immediate delay completion. Explicit yield retains its existing behavior.

For example, with caller actual/base 8/8 and an owned ready peer at 7/7, the
reference returns immediately without peer progress. The old kernel gives the
peer a full approximately 20 ms turn. With caller actual/base 10/8 and peer 9/7,
the delay must first restore the caller to 8 and let the eligible peer run.
Selecting against the original dynamic priority 10 would also be incorrect.

This is a correctness fix. The measured world-read replay does not establish
a Forza streaming improvement.

## Public oracle

The native probe uses public setters and their returned prior actual priority,
plus the public base query. It does not infer actual Spirit priority from its
potentially stale public shadow. Reference public fields additionally expose
remaining quantum. The table describes observed behavior:

| Call and state | Priority after return | Selection / result |
| --- | --- | --- |
| Zero delay, dynamic priority below 16 | Base priority | Equal-or-higher after reset; success |
| Expired positive absolute delay | Same as zero delay | Same successful immediate completion |
| Dynamic priority below its base | Restored upward to base | Same selection threshold |
| Real-time actual priorities 16, 20, 31 | Unchanged | Lower-priority peers do not run |
| No eligible ready thread | Dynamic reset still occurs | Success; remaining quantum preserved |
| A thread handoff occurs | Post-reset priority | Quantum resets to the normal title quantum |
| Negative relative delay that blocks | Boost preserved | Existing timer wait path |
| Queued user APC interrupts alertable delay | Current priority preserved | `STATUS_USER_APC`, exactly one callback |
| Nonalertable zero delay with queued APC | Immediate completion | APC remains pending |
| Explicit yield without ready peers | Current priority preserved | `STATUS_NO_YIELD_PERFORMED` |
| Explicit yield with a ready lower peer | Existing one-level decay | Peer may run |

Bases 6, 8 and 10, actual priorities 6 through 31, and all combinations of
KernelMode/UserMode and alertable/nonalertable were exercised. A short owned
CPU loop consumes part of the quantum before another zero delay: the reference
preserves values 48/51 when no handoff occurs, and returns with 60 after a
handoff. An unconditional quantum reset would therefore be incorrect.

The broad rule does not mean every timer call resets priority: an unexpired
relative wait follows the existing timer path. The test also retains the
explicit-yield control to prevent accidentally changing that separate API.

## Implementation and dispatcher invariants

Patch `0106-xbox-immediate-delay.patch` changes only `ntoskrnl/ke/wait.c` at
runtime. Xbox skips the desktop early UserMode zero-yield shortcut so normal
WaitNext bookkeeping, alert checks and APC checks occur first. The successful
`NoWait` path releases the dispatcher lock while keeping SYNCH_LEVEL, then:

1. Acquires the current thread and PRCB locks.
2. Restores a non-real-time priority to base and clears boost decrement state.
3. Preserves any committed `Prcb->NextThread`; otherwise selects a ready thread
   using the resulting current priority and marks it Standby.
4. Resets quantum only when a handoff exists.
5. Releases both locks and calls the existing `KiExitDispatcher` with saved IRQL.

A committed NextThread is never discarded, requeued or replaced. Ordinarily,
releasing the dispatcher lock consumes a previous handoff before returning
below DISPATCH_LEVEL. The legal WaitNext exception enters the delay with the
lock already held after signal-then-wait. The helper stays at SYNCH_LEVEL and
preserves the committed handoff until normal dispatcher exit. If the saved
IRQL requires deferral, the existing dispatcher schedules its software
interrupt instead of making an illegal immediate context switch.

Host cases force lower/equal/higher preselected standby threads, with and
without ReadySummary, to verify pointer/lifecycle preservation and no second
ready dequeue. These defensive cases are not a claim that ordinary UP delay
entry produces a lower-priority standby thread. The native signal-then-delay
case additionally checks WaitNext completion and restored IRQL.

APC and alert break paths precede NoWait and keep their original return status
and user APC delivery. The helper never normalizes an arbitrary status value.
The desktop preprocessed wait.c token stream is identical to the baseline;
thrdschd.c, including explicit NtYieldExecution, is byte-identical.

## Validation

The [machine-readable evidence](evidence/immediate-delay-2026-10-13.json)
records artifact hashes and individual replay observations. The qualified
release64 ROM is
`67e35e918821d85f6ae6b3c9f4563c2122b497e989aeaa0ecb6a79dba040e941`.
The packaged rebuild is byte-identical to the native-tested candidate.

- Actual-source scheduler harness: 6,084 assertions pass. The baseline fails
  2,213 oracle assertions. Queue and locking services are mocked; expected
  priority, selection, status and quantum results come from the public oracle,
  not from evaluating the implementation under test.
- Native untraced reference/candidate/candidate/reference: 537/537 each.
  Includes lower/equal/higher peers after reset, RT/no-ready cases, all four wait
  modes, relative and expired deadlines, APC controls and WaitNext.
- Existing actual-source wait adapter: 223 cases pass.
- Existing I/O APC completion/delivery/rundown: 63 cases pass, with 119 IRPs
  released exactly once, 48 MDLs and 24 buffers freed.
- CI runs the new source harness and native 537-check fixture against release
  and debug firmware at both 64 and 128 MiB.

The scheduler fixture makes no elapsed-time assertions; serial output stays
outside measured intervals. The reference is used as a public behavior oracle,
not as source or instruction material. A separate root-agent review checked
APC precedence, SYNCH_LEVEL lock ordering, committed handoff preservation,
remaining quantum, explicit yield isolation and the real-time guard.

Two earlier attempts are excluded from qualification. The first candidate
selected against current dynamic priority and was rejected by a reference-first
boosted-priority case before candidate execution. An expanded oracle later
faulted on the reference when its fixture changed base priorities after
artificially lowering dynamic priorities below their old bases. The corrected
fixture restores dynamic state before supported +/-2 base changes and passes
79/79. Raw receipts for both excluded attempts are retained in the investigation.

## World regression and limits

The untraced GPU fixture replays the same captured 1,024 world-resource requests
for each of two datasets at depths 1, 4 and 12, including equal 900-free-page
pressure. Async2/candidate/candidate/async2 each pass 19/19 with data SHA,
completion APC and IOSB checks. Equal-pressure aggregate medians are:

| Depth | Async2 ms / 1,024 | Delay fix ms / 1,024 |
| --- | ---: | ---: |
| 1 | 102.41 | 99.40 |
| 4 | 82.36 | 82.31 |
| 12 | 78.56 | 78.13 |

Per-run ranges overlap. This supports world-read correctness and nonregression,
not a reproducible streaming speedup. It does not reproduce concurrent game
CPU work or demonstrate a fix for the visible Forza symptom.

The late public API capture contains 986 reference and 1,044 old-Spirit
alertable zero-delay entries on the primary read issuer. It contains no calls
to the mapped priority setters; base query ordinal124 was not mapped, so lack
of its events says nothing about whether the game called it. Those late
captures alone cannot establish thread priorities.

Two earlier snapshots of the original Spirit VM use its exact owned build and
compiled native structure offsets. They identify the primary read issuer as
native c103b820/public c103b9d4, actual/base 8/8 and running, and the secondary
issuer as native c11e5820/public c11e59d4, actual/base 8/8 and ready. Earlier
traces from that same VM independently identify both read issuers. These are
instantaneous prior-build observations. Repeated pointer values in a later
boot do not establish thread identity or current priority across runs.
Reference game thread priorities remain unmeasured. Any two-issuer fixture
using those values is an explicitly bounded scheduling control, not a claim
that all late-v4 or reference game states are identical.
