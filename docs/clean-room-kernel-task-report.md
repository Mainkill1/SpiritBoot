# Independent clean-room kernel implementation report

Date: 2026-10-07. Branch: `spiritboot/clean-room-kernel` in `/workspace/SpiritBoot-cleanroom-kernel`.

## Separation and references

No prohibited inputs were accessed. I read the assigned task brief/design, this isolated open-source kernel and its existing public tests, and the permitted public nxdk checkout. I did not inspect the supplied firmware/archive, disassembly, comparison artifacts, other SpiritBoot checkouts, or earlier analyst conversation. Runtime results below were communicated by the integration agent from newly generated open guest output; I did not read those logs directly. No subagents, publication, integration-tree source changes, proprietary keys, or firmware-derived algorithms were used.

Allowed reference sources:

- Roswell source baseline `1569e2e89fb47cc72b9c704a8884f98200432bd4`, https://github.com/mborgerson/roswell/tree/1569e2e89fb47cc72b9c704a8884f98200432bd4 . Existing allocator, native I/O completion, debug transport, ATAPI/PCIIDEX drivers and public guest tests supplied the implementation infrastructure.
- XboxDev/nxdk revision `14d5ee97e73347c973f1f57b68b79ec08c9e77f2`, https://github.com/XboxDev/nxdk/blob/14d5ee97e73347c973f1f57b68b79ec08c9e77f2/lib/xboxkrnl/xboxkrnl.h . This is the authority for console declarations, callback signatures and IDE channel layout.

New modules carry GPL-2.0-or-later SPDX notices. Adapted existing tests retain their existing context/license.

## Commit range

Base: `1569e2e89fb47cc72b9c704a8884f98200432bd4`. Final implementation/test commit after review fixes: `f67f2b1d21f249e1dec8efa652f8747551fae844`. Original implementation head was `1ad2cef8045910bfafba783baad44e19578b2e07`.

| Commit | Change |
| --- | --- |
| `2dffd455` | Shutdown notifications, physical page pins, bounded prompt |
| `092ce85a` | One owned scatter/gather IRP with native async completion |
| `3f1a10aa` | Bound attached prompt text before KD transport |
| `2811b5f5` | Use Xbox large-page address validation for SG and pins |
| `630635e0` | Require an actual configured debugger input capability |
| `ef1249ac` | Validated warm-reboot page handoff and early reservation |
| `15c57b53` | Public IDE callbacks connected to active ATAPI/IRQ owner |
| `1ad2cef8` | Host tests, deterministic pending IO and warm reboot guests |
| `c692ac81` | Unbind borrowed IDE IRQ before release, generation-safe same-IRP retry |
| `a203814f` | Sticky overflow pins and preflight of repeated PFN aliases |
| `0c241028` | Defer nested ordinary reset; lock-free emergency invalidation |
| `fdc3fc17` | Native SG IOSB/event/APC delivery for errors and cancellation |
| `679c611d` | Error/overflow/recursive-reset guests and host lifecycle checks |
| `bad58768` | Preserve public noreturn ABI with callback-owner unwind; other-thread parking |
| `f67f2b1d` | Suppress normal kernel APCs across all shutdown boundaries through hardware reset |

No implementation changes are pending. Initial implementation commits intentionally include the fixes exposed by intermediate guest runs as subsequent focused commits.

## Implementation and changed interfaces

### Shutdown notifications

`ntoskrnl/xb/shutdown.c` implements the public caller-owned 16-byte registration layout, a locked stable priority list and detached pending list. High priorities execute first. Duplicate registration is ignored. Unregister searches both lists, so a callback can remove a later pending callback. The callback receives its registration pointer outside the spinlock. Registration during shutdown is ignored; nested drain calls do not invoke twice. Caller storage must remain alive until an executing callback returns or its shutdown unwind completes; unregister cannot cancel a callback already running.

`HalpXboxPowerAction` drains before disabling interrupts and before any kernel-initiated SMC action. The title export and native firmware-return path use that common action. This replaces the former export no-op. Ordinary nested power requests preserve the public noreturn ABI: a private exception aborts/unwinds the active callback to a kernel-owned PSEH drain boundary, then the outer command continues the pending list and issues the sole hardware action. Only the active callback's actual thread may raise that private unwind. Other ordinary threads making a nested power request wait on an unsignaled shutdown gate until reset, without returning to their callsite or raising an unmatched exception. The outer action wins. The ordinary HAL enters a native critical region before the power-claim CAS and retains its winning depth through callback drain, persistence publication and the nonreturning hardware reset; it never reenables normal kernel APCs before reset. A losing nested request balances only its newly entered depth before owner unwind or other-thread wait. The private drain wrapper independently balances its critical region with PSEH finally, and callback finally clears the owner even on propagated exceptions. This suppresses normal APCs during owner publication/handler installation/removal gaps and the post-drain interval. Special APCs remain enabled for native synchronous I/O completion. Callbacks must not wait for normal kernel APC delivery during shutdown. The title wrapper also skips nested filesystem/launch work, preserving the outer launch intent. Emergency returns at non-PASSIVE IRQL or with IF disabled bypass all normal callbacks and PFN locks, invalidate the persistence magic through the lock-free false-publish branch, and issue the hardware action immediately. This explicit emergency exception prevents bugcheck/debugger deadlock.

### Physical page pins

The page-supply PFN metadata now has a USHORT per page: 14-bit nested count, sticky-overflow flag and deferred-free flag, plus per-PFN USHORT multiplicity scratch protected by the PFN lock. Buffer and physical APIs have nxdk's VOID signatures; physical arguments are byte addresses and may have low bits. RAM bounds, overflow, invalid mappings and device addresses are checked before indexing metadata. Counts balance exactly through `0x3FFF`. A further lock latches conservative retention until reboot, because the VOID API cannot report overflow; subsequent unlocks cannot unpin an unknown number of outstanding locks. Unlock at zero is inert. Buffer preflight counts repeated aliases of each PFN before modifying any counts, so an insufficient unlock count changes no pages; locking across the limit accepts all valid pages and latches the overflowing PFN instead of partially acquiring the buffer. Xbox's valid-address helper handles KSEG0 large PDE mappings, unlike the native PTE-only helper that caused the first experimental SG failure.

Contiguous allocation cannot relocate a pinned movable page. Freeing a pinned contiguous allocation retains the allocation and its bookkeeping: unlock and retry free. Returning a pinned movable page defers reclamation until the last unlock. SG owns its pins until completion. Allocator metadata sizing and early page-supply setup include the new array.

### Contiguous persistence

`ntoskrnl/xb/mm/persistence.c` uses an independently designed one-shot handoff at PA `0xD000`: versioned low-64-MiB page bitmap, image-base binding, existing launch-slot hash and FNV-1a integrity checksum. Magic is cleared before publication and written last after a memory barrier. It is consumed/invalidated on every read, including failed validation. Power off/cycle invalidates it; warm reset publishes after shutdown callbacks.

Mark/unmark validates a requested subrange against the exact live allocation size and checks arithmetic overflow. Any selected partial page persists whole. Unmark removes persistence selection without freeing ownership. Normal free clears selection. Fixed loader/handoff/NV2A reservations are rejected; boot revalidates every selected PFN against actual loader descriptors and rejects the entire handoff on any collision or malformed header.

Restored PFNs are excluded before ARM3 boot carving and before free-list population. They retain physical address/content and cannot satisfy a competing allocation. Restored allocations are maximal selected page runs that support allocation-size queries, unmark and free. The original launch page PA is included in the existing launch slot and adopted into live allocation bookkeeping where valid, avoiding repeated launch-page orphaning.

The loader image/stack moved from low 1–2 MiB to upper RAM near 125 MiB, with an identity large-page mapping there. XZ workspace moved from 32 MiB to 112 MiB. This prevents the loader/decompressor from overwriting selected low-RAM title pages before validation. The existing 128-MiB machine prerequisite remains.

### Scatter/gather completion

`ntoskrnl/xb/scattergather.c` captures the four-byte console segment elements into request-owned page/PFN metadata, pins them, allocates one page-aligned bounce buffer, and dispatches one multi-page IRP/MDL per API call. Gather copies before dispatch; scatter copies the reported completed bytes in the completion callback before native IOSB/event/APC delivery. Segment low bits retain existing public-test behavior (ignored); bad transfer counts are rejected.

The existing native request manager owns file/event references, thread IRP tracking, synchronous file locking and pending completion. Async handles return dispatch status without waiting on a shared file event. The request-specific callback frees the bounce MDL/buffer/context and releases pins exactly once. Error unwinding releases all resources. A native-private opt-in `IRP_XB_SG_COMPLETION` flag selects the existing single IopCompleteRequest IOSB/event/APC delivery branch for SG even when final status is an inline error, a pending error on a synchronous file, or cancellation. Ordinary native IRPs retain their prior NT error policy; no SG code independently signals or queues a second APC. Access, unbuffered handle, offsets, append/current-position forms, EOF/partial results and native event/APC behavior are preserved. No new public syscall signature is introduced; nxdk's incorrectly narrow gather return declaration is called through a correctly typed NTSTATUS function pointer in tests.

### IDE integration

`sdk/include/reactos/xb-ide.h` defines the public nxdk layout and compile-time checks: channel 264 bytes, DPC 28, timer 40, queue 12, interrupt 112, StartPacketRoutine offset `0x10`, CurrentIrp offset `0x20`. `ntoskrnl/xb/ide.c` replaces the former zero-filled data export.

The primary PCIIDEX ISR wraps the existing native hardware owner and invokes the mutable public InterruptRoutine. Saved defaults chain the actual operation at most once. Public interrupt synchronization/connect use the existing interrupt shadow table, borrowing the active native IRQ. Disconnect does not detach the driver's borrowed owner. No second IRQ is allocated. The existing adapters now live in `ntoskrnl/xb/interrupt.c`. A persistent driver-owned tombstone prevents fallback to uninitialized title shadow storage after unbind. Borrowed pointer lookup/use is protected from pageable teardown by DPC level on UP Xbox. Teardown disables device IRQs, cancels timer work, clears public/native context and unbinds before IoDisconnectInterrupt releases storage. Failed IRQ connection follows the same cleanup. Detached borrowed synchronize/connect/disconnect refuse safely; title initialization cannot replace that owner. A request generation counter prevents completion from clearing CurrentIrp when the default callback restarts the same IRP.

Actual ATAPI StartIo, completion DPC, queue progression, timeout recovery and completed reset call the public mutable callbacks. CurrentIrp, busy/requested/expecting IRQ, timeout and PRD state reflect these paths. FinishDpc is the driver's actual shared completion DPC. Timer/TimerDpc run the primary native port timer; teardown cancels them. Secondary-channel operations remain on the native path.

The initialized public DeviceQueue busy state tracks the native lifecycle; its list is not an alias of all private ATAPI queued requests. Retry count fields are not a fully mirrored native retry scheduler. Defaults chain only the current native operation inside the corresponding callback, not arbitrary title-submitted packets or a saved callback invoked later. Those broader behaviors are not claimed.

### Debugger prompt

Ordinal 10 maps to `XeDbgPrompt` instead of the fatal fallback. Zero length/null response returns zero without writing; detached one-byte output becomes empty without touching following bytes. Prompt/input STRING lengths are bounded by USHORT and native transport limits. The wrapper uses the existing native DebugPrompt input path when it has actual input capability.

KDBG=FALSE's local diagnostic packet shim could appear attached while synthesizing receipt; it cannot obtain interactive input. `NxkDebuggerPromptAvailable` distinguishes configured input capability, so both verified KDBG=FALSE builds return an empty response promptly. KDBG-enabled existing console input remains wired but was not compiled/runtime-tested here. Interactive prompt support is therefore not verified.

## Tests and evidence

### Local checks

- Fresh DBG=1 and DBG=0 Release configurations, KDBG=FALSE: successful flash builds, ABI compile checks and init-reference audits. Fresh release completed 733 targets; debug's initial fresh build completed 745 targets. Final committed incremental checks exited 0 and produced unchanged flash hashes.
- `tests/host/clean-room/run.sh /workspace/SpiritBoot-cleanroom-kernel-output/host`: actual-source persistence checks 18/18, shutdown 9/9, IDE/interrupt lifecycle 24/24, HAL power action 24/24, and physical pin 13/13 passed (88/88). IDE checks compile actual ide.c and interrupt.c, protect released native IRQ memory with mprotect(PROT_NONE), exercise detached public calls then reattach, cancel the actual public timer, and finish/restart the same IRP. HAL checks compile actual reboot.c and shutdown.c, call real HalReturnToFirmware recursively, assert both callbacks precede the sole outer reset, assert the owner callback's noreturn callsite never resumes, simulate a different thread parking without a private exception, and separately exercise HIGH/APC/IF-disabled emergency bypass. Additional focused scheduling hooks check normal-APC suppression at the actual power-claim CAS, owner publication/lock release, PSEH frame entry/exit, persistence publication and SMC action. They assert the winner retains exactly one outer depth through reset, the losing other thread balances its depth, emergency reset adds no depth, and direct drain balances on return and propagated exception. The same source-level test failed before the APC guard at the CAS/publication/hardware assertion (`host-apc-before.log`), then passed after it. The host uses an explicit SEH/scheduler model; native PSEH/RTL and the actual optimized public noreturn declaration are verified by the direct warm guest. Pin checks extract and compile the actual supply bookkeeping/public lock bodies (privileged relocation assembly is omitted), checking alias multiplicity, invalid mappings/range overflow, sticky saturation and deferred free. These use minimal fake NT spinlocks/types on the host; they validate list/handoff algorithms, not multiprocessor scheduling or guest ABI sizes. Guest/kernel compile assertions cover actual 32-bit ABI.
- Both standalone nxdk guests compile successfully with the pinned image, including the deterministic delayed-completion fixture.
- `git diff --check`: passed. Working tree clean after final commit.

### Direct xemu runs communicated by integration agent

1. Baseline prompt probe bugchecked at unimplemented ordinal 10 (`e0000002`), retaining behavioral red evidence. The original pin setup selected a physical address above the contiguous allocator's 64-MiB ceiling; this was a test setup failure, not evidence of a pin bug. The corrected probe first proves successful relocation of an eligible unpinned low-RAM page, then proves nested pins prevent it until both unlocks. The integration agent also reran that corrected guest against the pristine baseline: the pinned physical page was incorrectly allocated, establishing pin behavioral red evidence before the expected fatal DbgPrompt stopped the run.
2. First experimental guest booted; corrected pins and IDE layout passed. SG returned ACCESS_VIOLATION because native valid-address checks missed Xbox large PDEs. Prompt observed a synthetic debug attachment. The raw DVD-device read returned INVALID_DEVICE_REQUEST. These real failures were retained and fixed at their source: Xbox address helper, actual transport capability and supported unbuffered DVD file path.
3. Revised contracts guest R2 passed 16/16 with clean emulator exit. IDE real I/O counters: starts=1, finishes=1, IRQs=1, next=1, invalid state=0. File tests cover scatter/gather bytes, offset, sub-page transfer, ignored segment low bits, buffered-handle rejection, EOF/short results, event/APC and two requests sharing an async handle. Those filesystem requests can complete inline; R2 alone does not establish overlapping pending completion.
4. Warm reboot guest passed 4/4 with clean emulator exit: same preserved PA/content across reset, stable callback order and duplicate/pending removal, restored one-page ownership/size, refusal of competing exact-window allocation. The guest then unmarks/frees and powers off.
5. The pre-review final contracts guest added two deterministic public-driver checks (18 total): both same-handle scatter/gather requests are held before any completion and must return STATUS_PENDING; IRPs and bounce buffers differ; IOSB/event state stays independent; segment arrays and offsets may be mutated after dispatch; gather input is snapshotted; reverse DPC-level completion produces independent events/APCs in reverse order and correct strided page data. The integration agent captured a passing 18/18 run with exit 0. Both calls returned `00000103` (STATUS_PENDING), completion/APC order was 1,0, APC counts were 1,1 and bad-state/data count was 0 for both scatter and gather.

6. Review regression guest (23 tests) passed 23/23 with clean exit on the first fixed flash. New checks cover inline EOF on synchronous and async handles, DPC-completed pending EOF on a synchronous handle, driver-acknowledged Cancel=TRUE async IRP completion, and 0x8000 physical locks/unlocks followed by free/exact-window allocation. Error cases retained their seeded IOSB sentinel until real completion and then delivered EOF/CANCELLED, zero bytes, one event and one APC. The same ISO on immutable pre-review R2 passed 19 and failed four: all three error-delivery checks timed out on their event, and overflow lost allocation ownership. Cancellation already passed on R2; its check now prevents regressions. This is actual native canceled-IRP completion, not a cancellation syscall test (nxdk exposes no cancellation syscall).
7. The review warm guest now has five checks. Callback 1 invokes the actual public HalQuickRebootRoutine through nxdk's unchanged noreturn declaration. Stage 2 requires NestedReturned=0 (the callsite did not resume) plus full callback order before accepting the outer reset. The first attempted return guard violated this ABI: the optimized guest had no callback epilogue after the call and faulted at EIP 0002284D with C0000005, followed by bugcheck/emergency reset. This failure is retained in `experimental-warm-review`; no function-pointer cast or softened assertion was used to hide it. The final callback-owner PSEH unwind fix passed 5/5 with clean exit in `experimental-warm-unwind`. The same final ISO on immutable pre-review R2 passed three persistence checks and failed the two callback-order/nested-reset checks, then exited cleanly (`pre-review-warm-red`). This proves the real public noreturn regression distinguishes the required behavior.
8. The integration agent additionally reported the earlier implementation's complete checked public XISO suite passed: 149 PASS (144 leaves/5 groups), COMPLETE 144/144, zero applicable oracle failures and all 253 deterministic baseline hashes matched, 261-second clean exit. One non-applicable S3TC queued diagnostic failure_count=11 was retained. This run preceded review fixes and is not substituted for final reviewed patch-build validation.

9. Final normal-kernel-APC guard fixes a source race identified after the passing warm run: an APC could previously execute while NxCallbackThread was published outside the matching private handler, or after owner clear and before the outer hardware action. Native `ntoskrnl/ke/apc.c` and `internal/ke_x.h` confirm that critical regions alter KernelApcDisable, leaving SpecialApcDisable and special native completion APCs available. The focused host checks and both DBG=1/DBG=0 flash builds pass on the guarded source. No redundant expensive guest run was performed for this small guard; final independent patch builds/direct guests remain the integration agent's next step. The reviewer inspected the working guard diff/logs and found no new source issue before it was frozen in f67f2b1d.

Integration-owned evidence paths (new open guest output; not source inputs):
`/workspace/SpiritBoot-cleanroom/artifacts/clean-room/experimental-contracts-r2/{serial.log,run.json}` , `/workspace/SpiritBoot-cleanroom/artifacts/clean-room/experimental-warm/{serial.log,run.json}` and `/workspace/SpiritBoot-cleanroom/artifacts/clean-room/experimental-contracts-pending/{serial.log,run.json}`. Review green and red evidence: `/workspace/SpiritBoot-cleanroom/artifacts/clean-room/experimental-contracts-review/{serial.log,run.json}` and `/workspace/SpiritBoot-cleanroom/artifacts/clean-room/pre-review-red/{serial.log,run.json}`. Noreturn warm captures: `/workspace/SpiritBoot-cleanroom/artifacts/clean-room/experimental-warm-review/{serial.log,run.json}` (failed return guard), `/workspace/SpiritBoot-cleanroom/artifacts/clean-room/experimental-warm-unwind/{serial.log,run.json}` (5/5 fixed), `/workspace/SpiritBoot-cleanroom/artifacts/clean-room/pre-review-warm-red/{serial.log,run.json}` (3 pass/2 fail discriminator). Integration agent owns emulator command lines and final reproducible source-patch application/runtime grading. I did not run xemu myself.

## Reproduction commands

The toolchain image used is `spiritboot-toolchain:verified`, local image ID `sha256:f770af86ab18f86ca6eaac9e491e7deef92eeaca496882229cf8ce3e712f5e44`. Only the permitted kernel and isolated output were mounted.

```sh
docker run --rm \
  -v /workspace/SpiritBoot-cleanroom-kernel:/src \
  -v /workspace/SpiritBoot-cleanroom-kernel-output:/out \
  spiritboot-toolchain:verified sh -c \
  'cmake -S /src -B /out/dbg -G Ninja -DCMAKE_TOOLCHAIN_FILE=/src/toolchain-gcc.cmake -DCMAKE_BUILD_TYPE=Release -DARCH=i386 -DSARCH=xbox -DDBG=1 -DKDBG=FALSE && cmake --build /out/dbg --target flash -j2'
# Repeat with /out/release and -DDBG=0 for the release build.

tests/host/clean-room/run.sh /workspace/SpiritBoot-cleanroom-kernel-output/host

docker run --rm -v /workspace/SpiritBoot-cleanroom-kernel:/src \
  -w /src/tests/xbe/clean-room-contracts \
  ghcr.io/xboxdev/nxdk@sha256:bab707b7ed2544e9956d51e7b411a4575ab66120bd608b3237698495203d15f7 \
  sh -c 'export PATH=/usr/src/nxdk/bin:$PATH; make NXDK_DIR=/usr/src/nxdk -j2'
# Repeat with workdir /src/tests/xbe/clean-room-warm-reboot.
```

Build/host logs in isolated output: `build-dbg-r2.log`, `build-release.log`, `build-committed.log`, `guest-pending.log`, `guest-r2.log`, `host-checks.log`, `host-review.log`, `build-review-final.log`, `build-review-committed.log`, `guest-review.log`, `guest-review-warm.log`, `build-unwind.log`, `build-unwind-release.log`, `guest-unwind.log`, `host-unwind.log`, `host-apc-before.log`, `host-apc-after.log`, `build-apc-guard.log`. Intermediate failure logs are retained in the same directory.

| Artifact | SHA256 |
| --- | --- |
| `kernel-output/dbg/flash.bin` | `cbdc84b0417e49cb707cc20c2c65bba1a5ff4594863194cc6cf48d82c03f35ee` |
| `kernel-output/release/flash.bin` | `78b4df31e8a1da97af2d0afb905f1584854dc68a0843fa3031aac4562bf11c9a` |
| `tests/xbe/clean-room-contracts/clean-room-contracts.iso` (review final 23 tests) | `f157fba1a1fd20a2b60bd411d906ea897bbaf94d334cf87e4f036031e020f296` |
| `tests/xbe/clean-room-warm-reboot/clean-room-warm-reboot.iso` | `a328fb65a3895e555664396116bc7740e8a248a4d6966aac9a466a23937789b6` |

Contract guest emits explicit begin/end PASS or FAIL markers, then SMC power off. Existing scatter fixture writes/removes one scratch file on HDD Partition1. Warm guest allocates/marks three pages, resets once through HalReturnToFirmware, reopens its own DVD ISO via the launch path, emits final TAP and powers off. Warm guest must run independently with its ISO still attached; it intentionally resets the emulator.

## Precise limits and unverified cases

- No Conker game image was supplied. No gameplay compatibility or measured IO performance gain is claimed.
- Cold RAM with no valid handoff is treated as cold boot; power off/cycle invalidates the slot. There is no separate hardware cold-reset discriminator. An externally preserved valid RAM slot surviving an abnormal physical cold reset could be accepted. FNV is corruption detection, not authentication. Loader address/image binding and one-shot consumption reject many stale cases, not every conceivable replay.
- Selected partial pages survive as complete pages. Adjacent selected pages restore as one maximal run, so original allocation grouping/requested byte length is not preserved across reset. Restored ownership remains until explicit free, even after unmark.
- Loader/decompressor relocation assumes the baseline 128-MiB RAM configuration. 64-MiB hardware operation is not supported/verified by this change.
- WC alias buffer translation is not expanded here: the baseline physical-address helper does not translate those alias VAs back into low RAM. Such buffers fail safely rather than acquiring pins. Count overflow deliberately retains the affected page until reboot; the API cannot recover exact nesting after overflow. This conservative leak is the defined safe behavior. Per-PFN alias multiplicity is preflighted; counts never wrap. Concurrent caller free/mark/IRP buffer lifetime still requires ordinary caller ownership discipline.
- Ordinary nested firmware returns never resume their noreturn callsite: the owner callback is unwound to the drain boundary, and other threads park for the outer reset. Callbacks must release ordinary resources before making a noreturn call or through supported SEH unwind/finally cleanup; plain C cleanup after that call is unreachable. Normal kernel APC delivery is suppressed through the ordinary hardware action; callbacks may use special native I/O completion APCs but must not wait for normal APCs. Emergencies intentionally skip callbacks and invalidate handoff to avoid unsafe locks/IO. Executing callback storage cannot be freed merely because unregister returns.
- IDE timer/timeout/reset hooks are connected in source but only normal DVD I/O callbacks were exercised at runtime. IDE actual-driver error recovery, cancellation, mutable timeout/reset hooks, high queue depth and stress shutdown were not separately driven. Same-IRP retry and detached IRQ lifecycle are covered by actual-source host shims, not a live PnP removal guest. Public queue/retry/private scheduling limitations are described above; deferred invocation of saved defaults and arbitrary title-originated native requests are not implemented contracts.
- KDBG=FALSE builds provide detached empty prompt, not interactive input. KDBG-enabled attached input path is wired to existing transport and remains unverified.
- Host tests are bounded algorithm checks. No fault-injection test exhausts every allocation or cancellation timing. Native completion owns pending/cancellation; the final held-IRP fixture specifically addresses overlapping request state/lifetime.

Review findings on IRQ lifetime/retry, SG error completion, overflow/alias pins, recursive reset and emergency reset were addressed in the final source. Source is ready for fresh review and reproducible patch integration. Nothing was published. The report itself is the sole authorized write outside the isolated kernel/output tree.
