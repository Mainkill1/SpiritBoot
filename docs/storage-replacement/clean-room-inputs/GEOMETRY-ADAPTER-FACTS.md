# Retained partition-owner adapter facts

Investigator export, 2026-10-14. This is an interface and behavior packet for adapting an independently authored geometry composer. No replacement wrapper is supplied. The old response body and its private response structure remain excluded. Facts below refer to the composed baseline; a future candidate must verify its own link and lifetime.

## Entrypoint and completion ownership

The retained dispatch expects an ordinary C function returning `NTSTATUS`, with inputs `PFDO_EXTENSION` and `PIRP`. There is no `NTAPI` on this local entrypoint. The upper operation is buffered `IOCTL_DISK_GET_DRIVE_GEOMETRY_EX`, input length zero. Its output buffer is the IRP system buffer and its capacity is the current stack's device-control output length. The retained enclosing dispatch writes the final status and completes the upper IRP once. The local adapter must supply a bounded final `IoStatus.Information` and return; it must not complete or free that upper IRP itself.

An independently authored adapter may use a new name. Keeping the old private function name, internal record type or response algorithm is unnecessary for ABI compatibility. Ordinary exported kernel APIs have the checked declarations in `geometry-api-declarations.h`. Header-only stack helpers remain subject to the existing approved field-fact packet and independent implementation policy.

## Owner snapshot

The granted partition-owner header contains these actual fields. These are declarations and meanings, not an instruction to reproduce the old query body.

| Owner field | Declared type | Meaning / ownership |
| --- | --- | --- |
| `LowerDevice` | `PDEVICE_OBJECT` | next lower attached device, owner keeps attachment alive |
| `SyncEvent` | `KEVENT` | owner's layout synchronization event |
| `LayoutValid` | `BOOLEAN` | validity of cached layout, not a guarantee that any output tail exists |
| `LayoutCache` | `PDRIVE_LAYOUT_INFORMATION_EX` | owner-managed allocation, invalidation/replacement may free it |
| `DiskData.DiskSize` | `UINT64` | refreshed exact disk byte count |
| `DiskData.BytesPerSector` | `UINT32` | refreshed sector byte count |
| `DiskData.PartitionStyle` | `PARTITION_STYLE` | current cached owner style |
| `DiskData.Mbr.Signature` | `UINT32` | MBR identity when style is MBR |
| `DiskData.Gpt.DiskId` | `GUID` | GPT identity when style is GPT; shares storage with the MBR identity |

Observed: the layout owner uses a synchronization event initially signaled, with a wait acquiring exclusive ownership and a set releasing it. Layout refresh updates style and identity while that ownership is held; layout-cache pointers do not survive an unlocked replacement as borrowed pointers. The wrapper's scalar snapshot must therefore come from one owner-approved critical section and must not retain a layout pointer after release. Capacity/sector refresh and layout refresh occur during boot enumeration; absence of an explicit hot-remove lock in this owner is a limitation, not a new reference guarantee.

Requirement: preserve the device/attachment and snapshot lifetime for the entire lower query. A snapshot for one response must contain a coherent style and applicable identity. Do not hold layout ownership across lower submission or a completion wait. This does not establish atomicity between a future media change and separately queried geometry; the supported boot-fixed HDD assumption must be recorded, or a candidate must introduce independently reviewed revalidation.

There is no owner checksum field. A successful MBR response cannot obtain a meaningful checksum from this snapshot alone. An unavailable checksum is initialized according to explicit candidate policy, rather than borrowed from uninitialized lower bytes.

## Lower query and actual byte counts

The standard basic geometry query is `IOCTL_DISK_GET_DRIVE_GEOMETRY` (numeric value in `geometry-abi-facts.json`), with no input. Its public output is a 24-byte `DISK_GEOMETRY`; it contains no exact disk byte count. Exact byte capacity must come from a valid owner snapshot or another independently specified bounded lower query, never from multiplying nominal cylinder geometry.

Observed interface limitation: retained `IssueSyncIoControlRequest` returns only `NTSTATUS`. It can report allocation failure, immediate lower dispatch status, or terminal status after a pending request; it does not return the lower `IO_STATUS_BLOCK.Information`. Reusing that status-only interface cannot prove how many lower output bytes were initialized. This packet does not approve its implementation body or infer any private helper grant from the prototype.

Requirement for a sized basic query: preserve the terminal lower status and actual Information, validate that a successful result supplies all 24 required bytes and does not exceed supplied capacity, and treat a short successful base result as a bounded error. Lower failure produces zero claimed upper bytes unless an independently specified public partial-result contract says otherwise. Allocation failure is `STATUS_INSUFFICIENT_RESOURCES`; an invalid or unavailable geometry/capacity snapshot produces an explicit failure. `STATUS_PENDING` is a submission result, never the final upper geometry result. Which error code represents malformed success is an explicit candidate policy.

The checked target supports `IoBuildDeviceIoControlRequest` and the ordinary event services. Its public contract assigns completion status/count to the caller's `IO_STATUS_BLOCK`, requires the event and system-memory output to remain alive through terminal completion, and assigns synchronous child-IRP disposal to the I/O manager. The adapter must not free that completed synchronous IRP itself. A fresh sized-query adapter is permitted; copying the old status-only helper body is not required or authorized. [Microsoft request-building contract](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/nf-wdm-iobuilddeviceiocontrolrequest).

## Public shape and style policy

Checked target facts: `DISK_GEOMETRY` is 24 bytes, `DiskSize` starts at byte 24, and the extended response's optional data starts at byte 32. Public partition information is 24 bytes. `PARTITION_STYLE_MBR=0`, `GPT=1`, `RAW=2`; the ReactOS-only declared `BRFR=128` is a separate value. The composed Xbox layout synthesizer actually reports MBR style 0 with signature `0x584f4258` for recognized FATX partitions. Merely having BRFR in a header does not establish that this driver emits it. A native result with style 0 is therefore MBR, not RAW and not BRFR. BRFR mapping requires separately observed consumer requirements and an explicit policy; this packet does not authorize silently relabeling it as MBR.

Public partition data maps MBR to signature/checksum and GPT to disk GUID. RAW or unavailable metadata must not be interpreted through either identity union. The native returned-prefix measurements supplied by the parent are 32/40/56/64/112 bytes for those output capacities; those measurements are external evidence and are not a new source-derived algorithm. A candidate following that policy initializes every claimed byte, emits meaningful records only when fully fitting, and leaves unavailable optional record headers as initialized size-zero records. The author must pin the native measurement artifact and may not call source-derived assumptions measured parity. This packet supplies shapes and owner facts; the parent approves the measured-prefix policy independently.

The numeric packet comes from a declaration-only x86 probe. All four kernel API prototype comparisons succeeded, and its object `.text`, `.data`, and `.bss` are zero bytes. `GEOMETRY-ABI-RECEIPT.json` records compiler/source/probe hashes and dependency scope. No private DDK helper body or unknown transitive header is approved by compiling the probe.

Primary mapping reference: [Microsoft public partition record](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntdddisk/ns-ntdddisk-_disk_partition_info).
