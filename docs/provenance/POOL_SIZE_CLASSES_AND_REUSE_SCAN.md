# Measured pool classes and reusable-page scan decision

## Question and constraint

Issues [213](https://github.com/Mainkill1/SpiritBoot/issues/213) and
[218](https://github.com/Mainkill1/SpiritBoot/issues/218) require actual page
savings and measured scan work. Smaller nominal blocks alone do not establish
a saving. A reuse index must also preserve common allocation/free latency.
Only pinned open Roswell source and owned public-API guests were inspected.
These records contain no title implementation, disassembly, or payload data.

## Environment and first census

The baseline is SpiritBoot main `7c92d97aff39446d245cf23bab9ade24248289e0`,
reconstructed source tree `694b0e2461558f6a5f7a774fd34c79bd7cdc111e`, release
64 MiB ROM `be180279642478d59bdd484abbaa3004d3efaf95a31194c838596341894c6827`.
Native Windows xemu SHA-256 is
`14777b55740706608cdfde97349eefa3d5115ece4c889679c9c8b96641a85f2d`.
The diagnostic fixture hash is
`526f278ab16a7a3a3d94dd709ebe30e4d53ec83e00ade636c17a304d379d7559`.

The existing PR223 census was ported as opt-in diagnostics. Its initial
unconditional free/query rewrites changed a normal release ROM; those
expressions are now entirely conditional, and an instrumentation-off build
reproduced the baseline ROM byte for byte. The diagnostic record is 107,232
bytes and scan counters are 552 bytes. The diagnostic kernel adds 27 resident
pages; the diagnostic guest's copied record adds another 27 image pages.
Neither overhead is present in the normal timing guest or release ROM.

The first native capture passed all 722 checks, including stable snapshot,
zero-integrity-counter, allocation conservation, and page accounting checks.
It covers actual kernel boot objects, 32 retained/retired threads, 1,024 IRP
allocation attempts, 128 reads of the owned guest image, an 18-size by
32-allocation ladder, and 4,096 subsequent allocation/free cycles. IRP
lookaside reuse means pool allocation count is not identical to IRP attempts.
No Conker or PGR2 allocation distribution was collected.

## Class choice and actual backing

The seed classes 96/192/384/768/1536 produce no boot page saving in optimistic
packing; adding 1536 strands an additional page. Offline search over measured
request-bin boundaries selects 272 and 320 as the smallest two-class set
recovering two optimistic boot pages. These results are packing lower bounds,
not an allocation-order or lifetime replay.

The production-body fixture first failed on the measured 69 retained boot
objects in the former 512-byte class: nine backing pages. With 272/320 classes
the exact allocator needs seven pages and preserves all contents. The actual
native kernel saves fewer boot pages than that bound because its allocation
order and retained empty pages differ.

The normal guest, SHA-256
`7478e1ecc3fb8e7fbbafc48a981f3ac7f6710fe028d0133e196411ec8490a7d2`,
passed all 697 checks with baseline, classes-only, count-only, and combined
ROMs. The classes-only ROM is
`01150f76b3f71c2a597ff392e86799a54903d4013a88b74f7c925a7328dfb15f`.

| Checkpoint | Baseline pool pages | Classes-only pool pages | Pages saved |
|---|---:|---:|---:|
| Boot | 39 | 38 | 1 |
| 32 retained threads | 47 | 45 | 2 |
| Threads retired | 47 | 45 | 2 |
| 64 retained IRPs | 47 | 45 | 2 |
| IRP and file work retired | 47 | 45 | 2 |
| Ladder live | 151 | 149 | 2 |
| Ladder retired | 119 | 117 | 2 |
| 4,096 churn cycles retired | 119 | 117 | 2 |

Available pages increase by exactly the same amounts; stack, image, and cache
ownership remain equal. The normal guest image is 22 pages on all four ROMs.
The class table adds four nominal constant bytes and eight free-list bytes
for the shared domain; these fit existing alignment padding. Every normal
64 MiB kernel section retains its original virtual size and consumes no new
resident image page. No frame-rate improvement is claimed.

Public usable capacities are truthful: requests 249–264 receive 264 bytes,
265–312 receive 312 bytes, and all other boundaries retain their prior
capacities. The native ladder observes request 256 changing 504 to264 and
writes/checks the entire returned capacity of every allocation.
`MmQueryAllocationSize` remains zero for these pool pointers on both ROMs;
whole-pool capacities still use `ExQueryPoolBlockSize`. Host tests cover every
request 0–2041, all class page counts/tails, both allocation domains, supplier
denial, pressure reclaim, wrong tags, double frees and link retirement.
The private opt-in header encoding is schema 4 with five class bits, preserving
all 18 class/domain values; it does not change the normal 8-byte pool header.

## Reuse scan result and rejected filter

The actual allocator already checks compatible list heads before scanning
the window, unlike the older issue 218 code sample. The baseline workload
performs 125 reuse searches among 6,385 pool allocations. Of 115 fallback
searches, 107 fail after checking all 4,096 state entries; the eight successful
fallbacks examine 559 entries total. Thus 438,272 of 438,831 entry checks are
negative searches. These are one-byte page-state lookups, not reads of each
4 KiB page's payload. The 4,096 warm churn cycles add no fallback searches,
and the IRP/file phase also adds no fallback work.

A production-body candidate maintains one compatible-domain empty count:
four bytes for shared 64 MiB operation, eight bytes with reserved upper RAM.
It preserves authoritative state checks for positive searches. The candidate
passed exact state/count equivalence, hidden compatible pages, separate
domains, supplier failure, pressure reclaim, and 10,000 retype cycles.
Native diagnostics reuse the identical original fixture. It reduces fallback
entry checks 438,831 to559 and maximum length 4,096 to76, with identical pool
backing and all 722 checks passing.

That candidate fails the common-path gate in the initial normal timing runs.
Count-only median 32768-pair batches regress about 11.4% for request 64 and 10.8%
for request 280. Request200 improves about 9%; this does not offset a regression
for other callers. Combined versus classes-only also regresses request 64 by
about 10% and request 280 by about 7%. These are exploratory single-launch
results, not a paired performance claim. The shipping source retains the
current head preference and linear fallback. The rejected candidate, fixture,
lock and native records are kept under the evidence directory.

Seven subsequent triplets alternate baseline/classes/count and
count/classes/baseline order. All 14,637 checks pass. Every repeated class
capture reproduces the one-page boot and two-page later savings, with exact
other-owner and available-page conservation. The validator pins all ROM,
guest, emulator, boot-ROM, EEPROM and backing-disk hashes, checks unchanged
emulator settings, requires every timing round, and rejects missing TAP or
wrong public capacities.

| Request bytes | Classes paired median change | Count-filter paired median change |
|---:|---:|---:|
| 64 | +1.104% | +9.726% |
| 200 | +0.338% | -11.066% |
| 280 | +0.680% | +9.575% |

Positive means slower. Each launch contributes the median of all five
32,768-pair batches; the table is the median of seven paired changes, not
individual-call latency. Class timing ranges cross zero and remain
inconclusive. One request 64 class capture regresses 12.70%; it is retained,
and no speedup or formal latency-equivalence claim is made. The count filter
regresses 64 and 280 in all seven pairs, with minima 7.47% and 7.07%; the exact
two-sided paired sign test is 0.015625 for each. That repeat confirms rejection
of the filter despite its improvement for request 200. The fixture and source
metadata cannot establish per-call p95/p99 or title performance.

Issue218 can be closed as not beneficial for these measured workloads: steady
activity adds no fallback work, successful searches already stop early, and
the measured candidate adds cost to common allocation/free paths. A future
workload with sustained hidden-empty searches would justify reopening the
index question; this result does not establish a universal allocator bound.

## Verification and sweep bounds

Final reconstructed source is
`6ae95feb5bf13252a50c52fef535ab98befd7a74`. The 64 MiB release rebuild is
byte-identical to the classes-only native ROM. Release/checked 64 and
release/checked 128 with reserved upper RAM build successfully. The repository
host suite passes 137 tests with three existing environment skips. Workflow
checks now run the census, scan and exhaustive class production fixtures.

The mixed ladder leaves 80 empty bucket pages after its peak. This is a
synthetic retained-capacity observation, not a title leak: issue 135 deliberately
retains hot backing and reclaims it under pressure. No immediate-last-free
retirement or arbitrary retention cap was added. Further pool-page bitmap
word scanning, eager retirement, and more classes require allocation-order,
pressure and lifetime evidence. The measured seed table's fragmentation
failure is a concrete reason to avoid broadening classes from intuition.

Raw receipts, serial records, diagnostics, candidate patches and class-table
analysis are in
[pool audit evidence](../optimization/pool-audit-2026-10-13/).
