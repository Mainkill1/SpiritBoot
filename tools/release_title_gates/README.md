# Final release title automation

These plans are frozen input routes for an attributed release64 candidate.
They do not contain or launch firmware, games, HDDs, EEPROMs, or xemu.
`contract.template.json` deliberately leaves only the candidate firmware
unresolved. Every disc and clean HDD seed is a pinned managed runner asset.

Every phase uses release xemu, a fresh process, a private HDD materialization,
64 MiB, cold application cache, no debugger, and no operator input. PGR2 and DOA
each create state under the exact candidate BIOS and EEPROM in phase one, then
import that exact retained HDD into a second cold process. Reusing a Complex HDD,
an HDD of unknown provenance, or a nominally similar disk invalidates the test.
PGR2 phase one must show the profile-name, license-plate, helmet, and resulting
main-menu states and must record HDD writes before its runtime can be imported.

Run the source tests from the parent directory:

```sh
python3 -m unittest discover -s tests -v
```

Finalize one attributed release64 BIOS. This verifies the supplied hash, updates
every package/runtime/diagnostic firmware reference, validates every phase-one
job, and creates isolated packages. The output path must not already exist.

```sh
python3 finalize_release_jobs.py \
  --flash /absolute/path/to/release64/flash.bin \
  --expected-sha256 FIRMWARE_SHA256 \
  --candidate-id rc-N \
  --contract /private/path/contract.resolved-input.json \
  --base-package /private/path/forza-rclass-gate-0168 \
  --output /private/path/finalized-rc-N
```

Execute every gate with no user input. The client directory is the local
`xemu-test-runner` checkout's `scripts` directory. The command registers the
pinned firmware if needed; creates and cold-reloads a candidate-owned PGR2
profile; runs Forza and two independent Halo 2 launches; creates a DOA save;
then imports and cold-reloads that exact DOA HDD.

```sh
python3 run_release_gates.py \
  --finalized /private/path/finalized-rc-N \
  --evidence /private/path/evidence-rc-N \
  --runner-url http://RUNNER:9368 \
  --runner-client /path/to/xemu-test-runner/scripts \
  --analyzer-dir "$PWD"
```

The run fails closed for crashes, incomplete runner evidence, manual
intervention, corruption/read-error log patterns, bad or incomplete screenshots,
failure to recognize the candidate-owned PGR2 profile, a pre-race screen mistaken
for gameplay, Halo menu identity/launch drift, missing DOA writes, failed DOA
reload, or the Forza R-class world-stream score. The Forza route waits without
input for the stable Starting Grid screen, starts the race once, requires two
consecutive in-race guide detections, records the bounded readiness delay and
load screenshots, and only then starts its 30-second drive. Both
phase-two jobs are created only from their exact retained phase-one `hdd.qcow2`.

Run the product-owned persistence XBE in two cold processes after building its
XISO from the assembled source. Phase A authors 2 MiB through alternating
noncached writes on the clean HDD seed. The tool imports that exact retained
HDD for phase B, which verifies every byte through synchronous and event-based
asynchronous reads and requires at least one pending completion.

```sh
python3 run_cold_storage_gate.py \
  --finalized /private/path/finalized-rc-N \
  --xiso /path/to/cold-storage-persistence.iso \
  --grader /path/to/tests/xbe/cold-storage-persistence/grade.py \
  --evidence /private/path/cold-storage-evidence-rc-N \
  --runner-url http://RUNNER:9368 \
  --runner-client /path/to/xemu-test-runner/scripts
```

To validate an individual generated job independently, run:

```sh
python3 release_job_validator.py job.json title-spec.json
```

The validator rejects unresolved or explicitly rejected firmware hashes, debug or
paused launches, snapshots, non-cold caches, shared guest state, wrong HDD/disc
assets, route drift, unpinned xemu/firmware, and any enabled manual intervention.
