# Request-position analysis of the existing 0170 qualification

**The measured 28.03% increase in 64 KiB mean return cost is not established as
an intrinsic size-specific regression.** Existing counters show a substantial
change in which request size starts each frame. This can confound per-size
means, but these data do not prove a causal explanation or a corrected
performance gain. The [original qualification](../README.md) and its decision
remain unchanged: weighted costs and 450 µs results are mixed, and 0170 remains
unselected. No new native run, fixture edit or firmware change was performed.

## Whole-case first-request mix

The fixture issues a strict sequence of 64 KiB, 512 bytes, 64 KiB, 512 bytes,
and so on. Callbacks issue no reads. A `pair_split` increments exactly when a
512-byte read is issued in a different frame from its immediately preceding
64 KiB read. Therefore every such split is a nonempty frame starting with
512 bytes, and every nonempty frame starting with 512 bytes is one split:

```
first_512_frames = pair_split
nonempty_frames = frames - zero_issue_frames
first_64K_frames = nonempty_frames - pair_split
```

This is an exact derivation from the owned fixture's counter definitions, not
an additional timing measurement. Empty frames do not create reads or reset
the sequence. A final unpaired 64 KiB read also preserves the identity.
The generator checks that first-size counts sum to nonempty frames, fit the
full per-size read counts, and cover the corresponding prefix counts. All
original fixture and summary checks run before this analysis.

For **783 free pages / 1 ms**, the whole-case counts are:

| Run | Nonempty frames | First 64K | First 512 | 64K reads that start a frame | 512 reads that start a frame | Whole-case 64K / 512 means, µs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| control1 | 251 | 174 | 77 | 17.37% | 7.68% | 82.345 / 56.546 |
| candidate1 | 254 | 116 | 138 | 11.44% | 13.62% | 69.821 / 63.292 |
| control2 | 254 | 73 | 181 | 7.19% | 17.85% | 64.195 / 72.700 |
| candidate2 | 251 | 175 | 76 | 17.48% | 7.60% | 82.186 / 58.527 |

All four cases have zero empty frames. Pair 2 changes 64 KiB-first share from
7.19% to 17.48% of that size's reads, while the 512-first share falls from
17.85% to 7.60%. Pair 1 moves in the other direction. The aggregate first-size
counts establish that the per-size populations are differently weighted by
request position. They do not identify the execution path or the cost of each
position over the full run.

## What the timed prefix can and cannot show

Each case records individual timings for only the **first 64 reads**. In this
case, those are frames 0–7, eight reads per frame, starting with 64 KiB in all
four runs. Thus the timed prefix contains eight first-position 64 KiB reads,
24 later-position 64 KiB reads, 32 later-position 512-byte reads, and **no
first-position 512-byte timing** in any of these four runs.

| Run | First 64K n / mean µs | Later 64K n / mean µs | Later 512 n / mean µs | First-64K mean excluding frame 0, µs |
| --- | ---: | ---: | ---: | ---: |
| control1 | 8 / 174.693 | 24 / 69.615 | 32 / 50.832 | 172.809 |
| candidate1 | 8 / 215.033 | 24 / 44.439 | 32 / 67.269 | 198.930 |
| control2 | 8 / 153.134 | 24 / 58.392 | 32 / 48.739 | 151.176 |
| candidate2 | 8 / 192.992 | 24 / 65.664 | 32 / 47.702 | 177.805 |

First-position 64 KiB reads are slower than later-position 64 KiB reads in
all four prefixes, including when frame 0 is excluded. This makes a
position-mix explanation plausible. Yet the same-position prefix means also
change between runs. The prefix is temporally biased, no first-512 timing is
available here, and the later frames dominate the full-case mean. We do not
extrapolate these prefix means into a claimed full-run cost decomposition.

The first 32 frame records reveal a specific parity change in control2:
frame 12 issues seven requests and hits its budget. Frame 13 therefore begins
at sequence 103 (512 bytes). Frames 13–31 continue starting with 512 bytes.
The other three runs start with 64 KiB throughout their first 32 frames.
This switch occurs after the individually timed prefix ends, so no read-level
latency after that switch can be assigned from the available OP records.

Neither the original fixture nor this analysis records IOSB state immediately
at read return, lower queue occupancy, or a device-idle transition. All sampled
return statuses are pending. `after_initial` counts fixture callbacks still
outstanding, not a direct measurement of lower storage activity. Calling the
first-position cost an “idle-start cost” would be a hypothesis, not an observed
execution path. The original weighted-cost and throughput verdict is retained.

## Complete timing and frame tables

[operations.csv](operations.csv) contains every sampled request across all
four runs and eight cases: **2,048 rows**, including size, frame ordinal,
sequence, native call duration and callback-after-return delay.
[frames.csv](frames.csv) contains all **1,024 sampled frames**, including the
entire inferred size order, issue count, initial callback counts and aggregate
read/poll durations. Inferred sizes beyond the first 64 reads follow the frozen
alternating sequence and cumulative frame issue counts; they are not new OP
observations. [analysis.json](analysis.json) retains all 32 case summaries,
whole-case derived counts, prefix counts and size/ordinal mean/median/min/max.

The following complete ordinal table covers the timed prefix of the focal
783-page / 1 ms case. Each cell is a mean in microseconds; each ordinal has
**eight observations per run**.

| Frame ordinal (zero-based) | Size | control1 | candidate1 | control2 | candidate2 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 65536 | 174.693 | 215.033 | 153.134 | 192.992 |
| 1 | 512 | 34.598 | 51.415 | 62.417 | 81.679 |
| 2 | 65536 | 85.643 | 54.082 | 83.568 | 100.460 |
| 3 | 512 | 74.271 | 88.865 | 40.969 | 36.894 |
| 4 | 65536 | 48.044 | 54.008 | 50.823 | 44.451 |
| 5 | 512 | 68.899 | 40.599 | 43.747 | 35.968 |
| 6 | 65536 | 75.160 | 25.226 | 40.784 | 52.082 |
| 7 | 512 | 25.559 | 88.199 | 47.822 | 36.265 |

The full 32-frame focal table below gives **first sequence / issue count /
first size**. A suffix K means 64 KiB and B means 512 bytes. The alternating
size order for every request ordinal is available in `frames.csv`.

| Frame | control1 | candidate1 | control2 | candidate2 |
| ---: | --- | --- | --- | --- |
| 0 | 0 / 8 / K | 0 / 8 / K | 0 / 8 / K | 0 / 8 / K |
| 1 | 8 / 8 / K | 8 / 8 / K | 8 / 8 / K | 8 / 8 / K |
| 2 | 16 / 8 / K | 16 / 8 / K | 16 / 8 / K | 16 / 8 / K |
| 3 | 24 / 8 / K | 24 / 8 / K | 24 / 8 / K | 24 / 8 / K |
| 4 | 32 / 8 / K | 32 / 8 / K | 32 / 8 / K | 32 / 8 / K |
| 5 | 40 / 8 / K | 40 / 8 / K | 40 / 8 / K | 40 / 8 / K |
| 6 | 48 / 8 / K | 48 / 8 / K | 48 / 8 / K | 48 / 8 / K |
| 7 | 56 / 8 / K | 56 / 8 / K | 56 / 8 / K | 56 / 8 / K |
| 8 | 64 / 8 / K | 64 / 8 / K | 64 / 8 / K | 64 / 8 / K |
| 9 | 72 / 8 / K | 72 / 8 / K | 72 / 8 / K | 72 / 8 / K |
| 10 | 80 / 8 / K | 80 / 8 / K | 80 / 8 / K | 80 / 8 / K |
| 11 | 88 / 8 / K | 88 / 8 / K | 88 / 8 / K | 88 / 8 / K |
| 12 | 96 / 8 / K | 96 / 8 / K | 96 / 7 / K | 96 / 8 / K |
| 13 | 104 / 8 / K | 104 / 8 / K | 103 / 8 / B | 104 / 8 / K |
| 14 | 112 / 8 / K | 112 / 8 / K | 111 / 8 / B | 112 / 8 / K |
| 15 | 120 / 8 / K | 120 / 8 / K | 119 / 8 / B | 120 / 8 / K |
| 16 | 128 / 8 / K | 128 / 8 / K | 127 / 8 / B | 128 / 8 / K |
| 17 | 136 / 8 / K | 136 / 8 / K | 135 / 8 / B | 136 / 8 / K |
| 18 | 144 / 8 / K | 144 / 8 / K | 143 / 8 / B | 144 / 8 / K |
| 19 | 152 / 8 / K | 152 / 8 / K | 151 / 8 / B | 152 / 8 / K |
| 20 | 160 / 8 / K | 160 / 8 / K | 159 / 8 / B | 160 / 8 / K |
| 21 | 168 / 8 / K | 168 / 8 / K | 167 / 8 / B | 168 / 8 / K |
| 22 | 176 / 8 / K | 176 / 8 / K | 175 / 8 / B | 176 / 8 / K |
| 23 | 184 / 8 / K | 184 / 8 / K | 183 / 8 / B | 184 / 8 / K |
| 24 | 192 / 8 / K | 192 / 8 / K | 191 / 8 / B | 192 / 8 / K |
| 25 | 200 / 8 / K | 200 / 8 / K | 199 / 8 / B | 200 / 8 / K |
| 26 | 208 / 8 / K | 208 / 8 / K | 207 / 8 / B | 208 / 8 / K |
| 27 | 216 / 8 / K | 216 / 8 / K | 215 / 8 / B | 216 / 8 / K |
| 28 | 224 / 8 / K | 224 / 8 / K | 223 / 8 / B | 224 / 8 / K |
| 29 | 232 / 8 / K | 232 / 8 / K | 231 / 8 / B | 232 / 8 / K |
| 30 | 240 / 8 / K | 240 / 8 / K | 239 / 8 / B | 240 / 8 / K |
| 31 | 248 / 8 / K | 248 / 8 / K | 247 / 8 / B | 248 / 8 / K |

## Reproduction and limits

```sh
python3 docs/performance/evidence/forza-complex-cadence-20261017/candidate0170/path-mix-analysis/reproduce.py
```

The tool uses only the already archived fixture logs and summaries. It verifies
input hashes and the frozen analyzer, reruns all original oracle checks,
checks observed OP size/sequence against inferred frame ordinals, and requires
exact equality of all three analysis outputs. `--write` regenerates those
outputs explicitly. Parent `SHA256SUMS` binds this additive analysis. The
original qualification files and fixture artifacts remain unchanged.

The derivation uses the owned [fixture source](../../../../../../tests/xbe/forza-poll-budget/main.c)
with its [frozen identity](../../initial-poll/release-identity.json). This
analysis is descriptive. It neither proves a cause for the per-size difference
nor rehabilitates 0170 as a performance improvement or a Forza fix.
