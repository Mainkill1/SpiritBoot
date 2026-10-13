# Matched RDTSC attribution after static interrupt entries

The matched diagnostic confirms that the completion bitmap cost disappears when the executed interrupt entry leaves the shared pool page. The interval containing the successful-completion bookkeeping and channel bitmap clear falls from 4.792–5.450 ms per 1,024 reads (mean 5.025 ms) to 0.119–0.131 ms (mean 0.124 ms). This is a 97.5% interval reduction, independently timed with guest RDTSC and calibrated against the Xbox PM timer outside each phase. It supports the mechanism behind the untraced replay's 35.74% depth-12/900-page improvement; it does not assign all of that larger improvement to one instruction.

Both runs contain identical instrumentation on exact async4 and async4+static-vector runtime. All 38 functional checks passed, all 24 phase byte hashes matched, and all 24,576 reads were accounted for as successful DMA completion with exactly one completion notification, accepted DPC enqueue, single-item DPC batch, and final request completion each. There were no callback filters, spurious/foreign IRQ returns, error/save-taskfile paths, retry/requeue, duplicate DPC insertions, or uncounted chains.

## Executed code versus copied bytes

Both sides retain identical data addresses in every phase:

| Object | Guest VA | Physical address |
|---|---|---|
| Request SrbStatus | c10035c4 | 03bf85c4 |
| Channel active-slot bitmap | c102d868 | 03baa868 |
| Native KINTERRUPT | c102d408 | 03baa408 |
| Legacy copied DispatchCode | c102d444 | 03baa444 |

The actual IDT entry on the baseline is c102d444 → 03baa444, so executed code shares the channel page. With the fix, the actual entry is 84002490 → 03402490, the compiled static entry for IRQ14. The old copied template remains on the channel page but is no longer the IDT destination. Thus the address metadata distinguishes executable code from merely copied bytes and rules out a fortuitous relocation of the channel allocation as the source of this pair's gain.

## Submission intervals falsify a broader initial guess

Additional narrowly bracketed submission stores were already cheap. Four blocks bracket five stores; the original completion block contains the sixth. Every added block has 12,288 observations on each side. Results below are means across twelve 1,024-read phases; they include both timestamp boundaries.

| Submission block | Baseline ms/1,024 | Static ms/1,024 | Baseline quiet observations | Static quiet observations |
|---|---:|---:|---:|---:|
| ActiveSlotsBitmap set | 0.140 | 0.156 | 12287/12288 | 12287/12288 |
| CommandFlags DMA assignment | 0.126 | 0.138 | 12288/12288 | 12288/12288 |
| CommandFlags await-interrupt OR | 0.174 | 0.177 | 12285/12288 | 12287/12288 |
| BytesToTransfer and DataBuffer assignments | 0.153 | 0.097 | 12288/12288 | 12288/12288 |

These numbers reject the hypothesis that all six channel writes each cost about 5 us. Completion is the expensive observed channel store. No runtime change to submission was proposed from these results.

Other measured spans also shrink. They are nested or consecutive sections of an intrusive diagnostic and must not be summed as independent savings:

| Span | Baseline mean ms/1,024 | Static mean ms/1,024 |
|---|---:|---:|
| PataProcessRequest outer ISR software span | 8.855 | 2.661 |
| Port completion slot lookup | 0.181 | 0.107 |
| Completion SList push | 0.308 | 0.212 |
| Completion DPC insertion | 1.072 | 0.600 |
| Request resource release | 1.017 | 0.765 |
| Port release/dispatch | 1.256 | 0.657 |
| IoCompleteRequest/class unwind | 4.976 | 3.435 |

## Completeness and disturbance limits

All per-read paths are fully counted. Quiet means the owned HAL interrupt-entry counter did not change between the interval's boundary snapshots; this is not a claim that boundary sampling eliminates every possible interruption. The entire outer ISR-software span is quiet for all 1,024 reads in nine of twelve baseline phases; the remaining three phases each include one higher-IRQ observation. All twelve static phases are fully quiet. The completion bitmap's own timing has no separate IRQ snapshot; its twelve totals therefore include the three possible baseline interruptions, which are explicitly retained. The large difference also appears in all nine wholly quiet baseline phases.

Added submission blocks independently record quiet and disturbed counts. Across baseline's four blocks there are four disturbed observations (one active-slot set, three await-interrupt ORs); static has two (one active-slot set, one await-interrupt OR). All observations remain in totals. Per-phase totals, quiet ticks, disturbed ticks/counts and means are preserved in irq-match-results.json; subsets are not normalized as whole-workload results. Device dispatch can start another queued operation, so its elapsed span includes actual submission and interrupt interference, not an isolated function's exclusive CPU cost.

Calibration frequency is 733.192–733.210 MHz on baseline and 733.199–733.221 MHz on static. DISPATCH_LEVEL clock controls (512 repetitions per kind) show mean paired-RDTSC costs 0.0334/0.0349 us; calling the kernel timestamp between a pair costs 0.1106/0.1100 us; PM timer calls cost 0.1785/0.1830 us; local byte or bitmap stores cost about 0.049 us including the pair. Raw minima and maxima at PASSIVE, DISPATCH and IDE interrupt levels are retained. No fixed observer overhead was subtracted from measured intervals. RDTSC resolution and call boundaries limit interpretation of the ~0.1 us residual; they do not explain the baseline ~5 us gap.

The instrumented runs are attribution evidence, not the performance acceptance gate. See IRQ-STATIC-REPLAY.md for the original untraced six-run comparison. The roughly 27 ms untraced gain is larger than this single ~4.9 ms saving, so further attribution of other objects/interrupt entry and completion work would be needed to explain the whole gain. Deeper original-HEAD source review corrected an earlier mechanism statement: the XBOX system build compiles out the byte-overlap guard and invalidates all TBs on the code page. Therefore the channel store invalidates the disjoint IRQ stub, and next-IRQ retranslation is a specific remaining attribution lead. Host counters or a boundary that includes translation would still be needed to quantify its share of the total gain. See IRQ-CODE-PAGE-MECHANISM.md.

## Artifacts

- Generator: make-irq-match.py, derived from the previously qualified v5 accounting protocol with four additional write blocks and actual-IDT address capture.
- Probe generator: make-irq-match-probe.py. Separate ISOs differ only in resolved private counter/function addresses and title label; request arrays and functional checks are shared.
- Exact source trees, ROM hashes and ISO hashes: irq-match-manifest.json.
- Baseline ROM: 5729831c0fec0a571d6565509e154726487c0eb52f87e0e21f77ec245bfe44b3.
- Static ROM: cf07d6d9625b871a22b788e99a0feb9d6e0ccce53d3d9e88e944d0034bdf1927.
- Run script: run-irq-match.ps1, task CodexStorageIRQMatch20261013 completed 0.
- Evidence: evidence/storage-irq-match-stock-{baseline,static}-20261013-144157-{1,2}.
- Regenerate results with analyze-irq-match.py; JSON preserves every phase and observer-control receipt.

The diagnostics add no proposed runtime optimization and are not for packaging. The parent subsequently confirmed the packaged owner-check discrepancy is inherited: unchanged PR233 base shows the same 626-pass/13-failure result on the owner-strengthened fixture; the packaged static candidate's matching source fixture passes639/639. Parent also reports packaged17+338+2071+7833nativechecks pass. Those are parent-owned qualification receipts, separate from this attribution pair.
