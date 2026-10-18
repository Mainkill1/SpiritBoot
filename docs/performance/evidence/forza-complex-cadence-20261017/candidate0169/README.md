# Candidate 0169 native return-cost qualification

**Correctness passes; a repeatable native return-cost gain is not established.**
At 450 µs and 783 free pages, 0169 changes mean native return time by +2.13%
then −2.09% versus the middle control. At 900 pages, both candidate trials
are slower: +1.48% and +2.88%, with throughput −0.26% and −1.35%. At 250 µs
and 783 pages, both candidate trials regress throughput (−16.44% / −4.73%).
Other cases vary in direction. These native measurements do not qualify 0169
as a repeatable performance improvement, despite its correct direct-call code
shape and successful functional checks. No overall Forza fix is established.

The run order is **0169 first → 0168 control → 0169 repeat**, with no
intervening runner jobs. Every run passes all eight cases of at least ten
seconds and the full generated-byte, canary, callback status/count/identity,
non-alertable phase and buffer-lifetime oracle. First-run correctness was
required before proceeding; the control also passed before the final repeat.
The [recorded plan](plan.json) names native `NtReadFile` entry-to-return cost
as the primary observation and whole-case throughput/poll costs as secondary.

This sequence measures the release firmware's behavior using the unchanged
[frozen initial-poll fixture](../initial-poll/README.md). It is separate from
the assembly-shape check: removing indirect calls alone is not a measured
latency gain. Two candidate observations around one control reveal variation
but do not establish statistical significance or compensate for all time/order
effects. We retain both observations and all eight cases instead of pooling
budgets or selecting only improvements.

## Native read entry-to-return means

“Weighted” divides the sum of every native read-call duration by the number
of reads, using each run's own counter frequency. It excludes the initial and
per-read alertable polls, outside-pump preparation/oracle and 33 ms blocking
intervals. Percent changes compare each candidate run with the middle 0168
control; negative cost change is a reduction.

| Free pages | Budget µs | 0168 weighted µs/read | 0169 first | 0169 repeat | First cost change | Repeat cost change |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 783 | 250 | 93.380 | 114.473 | 100.328 | +22.59% | +7.44% |
| 783 | 450 | 74.929 | 76.523 | 73.363 | +2.13% | -2.09% |
| 783 | 1000 | 65.039 | 66.362 | 66.481 | +2.04% | +2.22% |
| 783 | uncapped | 65.325 | 61.707 | 67.750 | -5.54% | +3.71% |
| 900 | 250 | 102.607 | 88.601 | 101.906 | -13.65% | -0.68% |
| 900 | 450 | 70.550 | 71.593 | 72.580 | +1.48% | +2.88% |
| 900 | 1000 | 66.220 | 64.974 | 67.541 | -1.88% | +1.99% |
| 900 | uncapped | 65.913 | 66.169 | 64.667 | +0.39% | -1.89% |

Per-size means below are **64 KiB / 512 bytes**, in microseconds. The separate
sizes avoid interpreting a changed size mix or completion timing as a uniform
native-call improvement. These are elapsed counter durations, not isolated
CPU instruction costs. Every submitted request is validated before reuse.

| Free pages | Budget µs | 0168 64K / 512 | 0169 first 64K / 512 | 0169 repeat 64K / 512 |
| ---: | --- | ---: | ---: | ---: |
| 783 | 250 | 101.549 / 85.211 | 118.262 / 110.684 | 111.808 / 88.848 |
| 783 | 450 | 80.514 / 69.343 | 80.148 / 72.893 | 77.046 / 69.676 |
| 783 | 1000 | 80.811 / 49.266 | 79.802 / 52.923 | 64.456 / 68.506 |
| 783 | uncapped | 84.574 / 46.077 | 82.598 / 40.815 | 82.850 / 52.650 |
| 900 | 250 | 110.307 / 94.888 | 94.822 / 82.364 | 101.346 / 102.466 |
| 900 | 450 | 69.868 / 71.233 | 74.427 / 68.755 | 74.649 / 70.511 |
| 900 | 1000 | 52.397 / 80.057 | 73.118 / 56.821 | 70.937 / 64.141 |
| 900 | uncapped | 84.079 / 47.746 | 82.727 / 49.610 | 85.144 / 44.191 |

## Whole-case verified throughput

Reads/s includes byte checking, preparation and the controlled blocking
cadence. It is a different quantity from native return cost. Positive change
means higher throughput; all regressions remain in the table.

| Free pages | Budget µs | 0168 reads/s | 0169 first | 0169 repeat | First rate change | Repeat rate change |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 783 | 250 | 83.467 | 69.744 | 79.516 | -16.44% | -4.73% |
| 783 | 450 | 149.144 | 149.162 | 154.233 | +0.01% | +3.41% |
| 783 | 1000 | 199.527 | 198.789 | 201.630 | -0.37% | +1.05% |
| 783 | uncapped | 199.047 | 199.757 | 202.179 | +0.36% | +1.57% |
| 900 | 250 | 77.448 | 85.570 | 77.284 | +10.49% | -0.21% |
| 900 | 450 | 154.611 | 154.213 | 152.531 | -0.26% | -1.35% |
| 900 | 1000 | 199.267 | 199.316 | 201.707 | +0.02% | +1.22% |
| 900 | uncapped | 199.604 | 199.257 | 202.130 | -0.17% | +1.27% |

The complete [comparison](comparison.json) retains initial-poll mean/max,
callback counts, per-read poll sums, zero-issue counts, issues/frame, per-size
native-call maxima and sampled operation/frame timestamps. These are synthetic
250/450/1000 µs budgets and an uncapped control; they are not established title
constants. The same sixteen persistent buffers cap outstanding requests and
per-pump issues at eight. Callbacks record completion and issue no reads.
There is no formatting or byte oracle inside the timed pump. The initial wait
consumes the same budget as subsequent caller-issued reads.

## Identity, order and reproduction

The candidate0169 release BIOS is
`c7dcfe9214d422ef0477e10a2ff552e08f6c78db0675085ad6cf88eef44a5527`;
0168 control is
`2d43d91ca5a4474a365e308b2117a642a94a2d7c7da6a3004409c267173680e6`.
All three use XISO
`8d94b0c6fa4699de29959e0bdc5ddd63b6b518ea7c65fcf22cf4da9e1f9b4630`
and published xemu executable
`5488be40bf3c1c444b507d084c8d964f8f7d73c2a912970495cf85a4f7239564`.
Launcher, configuration, arguments, 64 MiB memory and the private disk path are
identical. Only the firmware input hash differs between variants. All packages
and requests were isolated and hash-checked before submission. No host reboot,
game session, firmware edit or fixture rebuild occurred during the sequence.

[Manifest](capture-manifest.json) binds source request hashes, all payload
hashes, run IDs, finished timestamps and prior-job identities. Its prior-job
receipts establish the consecutive order. The sanitized [build receipt](build0169.sanitized.json)
binds the exact 0169 release/source tree and original receipt hash; host/source
checks are not substituted for these native measurements.

The same private HDD/EEPROM state was reused without an independently hashed
reset between runs. The fixture reseeds only its generated private file;
this is not a cold-cache comparison or an actual-title replay. Earlier
[baseline/0168/Complex observations](../initial-poll/README.md) remain contextual
references and are not treated as new controls in this sequence. The earlier
0167 variation also cautions against interpreting a single improved result as
stable title behavior.

Runner receipts preserve execution completed, generic correctness/evidence
not evaluated and comparison ineligible. The separate frozen analyzer supplies
the fixture oracle verdict. No runner-framework acceptance or overall game
performance claim is made.

```sh
python3 docs/performance/evidence/forza-complex-cadence-20261017/candidate0169/reproduce.py
```

Reproduction verifies the frozen analyzer identity, build/input/run hashes,
consecutive order and all three raw serial logs, requires exact archived-summary
equality and emits `comparison.json`. The reused analyzer's 24 regressions
pass. Root `SHA256SUMS` binds this subtree. Original requests, full runner
receipts and selected raw serial outputs remain under
`.scratch/forza-poll-budget-0169-native-20261017/` outside the product worktree.
The durable archive contains only owned fixture serial, numeric summaries and
sanitized metadata/reproduction code. Environment mappings, private endpoints,
workstation telemetry and BIOS/emulator/EEPROM/HDD/game/RAM/snapshot bytes are
excluded.
