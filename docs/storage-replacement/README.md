# GPL-compatible Xbox storage class replacement — implementation dossier

**SINGLE PR DELIVERY:** [PR #248](https://github.com/Mainkill1/SpiritBoot/pull/248) owns the entire implementation through final release checks. The authoritative, detailed task list is [IMPLEMENTATION-CHECKLIST.md](IMPLEMENTATION-CHECKLIST.md). Internal P0–P5 checkpoints are commits/reviews *within #248*, not additional PRs. This file describes the boundary; where historical provisional stages conflict, the master checklist takes precedence.


**Status:** the independently authored complete candidate now replaces the HDD
and optical class layer, boots in all four 64/128 MiB release/debug profiles,
and passes the full API regression in each profile. The exact 64 MiB release
also passes all 149 records in a local 144-leaf broad-XISO diagnostic. See the
[native cutover bring-up](NATIVE-CUTOVER-BRINGUP-2026-10-15.md) and
[issue #245](https://github.com/Mainkill1/SpiritBoot/issues/245). Performance,
physical hardware, corresponding-source, and final independent provenance/legal
review remain release gates.

## 0. Scope, release identity, and why a narrow rewrite

The published v1.0.0 audit identifies **139 distinct retained Microsoft sample/private-header function bodies** within the compiled firmware: 65 represented by 66 native named symbols, 79 confirmed nonzero inline source functions, with five identities in both sets. This is **not** a percentage of image bytes or RAM, and is not a finding that every tiny body is independently protectable. The actual retained transfer-queue, submission, completion, retry, sense and disk-control implementations are substantive. The separately identified 19 `srbhelper.h` and three `classpnp.h` SDK/DDK helper names, plus five additional SCSI utility identities, still require removal or independent rights resolution. The pinned [baseline audit](baseline-provenance-audit/README.md) records compiled occurrences and footprint limits.

Pinned product revision: `b65a3f77d9887c9285e936996eb4d286a66f540c`.
Pinned Roswell revision: `1569e2e89fb47cc72b9c704a8884f98200432bd4`.
Assembled released source tree: `3c23ea01cf43c2979c4c3ef247236e03d079f465`.
Released 64 MiB image SHA-256: `c630d22f2353d3898024d510f0b402b64bccdb331781fe7885389f73d6200853`.

Goal: **a single bootable SpiritBoot `flash.bin` containing a GPLv2-compatible, independently implemented HDD class driver, a minimal optical class driver and a shared request engine**, while retaining permitted and tested ATA/ATAPI, partitions, FATX, XDVDFS, I/O manager, cache and XBE infrastructure. No runtime plugin, external driver or second BIOS. License permissions must be established before any existing source is reused. A separate grant/exception is an alternative resolution; this track assumes replacement.

The current statically linked chain, from the *pinned baseline* source (not a claim about every later patch):

```text
Xbox game / dashboard / loader
        |
Nt*File / file-object / IRP / cache
        |
FATX (vfatfs) / XDVDFS
        |
partmgr / mountmgr; NxkDriveDeviceTree() namespace and PnP initiation
        |
Disk + ClassPnP           NxCdrom + ClassPnP      <-- replace THIS class layer
        |                      |
        +---- legacy SRB ------+
                    |
             atapi / pciide / pciidex
                    |
             MCPX PATA / HDD / DVD
```

**Target:** a new `nxstorage` common SRB request engine + `nxdisk` class FDO, and an adapted `nxcdrom` independent of ClassPnP. Exact library partitioning can change with measured evidence. Prefer separate small compilation units, static linking into `xboxkrnl.exe`, preserving registered driver names and device namespaces. The *new backend must be a compile/link-time choice*, not a runtime toggle that still ships MS-PL object code.

## 1. Ownership boundary: what remains

| Boundary | Retain or rebuild | Why |
| --- | --- | --- |
| `ntoskrnl` I/O/object manager, IRP/MDL/APC/DPC, handle and completion machinery | **Retain** | Public kernel ABI and lifetime semantics; optimize independently only under separate tests |
| `ntoskrnl/xb/devtree.c` fixed Xbox tree | **Adapt** | `\Driver\Disk` / `\Driver\Cdrom` AddDevice/start flow; preserve relationships/names |
| `drivers/filesystems/vfatfs` FATX | **Retain** | Current FATX, async read, save and writeback correctness/performance |
| `drivers/filesystems/xdvdfs` XISO | **Retain** | Optical file parsing and normal filesystem IRPs |
| `drivers/storage/partmgr` | **Retain** | Partition0/Partition1.., offset translation, metadata/geometry dependencies |
| `drivers/storage/mountmgr` | **Retain** | Namespace and volume link behavior |
| `drivers/storage/ide/atapi`, `ide/pciide`, `ide/pciidex` | **Retain, audit dependencies** | Existing device discovery, SRB transport, DMA, interrupts, low-level ATA/ATAPI and chipset path |
| `drivers/storage/class/classpnp` | **Replace incorporated implementation** | MS-PL library currently folded into kernel |
| `drivers/storage/class/disk` | **Replace incorporated implementation** | MS-PL class driver currently folded into kernel |
| `drivers/storage/class/nxcdrom` | **Adapt / refactor** | Roswell optical driver uses ClassPnP types, callbacks, transfer and IOCTL helpers |
| headers/private helper inlines | **Audit and independently replace as needed** | Merely dropping libraries may retain compiled SDK/DDK/MS-PL implementation |

`nxcdrom` is not optional. It currently calls `ClassInitialize`, `ClassClaimDevice`, `ClassCreateDeviceObject`, `ClassReadDriveCapacity`, `ClassSendSrbSynchronous`, `ClassDeviceControl`, `ClassCompleteRequest` and related ClassPnP helpers. Do not unlink ClassPnP until the optical path is independent.

## 2. File-by-file implementation map

**These are target files inside the assembled Roswell source checkout**, not files immediately present in the SpiritBoot product repository. SpiritBoot imports Roswell via ordered `patches/roswell/*.patch` referenced with SHA-256 in `sources/firmware-lock.json`. Modifications must be committed as reviewed ordered patch(es), with the lock updated and isolated rebuilds.

| File or directory | Proposed edit | Phase |
| --- | --- | --- |
| NEW `drivers/storage/class/nxstorage/CMakeLists.txt` | `nxstorage` static library, Xbox-only sources, no ClassPnP linkage; no compulsory dynamic registration | C |
| NEW `drivers/storage/class/nxstorage/nxstorage.h` | Own narrowly scoped device/request context, geometry, API declarations; avoid copying `classp.h` or `disk.h` private layouts | C |
| NEW `drivers/storage/class/nxstorage/device.c` | Independently implemented AddDevice, attach/PnP lifecycle, startup failure unwind and resource teardown | C–D |
| NEW `drivers/storage/class/nxstorage/request.c` | Parent/child IRP lifetime, SRB creation and dispatch, chunking, DMA-boundary rules, exactly-once completion | C |
| NEW `drivers/storage/class/nxstorage/sense.c` | Error/sense-to-public-status mapping and bounded retry policy; never unbounded or double retries | C |
| NEW `drivers/storage/class/nxstorage/control.c` | Shared supported disk/optical control requests, capacity/geometry and media/flush helpers | C |
| NEW `drivers/storage/class/nxstorage/driver.c` | Export the required public `DiskDriverEntry`/`CdromDriverEntry` boot ABI, AddDevice callbacks, device names, HDD/optical dispatch and PnP forwarding | D–E |
| `drivers/storage/class/nxcdrom/nxcdrom.c` | Remove all dependence on ClassPnP; retain correct observable optical behavior but use owned device/IRP routines | E |
| `drivers/storage/class/nxcdrom/CMakeLists.txt` | Use new owned interface; drop ClassPnP-specific settings only when their dependency is gone | E |
| `drivers/storage/class/CMakeLists.txt` | Register new library; keep baseline targets conditionally during development | C–F |
| `drivers/storage/ide/atapi/{scsi.c,satl.c}` | **Audit first; patch only if proven necessary** for transport/lifetime bug or required SRB contract; preserve hardware paths | D–E |
| `drivers/storage/partmgr/{partmgr.c,partition.c}` | **Avoid edit**; adjust only if a tested public contract requires it | D |
| `ntoskrnl/io/iomgr/driver.c` | **Required:** adapt `IopFoldedInDrivers` registration, driver names, ordering and entry ABI | D–F |
| `ntoskrnl/xb/devtree.c` | Switch HDD entry symbol to new implementation, preserve `\Driver\Disk`/`\Driver\Cdrom` names and PnP topology | D–F |
| `ntoskrnl/include/internal/nx-devtree.h` | Audit fixed-tree prototypes and interface assumptions; alter only where necessary | D–F |
| `ntoskrnl/xb/devnode.c` | Audit ClassPnP-specific fabricated devnode assumptions; remove only proven-dead dependency | F |
| `ntoskrnl/CMakeLists.txt` | Mutually exclusive legacy or GPL storage libraries; final product link must omit `classpnp` and `disk` | F |
| `drivers/storage/CMakeLists.txt` | Validate parent discovery and dependency closure | C/F |
| `sdk/include/...` relevant public storage/WDK declarations | Keep interface facts only with verified rights; replace nontrivial inherited inline bodies | B/F |
| Existing `tests/host/storage-completion/` and NEW `tests/host/nxstorage/` | Old `storage-completion` extracts Microsoft-derived `TransferPktComplete`: baseline-only, **excluded from isolated implementer inputs**. New test must compile real NEW production functions | B–E |
| `tests/xbe/storage-contract/`, `fatx-async-lifetime/`, NEW `storage-class-contract/` | Expand black-box public API tests before switching default | B–F |
| `patches/roswell/<next-unused>-*.patch` | Ordered patches **inside PR #248**; current pinned lock already uses `0121` and runs through `0125a`, so inspect current head for next free suffix | C–F |
| `sources/firmware-lock.json` | Add path/hash for each patch, preserve complete ordering and base revision | C–F |
| `scripts/build-firmware.py`, `tools/firmware.py`, `tests/host/test_firmware.py` | Expose explicit backend selection, fail closed on fallback, record requested/actual backend in `build.json` and validate CLI/config/lock behavior | C–F |
| `tools/storage_migration_gate.py` | Preflight archive/symbol/owner-source sentinel; **not** a license certification | A (this PR) |
| `tests/host/test_storage_migration_gate.py` | Synthetic tests for the sentinel; regular host CI discovery | A (this PR) |
| `docs/storage-replacement/*` | Contracts, provenance barriers, test and merge criteria | A (this PR) |
| `docs/BUILD_AND_RUN.md`, release credits/notices | Document verified end-state only; publish no compliant-claim until separately audited | F |

Do not transplant existing `class.c`, `xferpkt.c`, `disk.c`, `geometry.c`, `classp.h` or their function bodies into this implementation. Function names below are **inventory labels for behavioral extraction**, not rewrite templates.

## 3. What to extract, precisely

**Extract public behavior / inputs / outputs / test observations; not Microsoft expression.** A separate specification/provenance reviewer may inventory the old implementation, but implementers receive only the approved external contract and test results.

| Existing identity/group (audit mapping) | Extract as behavior only | Target ownership |
| --- | --- | --- |
| `ClassInitialize` and device creation | `DriverEntry` callbacks, device stack composition, IRP dispatch set, accepted PnP minors, symbolic names | `device.c`/`disk.c`/optical |
| `DiskCreateFdo` / disk start | Device namespace, disk numbering, raw Partition0 object, VPB/flags, lower attachment, sector/capacity reporting | `disk.c` |
| `ClassReadWrite` and `DiskReadWriteVerification` | Bounds/alignment, 64-bit offsets, invalid-buffer/status behavior, zero-length, EOF and partial transfer policy | `request.c` |
| `SubmitTransferPacket` / `TransferPktComplete` | Legacy SRB interface, splitting, in-flight lifetime, error propagation, completion ordering, pending and cancellation | `request.c` |
| `ClassInterpretSenseInfo` family / retry helpers | Observable statuses for timeout, not-ready, unit attention, media missing/change, illegal request, write protection | `sense.c` |
| `DiskDeviceControl`, drive geometry/capacity | Required IOCTL input/output shapes, lengths, status for unsupported commands, partition manager queries | `control.c` |
| `ClassSendSrbSynchronous` / `ClassReadDriveCapacity` | Transport-level command semantics for DVD capacity, TOC and media verification | `request.c` / optical |
| `ClassClaimDevice` / `ClassReleaseRemoveLock` | Device ownership, request admission and finite completion lifetime | `device.c` |
| `srbhelper.h` / `classpnp.h` inline helpers | Only public ABI constants/structure definitions when licensing permits; independently express helpers | `nxstorage.h` / local helpers |

**Potentially extracted source:** preexisting independently authored SpiritBoot fixes, public tests, compatible lower-driver interfaces. **Not automatically extractable:** MS-PL bodies, translated pseudocode from MS-PL routines, shared private macros, SDK/DDK inline implementations, or arbitrarily re-licensed ReactOS snippets. Document exact licenses and grant evidence for each reused body.

## 4. Replacement design: specific runtime rules

- **Kernel ABI stays stable.** Maintain file/volume handles and device names `\Device\Harddisk0\PartitionN`, `\Device\CdRom0`, matching driver names and filesystem mount order. Adapt internal implementation, not consumer-facing handles.
- **No bypass of `atapi` initially.** HDD read/write and optical commands go to the existing lower driver using its legacy `SCSI_REQUEST_BLOCK` contract. Direct ATA or MMIO redesign is a separate optimization PR only after parity.
- **Single request owner.** Represent a parent IRP and any child SRB/IRP with explicit allocations, transfer progress, per-request retry budget, lower-device lifetime, MDL ownership and cancellation state. A parent must complete exactly once, regardless of lower synchronous, pending, failed or inline completion.
- **No extra worker round trip on healthy reads.** Queue only to preserve lower-device admission/serialization, retry timing, or required IRQL rules; do not add an extra filesystem worker. Direct FATX eligible read paths already hand IRPs to storage.
- **Split only for real limitations.** Respect current sector size, CDB/LBA addressability, max transfer, DMA scatter/gather/PRD capacity, adapter alignment, and buffer length. Check multiplication/offset overflow before touching I/O. Zero-length operations do no lower I/O.
- **Correct status and byte count.** Propagate parent `IoStatus.Status`/`Information`, visible `STATUS_PENDING`, APC/event semantics, write/read failures and short transfers. Never hide partial write failure or fabricate a success.
- **One retry authority.** Separate retry policy at class boundary from lower transport retries. Define status-specific, bounded counts/deadlines; never retry writes after uncertain completion without evidence it is safe.
- **Durable writes.** Preserve FATX metadata/data write-through and flush ordering on `IRP_MJ_FLUSH_BUFFERS`, including device cache flush support and error reporting. A successful write alone does not prove crash durability.
- **DVD is distinct.** Read-only sector size, TOC, READ CAPACITY, TEST UNIT READY, media insert/eject/change, sense and no-media behavior need optical tests. Do not assume HDD policy applies.
- **Small residency.** Boot-only discovery/probe code should be eligible for INIT discard. Persistent device structures and lookaside pools must be measured, allocation failures handled and hot code kept resident where justified. Link-time garbage collection does not establish page reclaim by itself.
- **No xemu shortcut in firmware.** Platform and on-hardware contracts remain generic Xbox hardware behavior. Emulator-specific knobs are strictly test harness controls.

Full [ABI and request-state specification](ABI-CONTRACT.md) and [test plan](TEST-PLAN.md).

## 5. Implementation stages and explicit exit gates

**A. Preparation (this draft PR, no firmware behavior changes).**
- [x] Define dependency closure, test/provenance design, file map.
- [x] Add an optional read-only build-link/symbol sentinel and its host regression tests.
- [ ] Independently confirm source attribution and actual live byte/RAM/page footprint from exact release artifacts (not KLOC).
- [ ] Approve implementation-neutral specification.

**B. Contract capture and fail-first fixtures.**
- [ ] Capture current and reference public ABI behavior without supplying implementation code to authors.
- [ ] Add native probes for raw HDD sector, disk control, optical TOC/media and async transfer edge cases.
- [ ] Record expected return `NTSTATUS`, `IoStatus.Information`, IRP pending, APC/event order, bytes and lower SRB commands.
- [ ] Pin input images, overlays, xemu/BIOS/fixture hashes; keep original/independent behavioral baselines.

**C. Shared transport implementation (not linked to product).**
- [ ] Independently implement `nxstorage.h`, `request.c`, `sense.c`, `control.c` and bounded host harness.
- [ ] Verify allocation failures, delayed/inline child completion, cancellation, retry, unmap, and status ownership in isolation.
- [ ] Add ordered Roswell patch and lock hash; do not enable candidate in release.

**D. HDD parity, internal partial-lab prototype (NOT yet compliant).**
- [ ] Add new HDD class FDO and dispatch (names preserved), geometry and required IOCTL contract.
- [ ] Validate raw sector, partition discovery, FATX file and save paths, repeated opens, write/flush.
- [ ] Enable a **partial-lab-prototype** only in internal diagnostic builds; at this step the optical driver may still depend on old ClassPnP, so do **not** claim the incompatible code is absent. Final `complete-candidate` unlinks both old class archives only after HDD **and** DVD paths are independent.

**E. DVD parity.**
- [ ] Adapt `nxcdrom` to new transport and remove all ClassPnP callbacks/helper references.
- [ ] Verify XISO mount, TOC, capacity, READ(10), no-disc, media change, errors, high-offset reads.
- [ ] Run long/async streaming tests; compare no extra worker/packet allocations.

**F. Full end-to-end cutover / license and performance gate (complete-candidate only).**
- [ ] Default to candidate only after 64 MiB parity, then all released 128 MiB and upper-RAM-reserved profiles; test 64/128 checked variants as applicable.
- [ ] Validate actual **link command**, COFF/LTO native+inline source attribution, data and header closure. No MS-PL retained function bodies; independently resolve the 22 SDK/DDK helper identities. Test script alone cannot certify this.
- [ ] Reproduce firmware `flash.bin`, bootable xemu startup, storage and title suite. Validate release flash-size, peak/resident RAM and code-page layout against baseline.
- [ ] Full notices/license text and complete corresponding source, including pinned patches/toolchain, independently reviewed.
- [ ] Remove old `classpnp` and `disk` target references only after complete candidate passes. Do not claim GPL compatibility until provenance/legal review concludes.

## 6. Review and rollback

This is **one implementation PR (#248)** with small, reviewable commits and checkpoint reviews inside that PR. No additional implementation PRs. Do not combine deep filesystem, memory-manager or ATA rearchitecture with the class-driver rewrite. Candidate and legacy are separate firmware builds until cutover; the public BIOS stays unmodified while any parity check fails. Keep the old GPL-incompatible code in historical source/patch archives only as required by source-distribution obligations; *not* linked into the new shipped image, and do not erase its original notices.

This PR now contains the complete class-layer replacement and a bootable
candidate whose exact link excludes the legacy class archives. It does not by
itself resolve #245: the remaining performance, physical-hardware,
corresponding-source, and independent provenance/legal review gates in
`IMPLEMENTATION-CHECKLIST.md` still control promotion.

Related: [provenance protocol](PROVENANCE.md), [ABI contract](ABI-CONTRACT.md), [qualification plan](TEST-PLAN.md), [storage compliance issue #245](https://github.com/Mainkill1/SpiritBoot/issues/245), [documentation PR #246](https://github.com/Mainkill1/SpiritBoot/pull/246).

Final replacement source inventory: [compiled-unit and function-group license map](COMPLETE-CANDIDATE-LICENSE-MAP.md).
