# Single-PR implementation checklist — SpiritBoot storage replacement

> **Canonical task list for [PR #248](https://github.com/Mainkill1/SpiritBoot/pull/248).** All steps are internal checkpoints of the same PR, not separate implementation PRs. The PR description and this document are intended to be kept synchronized; when implementation updates require a change, update both. Bounded independently authored primitives now exist; the full replacement and native qualification remain unfinished.

---

Native rig correction (operator approved 2026-10-14): primary Steam Deck `10.0.0.42`; secondary Windows `10.0.7.1`, observed Ryzen 9 6900HX. Launch/control Windows graphics through the logged-in Codex PowerShell desktop pipe. Keep machines separate.

See [current implementation evidence](IMPLEMENTATION-EVIDENCE.md) for completed work and remaining gates.

## Full task contract

**Status: DRAFT / IMPLEMENTATION REQUIRED.** This is **the one PR** for the complete replacement, its tests, migration tooling, benchmarks, and release verification. **Do not open follow-up implementation PRs.** Implement in focused commits and check off the tasks **here**, with evidence attached to this PR. Preserve today's product BIOS until the *complete candidate* passes; no partial builds marketed as a compliant release.

**Goal:** independently authored GPLv2-compatible replacement for incorporated Microsoft-licensed ClassPnP/Disk storage implementation, **statically compiled into the existing `xboxkrnl.exe` within the single `flash.bin`**, including removal of `nxcdrom`'s ClassPnP dependencies. No external drivers, runtime downloads, new firmware formats, or unrelated filesystem/ATA rewrites.

**Related:** existing unresolved compliance issue [#245](https://github.com/Mainkill1/SpiritBoot/issues/245), credits work [#246](https://github.com/Mainkill1/SpiritBoot/pull/246). This PR must **not** close #245 or claim final GPL compliance until exact compiled-source provenance and rights have been independently reviewed.

## Verified baseline and scope

- Audited v1.0 snapshot: SpiritBoot `b65a3f77d9887c9285e936996eb4d286a66f540c`, Roswell `1569e2e89fb47cc72b9c704a8884f98200432bd4`, compiled source tree `3c23ea01cf43c2979c4c3ef247236e03d079f465`, release64 SHA256 `c630d22f2353d3898024d510f0b402b64bccdb331781fe7885389f73d6200853`. Re-confirm *current composed* baseline before coding.
- Audit identified 139 Microsoft sample/private-header **source function identities** with compiled native/inline representation, not 139 full files or a fraction of all BIOS bytes; additional 19 `srbhelper.h` and 3 `classpnp.h` helper identities require separate permission resolution.
- **Preserve:** I/O manager, FATX/`vfatfs`, XDVDFS, cache, `partmgr`, `mountmgr`, `atapi`, `pciide`/`pciidex`, IRQ/DMA, XBE ABI/loader, original supported physical Xbox behavior, current asynchronous FATX fast path and write-through contracts.
- **Replace:** incorporated `drivers/storage/class/{classpnp,disk}` implementations, including surviving inline/private helper bodies where required by rights review; make `nxcdrom` independent of ClassPnP.
- **Implementation source:** use independently authored/public behavioral specifications and permitted source only. No translation, rename, or reformat of MS-PL driver bodies into GPL.
- Current 64/128 debug/release CI builds the **old** driver and tests bounded independently authored primitives on the host. They do not qualify a replacement. PR remains draft.

## Architecture to build (all components stay inside the BIOS)

```text
Titles / dashboard / XBE loader
            |
        Nt*File / I/O manager
            |
        FATX / XDVDFS / cache
            |
         partmgr / mountmgr
            |
     +----------------------+
     | nxdisk | nxcdrom     |   independently implemented class layer
     | nxstorage transport  |   SRBs, lifetime, geometry, retries
     +----------------------+
            |
     existing atapi/PCI IDE
            |
        Xbox HDD / DVD
```

Maintain guest-visible names (`\Driver\Disk`, `\Driver\Cdrom`, `\Device\Harddisk0\PartitionN` and optical namespace), valid `IoCreateDriver` startup, kernel ordinals, PnP/AddDevice/start/attachment order, IOCTL/status semantics, and equivalent write durability.

**Internal checkpoints P0–P5 below are phases/commits WITHIN THIS SAME PR, not separate PRs.** Only `complete-candidate` must completely exclude the old linked libraries; an internal `partial-lab-prototype` may be incomplete but must be clearly labeled and must not be published.

## P0 — Correct integration map, clean-room inputs and deterministic gating (required before coding broadly)

- [x] Select and reconfirm the exact **current reference64** baseline composition: the [composition receipt](CURRENT-REFERENCE64-COMPOSITION.md) verifies the current lock/all 146 patches, matching assembled tree, actual PE/flash bytes, toolchain and full36 xemu/EEPROM/HDD/ISO/fixture identities. The ROM reproduces the optimized published64 hash. Final candidate/profile qualification remains open.
- [ ] Inspect the current *assembled* Roswell source and produce a caller→callee/device dependency matrix. Confirm class / disk / optical dependencies, lower SRB support, PnP, partition controls and persistent memory footprint by actual compiled attribution; the 139 count is **not** a size estimate.
- [x] **Inspect the required boot file** `ntoskrnl/io/iomgr/driver.c`: review `IopFoldedInDrivers`, entry ABI, names/order, plus `ntoskrnl/xb/devtree.c`, `ntoskrnl/xb/devnode.c` and `ntoskrnl/include/internal/nx-devtree.h`. The independently reviewed [boot audit](boot-dependency-audit/README.md) binds 25 files and 62 ranges to the actual assembled tree. This closes inspection only; P3 replacement registration and native outcomes remain open.
- [x] Define exact build states `legacy-reference`, `partial-lab-prototype`, `complete-candidate`. Add explicit backend option CLI → `tools/firmware.py` → CMake → actual linker graph → `build.json` → tests/CI; reject missing/unknown setting and **silent fallback**. Keep separate output directories.
- [x] The starting lock contained `0121` and ran through `0125a`; this PR now adds ordered patches through `0133`. Continue using the **next available** ordered Roswell filename(s); update `sources/firmware-lock.json` SHA256 without reordering/overwriting prior patches.
- [x] Produce an approved clean-room inputs manifest identifying authorship/licensing/hashes and allowed public tests/standards. Separate implementer access from legacy-source review; **do not** hand the implementer the unfiltered assembled Roswell tree, patch history, old code, disassembly, private helpers or generated old-source tests. Record any prior exposure; an AI session boundary alone is not license proof.
- [ ] Investigate/resolve rights for 19 `srbhelper.h` + 3 `classpnp.h` inlines **before** importing headers/functions, and enumerate other compiled copied/unknown helpers. Keep original notices and separate acceptable interface facts from protected implementations.
- [x] Segregate the legacy `tests/host/storage-completion/check.py` test created by patch `0108`: it extracts **old** `TransferPktComplete` source. The actual CMake backend guard permits it only for `legacy-reference`; owned production tests verify locked patch hashes and apply only new production/test paths. Independent review checked rejection of partial, complete, missing and conflicting selections. Native candidate qualification remains open.
- [x] **Fix the current migration preflight parser before promoting it to a release gate**. Regression tests must reject `-Wl,-lclasspnp`, `-l:libdisk.a`, grouped hidden `@response` files, non-nm garbage, `_TransferPktComplete.constprop.0` identity, stale/mismatched source/PE/flash evidence. Consume actual resolved linker inputs/map rather than a lenient guessed invocation; preserve `PRECHECK_ONLY_NOT_LICENSE_CERTIFICATION`.
- [x] Record an approved functional contract matrix before implementation: status/bytes/IRP/MDL/lower CDB/IOCTL/error/namespace behavior, explicitly distinguishing observed vs inferred/unknown. Host and public-XBE probes must not copy MS-PL logic.

### Completed bounded preparation, still outside candidate qualification

- [x] Independently authored request core: 44 deterministic + 8 controlled real-thread ownership scenarios; sanitizer and i386 helper checks. Native IRP/MDL/cancel/rundown adapter remains open.
- [x] Independently authored geometry composer: 13 scenarios / 6,001 checks; measured count-compatible initialized-prefix policy and remaining native parity gaps.
- [x] Narrow geometry owner adapter: 16 scenarios / 61,973 checks, independently reviewed ownership/lock boundaries and actual Xbox target assertions; compiled and linked only for the explicitly selected lab/candidate route. Bounded Deck query parity is recorded; full native parity and caller lifetime/IRQL qualification remain open.
- [x] Independent normalized cache-property encoder: 20 sanitizer fixture groups and i386 helper/ABI checks. Native metadata capture and property dispatch remain open; the raw WORD84/WORD83 validity correction is documented.
- [x] Independent cache-publication primitive: 32 sanitizer host groups, stale/duplicate/reset/generation rejection, raw-memory exclusion and linked i386 helper checks. Reviewed transaction/lifetime requirements are recorded; native producers, source guards, worker-result handoff and installed dispatch remain open.
- [x] Fresh-author [native adapter integration plan](independent-implementation/native-adapter-plan/PLAN.md), with 43 opened-input hashes checked against the isolated approved export. Boot orchestration and repeated START obligations are resolved for planning; worker publication and required upper MDL profiles now have reviewed [bounded facts](native-seam-facts/WORKER-HANDOFF-FACTS.md) and a [next-task breakdown](independent-implementation/native-adapter-plan/NEXT-NATIVE-TASKS.md). This is planning only; P1, implementation, native qualification and final provenance remain open.
- [x] Read-only baseline provenance/footprint audit: 22 SDK/DDK helpers plus five additional SCSI utilities and exact compiled occurrences are recorded. Grants/removal and native storage allocation high-water remain open.
- [x] Actual CLI/CMake missing/unknown selection and absent complete adapter rejection; real reference64/reference128/reserved128 release ROMs reproduce published hashes. Final full profile matrix remains open.
- [x] Protected PowerShell desktop pipe proof and first owned graphical guest on Windows Codex/session1; earlier direct launches remain provisional evidence.
- [x] Source-only public-API fixtures and paired-run analysis toolkit: reviewed clean DVD metadata generation, isolated Windows wrapper mock build and strict JSON/serial evidence decoding; initial toolkit checks passed 250 host tests with three skips. Corrected Deck and [Windows V27](WINDOWS-NATIVE-QUALIFICATION.md) qualify bounded byte-fill/public-query/owned-deadline/post-deadline checks; the original Windows V23 failed deadline is retained. Full P1 recorder/control/clock/calibration/count gates and native full-class qualification remain open.

- [x] Qualify the complete 36-case Deck functional matrix on the published reference64 BIOS: all 36,864 operations and 188,416 assertions passed, with raw evidence and cleanup retained in the [full36 receipt](FULL36-FUNCTIONAL-QUALIFICATION.md). This closes functional method coverage only; all rows remain performance-ineligible, Windows full36 and P1 remain open.
- [x] Qualify unchanged-fixture [post-END context collection](STORAGE-POST-END-CONTEXT.md) with the generic collector and owned final quit. The Deck pilot passes 1,024 reads/4,096 checks; its Btrfs file-identity fix and failed prior attempts are recorded. This qualifies the collection method, not A/A timing or P1.

## P1 — Performance baseline and regression decision rules (must precede major driver work)

- [x] Reconstruct and verify the current optimized reference64 product before benchmarking. The [current composition](CURRENT-REFERENCE64-COMPOSITION.md) reproduces the entire published ROM, preserving its IRP-owned FATX lease, eliminated completion context, conditional idle-clock sampling, direct-read mapping, gather-write and DMA bounce/interrupt behavior. Candidate preservation still requires its own P2–P4 evidence.
- [ ] **Run A/A first**: current baseline against independent instances of itself. Determine normal run-to-run variance separately on Steam Deck (**primary**) and Windows Ryzen 9 6900HX at `10.0.7.1` (**secondary**); no cross-machine averaging. Pin xemu/Vulkan config, host SSD, CPU governor, power/thermal policy, guest/host caches, HDD base+independent overlays and test seeds.
- [ ] Freeze *predeclared* primary workloads: aligned small HDD read QD1; both existing 1,024-read FATX sequences at QD1/4/12 and memory pressure; write+real cache flush; DVD/XISO reads; boundary split/fragmented SG. Add warm/cold-ish preparation as separate cases. Then expand to actual game streaming.
- [ ] Implement/report deterministic automated A/A and paired A/B run harness (proposed `tools/storage_perf_compare.py` + host tests): pin manifest, record all attempts/timeouts, checksums, operations completed, cache preparation, run pairs, latency distribution/throughput/tail and run-level confidence intervals; emit `PASS` / `REGRESSION` / `INCONCLUSIVE`. **Do not invent baseline numbers.**
- [ ] Use five independent pairs only as an initial noise pilot; freeze a sufficient independent confirmatory count from A/A (often more than five) **before candidate values are reviewed**. Alternate/randomize A/B, analyze pair as statistical unit; do not treat thousands of correlated operations within one run as independent samples.
- [ ] Capture full **caller issue→consumer-ready** duration and data integrity; diagnostic timestamps distinguish queue/admission, SRB preparation, command start, lower completion and APC/event wakeup. These are elapsed intervals, not exclusive CPU timing. Acceptance binaries have per-I/O tracing and expensive guest clocks **disabled**.
- [ ] Track allocations/frees, context switches/worker hops, SRB/`IoCallDriver`/IRQ counts, retries, bounce copies/bytes, queue high-water, MDL mappings, persistent/peak pool, ROM occupancy/padding and frame-time/asset-ready deadlines. No apparent speedup from fewer verified reads or flushes, skipped work or timing a shorter region.

**Proposed initial numeric release gates, to freeze or revise *from A/A calibration before implementation***:

| Gate | Candidate acceptance |
| --- | --- |
| Data/correctness/durability/lifetime | **Zero** unexplained corrupt bytes, wrong status/`Information`, missing APC, double completion, stuck I/O, leaked reference/pool or weaker flush ordering |
| Healthy small/single-segment path | No unexplained extra upper worker trip, allocation, copy, lower command or interrupt |
| Per-primary-case batch / request latency | One-sided upper 95% bound on candidate/baseline latency ratio `<= 1.02` |
| Per-primary-case throughput | One-sided lower 95% bound on candidate/baseline throughput ratio `>= 0.98` |
| Request p95/p99 latency | Upper bound on ratio `<= 1.05`, requiring enough independent run/tail samples |
| Game streaming/frame tails | No additional missing/late assets/deadline misses; proposed p95/p99 frame-time upper bound `<= 1.03` plus absolute ms |
| Memory / flash | Fit all shipped envelopes; no unapproved resident/peak RAM growth or sustained pool increase |

A result whose confidence interval crosses a limit is **INCONCLUSIVE—not PASS**. A repeatable smaller loss still needs investigation. Thresholds are proposed measurement tolerances, not permission to spend performance. Do not stop on average FPS alone or bury single-workload losses in a mean.

## P2 — Independently build the shared request engine and OWNED host tests

**Required assembled-source targets** (final grouping may change only with documented reason):
- `drivers/storage/class/nxstorage/{CMakeLists.txt,nxstorage.h,device.c,request.c,sense.c,control.c,disk.c}` (all NEW, independently authored).
- `drivers/storage/class/nxcdrom/{nxcdrom.c,CMakeLists.txt}` (adapt to remove ClassPnP, preserving permitted original-owned functionality).
- Later integrate via `drivers/storage/class/CMakeLists.txt`, `ntoskrnl/CMakeLists.txt`, `ntoskrnl/io/iomgr/driver.c` and `ntoskrnl/xb/devtree.c`.

Tasks:
- [ ] Implement small owned `nxstorage` device and SRB request context, with **explicit ownership table** per parent/child IRP, original/partial MDL, SRB, sense, buffer, lower-device ref, FATX lease, retry generation and completion state. Specify allocation, borrower, cleanup, IRQL and unwind.
- [ ] Validate 64-bit offset/end arithmetic, zero-length/OOB/unaligned accesses, sector size, 28-/48-bit LBA/CDB constraints, max transfer, PRD/SG boundaries and MDL offsets **before hardware submission**.
- [ ] Provide a simple single-SRB fast path where compatible; use **bounded iterative segmentation** for larger I/O. No unbounded recursive next-segment submissions from inline completion; avoid a heap allocation per pointer or global unbounded packet queue.
- [ ] Handle lower inline success/failure *before* `IoCallDriver` returns, pending completion, partial bytes, parent`/`child result distinction, `STATUS_PENDING`, `IoStatus.Status`/`Information`, event/APC delivery, priority boost, thread exit/cancel/close/truncate/delete and allocation failures. Exactly one parent completion; no use-after-free or double-free.
- [ ] Preserve lower `Srb->OriginalRequest`/MDL/DataBuffer alignment/lifetime, lower completion IRQL, lock/reentrancy rules. No upper class lock held over lower submission, synchronous wait or completion without proof.
- [ ] Define class-vs-lower retry ownership and total deadlines, `SRB_STATUS_QUEUE_FROZEN` recovery, reserved bounded recovery resources, queue progress under exhaustion, autosense/status mapping, lower requeue generation. Do not blindly retry writes whose completion is unknown or serialize all queue depth to one.
- [ ] Ensure real durability command chain: upper write/flush → required metadata/data ordering → cache-sync CDB → ATA hardware path/error propagation. **Pinned `SRB_FUNCTION_FLUSH` returns success without itself being the cache-sync path; Xbox/PATA FUA is cleared.** Recheck composed source and explicit test before selecting any shortcut.
- [ ] Add independently authored `tests/host/nxstorage/*` compiling the **new production functions** against deterministic lower-device doubles/fault injectors. Demonstrate 1 read → 1 write + actual flush, then queue errors/inline completions/low memory; use sanitizers on supported host builds.
- [ ] Measure new primitive path vs frozen baseline structurally and on Deck before expanding implementation. No hidden worker round trip, per-I/O clock sampling or lost existing FATX optimization.

## P3 — Integrate the first real read/write and optical vertical slice, then complete behavior

- [ ] Register driver entry points in **`ntoskrnl/io/iomgr/driver.c:IopFoldedInDrivers`**, validate `DriverEntry` ABI/order, complete driver dispatch, PnP FDO/PDO hierarchy/`BusRelations`, `DO_DEVICE_INITIALIZING` and attachment in `ntoskrnl/xb/devtree.c` and derived nodes.
- [ ] HDD: expose `\Device\Harddisk0\Partition0` and allow preserved `partmgr` to publish FATX Partitions1..N with correct layout/offset, alignment, geometry/capacity, IOCTL lengths and statuses, read/write/flush, write-protection and error paths.
- [ ] DVD: remove **all** ClassPnP direct helper/private-layout dependencies from `nxcdrom`, keep `\Device\CdRom0` and XDVDFS mount order; implement READ(10), READ CAPACITY, READ TOC, TEST UNIT READY, media-change/no-disc, sizes/unsupported IOCTLs, read-only rejection and bounded sense handling.
- [ ] Verify lower ATA/ATAPI gets equivalent commands, queues and DMA/interrupt behavior; ensure HDD and DVD sharing the controller do not suffer new head-of-line blocking.
- [ ] Label incomplete hybrid as `partial-lab-prototype` with old source still included, **not a compliant candidate**. Only `complete-candidate` eliminates both old archives and all retained incompatible implementation. Make one bootable, standalone GPL-compatible `flash.bin` in the final build.
- [ ] Run open XBE boot/sector/TOC/partition/flush native probes and focused Deck sentinel performance before completing the remaining control/error matrix.

## P4 — Existing/new compatibility, faults and real-world measurements

- [ ] Exact candidate-facing host/native tests for single/multi-SRB, all allocation failure sites, inline/pending/cancel/teardown races, low memory, duplicate callback defense, partial transfer, queue freeze/unfreeze, timeout, failed media, HDD and DVD geometry/status/IOCTL buffer sizes, power/reset/flush ordering.
- [ ] Preserve existing `storage-contract` 48 checks, `fatx-async-lifetime` 7,833 checks (documented QMP throttle **correctness only**), `save-path-separators` 34 checks, DMA/SG, cache/async/metadata/writeback, interrupt/APC and XDVDFS tests; ensure test source includes **new** candidate code rather than extracted old `TransferPktComplete`.
- [ ] Run full API and both XISO variants at milestone checkpoints, not after every small edit. Verify data byte-for-byte, status/event/APC order and stable memory/MDL pool after repeated reads/writes/resets.
- [ ] Game probes: DOA Xtreme create/save/reset/reload; Forza Motorsport scenery-streaming and asset-ready; Halo/Halo 2 boot/load; Conker scene transitions. Captures need test/run image hashes and, for streaming, p95/p99 frame milliseconds not just mean FPS. No game content committed.
- [ ] A/B on Steam Deck and Windows Ryzen independently, both with untraced release builds, identical binary/settings except class implementation, frozen run count, paired distributions, matched caches and sector bytes. Report **every** primary workload, confidence bound, errors and regression root cause.
- [ ] Run 64/128 MiB release + checked/debug and supported upper-RAM-reserved profile. Measure compressed kernel bytes vs fixed `flash.bin` envelope, linker section/page hotness, INIT discard, resident RAM and per-device high-water. Physical console IDE/DMA/optical/cache tests when available; xemu pass is not hardware proof.

## P5 — Static-license closure, final validation and merge gate

- [ ] Candidate linker inputs (including expanded response/archive transitive closure) contain **no `libclasspnp.a`/`libdisk.a`**. Validate actual retained PE native functions, optimized inline/code/data ranges, inlined SDK/DDK helper bodies, and build input grants—not just old symbol-name grep.
- [ ] Resolve or eliminate 22 SDK/DDK helper identities, five additional SCSI utilities and any other discovered uncertain source; verify GCC runtime exception, original notices and full corresponding source. Preserve old archive historical notices where required but do not ship incorporated incompatible code in final BIOS.
- [ ] Validate `build.json` backend identity/source tree, patch SHA256, PE/flash hashes, no unauthorized backend fallback, deterministic clean builds and correct 64/128 firmware memory/size.
- [ ] Run final host/native/XISO/save/game/performance matrix against the **exact** final candidate; external legal/provenance reviewer and technical code reviewer verify compiled firmware. Record any supported/unverified physical hardware scope.
- [ ] Mark ready for review only when all correctness, provenance, performance and footprint gates are PASS; do not close #245 or publish a “GPL-clean” claim on partial evidence.

## Documents and required evidence

- [Implementation map](README.md)
- [HDD/DVD/IRP/SRB contract](ABI-CONTRACT.md)
- [Performance and compatibility qualification](TEST-PLAN.md)
- [Provenance and clean-room process](PROVENANCE.md)
- This document is the synchronized single-PR implementation checklist.
- Current read-only non-certifying checker: `tools/storage_migration_gate.py` and its host regression tests.

**Definition of done:** one self-contained original-Xbox BIOS with independently implemented and verified storage class functionality, preserved behavior and saved games, no identified incompatible implementation included, full source/licensing closure, and measured non-regression on the frozen Steam Deck + Windows Ryzen workloads. No follow-up implementation PR is required or requested. The **single PR remains draft until all tasks finish.**

### Zero-domain descriptor admission correction

Patch `0133` corrects a bounded owned request-core admission defect: a valid
MDL may have original numeric domain zero. Explicit validated descriptor
presence is now separate from that address. The [fix writeup](independent-implementation/zero-domain-mdl/FIX.md)
records RED/GREEN evidence, 44 request scenarios, eight pthread scenarios and
freestanding checks. This changes an unlinked primitive, not the published
reference ROM. The 146-patch reference composition receipt remains a historical
reference identity; the current lock now contains 147 patches. Native adapter
qualification and full replacement remain open.
