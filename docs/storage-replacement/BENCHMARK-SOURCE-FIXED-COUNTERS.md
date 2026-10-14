# Source-fixed counter checkpoint

This opt-in analysis checkpoint implements the approved clock design's exact
arithmetic and paired statistical inputs. It consumes a small readable native
importer interface; it does not implement that importer or establish runtime
clock, provider precision, physical durability or P1 qualification.

Absent `counter_policy`, recorded-frequency conversion and legacy decisions are
unchanged. The new policy has `schema_version: 1`,
`conversion: "source-fixed-rdtsc"`, `counter_hz: 733333333`,
`platform: "deck"` or `"windows"`, `paired_conversion_budget:
{"numerator": 1, "denominator": 1000}` and a relative `context_contract`
descriptor (`path`, `sha256`). The rate and budget cannot be caller overrides.

The readable context contract binds the same schema/conversion/rate/platform,
exact `xemu_sha256`, frozen `environment_sha256`, explicit `assumptions`, and
`source_binding`, `verifier_artifact`, `interval_helper`, `review_receipt` file
descriptors. The helper descriptor must hash the exact owned helper bytes
executed by the comparator. Windows also supplies an actually qualified positive
`qpf_hz` within uint32; missing QPF is unknown, never inferred from Deck. The
decoded review receipt has `status: "reviewed_for_conditional_arithmetic"`,
`reviewed_utc` before schedule creation and `contract_facts_sha256`, the canonical
digest of the contract excluding only its `review_receipt` field.

Each row supplies `native_run_id`, a `counter_provenance` descriptor and a
`clock_provenance` descriptor. The raw counter file binds schema1,
`attempt_id`, `schedule_sha256`, `manifest_sha256`, `case_sha256`,
`environment_sha256`, `runner_sha256`, and `timing_sha256` (the canonical digest
of original `elapsed_ms`, `latencies_ms`, `timing_scope`). It retains canonical
native `meta`, `summary`, `end` and every `operations` record. Native numeric
fields remain strings. RDTSC frequency/ticks must be positive uint64; every
operation's case, index, ticks, status, IOSB status and information are checked.
Original reported milliseconds are checked against the original reported
frequency. All raw metadata, including original frequency estimates, stays in
the immutable provenance file; no frequency or historical milliseconds change.

The decoded clock proof has schema1,
`verification_status: "verified_by_pinned_importer"`, `native_run_id`, the same
job/case/environment/runner bindings, `context_contract_sha256`,
`verifier_sha256`, `raw_counter_sha256`, and `native_evidence`. That last object
maps `request`, `result`, `input_manifest`, `guard`, `host_context` to readable
file descriptors. Artifact-set mode additionally requires `preparation_receipt`
and equality of request/input/preparation hashes to its artifact bindings.

This interface checks actual file bytes and cross-bindings, not just a user
boolean. Factual qualification still belongs to the independently reviewed,
pinned importer: it must validate native execution/outcomes, exact process and
input lifetimes, the source/backend/startup assumptions, allowed controls and
actual host context against those files. The comparator does not execute the
external verifier or authenticate unsigned receipts. A fabricated self-hashed
packet is not native qualification. Real native calibration remains pending
that importer and review; the tests use explicitly invented verifier/context
files and never claim an actual importer ran.

The committed exact interval helper derives separate source-fixed batch latency,
reciprocal batch throughput and nearest-rank p95/p99 from the original raw ticks.
Deck and integer Windows scaling use error envelope `1/R` seconds; nondivisible
Windows QPF uses `1 ns + 1/R`. These are conditional conversion arithmetic
envelopes, not total provider precision, QPF resolution or scheduling uncertainty.
The observed Windows F=10,000,000 context, for example, has 100 ns count quantum;
this alone is not a short-interval precision qualification.

Every pair preserves reduced exact rational center/lower/upper ratios. Zero or
unbounded endpoints, missing pairs or endpoint relative deviation above1/1000
make the whole required paired metric INCONCLUSIVE; no observations are removed
to improve a result. A/A calibration refuses such a cohort. The frozen
`pilot_intervals` cover every case, metric and pair, and the count planner verifies
their central ratios and complete endpoint facts on reanalysis.

Planning reuses the existing binomial algorithm: a latency/tail success requires
upper endpoint <= frozen limit; throughput requires lower endpoint >= limit.
Crossing intervals count outside the margin. Confirmatory confidence bounds use
the same binomial ranks on all lower and all upper endpoints separately. Exact
rationals are compared with the canonical frozen decimal limits; float values
are display/descriptive summaries. The probability calculations remain the
existing floating-point binomial method, not a formal precision proof.

Reports label the conversion, preserve raw provenance and original batch
milliseconds, and expose exact confidence bounds and all paired intervals.
Observed native operation errors remain REGRESSION; missing/inconsistent evidence
remains attributable unknown. Full36/count/correctness/healthy-path gates remain,
and separated physical write durability remains INCONCLUSIVE. No native runs,
candidate timing, performance acceptance or complete driver qualification were
performed by this checkpoint.
