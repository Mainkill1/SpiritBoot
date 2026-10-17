# Kernel test coverage and extraction comparison

Audit date: 2026-10-15 UTC. Product inventory at `61d57c939d86e363de313ee75494debd77f9ddff`. Counts below describe distinct catalogs; they must not be added together as unique coverage or treated as freshly executed passes.

## Existing coverage

| Inventory | Scope | Evidence limitation |
| --- | --- | --- |
| Product host tests | 41 unittest modules, 480 syntactic test methods | Inventory, not a branch-coverage result; the final integrated run is recorded separately |
| Product native fixtures | 22 standalone XBE directories | Buildable fixtures are not proof of native execution |
| Assembled API regression | 100 registered groups | Groups are not individual exported functions |
| `sources/native-regressions.json` | 31 named fixtures, 5,481 declared assertions | Catalog assertions, not a fresh all-fixture pass |
| Other CI-built suites | Clean-room 23 checks; warm reboot 7; release64 ROM shadow 7; kernel performance 41 workloads | Keep correctness checks separate from timing workloads |
| `sources/xiso-suite-lock.json` | Older broad catalog: 144 executable leaves and 5 structural groups | Distinct catalog/version from later historical API measurements |
| Historical final memory results | 634 enabled API leaves, 40 kernel workloads, 2 streaming phases, 4 synchronization modes, 5 explicit exclusions | See `../provenance/remaining-memory-20261013/README.md`; prior-image results do not qualify the replacement |

Covered families include RTL/string/time routines, threads/waits/APCs/synchronization, pool/virtual memory/mappings, objects/handles, file/IRP/FATX/XDVDFS behavior, interrupts, crypto, and boot/video behavior.

The earlier export inventory lists 371 exports (337 callable, 34 data). No complete export-to-test mapping or measured line/branch coverage report was found. Therefore **all kernel implementation covered** is not an established claim. Export coverage alone would also miss internal error, lifetime and concurrency paths.

Before claiming completeness, maintain a versioned mapping from each export and each changed internal contract to its fixture, normal/error/boundary cases, exact native execution receipt, or explicit untested/excluded disposition. Unmapped entries remain visible gaps. Add targeted tests for replacement paths and fault injection as specified in [TEST-PLAN.md](TEST-PLAN.md); do not count tests of removed baseline bodies as candidate coverage.

## Current native evidence

Windows V362 qualified all 36 selected storage cases. Deck V37 completed 216 qualified captures over the same 36 cases, three cycles and two reference arms. Both arms use the existing reference BIOS; neither contains the installed replacement.

The final Deck V37 analysis is `READINESS_VETO`, with 432 paired metric comparisons and 13 case/metric combinations repeatedly outside the proposed band. There are no listed functional/context failures, but `performance_acceptance_eligible` is false. Identical-BIOS variation must be understood before interpreting a candidate delta. These three diagnostic pairs do not satisfy the planned minimum five-pair calibration. Preserve all samples, including unfavorable results.

Retained final-analysis SHA-256: `20ac60d5b6eb0b69b5f80de04f534e14fa64c28ef7c96ba12e0a0df9bd2f1591`; qualification snapshot SHA-256: `cbd8d2d99e9af2f227db7bf3b8bdf5afd7bdf26ea891d39cd9cad33f1e1f6407`.

The later [resident-recorder diagnostics](IO-PERFORMANCE-DIAGNOSTICS-20261015.md)
functionally qualify six of the recorder's 24 FATX leaves on the fixed
pre-extraction release64 BIOS. The ten-run queue-depth/pressure campaign passed
10,240 operations, the order-aware worker control passed 3,072, and the
raw-device ABBA discriminator passed 4,096. These overlap one synthetic dataset
and are not additional kernel-export coverage. Their descriptive timing narrows
the slowdown to both the public raw path and unequal added FATX work; it is not
the required candidate-facing, two-host, powered acceptance comparison.

## Required before/after report

Use the full protocol and acceptance gates in [TEST-PLAN.md](TEST-PLAN.md). Freeze the pre-extraction ROM and final candidate ROM, emulator, suites, configuration, workload order, and independent identically seeded writable images. Compare within each host; keep Steam Deck and Windows results separate. A new emulator build requires matched measurements for both BIOS images.

Run every supported executable leaf in both broad XISO suites, the complete API regression, and focused replacement/save/async fixtures. Record unsupported Complex cases explicitly and exclude them symmetrically from the shared comparison; retain applicable SpiritBoot-only correctness checks separately. Report executed, passed, failed, skipped and aborted counts, with reasons, rather than treating missing leaves as passes.

Report per-leaf before/after values and uncertainty for latency and throughput, p95/p99 tails, plus memory residency/peak pool, allocations, copies, queueing and CPU/frame timing where valid instrumentation exists. Include boot/load and game-streaming checks. Aggregate summaries must not hide individual regressions. Use the real emulator process for host metrics, not its PowerShell wrapper. Timing runs must exclude debugger/fault-injection overhead.

Performance qualification and the code-provenance/license audit are separate release gates. Passing tests or unchanged performance does not establish the extraction's licensing result. The full replacement, complete coverage mapping and accepted before/after performance report remain outstanding.
