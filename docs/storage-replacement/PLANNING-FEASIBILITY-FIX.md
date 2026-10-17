# Reject impossible performance experiments before native collection

The saved five-pair pilot combined 95% planning confidence, 80% family planning power across 144 metrics, a 30-pair minimum and a 2,000-pair confirmation cap. Even if every pilot pair met every margin, the existing count planner requires 4,427 confirmation pairs. The old specification validator accepted this plan and could schedule expensive native collection that could never produce an accepted calibration under its own rules.

`tools/storage_perf_compare.py` now runs the same planner on a hypothetical perfect pilot during specification validation. If even this best case cannot meet the frozen cap, validation fails before creating a schedule or writing the CLI output. It tells the operator to increase the pilot count or cap before collecting data. Actual observations still determine the required confirmation count; passing this check does not qualify a pilot, approve its runtime budget or guarantee sufficient power.

The acceptance margins, planning confidence/power, exact paired-median method, simultaneous confidence bounds, operation/data checks and actual-sample retention rules are unchanged. Existing frozen diagnostic artifacts remain unchanged. Increasing the cap to thousands of pairs is not an automatic remedy: a new plan must have an affordable prospective run budget and measured repeatability.

## Verification

A new regression test first failed because the invalid specification produced a schedule. After the fix it verifies both the Python scheduling API and actual CLI reject that specification without creating an output file. A second test verifies a larger pilot can preserve 95% planning confidence and the existing 2% latency/throughput and 5% tail margins. All 30 comparator tests pass. Full product checks are recorded with the integration commit.

## Separate V37 interpretation correction

The completed V37 cohort retains all 216 reference-ROM captures and its original `READINESS_VETO`. Its majority-of-three screen tests individual-pair exceedances of an arithmetic interval, whereas the acceptance tool estimates a population median across independent run pairs. The arithmetic interval bounds tick conversion; it is not a confidence interval for run-to-run variability. Consequently that screen must not become a necessary prerequisite to a larger statistical pilot.

For example, under an illustrative unbiased log-ratio distribution with 2% standard deviation, that screen vetoes at least one of 36 independent latency cases with probability about 92.51%. This is a mathematical counterexample, not a model fitted to the host or a p-value for V37. An independent review also identified the impossible five-pair/cap combination above. Neither finding proves equal BIOS performance or explains all observed host variability.

Prospectively, retain the three-cycle result as a method diagnostic. Use bounded telemetry to investigate startup, host scheduling and workload costs, then freeze a feasible complete pilot before further collection. Do not rerun three-cycle cohorts until one passes, discard observations, widen product margins, or promote historical diagnostics into calibration. No candidate performance decision is authorized by this correction.

The request recorder also needs precise scope labels: its `qd_actual` field is the maximum number of occupied caller slots before APCs are reaped, not sustained lower-device queue depth. Buffer poisoning and byte verification run on the issuing thread and are part of the recorded caller workload. Public timestamps cannot establish physical command concurrency. Preserve the existing workload identity when comparing results; a future recorder with different verification or timing boundaries needs a fresh version and matched baseline/candidate runs.
