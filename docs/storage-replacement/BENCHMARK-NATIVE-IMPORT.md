# Local native import and relative A/A timing

`tools/storage_native_import.py` replays retained native evidence locally. It
never dispatches a job, starts an emulator, changes a native ledger, or executes
code selected by an evidence JSON field. The caller supplies the collector path
and exact collector, external review and original ledger SHA-256 pins. The
review binds the original native plan, outer manifest and parser; every declared
outer file is checked before the reviewed collector is imported. The product
parser must have the approved source hash. Generic collectors use the pure
`configure(plan_root, plan_sha256)` interface.

The importer observes actual outcomes before grading, compares original raw
artifact hashes and original grading with a fresh evaluation, and checks owned
ready/exit lifetime records. Missing, changed, duplicate or failed evidence is
preserved as failed verification. The original seed and actual prepared image
remain separate identities. There are no invented physical flush, durability or
private structural counts.

Historical V32/V33 and the V343 method pilot remain timing-ineligible. Passing a
functional guard does not change their predeclared scope. The portable Windows
V4 checker validates the actual QPF samples and owned desktop lifetime, while
preserving its unknown provider precision and unqualified storage/cache scope.
This importer currently emits timing proofs only for the Deck method below.

## Fresh A/A inputs

Before capture, freeze the comparator's complete A/A schedule and per-case
artifact map, with `runner_sha256` identifying the actual generic collector.
The source-fixed context contract identifies this importer's exact source,
the owned exact interval helper, source evidence and an independently reviewed
contract receipt. The caller separately pins that receipt's hash. Its review
predates the sealed schedule. Collector code has no embedded plan hash, so the
order is code → schedule → metadata binding/request → native plan → review.

The native plan must declare `timing_calibration_eligible: true`,
`timing_scope: "within-host-relative-AA"`, `schedule_sha256`, and
`context_contract_sha256`. Every request declares and pins `aa-binding.json`
before launch. This host metadata file is not a guest-consumed workload seed:

```json
{
  "schema_version": 1,
  "scheduled_attempt_id": "exact scheduled attempt",
  "schedule_sha256": "sealed comparator schedule digest",
  "manifest_sha256": "resolved job manifest digest",
  "case_sha256": "exact frozen case digest",
  "artifact_set_sha256": "actual artifact-set file hash",
  "case_artifact_sha256": "resolved case artifact digest",
  "workload_identity_sha256": "fixed metadata workload identity",
  "environment_sha256": "frozen environment digest",
  "runner_sha256": "actual reviewed collector code hash"
}
```

The actual input manifest must verify that file's declared bytes. The importer
checks native counts, exact request byte vectors, assertions, cache label,
queue depth and pressure target against the frozen case. Each native attempt
also pins `recorder_xbe_sha256`; actual ROM, emulator and mounted ISO inputs
must match the resolved roles. Original released ISO, recorder/wrapper ISO,
source HDD seed and prepared HDD remain distinct. The normalized preparation
request contract binds case/recipe facts, avoiding a schedule digest cycle.

The clock contract adds `runtime_requirements` with
`method: "deck-post-END-construction-v1"`, the observed `libc_sha256`,
`host_cache_mode`, and a literal `host_controls` map. Pin the actual dynamic
governor/driver/caps, GPU policy, power and SSD policy. Instantaneous frequency,
temperature and battery observations are retained without being called fixed
CPU frequency or total clock accuracy. Guest warm/cold-ish priming is separate
from host cache isolation, which may be cold for both guest policies.

## Actual context and output

The reviewed collector grades strict END → typed post-context queries → owned
final quit. The importer requires actual successful monotonic reads, matching
observer/target boot and time namespace, Seccomp 0, absent LD_PRELOAD/LD_AUDIT,
readable mapped libc identity/hash and a vDSO mapping. The exact pinned product
observer recalculates the mapping proof, including the bounded Btrfs root
subvolume device distinction. Owned PID/start/executable/launch and complete
serial EOF/prefix hashes must agree. A shutdown sampled after END is retained
as a post-window state; continuous running is a stated construction assumption.
Host policy and completed runtime cache receipts must match their separately
declared contract. Missing observations do not qualify from a boolean.

`configure_schedule(schedule, artifact_root=..., clock_review_sha256=...)`
and `emit_job(native_attempt_id, output_root=artifact_root)` emit normalized
rows, original raw counter records, actual artifact/preparation bindings and
readable clock proofs. Proofs are stored under `native-import/<scheduled-id>`;
an identical replay is allowed and differing existing bytes are preserved.
The original recorded frequency and millisecond values remain unchanged.
The comparator separately derives the 733333333 Hz intervals and applies its
exact paired conversion budget. Public API write/readback timing can qualify;
physical durability and missing structural companions keep combined P1 open.
`performance_acceptance_eligible` stays false even when the narrow
`timing_qualified_for_declared_scope` is true.

The CLI accepts `--collector`, `--collector-sha256`, `--review`,
`--review-sha256`, `--ledger`, `--ledger-sha256`, `--evidence-root`, and a new
`--output` JSONL path. The collector and approved native plan/manifest are
co-located local inputs. Fresh A/A additionally uses `--schedule`,
`--schedule-sha256` (the canonical sealed digest), `--artifact-root`, and
`--clock-review-sha256`. It returns 2 when any selected attempt fails verification
or timing qualification. Partial proofs and actual outcome details are retained.

Unsigned receipts provide consistency for owned controlled-lab runs, not
cryptographic authentication of machine execution. This method assumes stable
ordinary clock construction and no unrecorded intervention through the measured
window. It does not prove total provider accuracy, continuous exclusion, an
absolute timing bound, cache controls beyond the declared policy, or full P1.

Portable host tests run without local native archives and exercise general
trust pins, exact schedule mapping, coherent runtime faults, physical unknowns,
public write provenance, independent guest/host cache policy and actual retained
Windows observations. Set `STORAGE_NATIVE_IMPORT_ARCHIVE` to the retained local
evidence directory for the additional V32 all36 and V343 Btrfs context checks;
those archive checks explicitly skip when the directory is not supplied.
