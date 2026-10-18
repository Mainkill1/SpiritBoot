# FATX direct native read path, 2026-10-18

## Decision

Patch 0181 is the corrected release64 candidate. It replaces the unsafe
patch-0180 shortcut with a bounded FATX one-command read route that participates
in the same quarantine, cancellation, removal, and retained-packet lifetime
domain as the generic nxstorage route. All other traffic keeps the
selected-0168 path.

The exact 64 MiB release image has SHA-256
`6bcee57b071f1fbae103b25ec66e33093dd8c78597f7d050d787ee45f0c23323`.
Its assembled source tree is `b8aaf4f81faf6fcbd85996f57927cfafb455bc21`;
patch 0181 has SHA-256
`6abace78ec7f6098c69fdb18c440ce246d5e1816bc3e15ecb3fab5eaba2b7ffc`.
[build-identity.json](build-identity.json) binds the firmware, source tree,
linker map, lock file, and nxstorage/vfatfs archives.

This is a storage-path correction and measured submission-cost improvement.
It is not proof that every Forza streaming delay is fixed. No manual title test
is requested for this candidate.

## Why 0180 was rejected

An independent transaction review reproduced four correctness holes in 0180:

- generic core quarantine did not stop a later marked direct read;
- quarantine did not cancel and drain live direct peers;
- quarantine during packet preparation could still commit a lower request;
- an inline completion during `IoCancelIrp` could release and reuse a retained
  child packet before `IoCancelIrp` returned.

Patch 0181 publishes quarantine through one adapter callback, invokes it
outside the core lock, cancels live direct peers outside the adapter lock, and
keeps the child external-operation lease through the cancel call. It also
rechecks quarantine between packet preparation and lower commit. Dynamic
marked overflow remains on the generic route and therefore drains under the
same quarantine boundary.

[0180-REJECTION.md](0180-REJECTION.md) maps every reproduced failure to its
0181 correction and executable regression.

The direct qualification is explicit: FATX marker, non-optical device,
retained non-dynamic envelope, and exactly one command from the shared
planner. Split, dynamic, write, flush, control, optical, and unmarked/non-FATX
requests use the generic route.

The implementation uses public I/O contracts and SpiritBoot's GPL source.
Complex was used only as a black-box behavior and timing reference; its
implementation body was not inspected or copied.

## Correctness gates

The exact source tree used for the release image passed:

- 54 native-adapter groups in plain and ASan/UBSan configurations;
- 51 core request tests;
- an active-slot differential scan with 1,528,352 observations and lifecycle
  capacity cases;
- eight pthread concurrency scenarios;
- ten packet tests in plain, sanitizer, and MSan configurations;
- nine owner/lifetime groups;
- cache and geometry suites.

The added adapter cases cover generic-to-direct quarantine propagation, peer
cancel/drain, quarantine during prepare, inline cancel completion, dynamic
fallback quarantine, removal while a canceled child lacks a callback, pending
and inline completion, short/over-reported/failing transfers, frozen queues,
QD12 payload association, FIFO/barrier ordering, split fallback, and removal.

The complete repository sweep passed 565 tests in 449.361 seconds, with 26
environment-dependent checks skipped because this Linux host does not provide
PowerShell or retained private native archives. The complete output is in
[full-host-tests.log](full-host-tests.log).

## Repeated generated workload

The fixture ran in fixed order selected-0168 / candidate-0181 / selected-0168 /
candidate-0181. Each case ran for at least ten seconds in a fresh emulator
process. Every payload, callback, pending-status, byte-count, canary, and
lifetime oracle passed. Each candidate is compared with its immediately
preceding control.

| Pair | Pages | Budget | Submission cost | Verified rate |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 783 | 250 us | -12.61% | +17.37% |
| 1 | 783 | 450 us | -7.14% | +3.97% |
| 1 | 783 | 1,000 us | -8.37% | -0.32% |
| 1 | 783 | uncapped | -10.74% | +0.12% |
| 1 | 900 | 250 us | -14.51% | +11.66% |
| 1 | 900 | 450 us | -8.22% | +5.77% |
| 1 | 900 | 1,000 us | -7.21% | +0.48% |
| 1 | 900 | uncapped | -7.95% | -0.26% |
| 2 | 783 | 250 us | -5.97% | +5.74% |
| 2 | 783 | 450 us | +4.47% | -0.50% |
| 2 | 783 | 1,000 us | -3.81% | -1.48% |
| 2 | 783 | uncapped | -3.70% | -1.48% |
| 2 | 900 | 250 us | +4.00% | +0.07% |
| 2 | 900 | 450 us | +7.06% | -6.50% |
| 2 | 900 | 1,000 us | +1.68% | -1.20% |
| 2 | 900 | uncapped | +4.91% | -1.29% |

The average of the two runs for each role is the decision view:

| Pages | Budget | Mean submission cost | Mean verified rate |
| ---: | ---: | ---: | ---: |
| 783 | 250 us | -9.13% | +11.72% |
| 783 | 450 us | -1.02% | +1.81% |
| 783 | 1,000 us | -5.99% | -0.90% |
| 783 | uncapped | -7.08% | -0.69% |
| 900 | 250 us | -4.93% | +6.01% |
| 900 | 450 us | -0.57% | -0.40% |
| 900 | 1,000 us | -2.63% | -0.36% |
| 900 | uncapped | -1.45% | -0.78% |

Mean submission cost improves in all eight cells by 0.57–9.13%. The
frame-limited 250 us rate improves by 6.01–11.72%. The 450 us, 1 ms, and
uncapped rates vary by up to 6.50% in individual adjacent pairs; the result
does not show a bandwidth increase at fixture saturation.

Per-size means were also audited. The two-run role means range from -15.94% to
+7.70%, below the 20% investigation threshold. The mean regressions are 64 KiB
at 783/450 (+6.27%), 64 KiB at 783/1,000 (+1.95%), 512 B at 900/250
(+1.55%), and 64 KiB at 900/1,000 (+7.70%). One individual
900-page/1,000-us/64-KiB comparison regressed 25.87%. That cell changed from 85
to 168 frames with a 64-KiB request in first position; first-in-frame requests
were much more expensive in both variants. The aggregate whole-cell change for
that pair was +1.68%, while the two-run whole-cell mean improved 2.63% and the
two-run 64-KiB mean regressed 7.70%. This composition evidence explains why
the isolated size mean is unstable, but it does not prove that all of its
difference is noise.

| Pages | Budget | Control first 512 B | Candidate first 512 B | Control first 64 KiB | Candidate first 64 KiB |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 783 | 250 us | 148, 148 | 140, 139 | 120, 121 | 126, 126 |
| 783 | 450 us | 134, 133 | 138, 147 | 123, 127 | 118, 110 |
| 783 | 1,000 us | 204, 86 | 103, 116 | 48, 168 | 148, 134 |
| 783 | uncapped | 0, 0 | 0, 0 | 251, 254 | 251, 250 |
| 900 | 250 us | 161, 139 | 137, 138 | 106, 129 | 128, 128 |
| 900 | 450 us | 132, 132 | 138, 123 | 125, 127 | 118, 135 |
| 900 | 1,000 us | 9, 168 | 0, 82 | 242, 85 | 251, 168 |
| 900 | uncapped | 0, 0 | 0, 0 | 252, 254 | 251, 250 |

Eight individual per-size `submit_max` values increased by more than 20%, with
the largest at 42.14%. Each maximum is one operation among hundreds, the cells
do not consistently recur across the two pairs, and their corresponding means
stay below 20%; they are retained in the raw summaries but are not treated as
representative latency distributions. A future latency claim needs percentile
capture rather than a single maximum.

[synthetic/comparison.json](synthetic/comparison.json) retains every adjacent
and two-run comparison, per-size values, and first-position counts. The four
raw serial logs, summaries, submission/result receipts, and SHA-256 bindings
are under [synthetic/runs](synthetic/runs). Two observations per role establish
a repeated direction for this fixture, not statistical significance.

## Automated title acceptance

All accepted title runs used release xemu SHA-256
`5488be40bf3c1c444b507d084c8d964f8f7d73c2a912970495cf85a4f7239564`,
64 MiB RAM, a fresh process, a private HDD, and no RAM snapshot.

Forza ran control/candidate/control/candidate. All four routes passed and
completed the driven race segment with intact menus, text, loading screens,
starting grid, and streamed scenery in the retained screenshots. The two
controls first showed the starting grid at sample index 4; both candidates did
so at index 3. Samples are one second apart, so this is a repeated one-sample
observation rather than a precise load-time or general map-streaming claim.

Three independent candidate PGR2 processes completed the race route. Their
cadence was 29.99999, 30.00010, and 29.99998 FPS; p99 frame intervals were
34.289, 34.260, and 33.887 ms. The reported early PGR2 crash was not reproduced
in these three clean runs.

Two setup attempts are excluded and named in
[title-acceptance.json](title-acceptance.json): one used a diagnostic with the
superseded 0180 hash, and one package contained stale failure evidence. The
clean r3 packages replaced both. The repository retains scalar screenshot
hashes/luminance, run IDs, outcomes, and performance summaries. Original title
screenshots remain on the runner and are not committed, so the repository
reproducer verifies their archived bindings and classifications but cannot
independently reclassify the pixels.

## Reproduction

Run the archived evidence check from the repository root:

```sh
python3 docs/performance/evidence/forza-direct-native-read-20261018/reproduce.py
```

Run the complete host regression suite with:

```sh
python3 -m unittest discover -s tests/host -v
```

The release image is rebuilt from `sources/firmware-lock.json`. The synthetic
and title jobs require the separately documented xemu runner and immutable
release assets; the committed plan, receipts, hashes, raw synthetic serial,
and run IDs preserve the reviewable public record without workstation
credentials, private endpoints, game images, HDDs, EEPROMs, or firmware
binaries.
