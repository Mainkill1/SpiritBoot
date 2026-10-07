# Task 2 fix round 1 — scoped independent review

Reviewed range: `df5fb616750b286b7e669c847920cc4a192a677f..0cd16fbe1e828f77d6ffb320c7574bf10792640b`.
Basis: original review Important I1, the Task 2 arithmetic contract, the appended
fix report, and `task-2-fix-1-review-package.diff`. The package body is
byte-identical to the actual `git diff --binary -U10` for this range. Only
`tools/kernel_performance.py` and its host tests changed.

## Verdict

- **Important I1: ADDRESSED.** The permitted uint64 samples can no longer lose
  variation or acquire a false improvement/regression through float rounding.
- **Scoped specification and product-quality review: PASS.**
- New breakage in this fix: **0 Critical, 0 Important**.

Unrelated packaging, kernel, CI and qualification work was not re-reviewed.
Out-of-scope Minor issues are deferred.

## Arithmetic and regression evidence

`tools/kernel_performance.py:199` reconstructs normalized samples directly as
`Fraction(ticks, iterations)` from retained integer fields. Trial medians,
overall medians (including even trial counts), per-variant intertrial and raw
sample ranges, paired differences and percentage calculations therefore remain
exact. The raw range includes all normalized samples of each variant, preserving
the original conservative threshold rather than narrowing its scope.

At `:208` and `:209`, improvement and regression use exact delta, exact maximum
variation and exact paired signs, with strict magnitude greater than variation.
`(6*n + 6)//7` at `:193` is exactly `ceil(6*n/7)` for integer pair counts and
requires six consistent signs for seven pairs. Zero differences do not count.
The symmetric regression rule remains intact.

The capture parser still permits the complete uint64 tick range at `:104`.
Its float `ticks_per_iteration` fields are presentation records and are not
consumed by the decision path. `display_numbers` runs after classification;
the exact numerator/denominator records remain integers through that conversion.
No normalized float participates in the decision medians, ranges, differences,
sign counts or threshold comparisons.

The new real-parser tests at `tests/host/test_kernel_performance.py:98` require
the original I1 sample set and its reverse to stay inconclusive: median delta
is respectively +1/-1 while raw variation is 1023. The test at `:113` preserves
definite improvement/regression for constant uint64 samples with +1024/-1024
delta and zero variation. The 1000-iteration case at `:124` requires inconclusive
classification with exact delta `1/1000` and range `1023/1000`, checks the rational
records and JSON serialization. Existing positive, negative, noisy, weak and
five-of-seven tests remain present.

The implementer report records the focused pre-fix failures, then 24 passing
analyzer tests and the full 66-test suite with one existing ownership skip
(65 passing), plus successful compilation and diff checks. These reported
passing commands were inspected, not rerun in this review.

## Regenerated actual report

Read-only inspection of `artifacts/optimization/performance-report-final.json`
and the original `performance-report-v1.json` confirms all 41 workload
classifications are identical: **6 timing improvements, 35 timing inconclusive,
0 timing regressions**. Capture records, execution log, dataset provenance,
runtime-input provenance and candidate-build provenance are identical between
the reports. The final analyzer hash matches the reviewed analyzer file.

An independent read-only calculation from the final report's retained raw
integer samples recomputed every workload's exact variant medians, maximum
range, paired differences, improving sign count and classification. All exact
decision records and classifications match; no discrepancy was found. The
seven-pair report requires six consistent signs. This check did not invoke the
analyzer, follow asset mappings, modify captures or regenerate a report.

## Review boundaries

Only permitted public product paths were read. No private/community/reference
analysis, subagent, Docker, emulator, passing test rerun, push or publication
was used. The sole written artifact is this adjacent scoped review. Existing
runtime and remote CI qualification boundaries remain those of the original
review; this verdict makes no broader kernel, throughput or gameplay claim.
