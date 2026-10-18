# Candidate 0170 paired native qualification

**Generated-fixture qualification only; no overall Forza fix is established.**
**Decision: keep 0170 unselected. No repeatable 450 µs gain is established.**
At 783 free pages, paired throughput changes are **+4.85% then −2.38%**, with
read-return cost **−7.01% then +1.82%**. At 900 pages, throughput is **−1.97%
then +1.98%**, with cost **+2.53% then −5.29%**. The direction reverses in both
memory conditions. The [recorded decision](decision.json) leaves the selected firmware lock unchanged.

All four 250 µs paired throughput changes are positive, but range from only
+0.76% to +5.59%. In the second pair, both 1 ms and uncapped cases regress by
1.17–1.50% in throughput; their weighted read-return costs rise by 1.63–5.14%.
The second pair also has a **28.03% regression in 64 KiB mean read-return
cost at 783 pages / 1 ms**, exceeding the 20% regression threshold. No cause
for that individual regression is established here. Weighted mean cost and
throughput regressions remain below 20%, but that does not hide the per-size
result. These observations satisfy correctness, not the requested performance
gates.

The order is **0168 control 1 → 0170 candidate 1 → 0168 control 2 → 0170 candidate 2**,
with no intervening runner jobs. Each run passes all eight cases of at least ten
seconds and the full generated-byte, canary, callback status/count/identity,
non-alertable phase and buffer-lifetime oracle. Each oracle verdict was required
before advancing to the next run.

0170 changes core lock handoffs on the 0168 base; it excludes 0169's static port
binding. The [source experiment specification](../../forza-native-submit-cost-20261017/core-lock-coalescing-spec.md)
explains the preserved callback and ownership boundaries. Fewer acquisitions
alone do not establish native performance. The [recorded plan](plan.json)
requires repeated native read-return and 450 µs throughput observations at both
memory levels, all regressions reported, and no unexplained regression over 20%.

## Native read entry-to-return means

Weighted cost divides the sum of all read-call durations by the number of reads,
using each run's own frequency. It excludes alertable polls, outside-pump
preparation/oracle and 33 ms blocking intervals. Changes compare each candidate
with its immediately preceding control; negative cost change is a reduction.

| Free pages | Budget µs | Control 1 µs/read | Candidate 1 | Change 1 | Control 2 | Candidate 2 | Change 2 |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 783 | 250 | 114.514 | 107.753 | -5.90% | 104.512 | 104.051 | -0.44% |
| 783 | 450 | 76.658 | 71.284 | -7.01% | 77.340 | 78.745 | +1.82% |
| 783 | 1000 | 69.445 | 66.558 | -4.16% | 68.445 | 70.363 | +2.80% |
| 783 | uncapped | 65.081 | 65.695 | +0.94% | 65.222 | 68.572 | +5.14% |
| 900 | 250 | 97.983 | 93.087 | -5.00% | 103.024 | 104.003 | +0.95% |
| 900 | 450 | 71.990 | 73.809 | +2.53% | 80.530 | 76.270 | -5.29% |
| 900 | 1000 | 68.288 | 65.305 | -4.37% | 69.925 | 71.955 | +2.90% |
| 900 | uncapped | 67.176 | 65.346 | -2.73% | 66.100 | 67.180 | +1.63% |

Per-size means below are **64 KiB / 512 bytes**, in microseconds. These preserve
size differences and avoid treating a different mix as a uniform improvement.

| Free pages | Budget µs | Control 1 64K / 512 | Candidate 1 64K / 512 | Control 2 64K / 512 | Candidate 2 64K / 512 |
| ---: | --- | ---: | ---: | ---: | ---: |
| 783 | 250 | 117.693 / 111.335 | 109.762 / 105.739 | 108.907 / 100.106 | 108.049 / 100.044 |
| 783 | 450 | 77.785 / 75.530 | 78.542 / 64.017 | 84.830 / 69.840 | 86.271 / 71.210 |
| 783 | 1000 | 82.345 / 56.546 | 69.821 / 63.292 | 64.195 / 72.700 | 82.186 / 58.527 |
| 783 | uncapped | 85.479 / 44.682 | 87.168 / 44.221 | 88.589 / 41.855 | 92.363 / 44.781 |
| 900 | 250 | 104.008 / 91.959 | 105.786 / 80.358 | 115.913 / 90.101 | 111.705 / 96.281 |
| 900 | 450 | 75.663 / 68.312 | 75.528 / 72.091 | 84.338 / 76.722 | 79.289 / 73.252 |
| 900 | 1000 | 74.318 / 62.252 | 70.713 / 59.892 | 64.941 / 74.913 | 77.761 / 66.144 |
| 900 | uncapped | 89.761 / 44.592 | 88.918 / 41.773 | 87.364 / 44.835 | 89.466 / 44.894 |

## Whole-case verified throughput

Reads/s includes preparation, full byte checking and the controlled blocking
cadence. Positive rate change is higher throughput. Every case and regression
is retained, including the 250 µs cases.

| Free pages | Budget µs | Control 1 reads/s | Candidate 1 | Change 1 | Control 2 | Candidate 2 | Change 2 |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 783 | 250 | 71.944 | 75.013 | +4.27% | 74.788 | 75.355 | +0.76% |
| 783 | 450 | 146.579 | 153.686 | +4.85% | 147.438 | 143.928 | -2.38% |
| 783 | 1000 | 198.953 | 201.796 | +1.43% | 201.712 | 198.690 | -1.50% |
| 783 | uncapped | 199.664 | 202.971 | +1.66% | 202.139 | 199.502 | -1.30% |
| 900 | 250 | 80.111 | 84.593 | +5.59% | 77.704 | 78.610 | +1.16% |
| 900 | 450 | 154.522 | 151.482 | -1.97% | 143.580 | 146.422 | +1.98% |
| 900 | 1000 | 198.165 | 201.821 | +1.84% | 201.026 | 198.676 | -1.17% |
| 900 | uncapped | 199.080 | 201.138 | +1.03% | 202.280 | 199.244 | -1.50% |

The full [comparison](comparison.json) also retains initial-poll mean/max,
callback counts, later poll sums, zero-issue frames, issues/frame, per-size
call maxima and sampled timestamps. The 250/450/1000 µs deadlines are synthetic
experiment parameters, not established title constants. The unchanged
[frozen initial-poll fixture](../initial-poll/README.md) begins timing before its
initial alertable wait and checks the deadline before every caller-issued read.
Callbacks only record completion; they issue no reads. Byte validation and
preparation occur outside the pump. Sixteen persistent buffers allow eight
prepared requests alongside up to eight awaiting completion, without reuse
of a buffer completed in that pump's initial wait.

## Identity, order and reproduction

0170 release BIOS SHA-256: `6f672d7450e43c9b0aff7779b31a7ff993cc823e86fc62b859909a248d641f79`.

0168 control SHA-256:
`2d43d91ca5a4474a365e308b2117a642a94a2d7c7da6a3004409c267173680e6`.
All four use XISO
`8d94b0c6fa4699de29959e0bdc5ddd63b6b518ea7c65fcf22cf4da9e1f9b4630`
and published xemu executable
`5488be40bf3c1c444b507d084c8d964f8f7d73c2a912970495cf85a4f7239564`.
Launcher, configuration, arguments, memory (64 MiB) and private disk path are
identical. Only the firmware payload differs. All isolated packages were
hash-checked before submission. No fixture rebuild, firmware edit, host reboot,
game session or other runner job occurred within the four-run sequence.

[Manifest](capture-manifest.json) binds all input hashes, source request hashes,
run IDs, finished times and prior-job identities. Prior-job receipts establish
the consecutive order. The sanitized [build receipt](build0170.sanitized.json)
binds the release artifact and exact source tree. Host and source gates do not
substitute for the native measurements.

The same private HDD/EEPROM state was reused without an independently hashed
reset between runs. Only the fixture's private generated file was reseeded.
This is not a cold-cache comparison or an actual-title replay. Two paired
observations do not establish statistical significance or remove all time/order
effects. Earlier Complex and candidate observations remain context, not newly
matched controls. No fresh Complex run is needed to isolate this change.

Runner receipts preserve execution completed, generic correctness/evidence
not evaluated and comparison ineligible. The independent frozen analyzer
supplies the fixture oracle verdict. No runner-framework qualification or
whole-game performance claim is made.

```sh
python3 docs/performance/evidence/forza-complex-cadence-20261017/candidate0170/reproduce.py
```

Reproduction verifies frozen analyzer identity, build/input/run hashes,
consecutive order and all four raw serial logs. It requires exact summary and
saved-comparison equality and prints the comparison. The frozen analyzer's
24 tests pass. Root `SHA256SUMS` binds the subtree. Original private requests,
full runner metadata and selected serial outputs are preserved outside the
product worktree at `.scratch/forza-poll-budget-core-native-20261017/`.
The durable archive includes only owned fixture logs, numeric summaries,
sanitized metadata and reproduction code. Environment mappings, private
endpoints, workstation telemetry and BIOS/emulator/EEPROM/HDD/game/RAM/snapshot
bytes are excluded.
