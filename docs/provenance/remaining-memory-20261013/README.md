# Remaining issues and final memory performance sweep

The candidate fixes every remaining enabled API correctness failure from the
original full-XISO comparison. All 47 final Windows runs validate: candidate and
Complex each pass 634 ordinary clean checks; the previous candidate passes 632.
The same five Complex/lab exclusions remain explicit. Seven focused candidate
probes add 1,448 passing assertions. This is public ABI and benchmark qualification;
release publication still requires the user's gameplay/save/reset checks.

## BIOS behavior and fixes

| Path | Previous SpiritBoot behavior | Selected behavior |
|---|---|---|
| Public process/threads | Empty process list; new threads missed process priority | Title threads link before creation callbacks, inherit priority, preserve increments/saturation and unlink after exit callbacks |
| System-data allocation | Clears every data page despite uninitialized public semantics | Takes the same physical frames without the data clear; page-table and VM zeroing remain required |
| Address validity | Entire system-memory aperture reported valid | Demand mappings follow actual present PDE/PTE state, including after free |
| Small pool | Requests near 256/280 used 512-byte blocks | Measured 272/320-byte classes preserve alignment and truthful query sizes |
| Padded modular arithmetic | Arithmetic/scratch width followed caller padding | Normalize internal modulus/base width while retaining full exponent and output/alias behavior |
| Large synchronous gather write | Temporary bounce buffer and byte copy | Pinned WB caller-page MDL, with pre-dispatch fallback; reads, async snapshots and small writes keep bounce behavior |

Focused causes and evidence: [threads](../PROCESS_THREAD_CONTRACT_20261013.md),
[saturation](../PROCESS_THREAD_SATURATION_20261013.md),
[pool](../POOL_SIZE_CLASSES_AND_REUSE_SCAN.md),
[SYSVA](../../optimization/SYSVA_MEMORY_SWEEP_2026_10_13.md),
[crypto](../MODEXP_PADDING_20261013.md),
[gather lifetime/costs](../GATHER_CALLER_MDL_20261013.md).

## Measured outcomes and limits

Final three matched triplets retain all 634 enabled API leaves,40 kernel
workloads, two streaming phases and four synchronization modes. Every CSV
contains 701 rows: every measured leaf/workload and five frozen exclusions.
The two previous process failures stay visible and are excluded from baseline
cost comparison;632 common leaf costs remain comparable.

| Workload | Previous candidate | Combined candidate | Observation |
|---|---:|---:|---|
| SYSVA 16 pages |56.379 us |21.966 us |61.0% less time |
| SYSVA 4096 pages |11.301 ms |2.868 ms |74.6% less time; Complex 2.782 ms |
| Padded 512 word exponent 1 |349.662 ms |0.196 ms |99.94% less time |
| Even-modulus API leaf |14.165 ms |0.235 ms |98.34% less time |
| Common 632 API sum |12.446 s |12.345 s |Overlapping ranges; mean 12.431 s→12.402 s |
| Complex/common API sum |17.200 s |12.345 s |28.23% shorter observed aggregate |

Large SYSVA gains also repeat across seven independent matched triplets. Two
seven-pair gather cohorts repeat a roughly 14% improvement for 2 MiB writes.
The minimal pool classes save one physical page at boot and two later pages in
every one of seven matches. Padded 512 word scratch shrinks 10248→28 bytes.
Permanent 64 MiB image RAM remains 14 pages/56 KiB; image, ROM and discard-page counts
remain 140/93/33. Diagnostic state is compiled off. Gather bounce avoidance is
structural; its net native peak-RAM saving has not been measured.

All results, including slower observations, remain published. Against the prior
candidate the API rows classify 38 lower/disjoint,46 higher/disjoint,548
 overlapping; including supplementary workloads: 49 lower,50 higher,595
 overlapping. Three-pair ranges are descriptive, not significance tests.
Notable slower leaves are file flush 1.769→2.811 ms, file-object checks 1.713→2.569 ms,
concurrent scatter 1.859→2.182 ms and no-access commit 0.507→0.657 ms, all three-pair
ranges disjoint. Small-file reopen 22.978→27.397 ms, DES3-CBC 9.849→10.682 ms and warm
object 64 costs rise with overlapping ranges. Pin 1/16 regress 0.096/0.545 us;
large pins overlap. Streaming and synchronization elapsed ranges overlap.
These prevent a uniform performance claim or a game/FPS prediction. A further 14-run, seven-pair gather-enabled/disabled control passes all 634
checks per run. Removing only the gather patch does not consistently remove
the earlier flush/file-object/async/VM signals: all four ranges overlap;
file-object, concurrent async and no-access commit medians are lower with the
patch. Flush is 28.1% higher in five pairs, small-file reopen 20.4% higher in six,
and the complete 634-leaf sum is 0.589% higher with overlapping ranges. These
are retained tradeoffs, not evidence of uniform equivalence. See the full
[gather control](gather-control/analysis/report.json) and all 639 rows. Only two control leaves have higher disjoint full ranges:
big-pool churn +3.56% and RC 4 plaintext key setup +5.03%; the other 632
overlap. All 21 control gate tests pass; no outliers are discarded.

The first crypto layout was rejected after unrelated controls slowed; the
revised layout retains the arithmetic gains and overlapping DES/SHA ranges in
its seven-triplet cohort. Placement causation is not proved. Complex's seven
pre-existing high-base modular arithmetic discrepancies are retained: both
SpiritBoot versions match the independent mathematical oracle. These failures
are not labeled unsupported or hidden in timing aggregates.

## Rejected proposals and remaining memory opportunities

The empty-pool count index eliminates most scans but slows common 64/280-byte
alloc/free batches 9.73%/9.58% in all seven pairs. Keep the existing compatible
head and fallback scan. PFN batching 4096 lock acquisitions→256 does not improve
measured SYSVA throughput and regresses a small pin control; it is excluded.
Only the simpler raw-data semantics and mapping-validity fix are selected.

The final [resident-memory/lifetime audit](../MM_FINAL_MEMORY_SWEEP.md) finds no
justified immediate permanent metadata or thread-size reduction. Supply
links/owners/pins already cost 24 pages on 64 MiB; pool metadata adds three release
pages. ARM 3's full PFN database is already replaced by one shared backing frame.
Workers return all 128 stack pages and retire all 32 objects in the census.
The largest observed synthetic retained-empty-pool envelope is 320 KiB and is
already reclaimable under pressure. Metadata packing could theoretically save
one 4 KiB page, before code/state costs; narrower pins or ABI views lack a valid
proof. Better compression alone does not free the reset-persistent reservation.

Prioritized next measurements:

1. Separate cold/warm small SYSVA costs and test selective TLB invalidation.
   The almost-warm path reads one PDE/PTE but reloads CR 3 twice per alloc/free;
   its roughly 5–6x Complex gap is not yet attributed among lock/TLB costs.
2. Measure sustained memory pressure: empty pool retention, owner-zero supply,
   pins/deferred returns, spills and relocation. Require an actual lifetime or
   pressure problem before changing reclamation policy or metadata.
3. Bound pathological supply failure/rollback and measure its outer transaction.
   A single bulk rollback scope reached roughly 3 ms; splitting PFN returns alone
   cannot shorten the outer SYSVA lock's DISPATCH_LEVEL lifetime. Counts alone
   do not establish scheduler/DPC latency or a speed benefit.
4. Investigate remaining cached I/O, small flush, pin translation, SHA/DES and
   full-width modular arithmetic with isolated work attribution. Keep exact
   data/cancellation/APC/event/position/EOF and mapping semantics.

## Reproduction and review

Unzip [evidence.zip](evidence.zip) into this directory. It contains owned serial,
launch/exit/input/config receipts, source-host logs and deterministic old/fixed
DMA-model reproductions; no HDD/game/proprietary BIOS/MCPX/EEPROM contents.

```
python3 analyze.py results analysis qualified-build.json \
  c630d22f2353d3898024d510f0b402b64bccdb331781fe7885389f73d6200853 \
  3c23ea01cf43c2979c4c3ef247236e03d079f465
python3 test-analyze.py results qualified-build.json \
  c630d22f2353d3898024d510f0b402b64bccdb331781fe7885389f73d6200853 \
  3c23ea01cf43c2979c4c3ef247236e03d079f465
```

The gate validates 47 nonoverlapping interactive 64 MiB runs, alternating triplet
order, exact firmware/XISO/emulator/EEPROM/HDD hashes, frozen launch configs,
TAP identity/order/status, checksums and every workload. Twelve corrupted or
incomplete evidence variants reject. The final rebuilt source differs from the
four-profile build snapshot only in the host DMA cache model; all nine reviewed
runtime files and the 64 MiB ROM are byte-identical.

Independent integration review found no remaining correctness/mechanism blocker.
It reproduced both fixture defects with separate and crossing PDE allocation
layouts, verified the corrected 115 source cases and independently recomputed
all final rows/receipt hashes. Its shell lacked 32-bit libc headers, so it did not
substitute 64-bit tests for an independent 32-bit sanitizer rerun; separate
implementer 32-bit sanitizer evidence remains retained. Product tests:134pass,
three existing skips,137total. Local source and four-profile firmware builds
pass. The independent seven-pair control is complete. Current-head CI remains the
merge gate; no release tag or publication is made.
