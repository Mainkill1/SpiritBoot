# Platform boundary

`request.c` is the production transport/lifetime core. Host tests compile this
file directly. A kernel adapter must also compile this same file, then connect
the following obligations to the target's public IRP, MDL and legacy SRB APIs.
There is no current kernel adapter or full storage driver in this deliverable.

Initialize configuration from measured capacity and negotiated lower adapter
limits. Sector/page sizes must be powers of two, page size must cover a sector,
and the contiguous alignment mask must be smaller than a sector. This bounded
slice supports READ/WRITE(10) only. `ata_max_blocks` is an explicit lower-device
limit; the tests' 256-block value is a fixture policy, not hardware discovery.
Cache capability is supplied by the platform: ENABLED means verified support
for real cache synchronization, DISABLED means independently established absence
of volatile caching, and UNQUALIFIED covers unknown or unsupported durability.
Do not infer this state from a successful SRB_FUNCTION_FLUSH or write FUA.
Device initialization also caches the validated sector shift/mask. The port
must not mutate configuration or those cached values during the device lifetime.
The final nx_device_init argument is the actual slot-storage byte capacity.
The core checks count against capacity/sizeof(slot) before clearing storage;
callers must provide the real allocation size. This guards multiplication on
32-bit targets without adding work to request submission.

The fixed `nx_slot` array, `nx_device`, port context and adapter transport storage
must remain resident until every whole core call, callback and pump returns,
with externally fenced admission/callback sources. Parent completion alone is
insufficient. The
platform may use independent slot arrays for independent devices. The core has
no heap, clock, worker or bounce-copy dependency. Healthy one-command data uses
one prepare, one submission, one retirement, and one parent completion. Reserve
child/SRB/sense/MDL storage at device setup to keep prepare allocation-free on
that path and to make queue recovery independent of pool availability.

| Object | Owner and endpoint |
| --- | --- |
| Parent IRP, original MDL and caller buffer | Borrowed from I/O manager/upper request until parent terminal delivery; never freed by core |
| Upper FATX lease and file/device references | Borrowed opaque pointer; upper ownership must pin the request until lower terminal completion |
| Device and core slot storage | Device owner; external admission seal plus whole-call/callback rundown fence before freeing |
| Child IRP, SRB, partial MDL and resident sense | Adapter owns prepared resources; core schedules exactly one retire after lower terminal report and submit return |
| Prepare failure's partial allocations/mappings | Adapter unwinds before returning failure; core calls no retire for failed prepare |
| Lower DMA, internal requeue and autosense use | Lower owns active child until the one terminal report; internal requeue is not a terminal report |
| Command/token pointer | Slot-resident during transport; copy token by value before calling nx_lower_done; old tokens may safely be ignored while device stays resident |

`enter`/`leave` protect short state changes against dispatch, lower completion
and cancellation. A kernel implementation needs an appropriate resident spin
lock and IRQL handling. Original host fixtures use deterministic single-thread
scheduling; the additional ownership fixtures use real pthread mutexes and
cross-thread calls. Neither provides a native IRQL guarantee. `mark_pending`
is the sole callback invoked under this lock. It must
be a nonblocking, nonreentrant leaf that marks the parent exactly once and does
not complete it. All other port callbacks run outside the lock and can reenter
the core. A pending submission return, an unresolved child, a flush barrier, or
admission while the pump is already active produces NX_PENDING dispatch.

`prepare` creates or resets the child. Supply the same child IRP in SRB's
OriginalRequest and the child's stack Scsi.Srb. Set DataBuffer to `data_virtual`,
which is a subrange of the original MDL virtual domain, and supply the original
or valid partial MDL to that child. A mapped system address is not a replacement
for this domain. Set the byte count, directions, CDB length and bytes shown in
the command. Initialize all SRB fields and SrbExtension correctly; supply an
owned resident sense buffer if autosense is used. For RELEASE_QUEUE use its
function value and no CDB/data, independent of memory pressure.

`submit` calls lower transport once and returns whether lower returned pending.
It must eventually report exactly one terminal outcome with `nx_lower_done`,
including inline errors. Report actual child IoStatus.Information, not SRB's
input DataTransferLength. Separate QUEUE_FROZEN from the base SRB status. The
core passes negative adapter status values through, permitting distinct timeout,
device absence, admission rejection and resource-error mappings. Adapter error
values must be negative and disjoint from the core's -1 through -9 statuses.
Terminal positive statuses are protocol errors. The core never retries data.

`nx_lower_done` can run the pump and retire an allocated child inside the OS
completion callback. That callback must copy the token/results first, call the
core, then return STATUS_MORE_PROCESSING_REQUIRED if child ownership was taken
by the adapter. It must not access a freed child or a command reused by the
pump after calling the core. The submitting stack frame ends command access
when it returns. An asynchronous transport may retain the descriptor until its
terminal callback, which must copy its token/results before calling the core.
Resource retirement is deferred until submit returns for inline results.

Submission commit is the locked inflight/prepared assignment after prepare and
the last precommit cancellation check. Cancellation accepted earlier retires
prepared resources without submitting. After commit it can race with the
unlocked port.submit call: the command may reach lower before the one cancel
request, and verified hardware-written bytes can remain. The core waits for
submit return before issuing cancellation if lower is still nonterminal. An
already-terminal inline child requires no later lower cancel. It waits for the terminal report
before retirement/parent completion. Cancellation does not undo hardware writes.
`cancel` asks lower to end child use; it does not authorize resource release.
Report ownership release only when DMA/recovery ownership actually end.
Platform cancel-routine removal, IoCancelIrp and parent cancel synchronization
remain adapter responsibilities. Queue release may follow a frozen cancellation.

`retire` frees/releases the prepared child resources exactly once. `complete`
sets parent status/information, applies correct completion priority, event,
IOSB and APC behavior, and delivers the parent once. Completion may free the
parent immediately; the core stores no live parent pointer after delivery.

There is no core teardown/quiescence API in this slice. The adapter must seal
admission atomically against new dispatch and hold device rundown references
around each entire nx_start/nx_lower_done/nx_cancel call, including port callbacks
and the pump that call may run. Outstanding admitted parents/transport callbacks
must also keep the device resident across pending intervals after entry returns.
These request/transport references and all whole-call references must drain.
Zero active slots is not sufficient: the core
clears active before port.complete, then continues scanning/locking device state.
The adapter must drain these calls and fence transport callback registration,
cancel/removal sources and any external holders before freeing device/slot
storage. This includes already-entered callbacks that report duplicate tokens.
Tokens defend stale reports only while the device remains resident; no guarantee
is made for a callback using a device or token resource after its lifetime ends.
Pthread tests model this external reference discipline, but no production kernel
adapter or native rundown guarantee is implemented/qualified.

If queue release fails, the core quarantines this device: waiting parents fail
without submission, new admissions fail, and live data/cache-sync commands get
one lower cancellation request. Their memory remains live until terminal lower
reports. Such internal cancellation returns IO_ERROR; caller cancellation still
returns CANCELLED. Recovery does not repeatedly retry release or uncertain writes.

If an adapter omits its terminal callback, the core keeps ownership and pending
state even when submit returned nonpending. There is no safe fabricated
completion or automatic timeout in this slice. A conforming adapter/lower
device must provide terminal cancellation/removal to drain teardown; bounded
termination under a broken callback contract is not claimed.

No online optical controls, sense policy, PnP/namespace, partition controls,
media discovery, geometry IOCTLs, shutdown dispatch, or NTSTATUS adapter is
implemented. NX_FLUSH is the reusable engine operation for future flush and
shutdown dispatch; its commands are real cache synchronization commands.

`nx_request.flags` accepts zero or NX_WRITE_THROUGH. Write-through is valid only
for NX_WRITE; unknown bits or use on READ/FLUSH fail INVALID without transport.
The kernel adapter will map the applicable FILE_WRITE_THROUGH, FO_WRITE_THROUGH
and SL_WRITE_THROUGH indications into this intent. No numeric Windows flag
value is guessed, and that actual adapter mapping remains a separate gate.

For nonempty write-through the same parent, slot and lease remain active through
all data chunks and one real cache-sync command after successful data. Later
writes wait from its admission until parent termination. Earlier ordinary writes
may run concurrently with its data, but must reach terminal completion before
its sync. Reads continue when transport/slot capacity is available. Enabled
cache requires real SYNCHRONIZE CACHE(10); independently established disabled
cache skips the hardware command while preserving the barrier. UNQUALIFIED
cache rejects write-through before any data, including zero-byte requests.
Zero bytes with qualified cache complete without data or sync commands.

Sync failure or preparation failure reports its error and the verified written
data byte count. Short/error data stops the chain without retries, extra writes
or sync; no success/durability claim follows. Cancellation between phases
prevents sync only if accepted before its commit; after sync commit the command
may still be submitted, receives one cancel request after submit returns if
still nonterminal, and
waits for terminal lower completion before resource retirement and parent
delivery. Both return CANCELLED with actual data bytes. A sync command transfers
no data and cannot increase the parent's byte count. Ordinary NX_WRITE still
does not promise durability. Error Information is an explicit candidate policy;
historical write-through failure Information/parity is not claimed.

## Valid descriptor with zero original domain

For nonempty data, initialize `nx_request.mdl_present` to exactly 1 only after
validating the actual non-null descriptor, its locked-page/PFN coverage and
lifetime. The numeric original domain `mdl_virtual` may be zero; it does not
prove descriptor absence. Preserve the original domain and actual descriptor
through transport. Zero-initialized callers without this evidence fail closed.
The core still validates extent, overflow and alignment; native PFN/DMA/PIO
qualification remains required. See [fix evidence](../zero-domain-mdl/FIX.md).
