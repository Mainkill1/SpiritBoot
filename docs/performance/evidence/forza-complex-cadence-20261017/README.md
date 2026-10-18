# Complex / SpiritBoot cadence and submission-burst baselines, 2026-10-17

**Status: comparison completed; the missing-world problem is not fixed.**
Both BIOSes pass the generated-data oracle and the same tested APC wait
semantics. Complex also exhibits callback occupancy on the roughly 33 ms frame
scale when the fixture polls at that cadence. The approximately 30 ms delay in
the earlier [Forza live capture](../forza-live-latency-20261017/README.md) is
therefore not, by itself, a signature of a SpiritBoot-specific APC delivery
bug. This fixture comparison does not measure native completion timestamps or
establish when either title publishes scenery.

The distinct baseline finding is submission cost: SpiritBoot's 512-byte
`tight-poll` submit calls take 11.1–11.7 times as long as Complex's. That is not
an elevenfold throughput difference. In these same runs, SpiritBoot's 64 KiB
tight-poll throughput is 5.7–5.8% higher, and its frame-cadence cases are similar
or faster. These are single-run point estimates, not repeated ABBA results or
proof of the real game's bottleneck. No firmware change was made for this
comparison and no performance fix is claimed. A second generated experiment
now shows that explicit 250/500 µs burst budgets reduce SpiritBoot issue counts
much more than Complex; the gap largely closes at 1 ms or without a budget.
That supports a possible mechanism, while the actual title budget and a
firmware remedy remain unproven.

## Candidate 0167 follow-up

The [separate repeated qualification](candidate0167/README.md) preserves this
baseline archive and compares two observations each of baseline and candidate.
The consecutive repeat gives +12.6% / −2.0% at 250 µs (783 / 900 free pages),
so the first-pass gains do not repeat uniformly. All byte oracles pass; no
overall Forza fix is claimed.

The [single 0168 observation](candidate0168/README.md) then improves the
original-fixture 250 µs rates by 18.3% / 12.3% versus A2, with every oracle
passing. It remains below Complex, and one observation does not resolve the
run-to-run variation.

A [separate initial-poll-budget comparison](initial-poll/README.md) now also
charges the initial alertable wait and compares baseline, 0168 and Complex.
Its contract and all eight results are archived separately; it remains a
generated workload, not a world-streaming acceptance test.

The subsequent [0169 → 0168 → 0169 native sequence](candidate0169/README.md)
passes correctness but does **not** establish a repeatable native return-cost
gain. Both 0169 trials regress the 900-page 450 µs case slightly, while other
cases vary in direction. Direct-call assembly shape is not treated as a
measured performance improvement.

The [0168 → 0170 → 0168 → 0170 paired sequence](candidate0170/README.md)
also passes all 32 sustained cases but leaves 0170 **unselected**. The 450 µs
throughput changes reverse sign between pairs at both memory levels. No
repeatable gain is established; all read-return costs and eight-case results
are retained, including a 28.03% per-size read-cost regression in the second
pair. The selected firmware lock is unchanged. The additive
[request-position analysis](candidate0170/path-mix-analysis/README.md) establishes
a whole-case first-size mix change and preserves the distinction between a
measured per-size mean difference and an intrinsic or causal regression.

## What ran

The [owned release fixture](../../../../tests/xbe/forza-callback-cadence/README.md)
creates and checks an 8 MiB generated file on private writable FATX storage.
It uses exported `NtUserIoApcDispatcher`, the actual Win32-style callback ABI,
full returned-byte validation, buffer/IOSB canaries, issuer identity, exactly-once
counts, allowed callback phases and status/count checks. Each dependent read
gets an immediate zero alertable poll. Frame cases insert a blocking 33 ms
non-alertable interval after an empty poll; tight cases keep polling. This is
a controlled wait experiment, not CPU-bound frame rendering or a replay of
actual title payloads.

Each BIOS completed all eleven TAP checks, forty controlled handoff probes,
thirty-two completion-before-poll semantic checks and eight cases of at least
ten seconds each. Every case reports zero failures and zero event-observation
`ready_misses`; entry/exit available-page counts equal the requested 900 or 783
pages. The generated payload and canary checks passed. All measured reads
returned `STATUS_PENDING` and received exactly one successful callback with the
requested count.

The final serial markers are `FORZA-CADENCE-END failures=0`. The runner's
`completed` state alone is not the correctness verdict: the archived analyzer
revalidates all required observations and the serial oracle outcomes.

## Wait semantics match

Each row below represents eight trials on **each** BIOS.

| Probe | Complex and SpiritBoot observation |
| --- | --- |
| Alertable zero delay; equal-priority peer enqueues during handoff | First call returns `STATUS_SUCCESS` with zero callbacks; callback arrives at a later alertable wait |
| Non-alertable zero delay; equal-priority peer | Same first-return result; no callback during the non-alertable interval |
| Alertable expired absolute delay 1; equal-priority peer | Same first-return result as alertable zero |
| User APC already queued before alertable zero delay | First call delivers one callback and returns `STATUS_USER_APC` |
| Alertable zero delay; lower-priority peer | First call returns success without a callback; enqueue during the first call is not established |

All eventual APCs arrived exactly once on the issuer in an allowed alertable
phase. The thirty-two I/O semantic checks per BIOS observed zero callbacks
through the completion-event wait and subsequent non-alertable interval, then
one callback with `STATUS_USER_APC` at the first alertable poll and an empty
successful drain afterward.

The equal-priority handoff result rules out the proposed explanation that
Complex necessarily rechecks a newly queued APC before returning from this
immediate-delay handoff while SpiritBoot does not. It does not qualify every
possible APC delivery path. Enqueue timestamps are recorded after the public
enqueue call returns, so negative timing observations remain conservative.

## Submission latency and whole-case throughput differ

These are means over all successful operations. `Submit` measures public
`NtReadFile` entry to return; `Callback` measures submission to callback entry.
Throughput includes buffer preparation, full byte/canary validation and polls
between requests. These quantities answer different questions.

### Tight polling

| Free pages | Read bytes | Complex submit µs | Spirit submit µs | Complex callback µs | Spirit callback µs | Complex reads/s | Spirit reads/s |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 900 | 512 | 13.02 | 152.12 | 68.58 | 341.85 | 1,373.86 | 1,038.06 |
| 783 | 512 | 13.07 | 145.25 | 69.29 | 342.40 | 1,369.60 | 1,034.45 |
| 900 | 65,536 | 14.27 | 45.81 | 83.39 | 126.26 | 1,036.69 | 1,096.46 |
| 783 | 65,536 | 14.20 | 46.14 | 83.50 | 125.75 | 1,034.70 | 1,093.34 |

For 512-byte tight polling, SpiritBoot's whole-case throughput is about 24.5%
lower even though its mean submit call is over eleven times longer. For 64 KiB,
Complex measures 64.79/64.67 MiB/s at 900/783 pages versus SpiritBoot's
68.53/68.33 MiB/s: SpiritBoot is about 6% faster in this fixture's whole-case
throughput despite its higher per-call submission latency. The measurement does
not identify which inter-request costs or run-to-run effects account for that
difference; more repetitions would be required to assess stability.

### 33 ms non-alertable cadence

| Free pages | Read bytes | Complex callback ms | Spirit callback ms | Complex reads/s | Spirit reads/s | Complex immediate callbacks | Spirit immediate callbacks |
| ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 900 | 512 | 33.258 | 27.878 | 29.479 | 34.788 | 2 / 295 | 54 / 348 |
| 783 | 512 | 33.517 | 26.247 | 29.255 | 36.887 | 0 / 293 | 76 / 370 |
| 900 | 65,536 | 33.217 | 32.814 | 29.328 | 29.476 | 1 / 294 | 1 / 295 |
| 783 | 65,536 | 33.316 | 32.784 | 29.234 | 29.494 | 0 / 293 | 1 / 295 |

SpiritBoot's 512-byte frame cases avoid the long interval more often because
more callbacks arrive during the immediate poll, so their mean latency is
lower and their read rate higher in this experiment. The 64 KiB frame cases
are close: SpiritBoot's point estimates are 0.5–0.9% faster. The controlled
900-to-783-page change does not produce a throughput collapse in this QD1
fixture. A free-page target does not reproduce the title's streaming pool or
allocator decisions.

## Eight-slot synthetic submission budgets

The separate [submission-burst fixture](../../../../tests/xbe/forza-submit-bursts/README.md)
now has completed native baselines on both BIOSes. It alternates generated
64 KiB/512-byte pairs through eight persistent slots, with up to eight issues
per burst, an immediate alertable poll after each issue, and a 33 ms blocking
non-alertable cadence. The tested burst budgets are explicitly synthetic:
250 µs, 500 µs, 1 ms and uncapped. They include native calls, immediate polls
and bookkeeping. They are not constants measured from the title.

Both BIOSes pass all ten TAP checks and all eight cases, with matching
submitted/verified/callback counts, full-byte/canary oracles, peak outstanding
counts no greater than eight, and unchanged target entry/exit page counts.
All operations return pending and complete successfully. Every case exceeds
ten seconds using its own counter frequency. The archived
[burst comparison](bursts/comparison.json) is reproduced from both serial logs.

| Free pages | Budget µs | Complex reads/s | Spirit reads/s | Complex issues/frame | Spirit issues/frame | Spirit throughput change |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 783 | 250 | 199.36 | 72.14 | 7.905 | 2.698 | -63.8% |
| 783 | 500 | 202.36 | 146.18 | 8.000 | 5.671 | -27.8% |
| 783 | 1000 | 202.44 | 198.76 | 8.000 | 7.932 | -1.8% |
| 783 | uncapped | 202.07 | 200.31 | 8.000 | 8.000 | -0.9% |
| 900 | 250 | 202.37 | 64.58 | 8.000 | 2.414 | -68.1% |
| 900 | 500 | 202.37 | 149.74 | 8.000 | 5.822 | -26.0% |
| 900 | 1000 | 202.13 | 198.47 | 8.000 | 7.912 | -1.8% |
| 900 | uncapped | 202.15 | 200.22 | 8.000 | 8.000 | -1.0% |

At 250 µs, SpiritBoot averages only 2.4–2.7 issues per frame versus Complex's
7.9–8.0. At 500 µs the figures are 5.7–5.8 versus 8.0. At 1 ms both approach
eight; without a budget both issue exactly eight per frame and throughput is
within approximately 1%. The uncapped mean burst costs are 65.9/63.9 µs for
Complex at 783/900 pages versus 696.2/686.4 µs for SpiritBoot. The first request
is allowed even if it takes longer than the budget, so the mean length of an
exhausted burst may exceed its configured budget.

The explicit budget also changes pair placement. At 783 pages and 250 µs,
SpiritBoot splits 129 of 361 complete pairs across frames versus Complex's
72 of 1,000; at 900 pages these counts are 151 of 323 versus zero of 1,012.
An odd-sized burst can shift subsequent pair/frame alignment, so one budget
crossing can be followed by several split pairs. These are issue-placement
observations, not missed callbacks. Every submitted request passed its oracle.

This is evidence that the measured call/burst overhead can reduce concurrency
when an application imposes a small issue budget. It does not establish that
Forza uses these budgets, prove that this mechanism causes the missing world,
or validate a firmware fix. The cadence still blocks instead of rendering,
and the full preparation/oracle cost remains inside whole-case throughput.
Only one completed run per BIOS is included for this fixture as well.

### Statistics-query observations match for invalid lengths

The burst prelude initializes the public `MM_STATISTICS` structure and four
ULONG canaries on each side to `0xa5`, then changes only `Length`. Both BIOSes
return `0xc000000d` for lengths `0`, `1`, `35`, `37`, `0xc1008c48` and
`0xffffffff`; the input Length, the other eight sentinel fields and all
canaries remain unchanged. Both return success for Length 36 and preserve the
canaries. Thus these invalid-length observations do not distinguish the BIOSes.
The analyzer treats status/field writes as observations and checks the canaries;
it does not manufacture this agreement by requiring a particular error result.

The successful prelude query reports different descriptive startup counts:
Complex has 16,222 available pages, 5 pool pages, 19 stack pages and 24 image
pages; SpiritBoot has 16,144, 62, 37 and 25 respectively. Both report 16,384
total pages, 167,936 committed/reserved virtual bytes and 16 cache pages. These
queries precede the generated-file setup and pressure allocation; they are
not measurements of the title's streaming-pool budget. All nine fields from
all fourteen calls are retained in the numeric summaries and owned serial logs.

## Run identity and reproduction

Both runs use the same published Windows xemu 0.8.136 executable, release XBE
and 64 MiB memory setting. Release archive identity:
`xemu-0.8.136-0-g458730bf5373-windows-x86_64.zip`, SHA256
`6fcab6a26657fecff95e09f0ef6ecf132a91cfbac6e80a88a9de96cc43d6f685`.
The archive hash matches the locally retained release checksum list. The
emulator is the published binary, not the instrumented title-trace build.
The runner arguments retain `guest_errors` logging; no instruction profiler,
fixed-address title probes or QMP disk throttle was requested.

| Artifact | SHA256 |
| --- | --- |
| Shared published `xemu.exe` | `5488be40bf3c1c444b507d084c8d964f8f7d73c2a912970495cf85a4f7239564` |
| Cadence fixture XISO | `55698144b2efbc230356ee33decaa89b5e3c9db8c672ad2b5abc62c330f1da49` |
| Cadence fixture XBE | `aa106cef5733d15f75492bad31751446fde8c44b7ac67532963e3033edb81bb7` |
| Burst fixture XISO | `3b960e63bf8170cd1636ec471dd55aabc2083b2790f9cd3e5e7221013122382e` |
| Burst fixture XBE | `01e4900c154bc8761591b81666eafa662969f97637f025fb6ea5748cd204ded8` |
| Complex BIOS | `1de4c87effe40d44f95581d204f9fa0600fbd5fe2171692316dcf97af0f4113f` |
| SpiritBoot release BIOS | `add882b6f50e9c9ae49705bb8374be5646e44ed1b72f0e2eb4b77bdedeeaf296` |

Complex job: `forza-cadence-complex-release-20261017-2`, completed
`2026-10-17T23:58:52.7610054+00:00`. SpiritBoot job:
`forza-cadence-spirit-release-20261017-1`, completed
`2026-10-18T00:02:56.6049468+00:00` (both October 17 in the operator's Pacific
time zone). The earlier empty Complex attempt is excluded.

Burst jobs are `forza-bursts-complex-release-20261017-1` (finished
`2026-10-18T00:11:54.2244079+00:00`) and
`forza-bursts-spirit-release-20261017-1` (finished
`2026-10-18T00:14:13.667837+00:00`). Both bind the same frozen burst XISO and
the same published emulator and BIOS hashes shown above.

The per-run performance frequencies differ: Complex reports 3,375,000 Hz and
SpiritBoot 3,374,488 Hz. Every conversion and duration check uses the frequency
reported by that run. Both satisfy the strict ten-second minimum; no tolerance
was added to conceal a short case.

[Cadence manifest](capture-manifest.json) and [burst manifest](bursts/capture-manifest.json)
record exact run IDs, source/build
hashes, executable/BIOS/config hashes and redactions. The sanitized runner
recipes retain the executed arguments and input hashes; their source hashes
bind them to the original requests. Environment mappings, private endpoints,
workstation telemetry and the live-host launch script are omitted. These
fixture requests have `SnapshotName: null`. Preserved gameplay snapshot paths
and hashes are absent from the supplied fixture summaries and must be recorded
separately by the operator; no snapshot bytes are included here.

This archive does not establish identical initial HDD/cache/EEPROM states from
hashes, and there is only one completed run per BIOS for each fixture. The fixture
reseeds its own file; that is not a cold-HDD condition or an actual-title replay.
These limits prevent treating the point estimates as a controlled game FPS or
world-streaming acceptance result.

Recompute and check the owned evidence:

```sh
python3 docs/performance/evidence/forza-complex-cadence-20261017/reproduce.py
python3 docs/performance/evidence/forza-complex-cadence-20261017/bursts/reproduce.py
python3 -m unittest discover \
  -s docs/performance/evidence/forza-complex-cadence-20261017 -p test_analyze.py
python3 -m unittest discover \
  -s docs/performance/evidence/forza-complex-cadence-20261017/bursts -p test_analyze.py
(cd docs/performance/evidence/forza-complex-cadence-20261017 && sha256sum -c SHA256SUMS)
```

`reproduce.py` parses both serial logs with the frozen analyzer, requires exact
agreement with both archived summaries, and emits [comparison.json](comparison.json).
The equivalent burst script reproduces [bursts/comparison.json](bursts/comparison.json).
All thirteen cadence and fifteen burst analyzer regressions pass. `SHA256SUMS`
binds the archived files, including the burst subdirectory.
The serial files contain only owned fixture/TAP records. No BIOS, EEPROM, HDD,
snapshot, game executable/data, game RAM or screenshot bytes are archived.
