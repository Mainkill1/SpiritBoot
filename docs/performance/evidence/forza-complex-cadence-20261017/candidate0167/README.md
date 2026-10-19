# Candidate 0167 repeated release burst qualification

**The repeated 250 µs result is mixed; no overall Forza fix is established.**
The first exploratory comparison suggested gains of 21.4% and 31.8% at
783 and 900 free pages. In the consecutive A2/B2 repeat, the corresponding
changes are +12.6% and **−2.0%**. The 500 µs cases improve in both comparisons;
1 ms and uncapped cases remain close. All four SpiritBoot runs pass every
full generated-byte, canary, status/count and callback-lifetime check.

A is the release baseline BIOS `add882b6f50e9c9ae49705bb8374be5646e44ed1b72f0e2eb4b77bdedeeaf296`.
B is candidate 0167 BIOS `f4c48706403c4c0c151e58d6ce5bba0b2748830fc5d3ab1b055757b0e0a80702`.
Both use the frozen release burst XISO
`3b960e63bf8170cd1636ec471dd55aabc2083b2790f9cd3e5e7221013122382e`,
published xemu executable
`5488be40bf3c1c444b507d084c8d964f8f7d73c2a912970495cf85a4f7239564`,
and identical launcher/configuration hashes. The source fixture and analyzer
were not changed between runs. Candidate 0167 includes changes preceding
0167; this BIOS comparison does not isolate a single patch's causal effect.

## Every case, including the repeat regression

Rates are successful reads per second over the whole case, including the
outside-burst byte oracle and preparation. Each case lasts at least ten seconds
at that run's reported counter frequency. “Change” compares B to A within the
same numbered observation; A1/B1 were exploratory and not adjacent runs.

| Free pages | Budget µs | A1 | B1 | Change 1 | A2 | B2 | Change 2 | Complex reference |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 783 | 250 | 72.136 | 87.575 | +21.40% | 65.818 | 74.094 | +12.57% | 199.355 |
| 783 | 500 | 146.177 | 161.449 | +10.45% | 151.723 | 163.462 | +7.74% | 202.360 |
| 783 | 1000 | 198.756 | 200.592 | +0.92% | 199.022 | 199.271 | +0.13% | 202.439 |
| 783 | uncapped | 200.312 | 200.844 | +0.27% | 200.505 | 200.490 | -0.01% | 202.070 |
| 900 | 250 | 64.581 | 85.135 | +31.83% | 72.680 | 71.207 | -2.03% | 202.372 |
| 900 | 500 | 149.741 | 155.467 | +3.82% | 150.796 | 157.060 | +4.15% | 202.366 |
| 900 | 1000 | 198.473 | 200.683 | +1.11% | 198.384 | 199.582 | +0.60% | 202.126 |
| 900 | uncapped | 200.219 | 201.000 | +0.39% | 200.525 | 200.331 | -0.10% | 202.153 |

At 250 µs, baseline run-to-run rates move from 72.136 to 65.818 at 783 pages
and from 64.581 to 72.680 at 900 pages. Candidate rates also move substantially.
Two observations per variant do not establish statistical significance or a
stable effect size. The candidate remains far below the one-run Complex
reference at this budget. The uncapped repeat changes are slightly negative
and are retained rather than rounded into an improvement claim.

## Execution and evidence contract

A1 is the [archived baseline](../bursts/capture-manifest.json); B1 is the initial
candidate run. Other experiments, including a different candidate, occurred
between A1 and B1. A2 and B2 then ran consecutively in that order through the
same live user-session runner, with unique job IDs and isolated hash-checked
packages. No host reboot, unrelated-process termination, firmware rebuild or
fixture modification was performed for this repeat. Private disk/EEPROM state
was reused, not reset to independently hashed identical initial images. The
fixture reseeds its private generated file on each launch.

The primary repeat observations were the two 250 µs rates; all eight cases are
reported. The [manifest](capture-manifest.json) records exact run IDs, completion
times, file hashes and order. Original local requests and run 1 remain intact.
The repeat jobs each use a 240-second ceiling. Runner execution completed, but
its generic assessment reports correctness/evidence `notEvaluated` and
comparison `ineligible`; the requests did not supply framework assessment
checks. Those [A2](baseline2-runner-outcome.json) and
[B2](candidate2-runner-outcome.json) results are preserved. Correctness here
means the separate frozen fixture analyzer passed every required record and
oracle, not that the runner framework independently qualified the comparison.

`reproduce.py` revalidates all five serial logs (Complex reference, A1, B1,
A2, B2), requires exact equality with each archived summary, checks repeat
input hashes and launch arguments against the baseline, and reports every
case in [comparison.json](comparison.json). Byte validation occurs on the
console for every operation before storage reuse; serial records retain the
pass/fail counts and representative timing samples rather than payload bytes.

```sh
python3 docs/performance/evidence/forza-complex-cadence-20261017/candidate0167/reproduce.py
(cd docs/performance/evidence/forza-complex-cadence-20261017 && sha256sum -c SHA256SUMS)
```

Only owned generated-fixture serial logs, numeric summaries, sanitized request
metadata and reproduction code are archived. Environment mappings, private
network endpoints, workstation telemetry and BIOS/emulator/EEPROM/HDD/game/RAM
or snapshot bytes are excluded. The unchanged frozen analyzer and its fifteen
regression tests are in [../bursts](../bursts/).

The timing remains a synthetic caller issue loop with immediate alertable polls
and blocking 33 ms intervals, not rendering or a title replay. Its burst clock
starts **after** initial retirement; it excludes that initial polling cost.
A separate experiment is needed to time a caller budget beginning before its
first alertable wait. Neither the synthetic budgets nor any callback-issued
read chain should be treated as established title logic. These observations
qualify this fixture only; the missing-world problem remains unresolved.
