# Xbox semaphore overflow fix

## Failure

The first native run of the new public-kernel contract XBE passed checks 1–47
on current-reference 64 MiB firmware
`c630d22f2353d3898024d510f0b402b64bccdb331781fe7885389f73d6200853`,
then stopped before reporting the expected semaphore-overflow result. The same
XBE passed all 59 checks on Complex. The stopped guest had EIP `0x8401e92d`;
the exact unstripped kernel maps that address to the terminal `cli`/`hlt`/jump
loop in `KeBugCheckWithTf`.

The next operation after check 47 was
`NtReleaseSemaphore(semaphore_at_limit, 1, &previous_count)`.
`KeReleaseSemaphore` correctly performs the limit decision while holding the
dispatcher lock and raises `STATUS_SEMAPHORE_LIMIT_EXCEEDED`. Xbox titles call
the exported Nt routine in `KernelMode`. The wrapper used
`ExSystemExceptionFilter()`, which returns `EXCEPTION_CONTINUE_SEARCH` for a
kernel-mode caller, so the expected overflow status escaped the syscall and
reached the bugcheck path.

## Change

Patch `0136-kernel-semaphore-overflow.patch` changes only the Xbox exception
filter in `NtReleaseSemaphore`. It handles
`STATUS_SEMAPHORE_LIMIT_EXCEEDED` and returns that status from the Nt API. All
other exceptions continue through `ExSystemExceptionFilter()`. The non-Xbox
path is unchanged. `KeReleaseSemaphore`, its dispatcher-lock-protected limit
decision, handle reference ordering, output ordering and object cleanup remain
unchanged.

The patch SHA-256 is
`ce8eeab6945e5a98e67dcb89e53810761e45ae9dffbcce7be7564ecce01dd125`.
The resulting 150-patch source tree is
`57419bea98b3a556c5a8c9bf3352cbe8e9d756e9`.

## Verification

The source-level checker compiles the actual selected
`NtReleaseSemaphore`, `KeReleaseSemaphore` and `ExSystemExceptionFilter`
bodies against a bounded exception/dispatcher shim. It passes 36 Xbox checks
and 35 non-Xbox preservation checks under AddressSanitizer and
UndefinedBehaviorSanitizer. These cover overflow status and state, object and
lock cleanup, user-mode probing, optional output, invalid releases and handles,
unrelated fault propagation, signed wrapping, and concurrent fill/drain at the
lock boundary. The contemporaneous product host suite completed 471 tests with
26 skips. The final integrated suite is rerun and reported separately because
later PR #248 additions increase discovery counts.
An independent replay applies the patch to the exact selected source, verifies
that only the intended function changes, reproduces the unpatched failure, and
passes both actual-source host profiles.

The release 64 MiB build is 524,288 bytes with SHA-256
`42ad0c392b97d195f6aacaa47b1c168f1f74038ddf3258257b21cfde99bcb647`.
An isolated repeat produced the same image byte for byte and recorded the same
source tree, source-worktree digest and firmware-lock digest. Release and debug
builds also complete for both 64 and 128 MiB profiles.
On the Windows user-desktop runner, the exact 59-check XBE, xemu executable,
configuration, EEPROM, 64 MiB setting and private-disk policy from the failed
reference run were retained; only the firmware and job identity changed. The
candidate reports all 59 checks passing, including the formerly fatal overflow
and unchanged semaphore count, then reaches guest shutdown. The runner records
named-pipe desktop launch, verified input hashes, private runtime state deletion
and zero owned processes after cleanup.

A separate broad API run with the same candidate passes 634 enabled leaves out
of 639 planned cases, with the five frozen Complex-compatibility exclusions and
all four older TODO-labelled leaves handled according to the frozen contract.
It records 634 timed leaves but is descriptive only and is not performance
acceptance evidence.

The fixture was then extended prospectively to 68 checks. The new cases issue
release counts `0`, `-1` and `LONG_MAX` from a semaphore already at its limit;
each verifies the exact status, untouched previous-count output, and unchanged
queried count and limit. Complex and the fixed SpiritBoot firmware both pass
68/68 with byte-identical serial output, normal guest shutdown, verified input
identities and complete owned-process/private-state cleanup. This also exercises
the target compiler's signed-wrap boundary instead of relying only on the host
shim's `-fwrapv` model.

## Evidence boundaries

The failed current-reference run remains the historical before-fix evidence.
The fixed candidate is the required pre-extraction firmware denominator for a
later storage-replacement performance comparison. Mixing this kernel fix into
only the post-extraction firmware would confound that comparison. Neither the
host shim nor the two native correctness runs qualify the independent storage
replacement, physical hardware, game saves, or performance acceptance.
