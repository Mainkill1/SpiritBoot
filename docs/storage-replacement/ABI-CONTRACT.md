# Xbox storage class replacement — implementation-neutral ABI contract

**Single PR:** see [PR #248 master implementation checklist](IMPLEMENTATION-CHECKLIST.md) for owner files, performance gates, and completion criteria. This contract must be frozen as observable/public behavior before the implementation team uses it; implementation source from ClassPnP is not an allowed input.


This is an **external behavioral specification**, not a porting guide from Microsoft implementation code. Values not established by a cited independent public test remain **verification targets**, not assumptions. Do not use implementation bodies or private logic from ClassPnP/Disk to fill gaps.

## 1. Existing boundary and proposed implementation

- Upper: existing `vfatfs`/FATX, `xdvdfs`/XISO, `partmgr`, `mountmgr`, kernel I/O manager, file-object, cache and loader interfaces.
- Candidate middle: `nxdisk` and `nxcdrom` register ordinary NT-compatible DRIVER_OBJECT dispatchers, containing owned device/request state and using a shared `nxstorage` engine.
- Lower: existing `atapi` bus device, legacy `SCSI_REQUEST_BLOCK` (`IRP_MJ_SCSI`) and `pciide/pciidex` interfaces, DMA and IRQ callbacks.
- Link/flash: one static `xboxkrnl.exe` payload, no external module and no dormant legacy implementation in candidate image.

Preserve `NxkDriveDeviceTree` boot order and existing fixed hardware topology. Xbox PnP may be simplified **only after** its required AddDevice/StartDevice and BusRelations behavior is verified against the existing upper/lower drivers; do not pretend that removing the MS-PL class library removes PnP's observable contracts.

## 2. Driver/device lifecycle contract

1. `DiskDriverEntry` and `CdromDriverEntry` are the required folded-boot ABI names. They register bounded, explicit `MajorFunction` tables and `AddDevice` with IoCreateDriver's existing startup path.
2. At AddDevice, acquire/attach a lower device, allocate independently defined FDO extension, initialize geometry/media state and guard, and unwind allocations/attachments in reverse order on any failure. Preserve driver names (`\Driver\Disk` and `\Driver\Cdrom`) and device-type/stack-size/alignment/direct-I/O flags expected by callers. The disk owner must create and retain the `\\Device\\Harddisk0` object directory before publishing `Partition0`; otherwise `IoCreateDevice` returns `STATUS_OBJECT_PATH_NOT_FOUND`.
3. At StartDevice, forward the PnP start request through the lower stack and answer the geometry/device-number controls required by PartMgr. `IOCTL_DISK_GET_DRIVE_GEOMETRY_EX` must publish both the 24-byte geometry prefix and the 64-bit disk size before partition enumeration can succeed. Support failed probe and unavailable media without poisoning later requests. Carry stable `\\Device\\Harddisk0\\Partition0` and optical namespace through existing namespace/partition components.
4. Handle only the actual PnP minor requests presented by the current `devtree` plus explicit test-generated edge cases. Record responses. Do not remove a remove-lock or allow a completion to access freed FDO/device state.
5. Driver lifetime is firmware lifetime in the ordinary Xbox case; teardown/error cleanup must nonetheless be correct for failed startup and test-induced stop/remove paths.

**Unknowns to test:** exact status for unattached disk/optical handles, PnP start failure and device count ordering; do not derive them from private source.

## 3. HDD data path

```text
upper READ/WRITE IRP
  -> validate offset/length/bounds/alignment (no lower request yet)
  -> acquire device/request lifetime + carry I/O owner
  -> map eligible segment (contiguous or MDL-scatter) within adapter limits
  -> build owned child SRB/IRP using supported lower-interface facts
  -> IoCallDriver to atapi
  -> child completion: status, bytes, retry decision
  -> next segment OR finish parent exactly once
```

Contract checklist:

- [ ] Zero length, negative/unrepresentable offset, overflow of offset + length, wrong sector alignment and out-of-range LBA produce independently observed status and information, with zero I/O on rejection.
- [ ] Validate 512-byte HDD sector expectations and actual IDENTIFY/capacity data; do **not** hardcode maximum size from current test image. Support 64-bit byte offsets and correct LBA/CDB selection where the lower driver permits them.
- [ ] Respect `AlignmentRequirement`, MDL buffer mapping, PRD and scatter/gather limitations, maximum physical pages and sector counts per command. Do not assume one IRP equals one ATA command.
- [ ] A direct fast path is valid when it is a single eligible transfer. A multi-command IRP must preserve total byte count and stop or retry according to observed error semantics.
- [ ] Preserve file-position/APC behavior established by the I/O manager; the class driver must not modify caller IOSB or free caller MDL prematurely.
- [ ] Fail on invalid geometry / missing drive, propagate write-protection and data-integrity failures; no success from an empty/short lower transfer unless specified.

Proposed context fields (design, **not** copying any existing private structure):

```c
// Conceptual fields; final types/ownership decided by implementer.
struct nx_request {
    void *parent_irp;             // borrowed until parent completion
    void *lower_device;          // referenced for entire request
    void *child_irp;              // allocated and owned by request engine
    void *owned_srb;              // one active transport command
    void *owned_sense;            // independently owned, if needed
    unsigned long long byte_start;
    unsigned long long bytes_total;
    unsigned long long bytes_finished;
    unsigned retries_remaining;  // finite policy, not a loop of fixed sleeps
    unsigned state;              // single ownership transition per stage
};
```

A request is allocated only when required by the actual lower IRP/SRB lifetime. No global unbounded queue, no heap allocation in the hard interrupt path, and no per-request worker dispatch simply to forward a ready read.

## 4. Asynchronous completion state machine

```text
NEW -> SUBMITTED -> [INLINE_COMPLETED | PENDING]
                    -> [RETRY_ALLOWED | NEXT_SEGMENT | TERMINAL]
                    -> PARENT_COMPLETED (once)
CANCEL/TEARDOWN ------^ after lower ownership is reconciled
```

- Create a strict ownership table: which layer allocates/unmaps/frees an IRP, SRB, MDL, sense buffer, file-object reference, lower-device reference and request context. Parent I/O manager MDLs are **borrowed**, not freed by the class layer.
- Lower requests may complete inline before `IoCallDriver` returns, complete later, fail immediately, return `STATUS_PENDING`, or retry/requeue internally. Account for all orders. There must be exactly one parent completion and no use-after-free when an inline completion frees child state.
- Record parent `IoStatus.Status`, `IoStatus.Information`, pending-bit propagation, APC/event/IOSB effect, and accepted `NTSTATUS` transitions in public test output.
- Preserve lower-driver queue semantics. Ensure the already identified same-IRP redispatch/requeue generation hazard is not recreated in an upper callback; handle retry by a monotonic generation/context rather than treating pointer equality as request identity.
- Cancellation and issuer termination must not release pinned buffers or resource leases while a lower request is active. Teardown runs only after all children terminate or are safely canceled.
- No waiting for a worker or completion at DISPATCH_LEVEL. Review IRQL constraints for DMA/IRQ callbacks, completion routines, locks and pageable/INIT code.

## 5. Geometry, partition and control requests

For each IOCTL, first capture a **public** contract: input/output length and access, exact status, information size, geometry/partition fields and failure path. Start with directly demanded cases; do not recreate desktop-only SMART/WMI/unload framework without a demonstrated requirement.

| Owner | Initial required contract | Validation |
| --- | --- | --- |
| HDD | `IOCTL_DISK_GET_DRIVE_GEOMETRY`, `_EX`, `IOCTL_DISK_GET_LENGTH_INFO` | partmgr start/mount; raw handle query |
| HDD | `IOCTL_STORAGE_GET_DEVICE_NUMBER`, required `IOCTL_STORAGE_QUERY_PROPERTY` | names/identity and title-facing callers only where observed |
| HDD | `IOCTL_DISK_VERIFY`, `IOCTL_STORAGE_CHECK_VERIFY` / media status | bounded verification/error behavior |
| HDD | Flush via `IRP_MJ_FLUSH_BUFFERS` / transport cache sync | durable save and error propagation |
| HDD | Partition operations required by `partmgr` `IoReadPartitionTableEx` / `IoWritePartitionTableEx` | preserve fixed FATX partition layout and errors |
| DVD | `IOCTL_CDROM_READ_TOC`, `IOCTL_CDROM_GET_DRIVE_GEOMETRY`, `IOCTL_CDROM_CHECK_VERIFY` | XISO mount, sector size, TOC |
| DVD | `IOCTL_STORAGE_CHECK_VERIFY`, capacity / no-media / media-change | insert/remove and reset behavior |
| Both | Unsupported IOCTLs and input/output buffer-size rejection | exact statuses, avoid memory corruption |

Not all entries have proven requirements from current native tests; construct a supported/unsupported matrix before implementation. Do not simply pass unknown IOCTLs to hardware without checking access and output buffer lifetime.

## 6. DVD-specific path

- Optical block size and capacity are independent of HDD. Handle `READ CAPACITY`, `READ(10)`, `READ TOC`, `TEST UNIT READY` and relevant sense conditions according to documented SCSI/ATAPI behavior and observed public API results.
- No writable DVD exposure by default. Treat no media, tray open, unit attention, spin-up/not ready, changed disc and TOC undersized buffer as distinct tests.
- Preserve the exact XDVDFS mount path and disc image compatibility in xemu; demonstrate large and repeated read correctness, including the first sector and final sector.
- Only remove `nxcdrom` ClassPnP-specific code after all invoked Class* helpers are independently replaced and all old static library dependencies are absent.

## 7. Retry, ordering and durability

- Explicit retry policy by error class: timeout, transport busy, media spin-up/not ready, transient unit attention, permanent CRC/illegal-command/write-protected. Bound attempts and wall-clock wait. Do not let class and ATA layers both retry the same condition indefinitely.
- State whether a failure may have modified disk; uncertain completion of a write must not automatically retry in a way that duplicates destructive metadata changes.
- Do not allow `FLUSH` to bypass prior submitted writes; preserve issue-order and publish a success only after correct device-level commit or explicit proof caching has been disabled.
- Trace start/end and status of a flush for controlled tests; release builds must compile out high-frequency event logging.

## 8. Public ABI evidence checklist

Capture one machine-readable entry per tested operation with: operation and device, input bytes/offset/flags, return value, `IoStatus`, APC/event order, transfer checksum, lower SRB command/length if available from an independent test hook, memory/handle deltas, platform and all build/image hashes. When outcomes differ among Complex, baseline SpiritBoot and candidate, label them rather than quietly choosing one. Implement correctness fixes separately if independent black-box evidence shows current baseline is wrong.

Reference only published hardware/command documentation, compatible source/interfaces with recorded grants, and independent black-box results. Source code or private-header bodies from the original Microsoft implementation are **not** part of this specification.


## 9. Critical source-review corrections and explicit new tests

**Boot driver registration (must be implemented):** the folded driver registry is at `ntoskrnl/io/iomgr/driver.c:IopFoldedInDrivers`, not solely `ntoskrnl/xb/devtree.c`. Preserve `\Driver\Disk` and `\Driver\Cdrom` names, `DriverEntry` calling convention, startup order and flags; trace the assembled post-patch code and `AddDevice`/`StartDevice` results, and prove the final device namespace and partition mount hierarchy through native tests.

**Flush != hardware cache synchronization:** in pinned `atapi/scsi.c:AtaReqTranslateRequest`, `SRB_FUNCTION_FLUSH`/SHUTDOWN succeeds without itself issuing cache sync; in Xbox `atapi/satl.c`, `AtaReqScsiReadWrite` clears FUA, while `AtaReqScsiSynchronizeCache` is a separate path with capability-dependent early returns. Confirm the *composed* baseline command sequence, cache-capability detection, write/metadata ordering and errors before implementing new flush. Assert actual expected CDBs/ATA commands and persistence; an apparent speedup caused by missing required flushes is invalid. Emulator process exit is not proof of physical drive-cache power-loss durability.

**Queue forward progress:** pinned `AtaReqCompleteRequest` may requeue, freeze a device queue and report `SRB_STATUS_QUEUE_FROZEN`. Make an explicit policy for class/lower retry ownership, bounded deadline, queue release/unfreeze, sense allocation, pool exhaustion, and mixed outstanding HDD/DVD traffic. Test that requests queued *after* the failing request complete or receive a bounded terminal result. Never introduce an unconditional single-request bottleneck or retry uncertain writes blindly.

**Ownership table required before request.c implementation:** list parent and child IRP, original/partial MDL, owned SRB/sense, buffer, lower device reference, original FATX IRP-owned resource lease, retry generation and completion context, each with allocator/borrower/callback/IRQL/cleanup. The lower driver consumes `Srb->OriginalRequest` and that IRP's `MdlAddress`; ensure the child mapping is valid throughout actual DMA. Caller's `IoStatus.Information`, APC/event and priority boost are independent from child completion return. Verify immediate completion before `IoCallDriver` returns, pending errors, cancellation/issuer exit, close/truncate/delete, lower requeue using same pointer, invalid map, allocation failure, partial segments and double-completion defense. Iterative segment submission must have bounded stack use on a long series of inline-completing children; no recursive per-sector stack growth.

**Fast-path work accounting:** an owned request structure does not justify one heap allocation per pointer or extra worker dispatch. Preserve the optimized FATX IRP-owned lease and conditional completion-clock behavior. Benchmark complete consumer-visible latency rather than just the lower request. Tests must compile independently authored **candidate** production functions, not the old extracted `TransferPktComplete` harness.
