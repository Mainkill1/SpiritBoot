# Independent clean-room kernel review

Date: 2026-10-07. Final source review: **approved at `f67f2b1d21f249e1dec8efa652f8747551fae844`**. R1–R5 and the follow-up R4 APC transition gap are resolved. No remaining concrete source defect was established. Final isolated patch-build/runtime validation remains an integration requirement.

Reviewed public kernel commit `1ad2cef8045910bfafba783baad44e19578b2e07` against `1569e2e89fb47cc72b9c704a8884f98200432bd4`, with the permitted public nxdk ABI declarations, behavioral specification, implementation report, and permitted experimental runtime captures. No attachments, community firmware, disassembly, comparison artifacts, other SpiritBoot checkouts, or prior analyst history were inspected. This review made no implementation changes and published nothing.

## Initial findings

These findings describe the initial committed range. They were sent to the integration agent for the original implementer to address. The reproductions below are source-demonstrable cases to add to focused regressions; this reviewer did not run them in xemu.

### R1 — P1: borrowed IDE interrupt outlives its native allocation

Locations: `ntoskrnl/xb/ide.c:105–116`, `ntoskrnl/xb/xbe.c:3074–3085,3130,3145`, `drivers/storage/ide/pciidex/chipset/pata_generic.c:895–900`.

The public interrupt shadow stores the driver's native interrupt in `BorrowedInterrupt`. Primary channel teardown calls `IoDisconnectInterrupt`, which frees that interrupt allocation (`ntoskrnl/io/iomgr/irq.c:142–172`), without clearing the shadow. Public `KeConnectInterrupt` subsequently reads `BorrowedInterrupt->Connected`; public `KeSynchronizeExecution` uses that freed object and its synchronization state. The bridge also retains the previous channel context and public connected state.

Reproduction: remove/stop the primary channel, then call either public routine on `IdexChannelObject.InterruptObject` before another successful attach. Pool reuse can turn this into invalid lock access or a kernel fault. Unbind and invalidate public lifecycle state before freeing the native owner; also cover failed startup and reattachment.

### R2 — P2: retrying the same IRP clears the new active IDE request

Location: `ntoskrnl/xb/ide.c:152–162`.

The finish adapter clears `CurrentIrp` after invoking the finish callback if its pointer still equals the finishing IRP. Native `AtaReqCompleteRequest` can requeue the same busy/resource-limited SRB (`drivers/storage/ide/atapi/scsi.c:354–357`) and dispatch it again before returning (`scsi.c:394–399`). The restarted request naturally has the same IRP pointer, so the outer finish clears the new active state. Its eventual completion then takes the mismatch bypass at line 155, omitting the public finish callback and leaving busy/expecting-interrupt state stale.

Reproduction: a primary request requeues without another queued request, or an adapter regression has its default finish operation restart the same IRP. Move the old request's state transition before the callback or identify active generations independently of the IRP pointer.

### R3 — P2: scatter/gather errors leave stale IOSB and suppress completion notifications

Location: `ntoskrnl/xb/scattergather.c:163–169`; native behavior: `ntoskrnl/io/iomgr/irp.c:330–335,494–559`.

The new scatter/gather path relies entirely on native completion to publish the caller's result. Native completion does not publish `UserIosb` for an immediate `NT_ERROR`, or for a pending error on a synchronous file, and suppresses the supplied event/APC in those branches. The former aggregate scatter/gather completion published its final status/count and notifications even for EOF. The current EOF fixture masks the regression by zeroing the IOSB and checking only the returned error and zero count (`tests/xbe/api-regression/io/scatter.c:439–445`).

Reproduction: seed the IOSB with `{STATUS_PENDING, 0xABCD}`, supply an initially unset event, and issue a scatter read at EOF on a synchronous unbuffered file. The call returns EOF while the IOSB remains stale and the event remains unset. A held driver completing a synchronous request with an error exercises the corresponding pending case. Publish request-specific error state and completion exactly once, preserving native IRP/file/event ownership; add inline error, pending error, and cancellation checks, including APC order/count.

### R4 — P1: a recursive actual reset skips the remaining shutdown callbacks

Locations: `ntoskrnl/xb/shutdown.c:57`, `hal/halx86/xbox/reboot.c:30–41`.

The list drain makes nested drain calls inert, but the nested HAL power action still publishes and resets the hardware. A callback invoking actual `HalReturnToFirmware` therefore resets before remaining detached callbacks execute. This is acknowledged in the implementation report, but violates the design's requirement that callbacks run before the actual reset.

Reproduction: register A before B; A requests firmware reset. B is never invoked in the initial implementation. Guard the actual power action across the entire drain/publication sequence and define how recursive actions are deferred. A drain-only test cannot establish this property.

### R5 — P2: saturating pin counts lose outstanding locks; aliases defeat preflight

Locations: `ntoskrnl/xb/mm/pagesupply.c:259–282`, `ntoskrnl/xb/mm/api.c:83–93`.

At count `0x7fff`, another public VOID lock call is silently ignored. After `0x8000` lock calls and `0x7fff` unlock calls, the page becomes unpinned even though a caller still has one logical lock outstanding. It can then relocate, or a pinned contiguous allocation can be freed. Avoiding numeric wrap alone does not preserve balanced pin ownership when no failure is observable to callers.

Buffer preflight checks each VA independently. If multiple adjacent mapped VAs alias one PFN, each check sees the same original count; increments can partially fail at the limit despite the all-or-nothing comment. Unlock preflight has the symmetric multiplicity problem.

Reproduction: nested physical locks on a movable page followed by the existing exact-window relocation pressure; also create a buffer containing repeated PFN mappings near the counter limit. Use conservative overflow retention or sufficiently broad accounting, and account for per-PFN multiplicity when validating a buffer operation.

## Evidence and unaffected paths

The allowed experimental pending capture reports 18/18 checks, return code 0, both same-handle requests pending, reverse completion/APC order 1,0, APC counts 1,1, and bad-data/state count 0. Source confirms separate contexts, captured segment/offset state, one bounce buffer and IRP per call, balanced failure unwind, and request-specific pin release. Bounce MDL removal before native completion avoids a second free. Successful pending ownership is supported by evidence; error/cancellation contracts need R3's focused coverage.

The warm capture reports 4/4 checks and return code 0, including same physical address/content, shutdown priority/removal, restored allocation size/ownership, and refusal of a competing exact-window allocation. Persistence validates the header, bitmap size, image binding, checksum, launch binding, and every selected page against boot descriptors before allocator population. It consumes invalid and valid magic once. The loader/workspace relocation keeps selected low-RAM pages away from early loader writes. No additional persistence failure was established by this review.

Contiguous allocation/free/persistence use the established contiguous-lock then PFN-lock order. Pinned contiguous free keeps tracking and requires unlock/retry; movable-page reclamation is deferred until its final pin is released. Ordinary counts and invalid-device-address rejection are coherent. R5 covers the arithmetic edge.

The shutdown list preserves descending priorities and stable ties, detects duplicates without trusting caller link fields, allows pending removal, and invokes callbacks outside the registration lock. Executing storage must remain alive until callback return, as documented. R4 concerns the hardware action rather than the list algorithm.

Public IDE channel size and offsets match the nxdk declarations and include compile-time checks. The bridge borrows the active driver's IRQ and connects callbacks to real start, completion, queue, timer, and reset paths. The normal I/O capture records starts=1, finishes=1, IRQs=1, next=1, bad=0. R1 and R2 cover lifecycle cases that this normal-path capture does not exercise.

The detached prompt path returns promptly, handles zero length without writes, and bounds native string sizes. Interactive attached KDBG input remains unverified; the verified KDBG=FALSE builds implement the empty-response path.

## Limits and follow-up review

Existing passed expensive guest/build checks were not rerun. Runtime evidence here belongs to the experimental images; isolated hashed-patch builds and final integration runtime checks remain the integration agent's responsibility. Host-shim results in the implementation report do not establish guest scheduling or IRQ teardown behavior.

Additional disclosed limitations remain: persistence restores maximal page runs rather than original allocation boundaries; valid retained RAM cannot distinguish every abnormal cold-reset replay; checksum integrity is not authentication; WC buffer aliases are rejected by the existing physical-address helper; title callbacks cannot arbitrarily invoke saved defaults later or submit independent native packets; queue/retry fields are not a complete public scheduler. No Conker gameplay or measured performance evidence is available.

Emergency HAL resets also deserve an explicit policy: bugcheck/debugger callers can arrive with raised IRQL or interrupts disabled, whereas the new drain and publication acquire DPC-level locks and callbacks may need normal I/O. The title-driven warm fixture does not establish behavior in that context. This is recorded as a review limitation rather than a separately reproduced failure.

The initial review is complete. The follow-up review below distinguishes resolved findings from remaining failures.

## Follow-up review through `679c611de39e624af011727c55cec03f1fa954c2`

Reviewed the frozen public-source range `1ad2cef8..679c611d`. Newly permitted evidence: `experimental-contracts-review`, `pre-review-red`, and `experimental-warm-review`. No source changes or repeated expensive checks were performed by this reviewer.

| Finding | Current status | Evidence |
| --- | --- | --- |
| R1: borrowed IRQ lifetime | Resolved | Primary resource release unbinds before `IoDisconnectInterrupt`; failed connect also unbinds. The interrupt shadow retains a driver-owned tombstone, rejects detached synchronize/connect, and prevents title initialization from acquiring a second owner. UP DPC-level exclusion protects borrowed-pointer use from pageable teardown. The reported actual-source host test poisons released storage with `mprotect`, then checks public calls and reattachment. |
| R2: same-IRP retry | Resolved | `NxkIdeStartRequest` advances a request generation; finish clears `CurrentIrp` only if the generation did not change. A same-pointer restart therefore retains current/busy/expecting state, and its final completion clears it. Actual-source host regression covers this case. |
| R3: SG error completion | Resolved | An SG-private IRP flag selects the existing native final-publication branch for errors. The bit does not collide with declared native IRP flags. Result publication, event/file signaling, APC queueing, event/file dereference, and IRP release remain on one native completion path; bounce/pin cleanup remains request-specific. Guest evidence covers inline synchronous and asynchronous EOF, pending synchronous EOF, and asynchronous driver-acknowledged cancellation. |
| R4: recursive public reset | Unresolved; demonstrated failure | The guard returns to a public call site declared non-returning. The new warm guest faults during its first nested callback rather than completing stage 2. See details below. |
| R5: pin saturation/aliases | Resolved with explicit retention limit | Overflow now latches a conservative pin until reboot, preventing silent loss of outstanding ownership. Batch scratch counts repeated PFN aliases before any mutation and rejects excess unlock multiplicity. Boot metadata sizing includes the extra array. Host alias checks and guest overflow/free/exact-window checks cover the fix. |

The contract-review capture reports 23/23 checks and return code 0. It explicitly records EOF IOSB `c0000011`, zero bytes, and one APC in each added inline/pending error case, and cancellation IOSB `c0000120`, zero bytes, and one APC. The same ISO against the pre-review image reports 19 passes and four failures: both inline error cases, pending synchronous error, and pin overflow. Driver-acknowledged asynchronous cancellation already passed before the fix; this evidence exercises canceled completion, not cancellation-request scheduling or cancel-routine races. The integration agent reports 72 passing actual-source host checks; this reviewer inspected their source but did not rerun the host suite.

### R4 follow-up — P1: returning from `HalReturnToFirmware` violates the public ABI

Locations at the reviewed follow-up: `ntoskrnl/xb/xbe.c:572–573`, `hal/halx86/xbox/reboot.c:39`, public `/workspace/SpiritBoot-public-nxdk/lib/xboxkrnl/xboxkrnl.h:4126`.

The public declaration is `VOID DECLSPEC_NORETURN NTAPI HalReturnToFirmware(...)`. The implementation now returns when shutdown is already in progress. An optimized title callback may consequently omit its epilogue and all continuation after the call; returning transfers execution into code for which the compiler assumed no reachable continuation. The allowed real warm-review capture records stage 1, then `C0000005` at EIP `0002284D` followed by bugcheck `7e` during this nested callback. It does not establish the exact generated instruction without a public-source build inspection, but the ABI contradiction alone is conclusive.

The host power fixture defines `DECLSPEC_NORETURN` away and asserts continuation after a nested call. That verifies the returning model, not the public ABI. Casting the guest call to a returning function pointer would similarly hide the production defect and is not an acceptable resolution.

A compatible deferred-reset policy must never resume the nested public call site. For example, terminate/unwind the current callback to a kernel-owned drain boundary and continue the other pending callbacks before the outer hardware action. Callback cleanup and stack/unwind semantics must be explicit. Native HAL paths must likewise avoid resuming callers that assume a non-returning reset. An explicitly unsupported nested-call policy can be documented, but must not be represented as a fixed/verified nested-public-reset contract.

The emergency path now skips callback/PFN acquisition at non-PASSIVE IRQL or with interrupts disabled and invalidates the handoff without acquiring the PFN lock. This addresses the initial report's emergency-lock concern for those contexts. It does not repair R4's ordinary nested public call.

Final signoff remains blocked by R4. The four resolved findings and 23-check experimental contract results do not establish successful warm reboot for this follow-up image. Final hashed-patch build/runtime evidence is still owned by integration.

## Unwind follow-up through `bad5876866953e2066ebca793d8d616d516ad04b`

The direct callback case now respects the public noreturn contract. Its nested firmware request raises a private noncontinuable status to the kernel's callback PSEH boundary; the call site is abandoned, remaining pending callbacks execute, and the outer hardware action/launch intent wins. Other ordinary threads wait on an unsignaled shutdown gate instead of raising an exception without a boundary. Emergency contexts keep the explicit immediate-reset policy. Ordinary resources must be released before making a non-returning power call, or through supported SEH unwind/finally cleanup; unreachable C continuation is not cleanup.

The actual public guest call remains unchanged. `experimental-warm-unwind` reports 5/5 and return code 0 in 1.775 seconds; the same ISO on pre-review R2 reports three passes and two failures, specifically callback order and nested reset. This establishes the direct owner callback's corrected ABI and continued drain, independently of the earlier returning guard's fault. Reported host checks total 76/76, including native power 15/15 with owner unwind and a modeled other-thread wait. The host scheduler/SEH model does not establish every real APC transition.

### Remaining R4 edge — P2: callback owner can exist without its unwind boundary

Location: `ntoskrnl/xb/shutdown.c:81–90` at `bad58768`.

`NxCallbackThread` is published before releasing the spinlock to PASSIVE and before `_SEH2_TRY` installs the callback handler. It is cleared only after `_SEH2_END` has removed that handler. A normal kernel APC can execute at PASSIVE in either gap (`ntoskrnl/ke/apc.c:422–429`). If that APC requests firmware reset, `NxkShutdownAbortPowerRequest` recognizes the thread as the owner and raises the private exception even though its matching boundary is absent. The direct nested-callback guest does not exercise those gaps.

Reproduction: queue a normal kernel APC whose routine requests firmware reset while the drain thread is at its dequeue spinlock; deliver it on the spinlock's lowering to PASSIVE before the callback PSEH frame is installed. A targeted host transition hook can detect owner publication without a handler, and a guest normal-APC probe can validate native behavior. Fix the complete owner/frame lifecycle; normal APC suppression through the non-returning outer power action is one possible policy, while special APCs must remain available for synchronous I/O. Merely clearing ownership earlier can park the outer drain thread indefinitely when a queued normal APC runs there.

This edge was sent to the original implementer. R1, R2, R3, and R5 remain resolved. The ordinary direct R4 case is fixed and has guest red/green evidence; final signoff remains pending the owner/boundary transition correction.

## Final guard review and signoff: `f67f2b1d21f249e1dec8efa652f8747551fae844`

The committed final diff matches the reviewed working guard. This reviewer confirmed HEAD and a clean working tree, inspected the committed production/test delta, and ran `git diff --check` for the final guard range successfully. The permitted `host-apc-after.log` records persistence 18/18, shutdown 9/9, IDE 24/24, HAL 24/24, and physical pins 13/13: 88/88 total. The permitted build log reaches flash assembly with a clean init-reference audit; the implementation report records successful DBG=1 and DBG=0 builds. Passed expensive guest checks were not repeated by this reviewer.

The ordinary HAL enters a native critical region **before** claiming the power action with CAS. A nested loser leaves only its own newly entered depth before owner unwind or other-thread parking. The winning outer thread retains its depth across the entire callback drain, persistence publication, interrupt disable, and non-returning hardware action. It never reenables a queued normal APC between handler removal and reset. Reset discards that thread and its retained guard; no returning caller inherits an unbalanced critical region.

The drain additionally has a balanced critical-region wrapper protected by PSEH finally, including direct-drain return and propagated exceptions. Callback finally clears ownership on both normal and exceptional exits. Normal APC suppression covers owner publication, spinlock lowering, handler installation/removal, and cleanup. Native `KiDeliverApc` still permits special APCs while `KernelApcDisable` is set; the critical-region primitive does not set `SpecialApcDisable`. Native final I/O completion uses a special APC with no normal routine, so this policy preserves synchronous I/O completion. Callbacks must not wait for normal kernel APC delivery during shutdown, and must not undo guards they do not own.

Focused host scheduling hooks examine CAS, spinlock release, PSEH entry/exit, persistence publication, and hardware action. They verify suppression at every relevant boundary, one retained outer depth through reset, a balanced losing-thread depth, no added emergency depth, and balanced direct-drain/propagated-exception cleanup. These are source-level scheduler/SEH models. The prior 5/5 real warm probe establishes native owner unwind through the unchanged public non-returning call, but predates this final small guard; the final independently patched image still needs its requested direct guest validation.

R4 is now resolved under the explicit shutdown policy: direct owner callback reset unwinds rather than returning; other ordinary threads park; emergency non-PASSIVE/IF-disabled reset skips callbacks and invalidates the handoff without normal locks. The remaining callbacks execute before the winning ordinary hardware action. Owner storage must remain alive until callback return or supported unwind cleanup completes. Ordinary resource cleanup must precede the non-returning call or use supported SEH finally.

**All five initial findings are resolved, and final source review is approved for reproducible patch integration.** This is not approval to omit final build/runtime checks or a claim of publication, gameplay compatibility, attached debugger validation, live PnP teardown stress, cancel-routine race coverage, or measured I/O performance. The limits described earlier remain: conservative pin overflow retains affected pages until reboot; persistence restores maximal runs and cannot authenticate every cold-reset replay; WC buffer aliases remain unsupported; IDE public queue/retry/default-callback behavior is bounded; attached KDBG input is unverified. No proprietary inputs or implementation/publication actions were used in this review.
