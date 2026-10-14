# Recorded storage performance experiments

`tools/storage_perf_compare.py` implements the P1 experiment workflow from
[the test plan](TEST-PLAN.md) and [the checklist](IMPLEMENTATION-CHECKLIST.md).
It schedules independent baseline A/A instances, freezes a confirmatory count
and decision rules from A/A, then compares recorded A/B attempts. It uses only
Python's standard library. It does not launch xemu or supply workload binaries.
An independently authored native recorder executes the jobs and records JSONL.
The same contract works with local captures and PowerShell captures.

The analyzer's host-test timing fixtures are invented solely to test analysis
behavior. Real native baseline observations are recorded in
[NATIVE-BASELINE.md](NATIVE-BASELINE.md); no accepted P1 performance measurements
are present. A harness PASS qualifies the frozen recorded performance experiment;
firmware correctness, memory/ROM envelopes, streaming deadlines, physical Xbox
behavior and source/license review still require their separate evidence.

## Experiment sequence

Use separate directories and specs for Steam Deck (`machine_role: primary`) and
Windows Ryzen 9 6900HX at `10.0.7.1` (`secondary`). There is no command to average machines. Populate the
baseline manifest from the exact current composed product, its actual build
record and hashes of the binaries/media that the recorder will use.

```sh
python3 tools/storage_perf_compare.py pilot \
  --spec evidence/deck/spec.json --output evidence/deck/aa-schedule.json

# Execute every aa-schedule.json job with the owned recorder, producing aa.jsonl.
# Each adjacent pair uses independent processes/overlays of the same baseline.

python3 tools/storage_perf_compare.py calibrate \
  --schedule evidence/deck/aa-schedule.json --results evidence/deck/aa.jsonl \
  --output evidence/deck/frozen.json

# Archive/review frozen.json BEFORE capturing or reviewing candidate timings.
# Candidate JSON is an identity manifest, with no timing results.

python3 tools/storage_perf_compare.py confirmatory \
  --calibration evidence/deck/frozen.json --candidate evidence/deck/candidate.json \
  --output evidence/deck/ab-schedule.json

# Execute every ab-schedule.json job exactly once, producing ab.jsonl.

python3 tools/storage_perf_compare.py compare \
  --calibration evidence/deck/frozen.json --schedule evidence/deck/ab-schedule.json \
  --results evidence/deck/ab.jsonl --output evidence/deck/report.json
```

Every output file is created exclusively: existing files are never overwritten.
The schedule, calibration and report bind canonical SHA-256 identities; the
calibration/report also bind the exact raw JSONL bytes. JSON files and JSONL
accept UTF-8 with an optional BOM and Windows line endings. Blank JSONL lines,
duplicate attempts and unscheduled extra attempts are rejected. Compare exits
`0` for PASS, `1` for REGRESSION and `2` for INCONCLUSIVE. Other commands exit
`2` on invalid input; their error JSON goes to stderr. Compare writes its full
report to stdout when `--output` is omitted.

Five complete A/A pairs are a noise pilot. Calibration estimates a larger
fixed count; it never chooses fewer than 30 independent pairs. If the pilot
cannot support planning within the predeclared cap, improve controls or declare
a larger A/A experiment and rerun it before candidate results are reviewed.
Do not append favorable retries, replace failures, drop cases, increase the
confirmatory count after inspecting results, or stop once a partial result looks
good. An incomplete confirmatory experiment is INCONCLUSIVE. All aborted,
timeout and error attempts remain recorded and fail acceptance.

## Spec and manifests

The spec is a JSON object with these fields. Hashes are lowercase SHA-256 hex
strings, except Git identities which may be 40- or 64-digit hex. Placeholder
hashes are not evidence; the recorder must independently verify the actual files.

| Field | Required content |
| --- | --- |
| `schema_version` | `1` |
| `machine_id`, `machine_role` | Unique physical host identity; `primary` or `secondary` |
| `baseline` | Identity manifest described below |
| `environment` | Actual `xemu_config`, `host_ssd`, `cpu_governor`, `power_policy`, `thermal_policy`, `memory_profile`, `cpu_gpu_config` |
| `cache_policies` | Nonempty preparation descriptions for `warm` and `cold-ish` |
| `seeds` | Nonnegative integer `workload` and `schedule` seeds |
| `order` | `alternate` or seeded `random` |
| `runner_sha256` | SHA-256 of the exact owned capture adapter, or a hashed inventory of its complete inputs |
| `pilot_pairs` | At least `5`; declared before this A/A capture |
| `minimum_confirmatory_pairs` | At least `30` |
| `maximum_confirmatory_pairs` | Sample-size planning cap, at least the minimum |
| `planning_power` | Desired projected family power, strictly between `.5` and `1` |
| `planning_confidence` | Exploratory per-gate A/A planning confidence, strictly between `.5` and `1` |
| `limits` | Exactly `latency`, `throughput`, `p95`, `p99` ratio thresholds |
| `cases` | The full predeclared case list |
| `structural_policy` | Optional explicit diagnostic companion contract described below; omission retains the original strict same-run counter contract |

Initial proposed limits are `{"latency":1.02,"throughput":0.98,"p95":1.05,
"p99":1.05}`. They are proposed tolerances, not measured results. Freeze/revise
controls and limits using baseline-only A/A evidence before implementation or
candidate timing review. The spec must not contain candidate inputs.

Each baseline/candidate identity manifest contains:

```text
product_commit, roswell_base, source_tree, patch_sha256s (ordered list),
toolchain_revision, pe_sha256, flash_sha256, xemu_sha256, fixture_sha256,
eeprom_sha256, hdd_seed_sha256, iso_sha256
```

The candidate may change product/source, patch, PE and flash identities. Roswell
base, toolchain, xemu, workload fixture, EEPROM and media seed identities must
match A. Every B job must use one exact candidate manifest. Every A job uses the
exact frozen baseline. Pin the full emulator/Vulkan settings and memory profile
in `environment`; preserve command lines, actual file hashes, logs and adapter
inputs with the evidence. Hash matching is a record-consistency check, not proof
that an operator really executed those bytes.

Every case has a unique `id`, `kind`, `cache_policy`, `operations`,
`assertions` and `expected_sha256`. Declare exactly one of `bytes_per_operation`
for uniform requests or `operation_bytes` for the exact issue-order list of
request lengths. Variable requests use the sum of that list, with no rounded
average. Their result must retain the corresponding observed `operation_bytes`
from each completed IOSB. An absent list is incomplete evidence; different
lengths fail even when their total matches. Any supplied list for a uniform
case must also match its declared size on every operation. Small HDD cases must match the
declared `request_bytes` on every operation. See the
[variable-request fix](BENCHMARK-VARIABLE-REQUESTS-FIX.md).
The expected checksum
is computed independently from the owned data that will actually be verified;
it is never inferred from candidate output. Every case has at least 1,000
operations to provide per-run tail evidence. All cases are primary decision
cases: the harness does not combine them into a favorable overall mean.

The required matrix appears **separately under both cache policies**:

| Kind | Required additional fields/cases |
| --- | --- |
| `small-hdd-read` | `queue_depth:1`; `request_bytes` from 512 through 4096 in sector multiples; sector-aligned `alignment_bytes` |
| `fatx-read` | Two distinct `sequence`/`sequence_sha256` identities; exactly `operations:1024`; each sequence at `queue_depth:1,4,12`, with `pressure_pages:0,900` |
| `write-flush` | Positive `real_flushes`; completed writes plus actual device cache synchronization and persistence verification |
| `dvd-xiso` | Both supported suites identified by distinct `variant` names; each has its actual `iso_sha256` |
| `boundary-sg` | Separate `variant:split` and `variant:fragmented` cases |

This is at least 18 cases per cache policy, 36 cases overall. Sequence hashes
must remain consistent across QD/cache/pressure cases. Use the existing owned
1,024-read sequences; do not substitute a shorter replay. DVD cases pin their
own actual ISO hashes in addition to the manifest's primary fixture ISO.
The native adapter must implement the declared segmentation/fragmentation,
memory pressure and queue depth, not merely record those labels.

Workload-specific owned settings (offset list, buffer/page layout, operation
order, reset/reopen policy, cache preparation commands, timeout and evidence
paths) may be additional case/spec fields. They are retained and covered by the
frozen hash. Include timeouts explicitly in those settings before the pilot.

## Recorder contract

Jobs are listed in execution order. Cases are shuffled deterministically inside
each independent pair. Each adjacent A/B pair executes the same case and seed.
`alternate` flips AB/BA across pair indices; `random` uses the pinned scheduler
seed. The workload seed is the base seed plus the independent pair index.
Each job carries its complete frozen case, manifest/hash, attempt identity,
ordinal, pair index, arm, cache policy, overlay identity and fresh-process flag.

The recorder must:

1. Verify actual manifest/fixture/media files and the environment controls.
2. Create a fresh independent overlay from the pinned HDD seed, copy EEPROM
   state independently, prepare the declared caches and start a fresh process.
   Reused mutated images and concurrent jobs invalidate the experiment.
3. Execute the complete workload and verify bytes, status/IOSB/APC/event contract
   assertions and, for writes, actual flush plus reopen/reset persistence.
4. Measure the full batch from first caller issue to final consumer-ready state.
   Record per-operation issue-to-ready latencies using the approved acceptance
   measurement method. Diagnostic phase traces are separate artifacts.
5. Emit exactly one JSON object per scheduled attempt, including errors and
   timeouts, and preserve raw serial/TAP/adapter output. No silent retries.

Acceptance records require `tracing:false` and `expensive_guest_clocks:false`.
Per-I/O firmware tracing, throttled lifetime fixtures and expensive guest-clock
diagnosis cannot be used for acceptance. If a release binary cannot provide the
declared request latency evidence without changing its timing behavior, report
that evidence as missing and obtain an INCONCLUSIVE result; do not invent it.
Independent overlays do not establish a cold host cache. Record the actual cache
preparation and keep cold-ish and warmed cases distinct.

One successful JSONL object has the following fields. Values shown by name are
to be filled from the actual schedule or actual observation, not copied as test
measurements:

| Fields | Meaning |
| --- | --- |
| `schema_version` | `1` |
| `schedule_sha256`, `machine_id` | From the schedule |
| `attempt_id`, `ordinal`, `pair_index`, `arm`, `case_id`, `manifest_sha256`, `workload_seed`, `overlay_id` | From the scheduled job |
| `environment_sha256` | Canonical hash of `schedule.spec.environment` |
| `runner_sha256` | Verified adapter hash, matching the spec |
| `fresh_process`, `fresh_overlay` | Both `true` after independent setup |
| `tracing`, `expensive_guest_clocks` | Both `false` for acceptance |
| `started_utc`, `finished_utc` | ISO 8601 timestamps with UTC offset; enclosing the entire attempt |
| `status`, `error` | `ok` and `null` on success; otherwise `timeout`, `error` or `aborted` with diagnostic text |
| `cache_preparation` | Object with `success:true`, actual `details`, and `policy_sha256` of the declared cache-policy string |
| `timing_scope` | Exact value `caller-issue-to-consumer-ready` |
| `operations_completed`, `bytes_completed` | Actual counts; must equal the frozen operation/byte counts |
| `operation_bytes` | Required for variable request cases: actual completed IOSB byte counts in issue order |
| `assertions_executed`, `assertions_failed` | Actual counts; all declared assertions execute and zero fail |
| `integrity_sha256` | Observed verified data checksum, matching the frozen expectation |
| `media_sha256` | Actual optical image hash for DVD cases, matching the case |
| `flushes_completed`, `durability_verified` | Actual flush count and `true` persistence verification for write cases |
| `elapsed_ms` | Actual complete batch latency, positive and no longer than the enclosing attempt |
| `latencies_ms` | Positive per-operation latencies; exactly one entry per declared completed operation |
| `counters` | Actual workload-window counters; the original contract requires all five healthy small-HDD counts. With `structural_policy`, missing counts do not invalidate timing; qualified structural evidence remains a separate required gate |

For unsuccessful attempts preserve partial counts/checksums and error evidence;
missing latency samples are expected. All identity/setup/time fields still
apply. Successful attempts must explicitly record `error:null`; an `ok` status
with a non-null error is a failed attempt. The final timestamp cannot be later
than the analyzer's current UTC time. Synchronize capture and analysis host
clocks before recording evidence. The report records every supplied attempt
and its status/counts, all
missing attempts, failures, and each case's decision. Timeout/error/abort,
incorrect data, incomplete operations/assertions, missing real flush, failed
persistence or increased healthy-path structural costs produce REGRESSION.
Invalid identity/setup/timing/tracing/sample evidence produces INCONCLUSIVE.

Canonical hashing is defined by Python's JSON serializer, with sorted object
keys, ASCII escaping, no extra separators and no NaN/Infinity:

```python
import hashlib, json
def canonical_sha256(value):
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()
```

For PowerShell, use a small Python helper or the exact recorded schedule hashes;
do not assume `ConvertTo-Json` emits the same canonical bytes. For example, an
owned `Capture-OwnedStorageJob.ps1` can accept the job and schedule objects and
return one complete record object, recording timeout/error itself:

```powershell
$schedule = Get-Content -Raw .\aa-schedule.json | ConvertFrom-Json
$utf8 = [System.Text.UTF8Encoding]::new($false)
$writer = [System.IO.StreamWriter]::new('.\aa.jsonl', $false, $utf8)
try {
    foreach ($job in $schedule.jobs) {
        # Owned adapter must return a failure record even when native execution fails.
        $record = & .\Capture-OwnedStorageJob.ps1 -Job $job -Schedule $schedule
        $writer.WriteLine(($record | ConvertTo-Json -Compress -Depth 100))
        $writer.Flush()
    }
} finally { $writer.Dispose() }
python tools/storage_perf_compare.py calibrate --schedule aa-schedule.json `
    --results aa.jsonl --output frozen.json
```

The adapter in this example is an operator-owned capture implementation, not a
script shipped by this change. An interrupted adapter leaves a partial JSONL;
that file must be retained and cannot pass. Place independent recordings and
raw artifact logs outside source-controlled fixtures.

## Separate structural diagnostic evidence

The published reference remains the exact untraced ROM. A public API recorder
cannot derive private worker, pool, bounce, transport-command or IRQ counts from
read-call totals. Before the pilot, opt into `structural_policy` to preserve
otherwise valid timing evidence while those counts remain unavailable. The
policy, workload and statistical planning rules are frozen with the A/A spec;
the derived confirmatory count is still rebuilt from complete untraced A/A
timings. The counter collector itself can be completed later, but its exact
implementation/source and independent qualification must be pinned and reviewed
before each structural capture. See [the fix writeup](BENCHMARK-STRUCTURAL-COMPANIONS-FIX.md).

The policy requires `schema_version:1`, `mode:diagnostic-companion`, a nonempty
`method` and `route_id`, actual `coverage_plan_sha256` and
`correspondence_rules_sha256` pins, and this exact `counter_units` mapping:

| Counter | Frozen unit |
| --- | --- |
| `upper_worker_hops` | `upper-request-worker-executions` |
| `allocations` | `successful-new-storage-pool-allocations` |
| `bounce_copies` | `bounce-copy-operations` |
| `lower_commands` | `physical-command-issue-attempts` |
| `interrupts` | `storage-isr-entries` |

The method/coverage plan must define actual storage ownership and the complete
caller-issue-to-consumer-ready window. A lookaside checkout is distinct from a
new pool allocation. Count executed upper worker requests, including overflow
and stack-overflow routes, rather than worker thread creation or enqueue calls
alone. Count physical command issue attempts rather than SRBs or DMA callbacks;
identify accepted/rejected/retried commands in supporting evidence. ISR entries
are distinct from serviced/spurious interrupts and polling. Count actual bounce
copy operations and bytes separately from cache/PIO/other copies. The fixed units
prevent a cheaper logical count from replacing a healthy structural gate.
An optional `collector_sha256` in the policy also freezes a collector already
available before A/A; otherwise the reviewed sidecar binds the later collector.

The analysis accepts separate companion JSONL with these additional arguments:

```sh
python3 tools/storage_perf_compare.py compare \
  --calibration evidence/deck/frozen.json --schedule evidence/deck/ab-schedule.json \
  --results evidence/deck/ab.jsonl \
  --structural-results evidence/deck/ab-structural.jsonl \
  --structural-evidence-dir evidence/deck/structural \
  --output evidence/deck/report.json
```

Each companion joins one scheduled healthy small-HDD attempt using
`timing_attempt_id`; list order does not choose the join. It is a distinct run,
with `schema_version:1`, `capture_mode:diagnostic-companion`, `diagnostic:true`,
and a unique independent `capture_run_id` and overlay. It must not reuse any
scheduled timing attempt/overlay identity. Declare a fresh process and overlay; captures must
follow the scheduled healthy-case order without overlapping. Bind these fields:

| Fields | Required binding |
| --- | --- |
| `schedule_sha256`, `calibration_sha256` | Exact A/B schedule and frozen calibration |
| `policy_sha256`, `method` | Canonical policy hash and declared method |
| `collector_sha256`, `collector_implementation` | Actual collector hash and hashed relative-path descriptor for its executable/script bytes |
| `machine_id`, `environment_sha256`, `memory_profile` | Actual declared host, controls and memory profile |
| `acceptance_manifest_sha256`, `capture_manifest` | Scheduled untraced source/ROM identity and full actual diagnostic build manifest |
| `case_id`, `case_sha256`, `pair_index`, `arm`, `workload_seed` | Exact case including request widths/order/depth, paired arm and seed |
| `route_id`, `route_sha256` | Declared route and hashed actual runtime route proof |
| `started_utc`, `finished_utc` | Valid completed capture interval after schedule creation |
| `cache_preparation` | Successful actual preparation, details and the same declared policy hash |
| `counter_scope` | `caller-issue-to-consumer-ready` |
| `status`, `error` | Explicit `ok` and `null` for qualified captures; failed/partial/missing outcomes remain recorded and cannot supply qualified counts |
| `counters` | Actual nonnegative integer values for all five gates; booleans and missing values are invalid |
| `coverage` | `complete:true`, integer zero `lost_events`, `overflows`, `ambiguous_events`; exact `operations_observed`; all five names in `counter_keys` |
| `raw_artifacts`, `qualification` | Readable file-hash-bound evidence and independently reviewed qualification described below |

Diagnostic product/source/patch/PE/ROM identities may differ. Roswell base,
toolchain, xemu, EEPROM and media remain the pinned values. A changed diagnostic
fixture requires qualified workload correspondence; its times never replace
acceptance data. Even if a companion uses the identical ROM, debugger stops,
tracing and observer interference make its timing diagnostic.

Every artifact descriptor has `path` relative to the evidence directory and
actual lowercase `sha256`. Absolute/missing/outside-directory paths and hash
mismatches make the affected structural evidence unavailable. `raw_artifacts`
contains exactly one `counter-ledger`, one `route-proof` and at least one
`qualification-support` role, with distinct paths. Other raw artifacts may be
retained. The counter ledger is JSON with `schema_version:1` and exact copies of
`capture_run_id`, `timing_attempt_id`, `schedule_sha256`, `policy_sha256`,
`counter_scope`, `counters`, `coverage`, `route_sha256`, `status` and `error`. It records observations
from the qualified collector, not values reconstructed from public read counts.
The route-proof JSON has `schema_version:1`, the same `capture_run_id`, actual
`capture_manifest_sha256`, declared `route_id` and `route_verified:true`.
The collector method must justify that runtime route verification in retained
evidence; a static route assumption alone does not qualify it.

The `qualification` descriptor references a reviewed JSON sidecar with
`schema_version:1` and exact `policy_sha256`, `method`, `collector_sha256`,
`capture_manifest_sha256`, `acceptance_manifest_sha256`, `case_sha256`,
`environment_sha256`, `capture_mode`, and `route_id` bindings. It includes a
readable/hash-verified `collector_source` descriptor for the exact source or
source inventory, readable `coverage_plan` and `correspondence_rules` descriptors
whose hashes equal the predeclared policy pins, `reviewed_utc` no later than capture start, and explicit true
`method_qualified`, `coverage_qualified`, `correspondence_qualified` and
`interference_qualified`. Its nonempty `support_sha256s` exactly names the
verified qualification-support artifacts. These cover compiled/inlined route
coverage, allocation/IRP generation and lifetime attribution, absence of event
loss, and whether diagnostic observations can support the untraced structural
claim. The methodology must not be changed after viewing candidate values.

The validator checks declared bindings and actual artifact bytes. It cannot
prove that qualification assertions are true, authenticate the reviewer, or
turn an invented fixture into a native observation. Independent factual review
of the method and supporting evidence remains required. No collector or native
structural measurements are supplied by this analysis change.

Valid actual same-run counts can instead use an acceptance row's
`structural_evidence` object with this full contract. Set `capture_mode:same-run`
and `diagnostic:false`; capture run, overlay, full manifest, time window and
counts must equal that acceptance row. The row must already be a valid untraced
timing attempt. Its cheap counting method still needs the verified implementation,
source, coverage, route and pre-capture qualification. Unqualified same-run
integers cannot bypass the separate-evidence gate. Supplying both an embedded
and separate companion for one attempt, duplicates or unscheduled companions is
an invalid experiment, rather than an opportunity to select favorable evidence.

In this explicit mode, reports include independent `timing_verdict` and
`structural_verdict`, case-level decisions, structural issues/failures, actual
qualified count evidence, policy hash and raw companion JSONL hash. Missing,
incomplete, lost, overflowed, ambiguous or unqualified evidence produces
structural INCONCLUSIVE while valid timing/calibration remains usable. No missing
count is filled with zero. An observed increase in any qualified paired healthy
count remains REGRESSION, even if other companions are unavailable. Every
required structural pair must qualify for combined PASS. Diagnostic latency
fields are ignored; acceptance correctness/durability failures and timing
regressions remain failures independently. Broader persistent/peak memory,
ROM-size, frame/streaming and P3 gates still require their separate evidence.

The report's `structural_attempts` preserves supplied capture outcomes, including
the distinction between missing `error` and explicit `error:null`. A failed or
partial diagnostic does not by itself invalidate unrelated valid timing data.
However, a same-host diagnostic interval overlapping an acceptance interval
invalidates that diagnostic's structural context, the affected timing's
untraced controls and any embedded same-run counts for that contaminated run.
Those timing rows are retained as attempts but removed from
qualified metrics, with attributable issues and INCONCLUSIVE timing decisions;
unaffected valid timing remains extractable. Touching interval endpoints do not
overlap. All declared same-host diagnostic lifetimes also participate in a
separate overlap check before capture qualification. Failed or partial captures
can invalidate other overlapping diagnostics' structural context; neither side
may supply qualified counts. This consistency check does not replace factual native confirmation of
the host/run intervals.

## Public API timing with physical durability still unavailable

The optional `spec.durability_policy` separates generation2 public
write/API-flush/close/reopen/read/full-comparison timing from the required real
device cache-sync and persistence gate. It is explicit opt-in; an absent policy
keeps the earlier strict write requirement. Every write case still declares
positive `real_flushes`, and the full36 matrix still includes writes under both
cache policies. In this first checkpoint there is no physical evidence parser:
every required write durability verdict remains INCONCLUSIVE. Supplied physical
counts or `durability_verified:true` cannot close that gate.

The policy has `schema_version:1`, `mode:"diagnostic-companion"`,
`timing_workload:"public-api-flush-reopen"`, a nonempty physical `method`,
`persistence_scope:"device-cache-sync-and-persistence"`, frozen
`coverage_plan_sha256` and `correspondence_rules_sha256`, and a
`timing_contract:{path,sha256}` descriptor. An optional `collector_sha256` may
remain unset during timing A/A planning. Before any physical capture, actual
collector implementation/source and independent qualification must be bound;
the method/coverage/correspondence rules cannot change after candidate values.

Each write case additionally declares `api_flush_calls == operations` and
`assertions == 11 * operations`, the complete generation2 public workload.
These public calls are distinct from the retained physical `real_flushes`.
Each public timing row supplies `flush_api_calls_completed`,
`reopen_readback_verified`, `durability_policy_sha256` and an
`api_timing_provenance:{path,sha256}` descriptor. All existing operation, byte,
assertion, integrity, clock, process/cache/host, order and untraced scope gates
remain. Durability-only separation also retains the earlier healthy-path
counter requirement unless a separate structural policy is present.

The readable timing contract binds schema1 `public-api-flush-reopen`, exact
fixture identity and readable `fixture_artifact`, `parser_artifact` and nonempty
`source_artifacts`, the full frozen case-to-request hash map, generation2,
eleven assertions per operation, independently reviewed method qualification
before capture, and readable coverage-plan/correspondence-rule descriptors
matching their policy hashes. Existing confined artifact verification checks
all bytes; it does not authenticate reviewers or prove that measurements
occurred. Actual factual independent review remains required.
The contract explicitly declares
`timing_conversion:"recorded-rdtsc-frequency"`, the currently supported
historical generation2 parser conversion. Missing or different conversion rules
remain unknown. Future source-informed conversion requires its separate frozen
importer/mapping work and cannot silently replace this rule or raw metadata.

The raw public JSON ledger binds schema1, scheduled attempt/schedule/manifest,
environment/runner, case/fixture/parser, durability policy and timing contract,
the timing row's latency/scope digest, and any fixed workload identities. Its
`meta`, `summary`, `end` and ordered `operations` retain the actual generation2
native fields. Require complete case/end framing, exact case/cache/count/byte/
assertion mapping, every initialized operation status/IOSB/information/tick,
actual successful flush-call count and complete reopen comparison. Integer
fields come from explicit native strings. In particular, missing raw
`summary.flush_calls` cannot acquire the parser's historical default zero.
Missing or contradictory proof remains unknown; observed zero/wrong API counts,
failed operations/assertions/data or a definite failed reopen comparison remain
REGRESSION. No missing value becomes false, true or zero.

Every batch and operation latency must numerically match
`raw_ticks * 1000 / raw_meta_frequency` milliseconds. Both raw ticks and
frequency must be positive uint64 values; derived and reported values must be
positive and finite. The exact representation allowance is relative tolerance
`8 * sys.float_info.epsilon` (approximately `1.7763568394002505e-15`) with zero
absolute tolerance, applied by `math.isclose`. This handles numeric representation
only and is not a native precision/clock qualification. Rehashed raw counter or
frequency changes cannot keep unrelated reported timing, and a row self-hash is
not a conversion proof. Zero/malformed/out-of-range values remain attributable
unknown evidence.

Every raw operation must also identify the exact scheduled case, rather than
borrowing another case's operations under a matching summary. These ledgers
depend on qualified upstream native parser/importer mapping to the actual raw
capture. Hash equality and native-shaped JSON do not authenticate a capture,
establish its lifetime/route, or make invented rows native evidence.

Use `--evidence-dir` with `calibrate` or `compare`; compare's existing
`--structural-evidence-dir` remains an alias. API timing can feed complete A/A
count planning and its independent `timing_verdict`. The report adds
`durability_verdict`, `durability_policy_sha256`, `durability_issues` and
`durability_attempts`, preserving supplied public and physical fields and raw
descriptor references. Unknown physical durability keeps combined P1
INCONCLUSIVE; a public correctness failure remains REGRESSION. Reported timing
describes the public flush/reopen workload and does not claim device-durable
latency. Diagnostic timing cannot substitute for the accepted public rows.

## Fixed fixture workloads and metadata labels

The current suite consumes case/cache selection and runs fixed request/data
artifacts. It does not consume the scheduler's numeric workload seed. For those
fixtures, optional `spec.workload_policy` declares schema1 `fixture-fixed`,
`seed_semantics:"METADATA_ONLY"`, exact `fixture_sha256` matching the baseline
manifest, and a readable `fixture_contract:{path,sha256}` descriptor. That
contract binds the exact fixture/source artifacts, full case/request hash map,
the same explicit semantics and method qualification before capture.

All independent pairs then retain one constant metadata
`workload_seed = spec.seeds.workload`, accompanied by
`workload_seed_semantics:"METADATA_ONLY"`, `workload_policy_sha256` and a fixed
per-case `workload_identity_sha256` binding policy, fixture and full declared
case/request. Timing and structural rows bind these identities. The label is
never described as a guest-consumed PRNG input; pair index and schedule seed
still control independent process pairing and declared launch order. Without
this policy, legacy base-plus-pair seeds remain unchanged. Policies and request
identities freeze before A/A and cannot be grafted onto old rows. Results cover
the declared fixed workloads, not a varied request population.

The native full36 adapter remains separate work. Its suite/DVD XBE artifacts,
per-case optical ISOs, original HDD seed lineage and actual prepared media bytes
need an explicit reviewed artifact-set/per-case identity mapping. A manifest's
file hash must not be replaced by an invented identity or a different lineage
hash to fit the analyzer. This checkpoint implements analysis of declared
evidence; it does not certify the native adapter, physical durability, clocks,
counter collector or P1 acceptance.

## Confidence and sample-size method

The statistical unit is an independent **run pair**, never an individual read
or frame. Each valid run produces full batch latency, bytes/ms throughput and
nearest-rank request p50/p95/p99. For every case/metric, the tool divides B's run
metric by A's paired run metric. It reports all ratios and absolute per-run
metrics, and bounds the **population median paired-run ratio**.

For `n` pairs choose the largest `k` such that
`P[Binomial(n, 0.5) <= k-1] <= alpha`. With sorted ratios, the lower bound is
`ratio[k-1]` and upper bound is `ratio[n-k]`. When no such `k` exists the bounds
are unbounded, represented as `null`, and acceptance is INCONCLUSIVE.
Use `alpha = .05 / (2 * number_of_cases * 4)` for each one-sided bound. The union
bound gives at least 95% simultaneous coverage across both bounds of all four
metrics and all cases; metrics/cases need not be mutually independent. The
calculation uses floating-point binomial probabilities, with ordinary numerical
rounding rather than a formal arbitrary-precision proof.

Latency/p95/p99 pass only when the upper bound is at most their frozen limit;
throughput passes only when the lower bound is at least its limit. An interval
entirely on the adverse side is REGRESSION; crossing a limit is INCONCLUSIVE.
Every case must pass, the exact frozen count must be present, all attempts must
be valid and all correctness/structural gates must pass for overall PASS.

For planning, count A/A paired ratios inside each metric's acceptance margin.
Compute a one-sided Clopper-Pearson lower bound on that probability at the
predeclared `planning_confidence`. Search for the smallest count at least the
declared minimum whose exact binomial probability of enough inside-margin
pairs reaches `1-(1-planning_power)/(cases*4)`; freeze the largest count required
by any gate. A lower probability at or below `.5`, or a count beyond the cap,
refuses calibration. The frozen file preserves pilot ratios, probability
bounds and all recommended counts for review.

The original A/A ratios are also preserved in a separate `pilot_ratios` ledger,
covering every frozen case/metric and exactly the declared number of pilot
pairs. Both confirmatory scheduling and comparison rederive all gate counts,
inside-margin successes, probability bounds and recommendations from that
ledger. The stored `planning` records must match the complete derivation, and
the confirmatory count must equal its maximum recommendation. Missing/truncated
facts or planning records, altered summaries and a smaller count even above the
30-pair floor are rejected. Older calibration artifacts missing this ledger
must be regenerated from their archived A/A results before candidate capture.

The planning probability bounds are exploratory **per-gate** bounds, not a
simultaneous certification of power. Five pilot pairs leave substantial
uncertainty; more independent baseline A/A pairs may be needed. The projected
power assumes candidate-equivalent runs retain the pilot's probability of
landing inside the margin. It is not proof of achieved power or a guarantee of
PASS. Candidate values never feed planning; final bounds and validity gates
still control acceptance.

The median method is distribution-free under independent representative run
pairs and conservative with ties. It avoids a normality assumption, but it does
not bound the arithmetic mean, worst run, rare catastrophic stalls, or a pooled
population p99. The p95/p99 gates bound the median ratio of **per-run** quantiles.
The 1,000-operation floor provides only basic within-run tail coverage; it does
not make correlated operations independent or precisely estimate extreme
tails. Inspect full distributions and raw logs for rare behavior and retain
separate streaming/deadline qualification. Scheduling and fresh processes help
control noise; they do not prove independence in the presence of thermal drift,
host cache dependence or background interference.

Archive the freeze before candidate capture/review. Hashes and timestamps detect
accidental edits and order violations, but are not signed attestations and do not
prove that nobody previously looked at candidate measurements.

## Authorship and host verification

This tool and its tests were independently authored from the implementation-
neutral requirements in this directory and ordinary Python/statistical
interfaces. No ClassPnP/Disk implementation, private helper body, source patch,
object/disassembly or implementation history was used as an implementation
reference. The test data was chosen independently. This records this tooling's
inputs; it does not establish firmware clean-room provenance or make claims
about other personnel's prior exposure.

```sh
python3 -m unittest discover -s tests/host -p test_storage_perf_compare.py -v
python3 -m unittest discover -s tests/host -v
```
