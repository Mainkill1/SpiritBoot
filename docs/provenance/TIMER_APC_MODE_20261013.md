# Preserve the timer APC delivery mode

## Trigger and externally visible behavior

A title arms a timer using `NtSetTimerEx(..., UserMode, ...)` and then waits
alertably on an unsignaled event. The existing kernel calls the callback near
expiry but leaves the event wait running until its timeout. A nonalertable wait
also receives that callback too early. Both behaviors lose the distinction
between a user APC and a kernel APC.

The full API regression hid this mismatch: `a_user_mode_apc_runs_on_expiry`
checked only callback count and context, discarding the wait result. Both kernels
therefore passed, although the reference consistently took approximately 50 ms
and SpiritBoot approximately 500 ms in the recorded campaigns.

## Owned-source cause

`ntoskrnl/xb/xbe.c:XeNtSetTimerEx` explicitly ignores `ApcMode` and calls the NT
`NtSetTimer` entry point. `ntoskrnl/ex/timer.c:NtSetTimer` initializes the timer's
APC using `ExGetPreviousMode()`. For a title running in ring 0, this is KernelMode.
The kernel APC executes normally, then the interrupted wait resumes.

The wrapper's justification predates working user APC delivery. The current
`KiInsertQueueApc` wakes an alertable UserMode wait with `STATUS_USER_APC`, and
`ntoskrnl/ke/wait.c` calls `KiDeliverUserApcs` before returning that result. That
existing routine drains the target thread's user APC queue, invokes each APC's
kernel routine, and then invokes its normal callback. No ring-3 transition is
needed by this path.

## Narrow change

Pass the requested APC mode to a shared timer setter and use it only when
initializing the APC. Keep the caller's actual PreviousMode for object access
and pointer probing. The existing NT entry point supplies its PreviousMode as
the APC mode, retaining the native NT contract. The Xbox entry point forwards
the explicitly requested APC mode. No scheduler, wait-loop, timer interval,
queueing, cancellation, or lifetime algorithm changes are needed.

## Regression and validation

`tests/xbe/timer-apc-mode` contains four synthetic public-API cases:

1. UserMode timer APC terminates an alertable wait with STATUS_USER_APC.
2. A nonalertable wait holds the UserMode callback; a subsequent zero-time
   alertable wait dispatches it.
3. Canceling a queued UserMode timer APC suppresses the callback.
4. KernelMode timer APC still runs without terminating the event wait.

The tests check exact callback counts, original context, and setting-thread
identity. Elapsed time is logged, never used as a pass/fail threshold.

The unchanged baseline fails five of 30 checks; Complex 4627 passes all 30.
For the first alertable case, baseline returns STATUS_TIMEOUT after 501 ms,
while the reference returns STATUS_USER_APC after 52 ms. In the two nonalertable
cases, baseline has already called the callback once; the reference leaves it
queued. The KernelMode control passes on both.

Reduced TAP logs and artifact hashes are in
[evidence/timer-apc-mode-20261013](evidence/timer-apc-mode-20261013).
The product host suite passes 130 tests with three skips both before and after
the patch. The focused XBE builds with the installed nxdk. The Release64 candidate builds successfully from source tree
`08deb3f812eabdb40bb6f536651e113cf307f8a9`.
The first candidate (before the review guard below) passes all 30 focused checks. Its alertable UserMode case returns
STATUS_USER_APC after 51 ms, versus reference 52 ms and baseline timeout 501 ms.
The nonalertable queueing, queued cancellation, and KernelMode control pass.

The full API run plans 639 cases: 634 enabled, with 630 ordinary passes and four
known TODO failures, plus five skips. No new failure appears. The known TODOs
are `io/bad-ptr/set_eof_beyond_free_space`, `io/storage/flush_volume_readonly`,
`ke/procprio/a_new_thread_starts_at_the_process_priority`, and
`ke/procprio/the_process_lists_its_threads`. The runner's summary includes TODOs
in its passed=634 total; that total must not be presented as 634 ordinary passes.
The full raw receipt is retained by the integration owner; the evidence folder
contains selected timer, TODO, skip and terminal rows plus artifact hashes.

## Scope and limits

This fixes the timer completion contract and removes timeout-length stalls for
titles using alertable user APC timers. It does not establish a game frame-rate
improvement. Reference behavior comes from public-API execution, not proprietary
source or disassembly. Kernel edits are based exclusively on owned/open source.

## Review follow-up: reject unsupported APC modes

Independent review identified that directly forwarding a malformed ApcMode would
let the APC code index outside its two queues. The Xbox wrapper now rejects
values other than KernelMode and UserMode with STATUS_INVALID_PARAMETER before
calling the timer setter. An already armed timer and the PreviousState output
are untouched by rejected requests. This is a defensive contract for unsupported
inputs; no matching reference behavior is claimed for malformed mode values.

A host regression compiles the actual production wrapper and verifies valid-mode
forwarding, rejection of -128, -1, 2 and 127 (with and without callbacks), and no
setter/output mutation after rejection. It fails before the guard at the invalid
mode status assertion and passes with the guard under ASan/UBSan.

The guarded Release64 candidate builds successfully from source tree
`4cc08b8fbc235d94600eacabfb03866563039256`; both CI pins track this tree.
The full host suite now passes 131 tests with three skips. The first-candidate
native evidence above predates this guard; repeated native qualification of the
guarded candidate is pending.
