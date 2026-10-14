# Storage replacement qualification and performance plan

**Single-PR rule:** all code, measurement infrastructure, test results and fixes live in [PR #248](https://github.com/Mainkill1/SpiritBoot/pull/248); see [the executable checklist](IMPLEMENTATION-CHECKLIST.md). These are internal milestones, not separate PRs.


**All expected values are evidence-dependent.** No new BIOS or runtime measurements were produced for this preparation PR. This document is a checklist and experiment specification, not a pass report.

## 1. Identity, candidate isolation and comparison order

Record the exact SpiritBoot product commit, pinned Roswell base and assembled `source_tree`, applied patch SHA-256 list, `flash_sha256`, `xemu_sha256`, toolchain revision, guest XBE/ISO hash, EEPROM hash, HDD/ISO seed hashes, overlay identity, memory profile and whether tracing is off. The established v1.0.0 release identities are in `README.md` and issue #245.

For each test use **independent, identically seeded overlays** and the same emulator/toolchain, CPU/GPU configuration and guest workload. Never reuse a mutated HDD overlay across BIOS candidates. Preserve complete serial/TAP output and count executed/failed assertions. Treat aborted runs as failures, not passes. Repeat on fresh process startup when testing teardown and warm-reset behavior.

Three important comparisons:
1. Known old SpiritBoot BIOS: regression/delta (does not prove retail correctness).
2. Independent public/Complex reference, where legal and available: behavioral reference, not implementation source.
3. Candidate new driver: exact public contract and host-owned test data.

Retain both pass/fail status and **performance evidence**; compile success alone is not an acceptance criterion.

## 2. Host tests (no xemu necessary)

Execute product host suite:

```sh
python3 -m unittest discover -s tests/host -v
```

This includes the preparation-PR migration sentinel's synthetic unit tests. The assembled Roswell source (obtain from `build.json["source_directory"]`) contains additional targeted tests. Current examples to keep passing, when their dependencies are present:

```sh
python3 "$GUEST_SOURCE/tests/host/storage-completion/check.py" \
    "$GUEST_SOURCE" /tmp/spirit-storage-completion
python3 "$GUEST_SOURCE/tests/host/dma-lifetime/check.py" /tmp/spirit-dma
python3 "$GUEST_SOURCE/tests/host/fatx/check-async-read.py" \
    "$GUEST_SOURCE" /tmp/spirit-fatx-async-read
python3 "$GUEST_SOURCE/tests/host/cache/check-writeback.py" /tmp/spirit-writeback
python3 "$GUEST_SOURCE/tests/host/xdvdfs-read-completion/check.py" /tmp/spirit-xdvdfs-completion
```

Fixture harnesses must execute **the actual production candidate functions**, not a second, independently guessed algorithm that simply passes its own tests. Include sanitizers where supported by host compilation. Add `tests/host/nxstorage` to the next Roswell patch for these failures:

| Category | Required cases and assertions |
| --- | --- |
| Decode/bounds | start=0; last valid sector; first OOB; zero-length; overflowed end; negative/wrapped offset; misalignment; short buffer; 28-/48-bit LBA boundary where supported |
| Transfer segmentation | exact max transfer; max+one sector; alignment/bounce boundary; MDL across page; fragmented virtual pages; PRD full; multi-command completion with exact offset and checksum |
| Completion | inline successful; pending completed later; immediate lower error; pending lower error; partial transfer; duplicate/later callback attempt; delayed child after issuer exits |
| Lifetime | parent/child refcount, reused pointer/generation, resource lease, failure before IRP submitted, failed child allocation, failed mapping, teardown races |
| Retry | busy/resource exhaustion; timeout; no media; write protected; media change; retry budget exhaustion; no unsafe reissue of uncertain writes |
| Cache/durability | write then flush; failed write followed by flush; metadata write ordering; actual device cache-sync failure, no false success |
| DVD | TOC undersized/exact buffer, format, media removed/injected, READ CAPACITY and READ(10) across end of disc |

Every lifetime test must verify allocation balance, exact IOSB bytes/status, no double completion, no stale MDL/unmap, no resource held on early error.

## 3. Native/homebrew XBE qualification

These fixtures are owned and synthetic and may alter the test HDD. Never run on the only copy of user data.

| Current owned fixture | Proven earlier behavior to preserve | Candidate expectation |
| --- | --- | --- |
| `tests/xbe/storage-contract` | 48 assertions for read-only flush, size cap, negative request, free space/EOF preservation | 48/48 on candidate, against reference; no weakened assertions |
| `tests/xbe/fatx-async-lifetime` | 7,833 assertions; concurrent issuers/APC/IOSB, close/truncate/delete with I/O outstanding | 7,833/7,833; matching one APC/read and normal exit |
| `tests/xbe/save-path-separators` | 34-check standalone reproduction for DOA path normalization | 34/34; double-separator success, triple and root cases rejected |
| `tests/xbe/sg-performance` | scatter/gather behavior and lower-driver path | Same exact data, statuses, no buffer lifetime regression |
| `tests/xbe/write-performance` | write/flush path | No data-loss regression and controlled timing |
| `tests/xbe/storage-class-contract` (new) | raw device and transport ABI independently observed | HDD/CD geometry, major functions, errors, media behavior |
| `tests/xbe/interrupt-public-abi` + `thread-irp-identity` | ISR/APC identity and IRP lifetime | no ownership/notification regression |
| Existing XDVDFS / FATX / cache host tests in firmware CI | filesystem correctness | same or strictly justified corrected behavior |

The `fatx-async-lifetime` fixture requires its documented **throttled** QMP setup to make pending I/O observable. Do not use throttled runs to claim performance. Test real error/status paths with deterministic fault injection where possible.

Add native `storage-class-contract` probes **before** enabling the candidate. Separate by:
- HDD open/close/read/write/flush, Partition0 and Partition1–N, raw capacity and seek beyond end.
- `IOCTL_DISK_GET_DRIVE_GEOMETRY[_EX]`, `GET_LENGTH_INFO`, `STORAGE_GET_DEVICE_NUMBER`, required partition queries and unsupported/undersized buffer statuses.
- Sector-level checksums at first/last sector of every partition with disposable images, no writes to reserved sectors except deliberate fixture.
- DVD drive open/close, no-disc state, tray/media transitions, TOC, READ CAPACITY, read-only rejection, full and final optical sector, repeated mount.
- Immediate/pending error, APC count, event order, IOSB initialization, exact bytes, cancellation by issuer exit.
- Write–flush–reset–reopen persistence, both graceful shutdown and emulator abrupt stop (separately classified).

## 4. Boot/integration and game compatibility

Do not conflate firmware size, boot progress, filesystem mount and in-game behavior. Require all:

1. Product host suite and assembled-source host suite.
2. Release64 (512 KiB ROM-backed kernel), debug64 as supported, release128 (256 KiB), debug128 (512 KiB), and upper-64-RAM-reserved variant when supported.
3. Cold and warm boot, EEPROM/HDD independent copies, HDD and DVD enumeration, dashboard XBE or test XBE load, FATX partitions and XDVDFS.
4. Complete public API regression and both supported XISO suites, plus focused save and async fixtures.
5. Operator-gated title journeys: DOA Xtreme create/save/reset/reload; Forza Motorsport world streaming; Halo and Halo 2 first playable/menu transitions; Conker load/scene transitions. Save checks must compare files after guest-visible flush, not just host QCOW2 L2 cache before a host backend flush. Game-specific content must not be committed to repo.
6. Independent physical Xbox test once available: revision, HDD model/LBA48, optical drive model, IRQ/DMA, PIO fallback, cold/warm reset, sustained read/write. **xemu success is not physical hardware qualification.**

Record per-profile `flash.bin` size, kernel PE and compressed payload bytes, boot INIT discard, page residency, pool allocations, unresolved external symbols and boot fatal codes. Do not silently increase persistent RAM to shrink code.

## 5. Performance benchmarking

Use the existing controlled FATX read replay (two 1,024-read datasets with queue depths 1/4/12, normal and 900-page-pressure configurations; `docs/optimization/FATX_DIRECT_ASYNC_READ.md`). The earlier direct-read candidate improved worker scheduling but still trailed Complex; those values are **previous-version observations**, not current baseline targets. The composed current baseline also contains the IRP-owned FATX lease / no extra per-read context and conditional idle completion-clock optimizations; do not reintroduce these costs. The existing legacy `storage-completion` host test extracts the original ClassPnP `TransferPktComplete`; it is **baseline-only**, not candidate proof.

Metrics to collect independently from correctness runs:
- p50/p95/p99 and total guest completion latency for device sector reads/writes; queue delay, SRB submit-to-completion and parent IRP overhead separated by phase.
- Number of calls to `IoCallDriver` per logical request, max outstanding child IRPs, mapped pages and PRD descriptors.
- Per-request allocations/frees, DMA bounce copies/bytes, status retries, wasted worker hops, context-switch counts.
- CPU core utilization, xemu main/vCPU threads, guest title frame-time p50/p95/p99, GPU utilization where relevant.
- Hot/cold kernel pages, flash bytes attributable to prior/new driver with compiler/linker source attribution; peak + resident RAM by subsystem.
- HDD throughput at queue depths 1/4/12, DVD sustained streaming and concurrent read with GPU load, write–flush latency/durability.

**Measurement contract before implementation:** pin exact baseline ROM/source/build and emulator/media identity; first run A/A (the baseline against independent instances of itself) on Steam Deck and separately i9-12900K. Freeze workload/caching/power controls, validity rules, minimum run count, metric thresholds and comparison method after A/A but before candidate results. Five independent paired runs are only a noise pilot; predetermine a suitably powered confirmatory sample size rather than continuing until results look favorable. Alternate/randomize independent A/B pairs and treat each run/pair as a statistical unit; individual reads/frames from the same run are correlated. Capture cold-ish and warmed guest/host caches separately: independent QCOW2 overlays do not guarantee a cold host cache. Instrumented diagnosis and uninstrumented acceptance runs are distinct.

**Decision rules proposed for calibration (not measured data):** per predeclared primary workload, one-sided upper 95% confidence bound for candidate/baseline batch or end-to-end request latency <= 1.02; corresponding lower confidence bound for throughput >= 0.98; p95/p99 upper bound <= 1.05 with independent tail/run evidence; p95/p99 frame-time upper bound <= 1.03 plus absolute milliseconds and no increased asset deadline misses. Require zero unexplained correctness/durability/queue/progress or MDL/pool regressions; no new per-request allocation, copy or upper worker hop without justification; all firmware envelopes fit and resident/peak RAM may not increase without explicit approval. If intervals overlap any rejection limit, label INCONCLUSIVE rather than PASS. Do not hide individual failed workload results behind a combined mean. The exact current release, not older 124→80 ms observations, is denominator A. Report distributions and raw measurements, not percentages from dissimilar sessions. Regressions require root cause or explicit user-reviewed trade-off.

## 6. Static dependency and provenance gates

The preparation PR adds a read-only sentinel; once real candidate builds exist:

```sh
# The link record must be the expanded *actual* linker command.
# symbols.txt must come from the exact unstripped linked xboxkrnl.
python3 tools/storage_migration_gate.py \
  --source "$GUEST_SOURCE" \
  --build-json artifacts/firmware-release/build.json \
  --link-line artifacts/storage-evidence/xboxkrnl.link-expanded.txt \
  --symbols artifacts/storage-evidence/xboxkrnl.symbols.txt \
  --mode candidate \
  > artifacts/storage-evidence/preflight.json
```

Gate requires evidence of new linked backend, preserved transport/FS libs and absence of selected `classpnp`/`disk` names from link, ClassPnP calls/imports in owned optical/new driver, and known Microsoft-derived symbol identities. It deliberately **does not** establish absence of inlined/renamed/optimized copyright material. A separate complete binary source/inline data provenance analysis, SDK/DDK permissions audit and license review remain mandatory. Include all three profile hashes/source trees and disambiguate compiler/runtime exceptions.

## 7. Merge failure conditions

**Reject candidate until resolved:**
- Any reproduced incomplete/corrupt game save, bad partition offset, unexpected write ordering, deadlocked I/O or unbounded retry.
- Missed APC/event, stale MDL/buffer access, duplicate completion, failed buffer validation or unknown ownership.
- DVD/TOC/media-change regressions, missing XDVDFS boot.
- Unexpected larger resident memory, release ROM overflow, unbounded per-request allocation, serious streaming/frame-time regression.
- Any MS-PL source body still attributed to the candidate image, incomplete helper-rights clearance, or incomplete corresponding-source/notice packaging.
- Missing paired test/provenance evidence, unsupported passing claims, or a fallback BIOS that still embeds old MS-PL code.

Passing means a separately reviewed GPL-compatible implementation is statically inside the BIOS and the source/release compliance gates have been satisfied. The preparation PR is **not** such a passing build.
