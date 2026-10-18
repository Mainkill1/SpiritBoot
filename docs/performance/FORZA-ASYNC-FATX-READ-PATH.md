# Forza asynchronous FATX read path

## Scope and provenance

This note maps the release64 source selected through Roswell patches 0180 and
0181 in PR 253. Patch 0180 introduced the bounded one-command route; transaction
review rejected it because its direct requests were not fully joined to the
generic quarantine and cancellation lifetime. Patch 0181 is the corrected
port. Source locations below are the upstream paths and line numbers in its
assembled tree. The original selected-0168 route remains the fallback.

The comparison boundary is strict behavior-only separation. No Complex,
ClassPnP, Disk, or nxcdrom implementation body was inspected. The work uses
public I/O contracts, SpiritBoot's GPL source, retained release-build
measurements, and black-box behavior/timing observations. Complex's internal
design is unknown and is not inferred here.

Statements are labeled as:

- **Measured:** recorded by the release-build Forza fixture.
- **Static:** counted from the current assembled source.
- **Inferred:** a performance hypothesis that still needs profiling or an
  isolated experiment.

## Measured localization

The corrected fixture ran 16 passes of 1,024 operations at queue depth 12
under 900 pages of pressure. Both candidate runs completed all operations.

| Phase | Known-good mean | Current mean | Change |
| --- | ---: | ---: | ---: |
| APC/caller batch | 39,841,266.5 ticks | 52,008,164.75 | **+30.54%** |
| Submission sum | 32,199,408.5 | 44,373,524.5 | **+37.81%** |
| Return-to-APC sum | 233,102,986.75 | 200,142,559.5 | **-14.14%** |

The current runs differed by 0.77% in total batch time. This is a repeatable
submission-side regression; the measurements do not assign it to one function.
The complete inputs and run records are in
`docs/performance/evidence/forza-map-stream-corrected-20261015/summary.json`.

## Current function path

### Title and I/O manager

1. `NtReadFile` in `ntoskrnl/io/iomgr/iofunc.c:2804` references the file
   object, allocates the parent IRP and direct-I/O MDL, locks pages, and records
   the title's event, IOSB, thread, and APC.
2. `IopPerformSynchronousRequest` at `iofunc.c:119` links the IRP to the
   issuing thread.
3. `IofCallDriver` in `ntoskrnl/io/iomgr/irp.c:1291` calls FATX.

### FATX fast path

4. `VfatBuildRequest` and `VfatAllocateIrpContext` in
   `drivers/filesystems/vfatfs/misc.c:241,278` allocate and clear one lookaside
   context.
5. `VfatDispatchRequest` at `misc.c:116` calls `VfatRead`.
6. `VfatRead` in `rw.c:1028` attempts `VfatTryAsyncRead` for an asynchronous,
   noncached file read.
7. `VfatTryAsyncRead` at `rw.c:936` acquires `MainResource` nonblocking and
   validates cleanup, bounds, alignment, cache state, and stack space.
8. `VfatPrepareSeekCache`, `VfatLookupSeekCheckpoint`, and
   `VfatRememberSeekCheckpoint` at `rw.c:134,169,193` manage a 16-entry
   per-FCB seek cache under `LastMutex`.
9. `VfatTryMapRead` in `fat.c:1713` walks no more than 8,192 FAT links in
   batches of 256. Each batch acquires `FatResource`; each resident FAT cache
   chunk is mapped and unpinned. The complete data range must be physically
   contiguous.
10. `VfatLockUserBuffer` normally finds the MDL already present.
11. FATX copies the stack, installs `VfatAsyncReadComplete`, tags the parent
    IRP as the `MainResource` owner, and calls nxstorage with the same IRP.

### FATX fallback

If metadata is cold, the range is fragmented or over budget, or a resource is
busy, `VfatQueueRequest` (`misc.c:401`) posts the context. `VfatDoRequest`
(`misc.c:349`) re-enters `VfatRead` with `CANWAIT`, then:

1. `VfatCommonRead` in `rw.c:726`.
2. `VfatReadFileData` in `rw.c:236`.
3. `OffsetToCluster` / `WalkFatChain`.
4. `GetContiguousClusterRun` in `fat.c:1016`.
5. `VfatReadDiskPartial` in `blockdev.c:155`, which allocates one child IRP
   and partial MDL for every physical extent.
6. `VfatReadWritePartialCompletion` in `blockdev.c:22`, which frees each
   child and signals the shared completion event.

The worker waits for all extent children. The queue comment says no more than
two workers, but `PostedRequestCount > 2` permits three before later requests
enter the serial overflow list.

### nxstorage submission

12. `NxNativeDispatchReadWrite` reaches `NxNativeAdapterSubmit` in
    `drivers/storage/class/nxstorage/native_adapter.c`. The adapter consumes
    and clears FATX's private one-hop marker while reserving the same retained
    envelope and installing the same synchronized cancel routine used by the
    general route.
13. `nx_plan_single_read` in `request.c` shares the generic validator and
    command planner. The direct route is admitted only if the complete request
    fits one READ(10) under every MDL-page, adapter-byte, ATA-block and command
    limit.
14. An admitted direct read prepares the retained child packet and calls the
    ATA stack from its FIFO admission owner. It retains submit-active completion
    deferral, exact byte/status publication, queue-frozen recovery, shared
    quarantine, cancellation and removal rundown. A quarantine transition is
    published outside the core lock, cancels live direct peers outside the
    adapter lock, and prevents a prepared packet from committing afterward.
    Cancellation holds the child's external-operation lease through
    `IoCancelIrp`, including inline completion. The route does not allocate a
    core slot or run the generic pump/retire/complete work.
15. Every unmarked or multi-command request follows selected-0168: `nx_start`
    reserves a core slot, and `pump` performs generic admission, command,
    retirement and completion bookkeeping. This includes dynamic and split
    reads, writes, flushes, controls, optical I/O and non-FATX reads.
16. Both routes call `nx_packet_prepare` in `native_packet.c`, which
    reinitializes the retained child IRP, SRB, sense buffer and next stack
    location, copies the CDB, and creates a completion ticket before calling
    the ATA stack.

The adapter retains 16 slots, envelopes, child IRPs, and control MDLs. Current
build accounting is approximately 39,360 bytes. No pool allocation occurs in
nxstorage for an ordinary read.

### ATA start

20. `AtaDispatchScsi` and `AtaPdoDispatchScsi` in
    `drivers/storage/ide/atapi/scsi.c:1842,1690`.
21. `AtaReqStartSrb`, `AtaReqStartRequest`, and `AtaReqTranslateRequest` at
    `scsi.c:1373,1033,980`.
22. `AtaReqExecuteScsiAta` and `AtaReqScsiReadWrite` in
    `satl.c:1935,569` translate READ10.
23. `AtaReqDispatchRequest`, `AtaReqAllocateSlot`, and `AtaReqSendRequest` at
    `scsi.c:921,842,659`. PATA permits one active hardware command; later
    requests enter the ATA device/port queues.
24. DMA `GetScatterGatherList` calls `AtaReqPreparePrdTable` at `scsi.c:569`.
25. `AtaReqStartIo` at `scsi.c:509` takes the interrupt lock.
26. `NxkIdeStartRequest` in `ntoskrnl/xb/ide.c:168` calls `PataStartIo`.
27. `PataStartIo` in `pciidex/chipset/pata_io.c:909` selects the device,
    polls busy state, programs DMA/taskfile registers, and issues the command.

### Interrupt, DPC, completion, and APC

28. `NxkIdeIsr` (`ntoskrnl/xb/ide.c:97`) enters
    `PciIdeChannelIsr` (`pata_io.c:1072`).
29. `PataProcessRequest` and `PataCompleteCommand` at `pata_io.c:733,168`
    stop DMA and report completion.
30. `AtaPortOnRequestComplete` in `atapi/portstate.c:232` schedules the
    shared completion DPC.
31. `AtaReqCompletionDpc`, `NxkIdeFinishRequest`, and
    `AtaReqCompleteRequest` at `scsi.c:789`, `ntoskrnl/xb/ide.c:186`, and
    `scsi.c:262` release DMA/queue state and start the next PATA request.
32. Child `IofCompleteRequest` calls `NxNativeAdapterChildComplete`
    (`native_adapter.c:624`) and `nx_packet_capture`.
33. The generic route calls `nx_lower_done`; `pump` performs separate RETIRE
    and COMPLETE passes through `port_retire`, `record_result`,
    `port_complete`, and `finish_parent`. The corrected direct route instead checks
    the captured lower result, performs bounded RELEASE QUEUE recovery if
    required, and completes the same parent envelope directly.
34. Parent `IofCompleteRequest` invokes `VfatAsyncReadComplete`
    (`vfatfs/rw.c:916`), which releases the tagged `MainResource`.
35. `IofCompleteRequest` (`iomgr/irp.c:1345`) unlocks the MDL and queues
    `IopCompleteRequest` (`irp.c:241`) as a kernel APC.
36. `IopCompleteRequest` publishes the IOSB/event, unlinks the IRP, and
    queues the title's user APC.
37. `KiDeliverUserApcs` (`ntoskrnl/ke/apc.c:528`) reaches
    `NtUserIoApcDispatcher` (`ntoskrnl/xb/xbe.c:1235`) on the issuing thread.

## Static cost of one warm contiguous 4 KiB read

This count assumes ordinary pending completion, no cancellation or error, and
an idle nx pump.

| Layer | Static work |
| --- | --- |
| I/O manager/FATX | Parent IRP, MDL, and VFAT context allocations |
| FATX locks | One retained `MainResource`; three `LastMutex` pairs; one `FatResource` pair per 256 FAT links |
| FATX scans | 16 seek checkpoints; one entry per FAT link; map/unpin per FAT cache chunk |
| nx direct submit | Retained-envelope FIFO/cancel synchronization, command validation/planning, and packet preparation; no core-slot or pump scan |
| nx direct completion | Submit-active deferral, exact result validation, optional RELEASE QUEUE recovery, and retained-envelope completion |
| nx generic fallback | Selected-0168 core-slot, pump, retire and completion scans remain for every request outside the bounded direct-read contract |
| nx writes | Direct route clears one command and resets the retained child packet; generic route also clears its core slot/command state |
| ATA | Device, port, and interrupt critical sections; queue insertion; scatter/gather and PRD construction |
| Completion | Child and parent unwinds, one kernel APC and one title APC |

Actual counts vary with cursor position, concurrency, inline completion, error,
recovery, and cancellation.

**Inferred hot operations:** repeated nx locking/scanning and reusable-state
clears are credible submission costs; ATA status polling and port accesses are
expensive emulator boundaries; cold FAT mappings trigger the much heavier
worker path. Required ATA and APC operations must not be removed on this
inference alone.

## Ranked rework

1. **Unify nx envelope and slot ownership.** Use one retained context and an
   O(1) free bitmap/list. This removes one allocation scan and duplicated
   lifetime state while retaining 16 accepted parents.
2. **Direct one-command read state path: corrected in 0181.** A FATX-qualified
   request now uses the retained envelope and lower packet directly. PATA's
   existing queue remains the physical depth-one scheduler, and the generic
   pump remains responsible for writes, flushes, barriers, dynamic/split I/O,
   optical traffic and controls. The direct and generic routes share one
   adapter quarantine boundary.
3. **Use explicit initialization/templates.** Initialize fixed READ10 SRB and
   stack fields once, overwrite all mutable lower-visible fields on reuse, and
   avoid full slot/IRP/sense/result clears where poison tests prove safety.
4. **Cache validated FATX extents per FCB.** Retain a sequential last-hit
   cursor and a bounded set of coalesced extents. Extend it only from validated
   resident FAT metadata and fall back on every miss.
5. **Repair and pool the fallback.** Make the worker bound match its policy,
   retain cache-manager progress, and pool per-extent IRPs/MDLs.
6. **Specialize the common PRD shape.** Only after the upper changes, test a
   one/few-page builder that preserves DMA mapping, cache flushing, and 64 KiB
   split rules.

## Correctness invariants

- Accept at least QD12 without resource failure; retain 16 disk contexts.
- Complete each parent exactly once with exact status and byte count.
- Keep MDLs/pages live until lower ownership ends.
- Do not reuse a context while dispatch, cancel, lower completion, or parent
  completion can reference it.
- Preserve generation/token rejection of stale callbacks.
- Synchronize cancel routine install/removal and drain committed lower work.
- Support inline completion, queue-frozen recovery, and quarantine.
- Hold the FATX `MainResource` through lower completion and release it once.
- Use the fast FATX route only for a fully resident, valid, contiguous range.
- Invalidate cached extents on every allocation-chain mutation.
- Preserve EOF, valid-data, cleanup, alignment, paging, and cache-coherency
  behavior.
- Preserve PATA's one active command, remove locks, DMA maintenance, status
  checks, interrupt acknowledgement, DPC ordering, and next-request start.
- Deliver the user APC on the originating thread under alertable-wait rules.
- A read optimization must not change write-through, flush, recovery, optical,
  control, or durability behavior.

## Test plan

### Partial initialization and templates

1. Poison every reusable slot, IRP, SRB, sense area, and stack location before
   prepare; a fake lower driver must observe exactly initialized fields.
2. Compare lower-visible packet fields with the existing fully reset path.
3. Cover pending and inline success, short transfer, failure, autosense,
   frozen queue, malformed completion, and all cancellation race points.
4. Reuse the same context across randomized offsets, lengths, status results,
   and completion timing.
5. Run QD1 and QD12 guest tests with alignment/page boundaries and cancellation.
6. Require two interleaved release-build Forza runs with no correctness loss
   and no submission regression.

### FATX extent cache

1. Generate contiguous, multi-extent, fragmented, and over-8,192-cluster FATX
   files and compare every result with an independent FAT-chain oracle.
2. Test reads within and across extent boundaries with hot and cold metadata.
3. Exercise extend, truncate, delete/recreate, and chain-changing writes while
   readers are active; stale mappings must never be used.
4. Inject cache allocation and `CcMapData` failure and verify ordinary fallback.
5. Bound per-FCB memory and test eviction/rebuild.
6. Record fast-hit reason, fallback reason, FAT links walked, FAT cache chunks,
   and extent-cache hits in a release-build QD12 pressure run.
7. Finish with human-driven Forza streaming beyond the initial load region.

## Patch 0181 outcome

Patch 0180 was rejected after review reproduced four quarantine/cancellation
lifetime failures. Patch 0181 corrects those contracts. Its exact release64
image has SHA-256
`6bcee57b071f1fbae103b25ec66e33093dd8c78597f7d050d787ee45f0c23323`.

In a fresh-process selected-0168/candidate/selected-0168/candidate sequence,
the candidate's two-run mean submission cost improved in all eight
memory/budget cells by 0.57–9.13%. The 250 us verified-read rate improved by
6.01–11.72%. Saturated rates varied slightly, and one request-size result was
composition-sensitive; the evidence reports it rather than claiming a device
bandwidth increase.

Two alternating Forza control/candidate pairs completed the automated race
route with intact retained screenshots. Both candidates first showed the grid
one one-second sample before their controls, which is descriptive rather than
a general streaming claim. Three independent PGR2 candidate runs completed the
race route at 30 FPS with p99 frame intervals below 35 ms; the reported early
crash was not reproduced in those clean processes. Exact builds, raw synthetic
serial, measurements, title run IDs, exclusions and limitations are in
[`forza-direct-native-read-20261018`](evidence/forza-direct-native-read-20261018/README.md).
