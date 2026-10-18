# Candidate 0171 paired native qualification

**Generated-fixture qualification only; no overall Forza fix is established.**

**Decision: keep 0171 unselected. The 450 µs gains do not repeat.**
At 783 free pages, paired throughput changes are **+1.13% then −0.19%**, with
weighted read-return cost **−3.58% then +3.07%**. At 900 pages, throughput
changes are **+8.39% then −1.81%**, with weighted cost **−12.61% then +3.98%**.
The second pair reverses the first pair's direction at both memory levels.
The [decision record](decision.json) leaves the selected firmware lock unchanged.

Other cases are also mixed. The second pair's 250 µs throughput regresses
3.57% / 2.48% (783 / 900 pages); weighted read costs rise 10.34% / 2.44%.
The 900-page uncapped weighted cost rises 9.54%, despite a 0.95% throughput
increase. No paired weighted or per-size mean-cost regression, or throughput
regression, exceeds 20%. All values and first-size mix counts are retained
below. Correctness passes; the requested stable performance gain is absent.

Observed maxima are a separate statistic: two per-size read-return maxima
increase by more than 20%. They remain visible below and in the decision record;
the statement above concerns means and throughput only. No causal explanation
for these maximum differences is established.

| Pair | Free pages | Budget µs | Size | Control max µs | Candidate max µs | Change |
| ---: | ---: | --- | ---: | ---: | ---: | ---: |
| 2 | 783 | 250 | 512 | 540.526 | 651.062 | +20.45% |
| 2 | 900 | uncapped | 65536 | 567.790 | 709.441 | +24.95% |

The order is **0168 control 1 → 0171 candidate 1 → 0168 control 2 → 0171 candidate 2**,
with no intervening runner jobs. Each run passes all eight cases of at least ten
seconds and the full generated-byte, canary, callback status/count/identity,
non-alertable phase and buffer-lifetime oracle. Each oracle verdict was required
before advancing to the next run.

0171 changes compiler optimization on the 0168 base: only `request.c`,
`native_adapter.c` and `native_packet.c` receive trailing `-O2` in Xbox/GNU
Release builds. Source algorithms and ABI flags are preserved; 0169 and 0170
are excluded. Host and linked-code checks are recorded with the
[owned submission investigation](../../forza-native-submit-cost-20261017/README.md).
Inlining and code shape alone do not establish native performance. The final
linked build exchanges some IRQL helper call depth while inlining other real
helpers; text grows 5,216 bytes. After linked inspection, the [plan](plan.json)
was explicitly amended before launch to authorize a bounded trial of the
existing build and measure its net effect despite the offsetting calls. No
linked critical-path improvement is assumed. The plan requires repeated native
read-return and 450 µs throughput observations at both memory levels, all
regressions reported, and no unexplained regression over 20%.

## Native read entry-to-return means

Weighted cost divides the sum of all read-call durations by the number of reads,
using each run's own frequency. It excludes alertable polls, outside-pump
preparation/oracle and 33 ms blocking intervals. Changes compare each candidate
with its immediately preceding control; negative cost change is a reduction.

| Free pages | Budget µs | Control 1 µs/read | Candidate 1 | Change 1 | Control 2 | Candidate 2 | Change 2 |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 783 | 250 | 122.276 | 105.238 | -13.93% | 104.499 | 115.301 | +10.34% |
| 783 | 450 | 75.510 | 72.806 | -3.58% | 73.142 | 75.387 | +3.07% |
| 783 | 1000 | 73.936 | 68.201 | -7.76% | 65.421 | 70.932 | +8.42% |
| 783 | uncapped | 67.475 | 69.289 | +2.69% | 70.543 | 69.278 | -1.79% |
| 900 | 250 | 101.675 | 100.773 | -0.89% | 105.613 | 108.185 | +2.44% |
| 900 | 450 | 80.002 | 69.916 | -12.61% | 75.310 | 78.311 | +3.98% |
| 900 | 1000 | 69.512 | 66.483 | -4.36% | 70.104 | 69.596 | -0.72% |
| 900 | uncapped | 72.602 | 69.952 | -3.65% | 65.940 | 72.230 | +9.54% |

Per-size means below are **64 KiB / 512 bytes**, in microseconds. These preserve
size differences and avoid treating a different mix as a uniform improvement.

| Free pages | Budget µs | Control 1 64K / 512 | Candidate 1 64K / 512 | Control 2 64K / 512 | Candidate 2 64K / 512 |
| ---: | --- | ---: | ---: | ---: | ---: |
| 783 | 250 | 135.943 / 108.609 | 110.685 / 99.776 | 106.893 / 102.105 | 118.878 / 111.714 |
| 783 | 450 | 80.938 / 70.074 | 78.253 / 67.359 | 74.350 / 71.934 | 83.383 / 67.380 |
| 783 | 1000 | 82.402 / 65.461 | 71.996 / 64.402 | 68.129 / 62.710 | 73.421 / 68.443 |
| 783 | uncapped | 88.873 / 46.076 | 88.071 / 50.508 | 90.438 / 50.648 | 90.495 / 48.061 |
| 900 | 250 | 108.066 / 95.267 | 100.733 / 100.813 | 112.248 / 98.978 | 112.392 / 103.978 |
| 900 | 450 | 84.126 / 75.872 | 77.326 / 62.507 | 81.979 / 68.632 | 84.795 / 71.827 |
| 900 | 1000 | 78.482 / 60.534 | 69.117 / 63.846 | 70.924 / 69.283 | 76.722 / 62.470 |
| 900 | uncapped | 87.661 / 57.543 | 89.037 / 50.867 | 85.725 / 46.156 | 92.053 / 52.408 |

## Whole-case first-size mix

The frozen caller sequence alternates 64 KiB and 512-byte reads. Each
`pair_split` counts nonempty frames starting with 512 bytes; 64 KiB-first frames
are `frames - zero_issue_frames - pair_split`. These derived counts describe
request-position mix, not native queue state or a causal cost decomposition.
Per-size mean differences can be confounded by this mix; weighted cost and
450 µs throughput remain the primary observations.

| Free pages | Budget µs | Control 1 first 64K / 512 | Candidate 1 | Control 2 | Candidate 2 |
| ---: | --- | ---: | ---: | ---: | ---: |
| 783 | 250 | 103 / 165 | 135 / 133 | 125 / 142 | 116 / 152 |
| 783 | 450 | 118 / 142 | 107 / 153 | 124 / 133 | 123 / 136 |
| 783 | 1000 | 168 / 86 | 107 / 147 | 138 / 113 | 101 / 152 |
| 783 | uncapped | 254 / 0 | 253 / 0 | 250 / 0 | 253 / 0 |
| 900 | 250 | 109 / 159 | 130 / 138 | 102 / 165 | 125 / 143 |
| 900 | 450 | 134 / 127 | 129 / 130 | 109 / 148 | 133 / 126 |
| 900 | 1000 | 144 / 110 | 68 / 186 | 98 / 152 | 132 / 121 |
| 900 | uncapped | 254 / 0 | 253 / 0 | 250 / 0 | 253 / 0 |

Prefix timings cover only the first 64 requests and frame records the first 32
frames. There is no IOSB-at-return or direct lower-queue/device-idle observation.
The [0170 ordinal analysis](../candidate0170/path-mix-analysis/README.md) proves
the count identity and illustrates these interpretation limits. No new fixture
instrumentation or callback-chain reads were introduced for 0171.

## Whole-case verified throughput

Reads/s includes preparation, full byte checking and the controlled blocking
cadence. Positive rate change is higher throughput. Every case and regression
is retained, including the 250 µs cases.

| Free pages | Budget µs | Control 1 reads/s | Candidate 1 | Change 1 | Control 2 | Candidate 2 | Change 2 |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 783 | 250 | 69.731 | 74.004 | +6.13% | 74.082 | 71.439 | -3.57% |
| 783 | 450 | 151.997 | 153.707 | +1.13% | 149.321 | 149.030 | -0.19% |
| 783 | 1000 | 200.857 | 202.279 | +0.71% | 198.439 | 201.132 | +1.36% |
| 783 | uncapped | 202.217 | 201.606 | -0.30% | 199.122 | 201.410 | +1.15% |
| 900 | 250 | 77.993 | 77.719 | -0.35% | 75.062 | 73.202 | -2.48% |
| 900 | 450 | 143.326 | 155.352 | +8.39% | 148.790 | 146.102 | -1.81% |
| 900 | 1000 | 201.920 | 201.718 | -0.10% | 198.142 | 200.466 | +1.17% |
| 900 | uncapped | 202.025 | 201.611 | -0.21% | 199.172 | 201.071 | +0.95% |

The full [comparison](comparison.json) also retains initial-poll mean/max,
callback counts, later poll sums, zero-issue frames, issues/frame, per-size
call maxima. Raw serial logs retain sampled timestamps. The 250/450/1000 µs
deadlines are synthetic experiment parameters, not established title constants. The unchanged
[frozen initial-poll fixture](../initial-poll/README.md) begins timing before its
initial alertable wait and checks the deadline before every caller-issued read.
Callbacks only record completion; they issue no reads. Byte validation and
preparation occur outside the pump. Sixteen persistent buffers allow eight
prepared requests alongside up to eight awaiting completion, without reuse
of a buffer completed in that pump's initial wait.

## Identity, order and reproduction

0171 release BIOS SHA-256: `903e8a9462a5457966a1327373297a19e53a48401724db8f6c2ec15e26752f37`.

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
the consecutive order. The sanitized [build receipt](build0171.sanitized.json)
binds the release artifact and exact source tree. The manifest also binds the
[reviewed linked-code receipt](../../forza-native-submit-cost-20261017/compiler-0171/linked-summary.json)
by hash, including the scoped command comparison and offsetting helper calls.
Host and source gates do not
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
python3 docs/performance/evidence/forza-complex-cadence-20261017/candidate0171/reproduce.py
```

Reproduction verifies frozen analyzer identity, build/input/run hashes,
consecutive order and all four raw serial logs. It requires exact summary and
saved-comparison equality and prints the comparison. The frozen analyzer's
24 tests pass. Root `SHA256SUMS` binds the subtree. Original private requests,
full runner metadata and selected serial outputs are preserved outside the
product worktree at `.scratch/forza-poll-budget-o2-native-20261017/`.
The durable archive includes only owned fixture logs, numeric summaries,
sanitized metadata and reproduction code. Environment mappings, private
endpoints, workstation telemetry and BIOS/emulator/EEPROM/HDD/game/RAM/snapshot
bytes are excluded.
