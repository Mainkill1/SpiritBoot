# Clean-room kernel compatibility design

The user requests explanations and independent implementation of the missing
kernel behavior identified during a community-firmware comparison. The goal is
working Xbox kernel contracts on xemu, with Conker: Live & Reloaded remaining the
eventual gameplay target. No game image has been supplied. The user authorizes
execution without further approval and selects direct XISO execution, not the
HTTP test runner.

## Separation

The analyst examined a supplied firmware. The implementation agent starts with
no conversation history and receives only this behavioral specification, the
existing open-source kernel, and public nxdk declarations. It must not open the
supplied archive, extracted firmware, comparison artifacts, disassembly, or the
analyst's earlier review. This is a documented workflow separation, not an
enforced filesystem security boundary or a legal certification.

Allowed kernel tree: `/workspace/SpiritBoot-cleanroom-kernel`, based on Roswell
commit `1569e2e89fb47cc72b9c704a8884f98200432bd4`. Allowed public ABI tree:
`/workspace/SpiritBoot-public-nxdk`. Existing public kernel code and its tests
may be used and adapted under their existing licenses. All new algorithms and
private state formats must be independently designed; no machine code,
firmware-derived constants, keys, or translated disassembly may be copied.

## Required behavior

1. **Shutdown notifications.** Registration associates a callback and priority
   with caller-owned storage. Higher priorities run earlier; equal priorities
   are stable. Unregistration prevents future invocation. Duplicate registration
   must not corrupt lists. Before a kernel-initiated shutdown/reset, detach and
   invoke callbacks exactly once outside the registration lock, passing the
   registration pointer. Reentrancy and registration lifetime must be explicit.
   Cover the title export and actual firmware-return path, not just a test hook.

2. **Contiguous-memory persistence.** A valid requested subrange of a live
   contiguous allocation can be marked persistent or unmarked. Selected pages
   retain their physical addresses and contents through a warm reboot and are
   restored to allocator ownership before any competing boot allocation. Normal
   free clears the corresponding persistence state. Cold boot, malformed or
   stale handoff, overlaps with boot reservations, arithmetic overflow and
   partial allocation ranges require defined handling. An in-memory flag alone
   is insufficient. Use an independently designed handoff, with bounds and
   integrity validation, integrated with existing launch-data handoff.

3. **Page locking.** Public buffer and physical-address APIs pin valid RAM pages
   with balanced, nestable accounting. Locked movable pages cannot be relocated
   by contiguous allocation/page supply. Unlock must not underflow, overflow
   must not wrap, and invalid device addresses must not index RAM metadata.
   Physical-address arguments are byte addresses, not page numbers. Define the
   behavior of freeing a pinned allocation. Match public nxdk signatures.

4. **Scatter/gather I/O.** Preserve the public API's synchronous/asynchronous
   completion, event/APC, IOSB, EOF/short-transfer, offset, access and unbuffered
   handle contracts. Gather all valid segments into a request owned until
   completion; dispatch a single multi-page IRP per API request where supported
   by the current storage stack. Bounce buffering is an acceptable first
   implementation if its ownership, copy direction and completion are correct
   and it reduces per-page dispatch. Use request-specific completion. Concurrent
   requests on one asynchronous handle must not read or overwrite another
   request's completion state. Allocation and dispatch failure must unwind.

5. **IDE channel integration.** Publish the public nxdk IDE_CHANNEL_OBJECT ABI,
   initialize its queue/DPC/timer/interrupt and connect its mutable callbacks
   to the actual ATAPI request/completion/interrupt path. Do not allocate a
   second hardware IRQ owner alongside the active driver. Title-installed
   callbacks must observe real request lifecycle state and may chain the
   original callbacks. Existing kernel shadow adapters must be used where
   console and native object layouts differ. A populated decorative object
   with no storage connection does not satisfy the requirement. Preserve
   existing HDD/DVD operation, cancellation, error and shutdown behavior.

6. **Debugger prompt.** Replace the fatal DbgPrompt export with bounded prompt
   input behavior backed by the existing debug transport. With no debugger
   attached, return an empty response promptly rather than waiting forever or
   crashing. Respect a zero-length output buffer and public character-count
   semantics. No changes to the remaining debugger exports absent from the
   reference behavior are required by this task.

Public-key/key blobs are data/provenance decisions, not algorithms to invent.
Do not introduce proprietary keys or pretend a new key matches existing Xbox
signatures. Cache read-ahead is outside this change: it was not a confirmed
feature difference in the requested comparison.

## Deliverables and verification

Kernel code belongs in focused existing modules or small new modules, retaining
GPL notices and recording allowed references. Add meaningful guest regressions
for changed behavior, including asynchronous concurrent scatter/gather, page
locking under relocation pressure, shutdown ordering/removal and a separate
warm-reboot persistence probe. Verify ABI sizes with compile-time checks.
Keep failure evidence and report any unverified behavior explicitly.

SpiritBoot retains the pristine upstream revision and ships a checked, hashed
source patch series. Builds apply those patches to an isolated source copy,
record their hashes in provenance, and leave the baseline checkout unchanged.
The published v0.1.0 baseline remains available unchanged. New images may be
published only after fresh build and direct XISO validation; never claim Conker
gameplay or a measured performance gain without the corresponding evidence.
