# Conditional counter interval arithmetic

`tools/storage_counter_intervals.py` implements only the exact numerical policy
in the independently reviewed P1 clock draft
`b1d13c15ed73c9028c5d630dd365bc50b3cad4bfe9303ba890cbafeeeb14fc69`.
It does not observe or qualify a runtime clock, import historical records, perform
A/A calibration, compute confidence intervals, or accept performance.

`counter_intervals(operation_ticks, batch_ticks, bytes_completed, platform=...,
qpf_hz=...)` retains the complete ordered raw tick tuple and batch. Values must
be positive integers; malformed, zero or missing values reject the entire input.
Each operation must fit within the enclosing batch. Small positive observations
are retained, including those whose lower duration endpoint is zero.

All arithmetic uses `Fraction`. The conditional rate is 733,333,333 ticks/s.
Deck and the Windows divisible-QPF branch use error envelope `e=1/R` seconds.
Windows requires an explicit positive QPF frequency within `UINT32_MAX`; when it
does not divide one billion, the envelope is `e=1ns+1/R`. Supplying a frequency
does not prove that it was observed or that the process used that branch.
The compiled strict error bounds are conservatively represented by closed
intervals `[max(0,ticks/R-e),ticks/R+e]` without reducing the bound.

Batch latency uses that interval. Throughput divides completed bytes by the
batch endpoints in reverse order. A zero lower duration endpoint leaves the
upper throughput endpoint unbounded, represented by `None`, rather than a
finite substitute. p95 and p99 use nearest rank `ceil(n*p)`, ranking centers,
lower endpoints and upper endpoints separately. Every operation participates.
Durations are in seconds, throughput in bytes/s, and ratios are dimensionless.

`paired_interval(baseline,candidate)` retains both input intervals and bounds
candidate/baseline by the opposite endpoints. `WITHIN_BUDGET` requires positive,
finite endpoints and both relative deviations from the center to be at most
the fixed exact `1/1000`. Otherwise the whole paired metric is `INCONCLUSIVE`.
For equal Deck durations, 2,000 ticks fail this ratio budget; 2,001 ticks reach
its boundary. The Windows fallback requires 3,469 ticks in that equal-duration
example. These are arithmetic examples, not empirical precision claims.

The caller still needs the frozen host/source/provider/startup/running-clock
conditions and complete workload evidence. Future statistical bounds must
include these deterministic uncertainty endpoints; this helper computes no
statistical uncertainty. It performs no overhead subtraction, sample filtering,
float conversion or historical metadata rewrite. Its rational outputs need an
explicit lossless representation in any future importer or serializer.

The nineteen focused host tests passed after the absent helper first produced
nineteen failures. Hand-derived thresholds and reciprocal ratios, a 210-choice
quantile enumeration and 864 compiled-floor examples check the equations.
Additional cases cover huge integer deltas, infinitesimal excess over the budget,
unbounded endpoints and malformed input. Root independently reran all nineteen
tests. No native operation or clock/performance qualification occurred.

Run the focused checks with:

```sh
python3 -B -m unittest discover -s tests/host -p test_storage_counter_intervals.py -v
```
