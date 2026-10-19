# Candidate 0168, original frozen burst fixture

**Single successful synthetic-fixture observation; no overall Forza fix.**
Candidate 0168 improves the 250 µs point estimates by 18.3% / 12.3% at
783 / 900 free pages relative to the repeat baseline A2. Its 500 µs rates
improve by 9.8% / 10.7%; 1 ms and uncapped rates remain close. All eight cases
pass the full generated-byte, canary, callback identity/count/status and
buffer-lifetime oracle. The earlier [0167 repeat](../candidate0167/README.md)
showed substantial variation and a 900-page tight-budget regression, so this
one later 0168 run does not establish a stable effect size.

Only firmware changed from the original burst comparison: BIOS SHA256
`2d43d91ca5a4474a365e308b2117a642a94a2d7c7da6a3004409c267173680e6`,
with frozen XISO
`3b960e63bf8170cd1636ec471dd55aabc2083b2790f9cd3e5e7221013122382e`
and published emulator
`5488be40bf3c1c444b507d084c8d964f8f7d73c2a912970495cf85a4f7239564`.
The caller clock in this fixture starts after initial retirement. It is not
the separate initial-poll fixture. Other host activity occurred between A2/B2
and this observation; this is not an adjacent randomized triplet. Shared HDD,
cache and EEPROM initial states were not independently reset and matched.

| Free pages | Budget µs | A2 baseline reads/s | 0167 B2 reads/s | 0168 reads/s | 0168 vs A2 | 0168 vs 0167 | Complex reference |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 783 | 250 | 65.818 | 74.094 | 77.835 | +18.26% | +5.05% | 199.355 |
| 783 | 500 | 151.723 | 163.462 | 166.569 | +9.79% | +1.90% | 202.360 |
| 783 | 1000 | 199.022 | 199.271 | 200.158 | +0.57% | +0.45% | 202.439 |
| 783 | uncapped | 200.505 | 200.490 | 200.633 | +0.06% | +0.07% | 202.070 |
| 900 | 250 | 72.680 | 71.207 | 81.597 | +12.27% | +14.59% | 202.372 |
| 900 | 500 | 150.796 | 157.060 | 166.955 | +10.72% | +6.30% | 202.366 |
| 900 | 1000 | 198.384 | 199.582 | 199.818 | +0.72% | +0.12% | 202.126 |
| 900 | uncapped | 200.525 | 200.331 | 200.668 | +0.07% | +0.17% | 202.153 |

The candidate remains substantially below the Complex reference at 250 µs.
All rates include outside-pump preparation and byte checking as described by
the [original fixture contract](../README.md#eight-slot-synthetic-submission-budgets).
No title-specific pump deadline, callback read chaining, rendering workload or
world-streaming acceptance result is inferred.

The unique job `forza-bursts-candidate0168-release-20261017-1` completed with
an independent full-fixture analyzer pass. The [runner receipt](runner-outcome.json)
retains its separate generic assessment: execution completed, correctness and
evidence not evaluated, comparison ineligible. No generic runner acceptance is
claimed. [Manifest](capture-manifest.json) and sanitized request bind exact
input hashes, run ID and completion time. The original local request/results
remain under `.scratch/forza-burst-0168-20261017/candidate/`.

```sh
python3 docs/performance/evidence/forza-complex-cadence-20261017/candidate0168/reproduce.py
```

Reproduction validates the new observation and all three reference logs with
the frozen analyzer and requires exact archived-summary equality. It emits
[comparison.json](comparison.json), reporting every case. The archive contains
owned fixture serial, numeric summaries and sanitized metadata only; no
BIOS/emulator/EEPROM/HDD/game/RAM/snapshot bytes, environment mappings or private
endpoints are included. Root `SHA256SUMS` binds these files.
