# Forza asynchronous FATX read path

## Scope and provenance

This note maps the current PR 248 release64 source assembled through Roswell
patch 0146. Source locations below are the upstream paths and line numbers in
that assembled tree.

The comparison boundary is strict behavior-only separation. No prior
known-good ClassPnP, Disk, or nxcdrom implementation body was inspected.
Comparisons use only retained release-build measurements, public I/O
contracts, and existing original-prose notes. The known-good implementation's
internal design is unknown and is not inferred here.

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

12. `NxNativeDispatchReadWrite` in
    `drivers/storage/class/nxstorage/native_adapter.c:882`.
13. `NxNativeAdapterSubmit` at `native_adapter.c:763` locks the adapter,
    linearly searches 16 envelopes, installs the cancel routine, and clears a
    local `nx_request`.
14. `nx_start` in `request.c:268` independently searches 16 core slots,
    clears the entire selected slot, and copies the request.
15. `pump` at `request.c:180` obtains pump ownership and circularly scans as
    many as 16 slots.
16. `build_command` creates one READ10 for a 4 KiB fixture request.
17. `port_prepare` at `native_adapter.c:253` calls `nx_packet_prepare`.
18. `nx_packet_prepare` in `native_packet.c:46` reinitializes the retained
    child IRP, clears its SRB, 32-byte sense buffer and next stack location,
    copies the CDB, and creates a completion ticket.
19. `port_submit` at `native_adapter.c:313` calls the ATA stack.

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
33. `report_result` calls `nx_lower_done`; `pump` performs separate RETIRE
    and COMPLETE passes through `port_retire`, `record_result`,
    `port_complete`, and `finish_parent`.
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
| nx submit | At least 13 adapter spinlock pairs and one cancel-spin pair |
| nx submit scans | Up to 64 inspections across four 16-entry scans |
| nx completion | At least nine adapter spinlock pairs and one cancel-spin pair |
| nx completion scans | Up to 48 inspections across RETIRE, COMPLETE, and no-work passes |
| nx writes | 256-byte slot clear; retained child IRP reset; SRB, sense, stack and result clears; request/CDB/ticket copies |
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
2. **Add a direct one-command read state path.** Transition an aligned READ10
   through `FREE -> PREPARING -> LOWER_OWNED -> RETIRING -> COMPLETING ->
   FREE`. Submit accepted reads to ATA and leave PATA's existing queue as the
   only physical depth-one scheduler. Keep the generic pump for writes, flush,
   barriers, and recovery until separately proven.
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
