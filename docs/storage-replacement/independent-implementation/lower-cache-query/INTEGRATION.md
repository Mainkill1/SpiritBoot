# Candidate-only integration requirements

The publication/query module and producer/query helpers are implemented and
execute in host tests. No product patch, native call-site wiring, target type
compilation or installed property handler is claimed. Root supplies the
CMake/LAB gate and native qualification. The released legacy-reference route
must exclude new fields, objects and call sites so its ROM is unchanged.
Coordinates in unexported files are approved packet facts, not bodies read by
this author. No full storage class adapter is included.

## Fixed ownership and query routing

Under the candidate gate, include cache_property.h and append newly owned
nx_lcq_state NxCacheQueryState at the END of ATAPORT_DEVICE_EXTENSION and
nx_lcq_writer NxCacheWriter at the END of ATA_DEVICE_REQUEST. Preserve measured
retained field offsets. New device state is four bytes; i386 writer is twelve
bytes, and copied terminal result is twenty bytes. Existing lower device,
request and whole-call references protect their residency. Generation checks
provide no protection against access after destruction. No new pool, per-I/O
allocation, clock, worker, probe, command or queue/IRQ transition is required.

Include native_hook.inc after native declarations in ioctl.c. After the existing
full query-input validation in AtaPdoHandleStorageQueryProperty, add the gated
case:

```c
case StorageDeviceWriteCacheProperty:
    *ForwardToFdo = FALSE;
    return NxAtapiQueryWriteCache(DevExt, Irp, IoStack);
```

Also initialize IoStatus.Information to zero on candidate
IOCTL_STORAGE_QUERY_PROPERTY dispatch entry, before the retained handler's early
short-input return. The helper cannot repair an IRP it never receives. This is
an explicit candidate error policy, excluded from the released route.

The hook takes one acquire snapshot, delegates to frozen nx_cache_query_encode,
sets actual Information, and returns native status. It never completes,
forwards, marks pending or installs a cancel routine. AtaPdoDeviceControl keeps
sole completion ownership and its existing remove-lock epilogue using the saved
IRP tag. No new helper accesses parent, buffer or device after owner completion.
This does not claim the retained epilogue has no device access.

Pure results map to SUCCESS, BUFFER_TOO_SMALL (input below12), NOT_SUPPORTED
(unsupported profile/property/query), INFO_LENGTH_MISMATCH (output below8), and
INVALID_PARAMETER (invalid buffer contract). Standard success returns initialized
8-byte header or full28 bytes; Exists/errors return zero Information. Version
and Size both equal28 for the fixed descriptor. Padding byte27 is initialized,
oversized tails untouched, and aliased SystemBuffer supported.

## Writer tracking and publication anchors

Include native_capture.inc after native declarations and new members exist.
These helpers are not a complete call-site patch. Every producer must be wired;
a constructor-only or READ CAPACITY-only patch is incomplete.

| Boundary | Required candidate action |
| --- | --- |
| PDO construction, pdo.c:753 | NxAtapiCacheInitialize before external exposure; profile starts Unknown |
| Request allocation/recycle | NxAtapiCacheWriterReset before unrelated request reuse |
| Constructed IDENTIFY before mapping | NxAtapiCacheTrack retains original Cached/Local destination, opcode and qualifying extent; preserve through mappings/requeues |
| Actual start, scsi.c:500/522 | NxAtapiCacheStart after PrepareIo/mapping/fallback, immediately before external start; invalidate again for already-built queued writers |
| Generic terminal, scsi.c:262 | Copy NxAtapiCacheRawResult before translation, internal-request early return, pointer changes or recycle |
| Runtime READ CAPACITY, satl.c:759/768 | After addressing/translation, publish qualifying raw result before successor starts; exclude every source/flag mutator throughout capture/CAS |
| Initial/re-enumeration, dev_identify.c:213/317/320 | Retain local result by value through cached copy, accepted profile and negotiated addressing consistency; publish SAME_DEVICE refresh as well |
| Post-config, dev_config.c:343/389/395 | Revoke before facts become unavailable; publish only after successful fresh local IDENTIFY, cached copy and applicable addressing/profile consistency; event signaling is insufficient |
| Addressing/profile mutation, enum.c:182 and callers | Invalidate/revoke before mutation; publish actual consistent flags using owned successful identity result |
| Reset portstate.c:165/298, removal pdo.c:85/675, reclassification | NxAtapiCacheUnavailable before facts lose validity; retain existing rundown; old terminal cannot restore revoked data |

Tracked commands are0xec/0xa1. scsi.c:739 rewrites DataBuffer during mapping;
REQUEST_FLAG_HAS_LOCAL_BUFFER classifies local destination at construction.
NxAtapiCacheStart uses actual REQUEST_FLAG_PROGRAM_DMA (0x00200000) after
preparation/fallback to distinguish PIO counted from controller-inferred DMA
completion. DMA opcode flags are not the engine proof. Recognized starts with
unqualified extent/proof still invalidate earlier qualification.

PIO raw success plus an exact512-byte request proves the retained counted
transfer contract. DMA raw success plus programmed descriptors establishes the
retained controller contract without an independent byte counter. Both require
raw status1 and extent512 before translation. Translation may rewrite status
and length to capacity success/8; those values prove no IDENTIFY completion.
Local completion is not publication: the existing worker must own the copied
result through cache copy and flags/profile consistency, without dereferencing
recycled request storage.

NxAtapiCachePublish rejects obsolete/nonqualifying results before raw capture,
then character-loads four words and actual TransportFlags/DeviceFlags into an
owned view. The current-result check is an epoch check, not a source lock. The
caller must exclude every PIO/DMA/software writer and flag mutator throughout
capture/CAS. Device.QueueLock alone does not cover hardware-write lifetime.
Runtime publication belongs at the locked terminal boundary before successor
start; workers need their existing exclusive producer boundary through cached
copy/profile/addressing consistency. Native review must prove these conditions
at EVERY boundary. Host mutex tests exercise this contract, not native guards.

## Retained cache facts and bounded lifetime

Compiled declaration facts prove retained cache/flush WordValid at word84
bits14..15, value1. WordValid83 at word83 separately supplies LBA48 negotiation.
Cache support/active are word82/85 bit5; regular/ext flush word83 bits12/13. The
helper copies no IDENTIFY predicate body and does not silently substitute public
normative validity checks for retained behavior.

Actual TransportFlags ATAPI0x10 yields optical, unsupported in this profile.
Actual negotiated DeviceFlags LBA48 flag0x4 plus recognized extended support
selects0xea; otherwise regular support selects0xe7; otherwise None. FUA and
registry DeviceType give no credit. Disabled cache may expose a selectable flush
capability although retained SYNC takes an early no-command branch. Unknown,
contradictory or unsupported cache remains Unknown with no flush credit. SYNC
success cannot establish these facts or physical durability.

The independent atomic scalar has9 payload bits and23 epoch bits. Each tracked
start/revocation advances epoch and clears qualification; a matching CAS
publishes the entire view. Duplicate/older results fail. Only8,388,606 epochs
are issued: reserved exhaustion never wraps. Mutation tries at most16 CAS
attempts; exhaustion/contention failure closes qualification permanently until
new object construction. Never re-init live state to reset it. Queries take one
acquire load and never read cached IDENTIFY. snapshot_proof and snapshot are
separate acquire reads; a future diagnostic needing jointly coherent proof and
capabilities must use one combined observation rather than assume two calls are
indivisible.

## Target assertions and acceptance gates

tests/abi_assert.c compares own types/constants with approved scalar facts and
compiles freestanding i386. tests/native_bridge_i386.c compiles actual new
helpers against LOGICAL types. Neither establishes opaque native layouts.
Candidate target assertions must use actual declarations; unknown SDK bodies
must not be reconstructed to make them pass.

| Native interface | Required target assertion |
| --- | --- |
| Model | little-endian i386; pointer/ULONG/NTSTATUS4; aligned4 atomics always lock-free; no linked libatomic helpers |
| IRP/IOSB | baseline IRP128 align8; SystemBuffer offset112 width4; IoStatus offset16; IOSB Information offset4 width4 |
| IO_STACK_LOCATION | size36 align4; output length offset4 width4, input length offset12 width4 |
| Lower fields | Device offset56, cached union offset216 size512; nested TransportFlags offset4, DeviceFlags12; baseline extension1008 align8 before append; new-member offset/alignment and grown allocation sizes correct |
| Request | DataBuffer28, DataTransferLength40, SrbStatus60, TaskFile.Command8; actual Flags/PROGRAM_DMA constant matches approved declaration; appended writer extent/alignment correct |
| IDENTIFY | size512 align1, support group164 size6, active170 size6; separate compiled bitfields distinguish validity at word83/84 |
| Public cache | query12/header8/descriptor28 align4; every offset/width/enum equals cache-abi-facts.h; IOCTL0x2d1400 |
| Status | actual symbolic constants equal status-facts.h and supplemental NOT_SUPPORTED0xc00000bb; MORE_PROCESSING_REQUIRED is not used for query routing |

Actual enlarged lower sizes are candidate facts, not baseline-size equalities.
Assert retained offsets plus appended member alignment/extent and audit all
allocation sizes. Existing dispatcher calling conventions remain unchanged;
these static helpers introduce no completion callback ABI.

Native acceptance requires candidate-only installed routing and actual native
Information/one parent completion;12/8/28 bounds/Exists/errors/aliasing; enabled,
disabled, Unknown, E7/EA/None, Ext-only-no-LBA48, optical; all initial/SAME_DEVICE/
post-config/runtime/reset/removal producers; queued starts and raw partial/error/
controller-error paths; mutation exclusion, duplicate/revoked result rejection,
rundown, inline/pending and owner recycling. Observe zero added commands/cache
settings/queue/IRQ transitions. Later separate diagnostics record actual SYNC
opcode and no-command reasons. This read-only property alone does not qualify
write-through or persistent drive data.
