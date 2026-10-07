# Task 2 independent specification and product-quality review

Reviewed product range: `feaccde..df5fb616750b286b7e669c847920cc4a192a677f`.
Packaging commit: `f1a53ef4e564c314b294dd9590ba7e2cb0af33f3`.
Approved Task 1 source: commit `87aba89a6ba9b2a58f2edd6e52d5e3aa1e8649d7`,
tree `f7adb302a762ed1945cc07d9c2ff428c643ba959`.

## Verdicts

- Specification compliance: **FAIL / changes required**. The analyzer can
  classify noisy permitted uint64 samples as an improvement, violating the
  required conservative variation threshold.
- Product quality: **FAIL / changes required** for the same false-claim defect.
- Findings: **0 Critical, 1 Important, 0 Minor**. These are one shared finding,
  not two distinct defects.

Packaging, source identity, preserved inputs, integration workflow and public
documentation otherwise satisfy the reviewed Task 2 requirements. This verdict
does not invalidate Task 1's independently approved kernel logic or the current
controller measurements; the arithmetic defect is outside their observed tick
range. A focused analyzer correction and scoped re-review are required before
accepting the tooling.

## Important I1 — floating normalization can erase variation and invent a speedup

Exact references: `tools/kernel_performance.py:103` permits ticks throughout
uint64; `tools/kernel_performance.py:105` immediately converts the normalized
samples to binary floating point; `tools/kernel_performance.py:181`, `:182`,
`:184`, `:187`, `:188` and `:189` use those rounded samples for medians, raw
variation and improvement/regression decisions.

For the existing `sysva-4096` workload, which has one iteration, repeat these
samples in each of seven otherwise valid baseline/candidate pairs:

| Variant | Sample 0 ticks | Sample 1 ticks | Sample 2 ticks |
|---|---:|---:|---:|
| Baseline | 9223372036854776833 | 9223372036854776833 | 9223372036854776833 |
| Candidate | 9223372036854775809 | 9223372036854776832 | 9223372036854776832 |

All values satisfy the current uint64 parser contract. Exact baseline median
minus candidate median is **1 tick**, while the observed candidate raw sample
range is **1023 ticks**. The required result is timing inconclusive.

Binary floating point rounds every candidate sample to the same number and
every baseline sample to the next representable number. The real analyzer
instead produces:

```json
{"median_difference": 2048.0,
 "maximum_observed_variant_range": 0.0,
 "improving_pairs": 7,
 "classification": "timing improvement"}
```

This was confirmed through `analyze()` and its real capture parser using a
read-only in-memory mutation of the fourteen existing capture serial streams.
Only these workload tick fields changed; TAP, checksum, iteration, sample,
image, timing-order and build contracts remained satisfied. Explicit unavailable
asset mappings prevented the probe from following controller fixture paths.
No capture or artifact file was modified. A direct exact-integer calculation
also confirmed delta 1 and range 1023. The first probe attempt used unresolved
relative capture paths and stopped with FileNotFoundError; resolving them
against pairs.json produced the result above.

Fix: retain exact arithmetic for normalized samples and all classification
decisions, for example `Fraction(ticks, iterations)`, including medians,
per-variant raw/intertrial ranges and paired consistency. Convert only for
presentation/JSON fields after making the exact decision. Add a focused
adversarial regression requiring this case to remain inconclusive; retain the
documented uint64 contract. Verify the symmetric regression boundary as well.
Existing synthetic fixtures at `tests/host/test_kernel_performance.py:29` use
small tick values and do not expose this loss of precision.

## Specification evidence and satisfactory areas

### Exact packaging and retained history

The complete review package body is byte-identical to
`git diff --binary -U10 feaccde..df5fb616`; all nine changed files are accounted
for. Product and approved public kernel worktrees were clean when inspected.

The new patch is byte-identical to the exact public-source
`git diff --binary 291ad9759f7993cb1f96d73bfa1c6f333c2bef34 87aba89a6ba9b2a58f2edd6e52d5e3aa1e8649d7`:
62888 bytes, SHA256
`0e8147f370fc591c1f6b440344d1271aa5d040291e54a15fba650a88ad8ff1f7`.
`sources/firmware-lock.json:8` retains 0001 first and appends 0002 with this hash.
The patch includes the seven reviewed source areas, host fixtures and guest
source/documentation; it contains no generated binary or media artifact.

0001 is byte-identical to its `feaccde` version, SHA256
`747a5974ac714bcf76a6516fc1ed3ced148880907bd41a3f3f62fbd3d60b168f`.
Direct read-only hashes of historical BIOS files still match:

- Release: 262144 bytes,
  `154276a142c7df727ea46f1a35ee9a896f7369221f10d07f21757a61bc8e6d60`.
- Checked: 524288 bytes,
  `7f7cb55be972308b570415863222ff8285e0f4de2d324a12425ee5e33c568ceb`.

`tools/firmware.py` and existing build scripts are unchanged. The retained
inline preparation at `tools/firmware.py:115` and `:132` uses validated patch
snapshots, an isolated clone, ordered `apply --check --index` and `apply --index`,
then records `write-tree`. No helper refactor was introduced.

Controller manifests `artifacts/optimization/final-release-v1/build.json`,
`final-release-repeat-v1/build.json` and `final-debug-v1/build.json` all record
public base `1569e2e89fb47cc72b9c704a8884f98200432bd4`, both ordered hash-checked
patches and exact approved tree `f7adb302a762ed1945cc07d9c2ff428c643ba959`.
Their command records include both indexed applicability checks and applications.
Direct file hashes match their output manifests. Release and independent repeat
are identical, 262144 bytes, SHA256
`48c3ee940d55628a74e17333a1e76966ad6ade5e44a41915d2d53348a37fdc74`.
Checked output is 524288 bytes, SHA256
`4016974c0b0a07a6d560c8afa13cd33026368bf2f7cbc3d967dc769bd4d9d2e8`.
These are inspected controller proofs, not reviewer build claims.

### Analyzer contracts and actual controller evidence

Apart from I1, the parser enforces clean exit/status, the required direct 128-MiB
snapshot configuration, independently regraded TAP 42/42 with no TODO/SKIP/errors,
unique terminal PASS, version/clock/frequency, all 41 workload IDs in source order,
fixed positive iteration counts, exactly samples 0–2 except cold sample 0,
uint64 bounds, correctness 1, matching semantic checksums and zero-failure summary.
It rejects unparsed PERF lines rather than silently ignoring them.

Pair validation requires at least seven unique pairs, matching xemu/HDD/DVD
identities, the fixed baseline release hash, a distinct consistent release-sized
candidate and the approved source tree. The optional build record binds candidate
output/source identity. Locally accessible explicitly named/mapped assets are
hashed without guessing container mappings. The precise controller log is checked
for alternating order, chronological nonoverlap and correspondence to each capture;
driver coarse starts receive the specified quantization allowance.

Raw sample records, empty overhead, asset records, input/code hashes and the
controller log survive in JSON. No overhead subtraction, aggregate FPS or gameplay
claim is introduced. Normal-size arithmetic implements the requested per-variant
range threshold, including raw variation, and six-of-seven consistency; it uses
the symmetric rule for regression. Tests meaningfully exercise malformed captures,
asset mismatches, failed correctness, ordering, insufficient pairs and noisy/weak
positive medians. The report records 21 new passing tests and 63 total host tests,
with the documented ownership skip; these passing tests were not rerun.

Read-only inspection of controller `paired-v1/pairs.json`, `runtime-inputs.json`
and `performance-report-v1.json` confirms fourteen capture records, each TAP 42/42
and 121 raw samples. Every reported run/serial hash matches its actual capture
file. Report provenance hashes match the dataset, runtime inputs, candidate build
and reviewed analyzer; the dataset's declared runtime-input digest also matches.
The immutable DVD record is 655360 bytes, SHA256
`34878f2e06b157d4d0a2c6b799babd364f66ecfa89f3cea0ef3ddc29b16d946e`.
The retained report has six per-workload improvements, no qualified regressions
and 35 inconclusive workloads. This review does not convert those workload results
into throughput or gameplay claims. The real tick values do not approach I1's
precision-loss range, so no current measurement conclusion is invalidated by I1.

### CI and documentation

`.github/workflows/firmware.yml:41` checks the manifest source tree and runs
clean-room host checks plus optimized `check.py`, ordinary pins and diagnostic
pins in the pinned toolchain after build. `:78` builds all four guests from that
same manifest source directory. `:88` retains existing direct guests and runs
the performance guest; `:116` invokes the strict capture validator. `:122` uploads
host work/log directories and all guest captures, including failure artifacts.
There is no HTTP runner and no single-CI-runtime performance inference.

The integration guide records exact source and patch identities, the seven
changes, conditional nonwrapping registry-count proof, diagnostic opt-in, actual
41-workload/42-TAP limits, counter evidence attribution, rejected-pin crossover
cost and deferred correctness/runtime qualification. `host-work.json` is an exact
copy of retained controller evidence. Inspected source logs report 30978 oracle
checks and 7307629 pin checks in ordinary and diagnostic modes; documentation
correctly distinguishes assertions from independent scenarios and host counters
from guest timings. Audit JSON and CSV remain unchanged with 371 rows each.
No unobserved new CI, game, firmware acceptance or publication pass is claimed.

## CannotVerify boundaries

- Full candidate direct/API/contracts/warm-reboot and matched XISO qualification
  is controller work in progress. This review does not certify those pending
  results, the pin-budget retention decision, gameplay or complete kernel correctness.
- The new remote CI workflow has not executed at this review point. Static
  inspection and reported syntax checks establish wiring, not a remote CI pass.
- Passing test suites, Docker builds and emulator runs were not rerun. Existing
  manifests/logs were inspected; the only executed analyzer probe was the new
  read-only adversarial precision case described above.
- Controller xemu/HDD and XISO fixtures named in provenance reside outside the
  allowed review paths. They were not opened or rehashed by this reviewer. Their
  capture/runtime hash identities and controller pre-run verification are the
  evidence boundary. Public product historical/candidate BIOS files and allowed
  capture/report files were read directly.
- Kernel ABI/ownership/IRQ/cancellation/security and seven-region implementation
  review remain the approved Task 1 boundary. Exact patch identity preserves that
  reviewed source; this review intentionally does not duplicate the kernel review.

No forbidden repository or proprietary/community/reverse-analysis artifact was
inspected. No subagent, Docker, emulator, push or publication was used. The sole
written artifact is this adjacent review report.
