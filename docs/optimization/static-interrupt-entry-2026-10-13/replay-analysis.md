# Static interrupt entry: untraced replay result

The static-vector candidate improves the original-xemu GPU-backed replay in every measured pressure/depth group. At depth 12 and exactly 900 free pages, mean time per 1,024 requests falls from 75.847 ms to 48.736 ms, a 35.74% reduction. Bracketed Complex averages 44.690 ms, so this candidate remains 9.05% slower than Complex on that group. This is a replay result, not a full-title frame-rate claim.

Sequence: Complex / async4 / static / static / async4 / Complex. Each launch uses a fresh HDD overlay and the unchanged GPU-backed world fixture containing the last 1,024 requests from each of two actual driving epochs. Firmware and xemu contain no timing instrumentation for this test; no recorder plugin was loaded. QMP is used only as a timeout escape, not for hot-loop observation. All six processes exited normally; all 114 checks passed; all 72 phases produced their expected byte SHA1. All 36 pressured phases began and ended with exactly 900 free pages. Normal-mode baseline and candidate both began with 14,305 free pages.

| Pressure | Depth | Async4 mean ms | Static mean ms | Complex mean ms | Reduction |
|---|---:|---:|---:|---:|---:|
| Normal | 1 | 106.148 | 75.084 | 59.551 | 29.27% |
| Normal | 4 | 81.235 | 54.684 | 47.372 | 32.68% |
| Normal | 12 | 76.051 | 48.925 | 44.979 | 35.67% |
| 900 pages | 1 | 97.477 | 73.193 | 56.260 | 24.91% |
| 900 pages | 4 | 82.008 | 56.272 | 46.392 | 31.38% |
| 900 pages | 12 | 75.847 | 48.736 | 44.690 | 35.74% |

Each mean contains four batches: two runs × two distinct recorded request sequences. No formal statistical confidence interval is claimed from these repeated sequences. The improvement is much larger than the spread and appears in all 24 paired phase comparisons, while bracketed Complex results remain stable enough to rule out a wholesale host-speed shift.

## Cause and limits

Prior fully accounted RDTSC capture identified about 4.9–5.2 ms/1,024 in the interval containing the channel active-slot bitmap store, compared with about 0.05 us for an ordinary private bitmap store. Native address capture proved the channel bitmap and executed KINTERRUPT DispatchCode share physical page 03baa000, while the request-status store is on a different page. Original xemu code routes stores to translated-code pages through its code-write slow path. In the Xbox system build, tb-maint.c disables the byte-range overlap test under XBOX and invalidates all translated blocks on that physical page. The completion bitmap write therefore invalidates the IRQ stub despite their disjoint byte offsets; its next invocation needs translation again. This corrects the earlier scan-only interpretation, which missed the XBOX conditional. See IRQ-CODE-PAGE-MECHANISM.md for exact source evidence.

The candidate routes each PIC vector through immutable kernel code while retaining native interrupt objects, callback/IRQL/PIC behavior, and existing object lifetimes. This causally removes executable stubs from the shared mutable pool page. The ~27 ms replay gain exceeds the single ~5 ms isolated bitmap interval: other writes to that shared page can also avoid slow handling. A matched diagnostic pair is planned to test the individual interval on async4 with/without the static-vector patch. Until then, do not attribute the entire gain to the single bitmap instruction.

No extra resident page was added: owned PE sections retain their addresses and rounded size, despite +516 code bytes and +64 data bytes. The independent review and 2,236 actual-function host checks are in REVIEW-STATIC-IRQ.md. Parent also qualified real public NV2A ISR/DPC/disconnect behavior separately.

## Reproduction and exact artifacts

- Baseline ROM: 368495b92eb15be75b39adfb692285d8683066ed1a7ef5fd4e4792b9b26d1803; async4 source tree 520914d4e614d185a00ca70d29b74b4d6fe58d76.
- Candidate ROM: 913293b4a86eac808313555867aa3099aba40903cc17a63c3c424b89a5c5dd77; source tree 6108cf4b697353bada1f9fa9df923db9d84054a8.
- Original xemu: cd4cfd696aa9c196cf44fd35765e16cf662afc16a689e1af4584fa79398784db.
- GPU fixture: d678cf5a013b41f3a945411a2cb09c69b36a3f0ca37de3a9a34474b8137de0fa.
- Base HDD SHA256: 358f800749beeae20d376eacf48db7285faf7d426fe5c3a72a057ef013a657e7.
- Launch script: run-irq-static.ps1. Scheduled task CodexStorageIRQStatic20261013 completed 0.
- Raw receipts: evidence/storage-irq-static-stock-*-20261013-142935-*.
- Parsed validation and all phase values: irq-static-results.json; regenerate with analyze-irq-static.py.

## Follow-up attribution

The matched RDTSC pair is complete: completion bitmap mean5.025→0.124ms/1024 and actual IDT entry moves off shared physical page while pool addresses stay identical. Submission channel stores were already cheap, so they do not explain the entire27ms gain. Full counts, quiet/disturbed accounting and clocks are in IRQ-MATCHED-ATTRIBUTION.md.
