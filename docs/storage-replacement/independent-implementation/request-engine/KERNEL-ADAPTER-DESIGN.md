# Kernel adapter requirements and design gate

Design only, 2026-10-14, independently authored by
`/root/pr248_independent_engine`. No adapter code is implemented or authorized by
this note. Implementation remains gated on root's frozen native P1 pilot,
reviewed declaration exports, and the unresolved ownership facts below.
The current production core and its 50 host scenarios remain unchanged.

## Decisions that must be settled before implementation

| Gate | Required fact or evidence |
| --- | --- |
| Child reuse | Target I/O-manager behavior when a driver-owned IRP is taken back with STATUS_MORE_PROCESSING_REQUIRED; whether IoReuseIrp and another lower submission may occur before the old completion callback unwinds |
| Lower terminal ownership | For every inline, queued, DPC, autosense, retry, cancel and queue-release path: all IRP/SRB/sense/MDL accesses that can occur after invoking terminal IoCompleteRequest; do not equate a terminal callback with proof that a retained lower stack frame has stopped using these objects |
| Cancel synchronization | Actual target cancel-routine installation/removal, cancel-spin-lock, atomic-exchange, child IoCancelIrp and terminal-completion contracts |
| Cache qualification | An actual supported target query for enabled/disabled volatile cache and selected hardware flush capability; successful SRB_FUNCTION_FLUSH or FUA is insufficient |
| Buffer/lease contract | Single MDL versus MDL chains, source virtual-address domain, locked-page lifetime, upper lease release point, and true lower alignment versus DMA-only alignment with PIO fallback |
| Runtime residency | Public declarations and behavior of device/lower references, admission sealing and callback-source rundown; active-slot count alone cannot authorize freeing |
| Pilot identity | Exact frozen native P1 composition, firmware/build identity, device/media inputs, observed IOSB/event/APC/control outcomes and performance baseline |

These gates request behavior/type facts, not excluded implementation bodies.
Root is separately investigating compatible kernel/lower behavior. This author
will not infer those facts from classpnp/disk/nxcdrom, private helper headers,
old patches, disassembly, or the full product source tree.

## Fixed resources and the unchanged engine boundary

Compile the exact independently authored `request.c` in both kernel and host
builds. Adapter dispatch converts one upper parent into `nx_request`; the engine
owns validation, segments, write/flush ordering, command generations and terminal
accounting. The adapter owns OS objects, cancellation registration, public
status/control semantics and all device/parent/callback lifetime fences.

Use device-owned nonpaged storage allocated during AddDevice/Start: engine slots,
parent envelopes, transport records, child IRPs, legacy SRBs, sense buffers and
partial-MDL storage. Supply actual slot byte capacity to nx_device_init. Every
boot allocation failure unwinds only objects not still borrowed by lower.
Do not add a heap allocation, worker dispatch, bounce copy, capability command,
or clock sample to a healthy one-SRB read/write.

Provision at least twelve independent data admissions per device, plus explicit
bounded control/recovery admission capacity. The adapter must enforce its data
admission budget so data cannot consume a reserve needed by controls. The core
does not designate particular slot indices as control reserves. Queue release
reuses the failed parent's already reserved transport resources. HDD and DVD
use independent device contexts while retaining their shared controller's lower
queue behavior; no controller-wide class serialization is proposed. Excess
admission fails with an explicit bounded resource status.

| Resource | Owner and release/reuse condition |
| --- | --- |
| Upper parent IRP | Borrowed I/O-manager request; adapter completes once and never frees/reuses it |
| Original parent MDL/pages and upper lease | Borrowed until all lower use ends and upper parent delivery is safe; no class unlock/free or lease revocation |
| Resident parent envelope | Adapter pool; holds parent pointer, copied intent, cancellation state, engine handle and references; persists through dispatch, cancellation and completion frames, even if the parent IRP is reclaimed inline |
| Device/lower references | Device owner plus outstanding-parent/transport and whole-call/callback references; released only after sealed admission and drained/fenced sources |
| Child IRP | Adapter-created at setup with sufficient lower stack depth; recycled only under a verified completion-stop/reuse contract; freed once at final device teardown |
| SRB/sense/partial MDL | Transport record; remains valid through queuing, recovery, DMA/PIO and terminal callback ownership; recycled only when no old lower path may access it |
| Adapter-created partial-MDL mapping | Adapter; release owned mapping before rebuilding/freeing that partial MDL; never unmap the original parent's shared mapping |
| Callback token/results | Copied by value before calling the core; no mutable old child/record access afterward |

IoAllocateIrp creates an unthreaded driver-owned IRP with nonpaged backing and
sufficient lower stack locations. IoReuseIrp applies to appropriately
driver-created IRPs, not an incoming parent. Those published facts establish a
possible resource family, not the target's reuse timing. [IoAllocateIrp](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/nf-wdm-ioallocateirp),
[IoReuseIrp](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/nf-wdm-ioreuseirp),
[Reusing IRPs](https://learn.microsoft.com/en-us/windows-hardware/drivers/kernel/reusing-irps).

Preferred resource policy is a fixed child/SRB/sense/MDL bank per engine slot,
conditional on the first two gates. A terminal callback must copy every needed
field, commit to unconditional STATUS_MORE_PROCESSING_REQUIRED, and never touch
that child/bank after calling nx_lower_done. The core can pump many later
segments before that original callback returns. Merely adding two banks does
not prove safe reuse: another callback can be paused after publication while the
pump continues. Public callback-stop documentation supports taking ownership,
but does not certify the retained target's later SRB/sense accesses. If these
facts are not established, fixed-bank reuse stays blocked. Do not conceal that
gap with a compulsory healthy worker/DPC hop or per-segment allocation.
[IoSetCompletionRoutine](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/nf-wdm-iosetcompletionroutine).

## Preparing and completing a data command

For one segment, obtain an idle, safely reusable transport record and reset only
owned state. Register completion for success, error and cancellation. Set the
child stack to IRP_MJ_SCSI with its Scsi.Srb pointing to that record's SRB. Set
Srb.OriginalRequest to this same child IRP; assign its MdlAddress to the borrowed
source MDL or a valid adapter-owned partial MDL. Never put the parent IRP in
OriginalRequest while supplying a different child's MDL.
The healthy whole-buffer single-command path should borrow the original MDL
directly. Use reserved partial-MDL storage when an exact subrange is required
by the verified lower contract; do not add avoidable mapping or page-lock work.

DataBuffer is the engine's requested virtual subrange within the original MDL's
domain. Preserve that address relationship for the lower PIO offset calculation.
A system mapping, if separately needed, does not replace the SRB address-domain
contract. Physical fragmentation does not require copying; respect negotiated
page/byte/alignment bounds. An MDL virtual address need not be dereferenceable
in the current thread. [MmGetMdlVirtualAddress](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/nf-wdm-mmgetmdlvirtualaddress).

Partial MDLs require an already locked/nonpaged source and enough target PFN
storage for the selected range, including its starting-page offset. Reserve that
storage at setup. Prefer avoiding a new system mapping when lower can consume
the MDL directly. If an owned mapping is created, its reuse/free needs the
appropriate partial-MDL cleanup. The original MDL and its mapping stay borrowed.
[IoBuildPartialMdl](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/nf-wdm-iobuildpartialmdl),
[MmPrepareMdlForReuse](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/nf-wdm-mmpreparemdlforreuse).

Populate SRB length, function, direction, submitted byte length, CDB length/bytes,
timeout and supplied sense storage. Initialize flags/links/scratch; do not leave
an apparent private SrbExtension. Let the retained lower fill its path/target/LUN
as contracted. Preserve required paging/other public request flags only after
the investigator exports their target meaning. Do not invent a DMA restriction
that loses documented optical odd-address PIO behavior.

Completion snapshots child IoStatus.Status and actual IoStatus.Information,
SRB base status/modifiers and a bounded valid sense extent. Reject Information
greater than the submitted command before narrowing to the core's uint32 count.
DataTransferLength remains an input count unless an independently established
target rule says otherwise. Report terminal outcomes once; internal lower retry
or requeue of the same pointers is not terminal. RELEASE_QUEUE addresses error
freeze; UNLOCK_QUEUE is a different condition. Preserve the core's bounded
recovery/quarantine and never replay a write of uncertain completion.

`mark_pending` is a resident, nonblocking leaf: mark the borrowed parent using
IoMarkIrpPending, without allocations, cancellation locks, completion or
reentrant core calls. Never mark an allocated child in its completion routine.
Map NX_PENDING dispatch to STATUS_PENDING even if parent delivery happened
inline; all other dispatch results remain distinct from terminal IOSB.
[IoMarkIrpPending](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/nf-wdm-iomarkirppending).

Parent completion removes/settles cancellation registration, sets final status
and verified byte count, then calls IoCompleteRequest outside every spin lock.
The I/O manager owns event/IOSB/APC delivery; the adapter must not manufacture a
second notification or access the parent afterward. Use IO_NO_INCREMENT for
errors/quick rejection; the successful disk/CD completion boost must be supplied
as a public target constant and qualified natively. [IoCompleteRequest](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/nf-wdm-iocompleterequest),
[IRP_MJ_WRITE](https://learn.microsoft.com/en-us/windows-hardware/drivers/kernel/irp-mj-write).

## Parent cancellation, commit and rundown

Reserve a resident parent envelope before exposing it through the parent's
approved public context field. Hold a registration reference while its cancel
routine is installed, a dispatch reference through nx_start return, and the
outstanding request/transport references through terminal ownership. Completion
can reclaim the parent IRP while dispatch still runs; its envelope must remain
valid independently.

The engine's admission handle is not an automatically published cancel handle.
Pass a private dispatch-local handle to nx_start. First prepare can publish a
copy of command slot/generation into the envelope under the envelope's lock;
after nx_start returns, dispatch can publish its local handle if the envelope
is still live. Cancellation arriving before publication records intent. Prepare
observes that intent and invokes nx_cancel outside adapter locks before returning,
preventing precommit transport. A barrier-only request publishes at dispatch
return, then consumes any recorded cancellation promptly. Validate this handshake
with callbacks that complete/finalize the parent before nx_start returns.

Use explicit registration states so a NULL previous cancel routine is not
mistaken for proof that no cancellation callback can still run. In the proposed
protocol, registration/removal and the callback's ownership claim are protected
by the system cancel lock and a consistently ordered envelope lock. A claimed
callback owns a reference until its exit handoff. Release the system cancel lock
before calling the core or IoCancelIrp. No adapter lock may remain held across a
core call that can invoke adapter completion. The target must certify this
protocol's API semantics; modern Windows behavior is a public reference, not a
replacement for target facts. [IoSetCancelRoutine](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/nf-wdm-iosetcancelroutine).

The core commit point is its locked inflight/prepared assignment after prepare
and the final cancel check. Before commit, accepted cancellation prevents
submission. After commit it may race with the unlocked lower call. Cancel the
adapter-created child once if it remains nonterminal after submit returns; wait
for terminal ownership and preserve actual data bytes. IoCancelIrp's Boolean is
not a terminal completion or proof DMA stopped. An already-terminal inline child
receives no late cancel. Cancellation does not undo hardware writes or sync.
[IoCancelIrp](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/nf-wdm-iocancelirp).

Teardown atomically seals new admission, requests appropriate cancellation, and
drains outstanding parents/transport plus whole nx_start/nx_lower_done/nx_cancel
calls and their port callbacks. Fence lower callback sources and external holders
before releasing devices, banks or code. Active==0 is insufficient: port.complete
can be blocked while pumping==1, and the pump continues after callback return.
No callback using a freed device is made safe by a value generation token. The
existing pthread tests demonstrate a host reference model, not a kernel adapter.
Broken lower terminal/cancel contracts remain a qualification failure; do not
free borrowed pages by fabricating a timeout completion.

## Discovery and durability

At Start, use bounded owned control resources to obtain valid device identity,
capacity, logical sector size, lower stack size and negotiated transfer/page/
alignment limits. Validate descriptor Version/Size and actual returned bytes;
preserve lower header-only negotiation. READ CAPACITY(16) support does not permit
READ/WRITE(16). The data core currently implements READ/WRITE(10); capacity beyond
its addressable LBA range needs an explicit qualification policy, not clamping or
an unsupported CDB fallback.

The approved declarations contain StorageDeviceWriteCacheProperty and
STORAGE_WRITE_CACHE_PROPERTY, but the supplied lower contract establishes only
device/adapter/alignment property support. If a target-supported cache query is
exported, distinguish enabled, independently established disabled and unknown
states; validate every field read. FlushCacheSupported can inform the policy
only if that target response accurately describes the real cache-sync route.
Do not access a private lower extension to obtain it. [STORAGE_WRITE_CACHE_PROPERTY](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntddstor/ns-ntddstor-_storage_write_cache_property).

Enabled cache requires a genuinely supported SYNCHRONIZE CACHE route and its
eventual outcome. Disabled cache may complete the ordered barrier without a
hardware command. Unknown/enabled-without-supported-flush remains UNQUALIFIED.
The lower's success-only SRB FLUSH/SHUTDOWN and cleared FUA are not evidence of
durability. A successful SYNCHRONIZE CACHE that lower implements as a no-op
because no flush opcode was selected also cannot qualify enabled caching.
Device capability correctness and physical power-loss durability need independent
observations; no such result is claimed here.

Map applicable FILE_WRITE_THROUGH/FO_WRITE_THROUGH/SL_WRITE_THROUGH intent into
NX_WRITE_THROUGH using exported target declarations and observed propagation.
The local engine flag is not a numeric Windows flag. One parent/slot remains
through all write chunks and the real sync; later writes wait, reads can continue,
and sync waits for prior writes. The engine's candidate failure Information keeps
bounded verified data bytes on sync error/cancel. Short/failed data stops without
sync or a durable success claim. Zero-byte qualified intent issues no command;
unknown cache rejects it. This failure-byte policy does not claim historical
write API parity. [NtCreateFile](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/nf-ntifs-ntcreatefile).

## Status, sense and controls

Candidate engine-to-NTSTATUS mappings, pending native freeze:

| Engine result | Adapter candidate |
| --- | --- |
| NX_OK / NX_PENDING dispatch | STATUS_SUCCESS / STATUS_PENDING |
| NX_INVALID, NX_RANGE | STATUS_INVALID_PARAMETER |
| NX_NO_MEMORY | STATUS_INSUFFICIENT_RESOURCES |
| NX_IO_ERROR, NX_PROTOCOL_ERROR | STATUS_IO_DEVICE_ERROR |
| NX_SHORT_TRANSFER | STATUS_BUFFER_OVERFLOW with actual data count |
| NX_CANCELLED | STATUS_CANCELLED with candidate verified-data count |
| NX_WRITE_PROTECTED | STATUS_MEDIA_WRITE_PROTECTED |
| NX_DURABILITY_UNSUPPORTED | STATUS_NOT_SUPPORTED |
| Valid negative native lower status outside reserved engine values | Preserve distinct timeout/device absence/admission/resource status |

Separate SRB modifier bits from its base status. Prefer the actual child IOSB
for the lower's documented timeout, no-device, selection-timeout, allocation and
admission/removal failures. Context-specific control normalization is separate.
Do not pass positive nonterminal statuses as core terminal success. Freeze final
parent IOSB/event/APC behavior, including any I/O-manager changes to failure
Information, against the native pilot.

Sense parsing must use AUTOSENSE_VALID plus an exported actual copied extent,
allocated capacity and advertised reply length. Zero owned sense storage before
reuse. Check fixed/descriptor format and enough bytes for each field before
reading key/ASC/ASCQ; absent/truncated/malformed sense does not create a fabricated
media diagnosis. Provisional policies: no-media -> STATUS_NO_MEDIA_IN_DEVICE;
not-ready/spin-up -> STATUS_DEVICE_NOT_READY without new indefinite class retries;
data protection -> STATUS_MEDIA_WRITE_PROTECTED; unsupported/illegal command ->
STATUS_INVALID_DEVICE_REQUEST. Validated media change with mounted VPB requires
volume-verification indication and STATUS_VERIFY_REQUIRED; unmounted change
reports an explicit device error. Native baseline mappings/counts remain unknown.

Controls are a separate bounded surface: the current core has no arbitrary CDB
or control-buffer operation. A future control path must share the adapter's
ownership primitive or gain an independently tested engine extension; it cannot
be advertised as already implemented by NX_READ/NX_WRITE/NX_FLUSH.

| Required control | Design obligation from approved contract |
| --- | --- |
| HDD device number | Initialized 12 bytes, disk 0/raw partition 0 candidate; partmgr Start dependency |
| HDD geometry / length | Initialized 24-byte geometry / 8-byte exact capacity; cylinder/head/track convention needs frozen native facts |
| HDD geometry EX | Accept 32-byte base and larger output; initialized base with exact 64-bit length; optional metadata policy explicit, no Data[1] padding minimum |
| Optical geometry | Initialized 24 bytes using validated media sector size; absent-capacity policy unresolved |
| Optical READ_TOC | Require 804-byte output; format-0/LBA bounded command; short DATA_OVERRUN normalized to success only with valid actual reply bytes |
| Optical READ_TOC_EX | STATUS_NOT_IMPLEMENTED, zero bytes |
| CHECK_VERIFY | TEST UNIT READY and bounded media handling; no output/0, optional ULONG/4, short nonzero output rejected |
| STORAGE_QUERY_PROPERTY | Validated input and lower device/adapter/alignment descriptor negotiation, including header-only responses; unsupported lower queries preserved |
| Flush/shutdown | Ordered real engine cache synchronization; never success-only SRB flush |
| Unsupported request | Explicit bounded rejection with zero unwritten bytes |

Buffered control data is SystemBuffer; initialize only claimed returned bytes
and never exceed OutputBufferLength. Control failures normally return zero bytes
except a deliberately normalized/defined partial descriptor result. Property
pass-through can retain the parent's lower DEVICE_CONTROL path, but its pending/
completion/rundown rules differ from allocated child ownership and require
separate tests. Do not apply a child STATUS_MORE_PROCESSING_REQUIRED ownership
rule blindly to a forwarded I/O-manager parent.

## Boot, namespace and resident runtime

Preserve registration order and names: Pci, pciide, atapi, Disk, Cdrom, partmgr,
MountMgr, Xdvdfs, Vfatfs, with RAW initialization first. Entry callbacks use the
target's NTAPI DRIVER_INITIALIZE signature. Public entry initialization occurs
at PASSIVE_LEVEL; actual folded-kernel linkage and declarations must be exported.
[DRIVER_INITIALIZE](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/nc-wdm-driver_initialize).

Attach each FDO to its supplied lower stack; HDD Start finishes before partmgr
Start/enumeration, and optical has no partmgr attachment. Preserve stack size,
lower alignment, DO_DIRECT_IO, valid VPB, device types and optical read-only/
removable characteristics. Attachment failure unwinds owned namespace/resources.
Attachment returns the actual next-lower object and establishes stack/alignment
facts, subject to target compatibility. [IoAttachDeviceToDeviceStack](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/nf-wdm-ioattachdevicetodevicestack).

Keep raw HDD \\Device\\Harddisk0\\Partition0, optical \\Device\\CdRom0 and
\\DosDevices\\CdRom0. Retained partmgr owns PartitionN links, FATX probing,
partition offsets and volume metadata; class must not add the partition offset
again or synthesize MBR/GPT/FATX partitions. Preserve the loader's optical and
Partition2 dashboard paths. Optical aligned tail/cross-capacity requests reach
lower with actual results; HDD range rejection must not be reused for optical.

Clear DO_DEVICE_INITIALIZING before ordinary admission. Runtime dispatch,
completion/cancel callbacks, envelopes, sense, core and transport code/data are
resident. Boot PnP/AddDevice may enter INIT only while the kernel's boot seal
guarantees no runtime pointer remains there. Disk/Cdrom PnP is replaced with
invalid-request dispatch and AddDevice cleared before INIT discard. Drain every
boot-created lower request/callback before discard; a failed/timed-out Start
does not authorize freeing a still-owned resource or INIT callback. Public
DeviceNode/VPB/static-tree interfaces must remain valid without any old private
class layout.

## Precisely scoped investigator exports

Export declarations/layouts/constants with original notices and provenance,
or independent behavior/type facts. Do not export full unreviewed headers,
class private layouts, srbhelper/classpnp helpers, macro bodies of uncertain
origin, or I/O-manager/lower implementation expression.

| Export | Exact facts needed |
| --- | --- |
| Scalar/callback ABI | NTSTATUS/ULONG_PTR/size_t widths; NTAPI; DRIVER_INITIALIZE, DRIVER_ADD_DEVICE, DRIVER_DISPATCH, PIO_COMPLETION_ROUTINE, PDRIVER_CANCEL signatures; success/warning/error handling |
| IRP / stack / IOSB | Public fields used for MdlAddress, IoStatus, Cancel/CancelIrql/PendingReturned, approved parent context, Read/Write length/offset, Flags/FileObject, Scsi.Srb, DeviceIoControl buffers/lengths and PnP START parameters; x86 sizes/offsets |
| IRP operations | Target declarations/behavior for IoAllocateIrp, IoReuseIrp, IoFreeIrp, IoCallDriver, stack access/setup, IoSetCompletionRoutine, IoMarkIrpPending and IoCompleteRequest; stopped-completion/reuse and post-completion lower-use facts in the first gates |
| Cancellation | IoSetCancelRoutine, IoCancelIrp, IoAcquire/ReleaseCancelSpinLock, registration/removal ownership and terminal cancellation; which parent context remains valid across a claimed cancel routine |
| Locks/rundown | Public spin-lock/interlocked operations and IRQL restoration; target device/reference/remove-lock/rundown primitives or a reviewed target-owned declaration seam; admission-seal and callback-source lifetime contract |
| MDL | Public MDL layout/PFN capacity, page constants, byte count/offset/domain, permitted single/chain forms, source locking/mapping flags; IoBuildPartialMdl, IoAllocate/FreeMdl, MmPrepareMdlForReuse and required safe accessors as facts, not copied helpers |
| Pool/initialization | Available nonpaged allocation/free API, tags, executable/data pool constraints, allocation-failure rules; safe fixed IRP/partial-MDL provisioning and actual lower stack depth |
| SRB/sense | Exact target legacy SRB size/alignment/version, timeout and paging flags, lower path/target/LUN policy, sense capacity and how actual copied sense length is reported, queue-release/cancel terminal semantics |
| Cache and capacity | Supported descriptor/CDB queries, response extents, capacity units, ATA block limit, true alignment/PIO fallback policy, cache enabled/disabled state and selected flush route; no private extension dependency |
| Write-through propagation | Reviewed values/declarations and behavior for FILE_WRITE_THROUGH, FO_WRITE_THROUGH, SL_WRITE_THROUGH; which upper indication actually reaches this raw class for ordinary/paging/scatter writes |
| Upper lease | Behavior-only FATX direct/scatter request/MDL lease ownership across thread exit, close, truncate, delete and cancel; existing acquire/release interface declarations only if class must participate |
| Device/boot interfaces | Public DEVICE_OBJECT/DRIVER_OBJECT/VPB fields and device flags/types; IoCreate/DeleteDevice, attach/detach, symbolic-link APIs; static-tree declarations, boot START resource-list lifetime and INIT-seal contract without excluded devtree/class bodies |
| Status/control ABI | Exact required NTSTATUS and completion-boost constants; public IOCTL/layout build gates; mounted verify flag/interface, media-change count policy, geometry convention and unknown end-of-media outcomes |
| Native pilot artifacts | Exact input/build identity and read/write/flush/control/lifetime observation records; no old class source or source-extracting tests |

## Acceptance plan after the implementation gate opens

| Case | Required observation |
| --- | --- |
| Setup faults | Fail each device/envelope/child/SRB/sense/MDL allocation or attachment; exact owned-resource unwind, no dangling namespace, no INIT callback left live |
| Healthy QD1/4/12 | One eligible SRB per one-segment ordinary transfer; no added per-I/O heap/worker/clock/copy; independent lower concurrency, unchanged direct lease behavior, stable pool/MDL high-water and native consumer latency |
| Inline / pending | Success/error before IoCallDriver returns, pending after inline callback, delayed terminal callback; one parent completion and correct pending return/event/IOSB/APC order |
| Real object pairing | Child pointer equals Srb.OriginalRequest; child MDL covers DataBuffer subrange; fragmented pages/odd optical addresses avoid PRD failures and preserve checksums |
| Child reuse blocker | Delay old completion/lower frames while later segments run; verify actual stopped-completion and all SRB/sense/MDL accesses before any reuse, including many inline segments and post-IoComplete paths |
| Partial / malformed | Verified short/error data only; over-reported counts rejected; absent/truncated/malformed sense bounded; control canary tails untouched |
| Cancel handshake | Before publication, during prepare, after commit before port call, active DMA, during sync and alongside parent completion/removal; one terminal parent, actual bytes, no released-page DMA or late cancel on a terminal child |
| Parent reclaim / rundown | Free parent inline, admit/reuse slot from completion, pause callback with active==0/pumping==1, seal admission and drain whole-call/request/transport references; device never freed early |
| Freeze / low memory | One error RELEASE_QUEUE, failed-release quarantine with owned-request cancellation; no new allocation dependency, unsafe write replay or unrelated HDD/DVD work stranded |
| Durability | Enabled/disabled/unknown/unsupported cache, real hardware sync trace and error, write-through multi-chunk data then sync, following-write barrier with concurrent reads, native power-loss qualification separately |
| Controls | Zero, short, exact and oversized outputs for every required control; initialized claimed bytes; TOC short normalization only with actual reply; verify/media policy frozen explicitly |
| Boot / INIT | Expected names/order/stack/VPB, HDD then partmgr, optical XDVDFS, FATX offset once, cleared initializing flags, boot callbacks drained before seal/INIT reclaim, bounded late-PnP rejection |
| Baseline qualification | Run against frozen P1 native A/A contracts and identities; report every mismatch/failure and all unknowns; host core passes do not qualify firmware |

No new test execution is claimed by this design note. The existing 50-case host
evidence qualifies only the independent engine's tested boundary. Adapter
implementation and native performance/durability remain future work after the
named gates, including root's frozen P1 notification.

## Inputs, exposure and attribution for this note

Used own request.c/request.h/ADAPTER.md; approved CONTRACT.md, CALLER-MATRIX.md
and PUBLIC-REFERENCES.md; narrowly viewed declarations/constants in approved
srb.h, scsi-interface-only.h, ntddstor.h, ntdddisk.h and ntddcdrm.h. No transitive
include or permitted lower/caller source body was followed. A narrow geometry
declaration display incidentally rendered the adjacent DiskGeometryGetPartition
macro; it was not used or copied. Public MmGetMdlVirtualAddress documentation
also displayed its macro definition; this note uses only its address-domain
behavior, with no helper expression carried into output. Public documentation
example bodies were not reused.

All linked primary Microsoft documentation was read as public API/lifetime
reference on 2026-10-14. One attempted public synchronizing-cancel-routines URL
was inaccessible through the browser and contributes no assumed facts. No
authentication restriction was bypassed, no SDK/helper implementation was
imported, and no old implementation/binary/history was inspected. Required
interface names, layouts, command/status meanings and namespace convergence
are interoperability facts. All organization, envelope/publication/rundown
proposal and acceptance cases are independently authored. This is an exposure
record and design proposal, not legal/personnel certification or run evidence.

Pinned local inputs (whole-file hashing for identity; semantic study remained
within the prose and declaration fragments identified above):

| Input | SHA-256 |
| --- | --- |
| `.scratch/pr248-independent-output/nxstorage/request.c` | `46beecd00b7ce2e5d37386f1a649778aedf68298690dfb65af95d81845e229e6` |
| `.scratch/pr248-independent-output/nxstorage/request.h` | `6225a87e944e13c32b658dec239aead12f79876bdb80eb9fe9760a8e36f1013b` |
| `.scratch/pr248-independent-output/nxstorage/ADAPTER.md` | `69a421e813da465eb2b3abafab93d75ca5c04ce31fdb61c3fee6f9399960712b` |
| `.scratch/pr248-permitted-inputs/CONTRACT.md` | `3e1bee5be3eb445b51310afc47aee2ad6410ffd855804c4686362d09f9b767b7` |
| `.scratch/pr248-permitted-inputs/CALLER-MATRIX.md` | `b882e311e462d853d3a153ff4ff9f34a5611e9bfaf6b59df50cb068a01fe91d2` |
| `.scratch/pr248-permitted-inputs/PUBLIC-REFERENCES.md` | `ed242b01fb02d667e4bd63c84688505f00537e3f139ba46fc63b3224a8a17e98` |
| `.scratch/pr248-permitted-inputs/approved-inputs.json` | `1fcb751b17c5b7153d2675ce047db59677bbca03aa44209a489ed037672491f2` |
| `.scratch/pr248-permitted-inputs/source/sdk/include/ddk/srb.h` | `870c13c119506ecb7e25047c95fbc0e81b8e6c21c83cd6cae34c27540efc5bde` |
| `.scratch/pr248-permitted-inputs/source/sdk/include/ddk/scsi-interface-only.h` | `002f04c8ecd5437e23e7c143c431e65805fded9167047874d333bfb34787446c` |
| `.scratch/pr248-permitted-inputs/source/sdk/include/psdk/ntddstor.h` | `a79bf9a5faf0588d5c04ed21ecc1204a9aa72db57cc9445c335f19914078f441` |
| `.scratch/pr248-permitted-inputs/source/sdk/include/psdk/ntdddisk.h` | `66817aa4381522928296c0ae33ab3231442386827473ba1f4e68fbdd0b233db7` |
| `.scratch/pr248-permitted-inputs/source/sdk/include/psdk/ntddcdrm.h` | `d3c5fe785477fdd4da88d1d77bd501ca516945edf89bd06f2e80601c4b09322e` |

This note is the only output changed by this design task. Existing production,
tests, provenance and their artifact manifest were left unchanged. The note
hash is reported separately because a file cannot contain its own final hash.

## Approved completion/cache checkpoint addendum

Root subsequently approved COMPLETION-OWNERSHIP.md, CACHE-CAPABILITIES.md,
TARGET-API-AVAILABILITY.md, target-api-declarations.h and
LOWER-CACHE-QUERY-PROPOSAL.md. These are behavior/declaration packets with no
I/O-manager or lower implementation bodies. They update the initial unknowns
above as follows; the original design/input table remains a historical snapshot.

For the inspected target paths, STATUS_MORE_PROCESSING_REQUIRED stops I/O-manager
packet processing without later child/stack/MDL access. IofCallDriver does not
inspect that IRP after lower dispatch returns. The described terminal ATAPI and
bridge paths no longer access old child/SRB/sense/partial-MDL contents after
completion; inline remove-lock epilogues retain only an opaque saved IRP tag.
They still access device/channel state. Fixed child reuse therefore has conditional
target support: every candidate callback/submission frame must stop touching old
contents before calling nx_lower_done, copy token/results by value, and preserve
device references through the older epilogues. No two-bank proof or native
candidate reuse result is implied. Parent reclaim, cancel crossing completion,
long asynchronous-to-inline runs and device-rundown tests remain required.

IoReuseIrp also requires no installed cancel callback/thread-list association
and clears packet state; owned MDL/sense cleanup is separate. IoFreeIrp does not
free attached MDLs. These supplied facts permit a precise future reset/cleanup
sequence but do not qualify an unimplemented adapter.

The declaration packet distinguishes linked NTAPI routines and FASTCALL
IofCallDriver/IofCompleteRequest from header-only operations. The latter must
not be called as nonexistent standalone symbols or copied from unapproved SDK
helper bodies. Future local helpers require reviewed public field/atomic facts,
independent authorship and checks. Missing native types/offsets/calling-convention
closure remain unapproved; target-api-declarations.h does not supply them.

The current Xbox lower exposes no MODE SENSE caching page, ATA passthrough or
StorageDeviceWriteCacheProperty. A successful SYNCHRONIZE CACHE can be a no-op
for unrecognized/disabled cache or for enabled cache with no selected opcode.
The actual selected 0xE7/0xEA path can issue hardware flush and report eventual
errors. Discovery must expose recognized enable facts and a selected hardware
route; query absence/no-command success is not proof of disabled caching.

The read-only lower query proposal still has no installed lower glue. A separate
bounded pure primitive is now implemented in cache_query.c from the newly
approved cache declaration-fact packet. It requires a coherent explicit
capability snapshot, preserves Unknown and unqualified durability, and has no
ATA/queue/interrupt effects. No full class adapter is authorized before root
freezes P1. No request-core bytes changed.

## Declaration-fact checkpoint and native assertion strategy

Root subsequently approved CACHE-ABI-FACTS.md/cache-abi-facts.json/h,
NATIVE-ABI-INVENTORY.md/native-abi-facts.json/h and ABI-PROBE-RECEIPT.json. The
packet contains numeric sizes, offsets, constants and prototype identities only;
native type definitions, raw probe/assembly/dependency files and helper bodies
are still unapproved author inputs. A numeric IRP/MDL size/offset inventory does
not authorize reconstructing an opaque structure or dereferencing kernel memory
from guessed fields. Future adapter source still needs interface-only reviewed
declarations plus independently authored header-only operations and applicable
grant/field/atomic/calling-convention facts.

The cache primitive now serializes the exact approved 12-byte input minimum,
8-byte header and 28-byte full descriptor, including byte-27 padding. The public
Version definition was independently verified on the primary Microsoft Win32
STORAGE_WRITE_CACHE_PROPERTY page: structure byte size; Size means total returned
data. Both are 28 in this fixed profile. Host/freestanding tests compare own
serialization constants with the approved numeric packet without importing SDK
structures. CACHE-QUERY-DESIGN.md states the required exact native sizeof,
alignment, offsetof, member-width, enum and IOCTL assertions before lower glue
can be admitted. Exact compiler/header identities and zero-text assertion-only
object evidence must be retained; source/body grants cannot be inferred from
successful compilation.

Native inventory points out a target-specific IRP arrangement (128 bytes,
alignment 8, MdlAddress 108, SystemBuffer 112, CancelRoutine 116), so neither
desktop field layout nor unchecked whole-header inclusion is an acceptable
shortcut. The future adapter must assert its actual declarations against the
approved native packet for every field it uses, and verify NTAPI/FASTCALL
callback prototypes on that target. The cache encoder uses none of these
fields. No native runtime, IRQL/cancel parity, lower integration or physical
durability qualification is claimed by the pure module's passing tests.
