# Native storage cutover bring-up — 2026-10-15

This note records the failures and fixes that made the independently authored
`nxstorage` class drivers bootable. It is runtime evidence for PR #248, not a
license certification or a performance result.

## Scope and identity

- Backend: `complete-candidate`
- Patched source tree: `920af8da4535d5adbb2018d388a8cc814cd479e7`
- Public folded-driver ABI: `DiskDriverEntry` and `CdromDriverEntry`
- Linked class archive: `libnxstorage.a`
- Excluded class archives: `libclasspnp.a`, `libdisk.a`, `libnxcdrom.a`
- Test emulator: xemu `0.8.136-0-g458730bf5373`
- Memory profiles: 64 MiB and 128 MiB

The replacement source is carried by locked patches `0138`, `0139`, and
`0140`. The source is GPL-2.0-or-later and uses public kernel/DDK declarations
and independently recorded behavior. The complete-candidate link and source
gates reject the old class archives and identified legacy helper bodies.
The [complete-candidate license map](COMPLETE-CANDIDATE-LICENSE-MAP.md) records
each linked replacement unit, function group, source hash, and directly used
interface-header terms.

## Failure 1: disk namespace parent was missing

The first complete candidate reached the new `DiskDriverEntry`, proving that
the folded boot ABI and link selection were correct. `add_disk` returned
`STATUS_IO_DEVICE_ERROR`. A debugger trace narrowed this to:

```text
create_class -> NXD_IO_ERROR (-8)
IoCreateDevice("\\Device\\Harddisk0\\Partition0") -> 0xc000003a
```

`0xc000003a` is `STATUS_OBJECT_PATH_NOT_FOUND`. The replacement attempted to
publish `Partition0` before an owner had created `\\Device\\Harddisk0`.

The fix adds an owned object-directory handle to the disk class context. The
driver creates the permanent kernel directory before the disk device, retains
the handle for firmware lifetime, and makes it temporary and closes it if
device publication fails. A production-source regression requires directory
creation to precede `NxNativeCreateClassDevice` and requires the rollback
path.

The resulting 64 MiB release image was
`ecd82c146a422e7ba30d78b8cd594eeb6268705cf22ade59bbf5a46c83515694`.
Both disk and optical AddDevice calls then returned success.

## Failure 2: PnP start stopped at the class driver

The Xbox device tree sends `IRP_MN_START_DEVICE` after each successful
AddDevice. The replacement initialized every unassigned major function with a
reject handler, so the class FDO returned `STATUS_INVALID_DEVICE_REQUEST`
instead of continuing the already established lower stack.

The fix installs `NxNativeDispatchPnp`. It validates the class extension,
advances the current IRP stack location, and forwards the request to the
attached lower device. The host adapter test verifies that both boot drivers
install the owned PnP dispatcher.

The resulting 64 MiB release image was
`86a8ea0224ae27723be6b58bf101111d331a32ea53b2a0309233047c56c1abdc`.
It booted the API XISO and ran all 639 checks, but 95 checks failed because no
HDD partition namespace had been published. DVD-backed checks passed.

## Failure 3: PartMgr required extended geometry

PartMgr starts successfully after querying `IOCTL_STORAGE_GET_DEVICE_NUMBER`.
Its BusRelations refresh then asks the lower disk class for
`IOCTL_DISK_GET_DRIVE_GEOMETRY_EX`. The replacement implemented base geometry
and length queries, but rejected the extended geometry code. PartMgr therefore
aborted partition enumeration, and every HDD-backed API check failed with a
missing-path status.

The fix accepts the extended control in both cold and cached paths. It obtains
capacity through the existing bounded READ CAPACITY transaction, publishes the
24-byte `DISK_GEOMETRY` prefix followed by the 64-bit disk size, reports 32
bytes, and reuses the validated capacity for later queries. The host regression
checks the exact returned length, disk-size field, and lack of a second lower
request.

The final 64 MiB release image is
`037950f7a00fc2a7a5faeb12fd46d61b0697819ca6852b94b2f808cdffef8ef6`.
Its exact API run completed in 8.228 seconds with 639 tests: 637 passed, zero
failed, and two existing xemu floating-point exception TODOs. The 128 MiB
release image `033dc0deb14da7ff4fc33b2b96477f8ac4af06402441c9ec7916fcab85772501`
produced the same 637/0/2 result. Debug64
`5f3df6250fd320b0308d31973d1cc464f189b2a961d73c2b6351286554a007d9`
and debug128
`ed8d2a08f85fa5bbde5e2be4e830111a0ae9b54dbb2d96ff0523f2c4bcba0873`
also produced the same result.

## Remaining qualification

The runtime cutover now has verified disk and optical AddDevice, PnP start,
PartMgr enumeration, FATX-backed file operations, XDVDFS-backed reads, async
I/O, scatter/gather, flush API behavior, and both memory layouts through the
API regression.

A local 64 MiB release diagnostic then booted the frozen broad-XISO image with
the final BIOS hash above and an isolated copy of seed HDD
`9c80ca05b6d8415f838598b15dc69e240c9b8caf191b7a201c5d351077fd04d3`.
It completed in 147.685 seconds. The extracted result contains all 144 selected
leaves and five structural groups; all 149 records report `PASS`, with no
catalog gaps, fixed-field mismatches, or built-in oracle failures. Two raw
framebuffer hashes differ from the historical Windows-renderer reference;
because this diagnostic used local llvmpipe, those renderer-dependent hashes
are informational and no timing comparison is claimed.

The exact release64 build's recorded candidate preflight passes all four
sentinels: expected libraries, forbidden libraries, known legacy symbols, and
owned-source references. Its final expanded linker graph contains
`libnxstorage.a` and omits `libclasspnp.a`, `libdisk.a`, and `libnxcdrom.a`.
That preflight deliberately does not certify license compliance: optimized
inline/data attribution, corresponding-source and grant review still require
independent closure.

The product host suite ran 504 tests in 440.834 seconds with zero failures and
26 declared skips. This includes the owned storage production harness and the
migration-gate regressions. All four final firmware files have their expected
fixed image envelopes: release64, debug64 and debug128 are 524,288 bytes;
release128 is 262,144 bytes.

Save/game checks, paired performance comparison on the approved rigs,
physical-drive durability, physical Xbox support, and final independent
compiled-source/provenance/legal review remain separate gates.
