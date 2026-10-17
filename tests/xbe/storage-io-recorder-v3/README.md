# Generation 3 public FATX I/O recorder

This maintained fixture supports 24 leaves: two fixed 1,024-request metadata datasets, requested QD1/4/12, pressure0/900, and warm/cold-ish policies. It uses public Xbox APIs. The reviewed C, request metadata, TAP emitter and host mocks are retained byte for byte; `source-provenance.json` binds the historical reviewed source closure and [LICENSES.json](LICENSES.json) records an exact per-file license grant without changing those reviewed bytes. The noncompiled `public-input-lineage.json` later received a path-only normalization from its staging-worktree paths to repository-relative paths; its four content hashes and all copied bytes are unchanged. The checked-in metadata initializer matches `replay-requests.csv`, checked by the host suite.

Every request has its own resident, page-rounded slice preserving its recorded alignment. All payloads are poisoned before timing. The APC records status/count/pointer identity and buffer-availability time; the complete byte/canary oracle runs after the batch. Warm cases run and verify a full warmup, then poison every buffer again and restore requested pressure before measured META. Generation 3 timings measure issue to APC availability and cannot be directly compared with V2's in-window byte-verification timings. Caller occupancy and maximum active slots do not establish private device queue depth.

The new `STORAGE-IO-V3-*` protocol is distinct from the V2 parser. META declares `timing=io_apc_available oracle=post_batch_full_bytes`. Per-operation output retains metadata, issue/APC timestamps, statuses, actual counts and oracle results. Normal/quiescent paths release owned resources. A timeout with possible outstanding I/O explicitly retains caller buffers until guest poweroff/VM teardown and reports cleanup incomplete, preventing a use-after-free.

## Build and host tests

From the repository root, with a prepared NXDK installation:

```sh
PATH=/path/to/nxdk/bin:$PATH make -C tests/xbe/storage-io-recorder-v3 NXDK_DIR=/path/to/nxdk
python3 -B -m unittest discover -s tests/host -p test_storage_io_recorder_v3.py -v
```

The build emits `bin/default.xbe` and `pr248-io-recorder-v3.iso`. The historical qualified build used NXDK commit `29638d0b`, clang 19.1.7 and the existing default unoptimized profile plus `-Wall -Wextra`. NXDK warns about optimized 19.x–20.1.2 builds; compiler/profile changes need their own artifact pins and qualification. Rebuilt artifacts have their own identities.

Normal host discovery compiles and checks both `-O0` and `-O2` C bodies in this single suite invocation; it does not rerun the repository's full host suite. Each profile exercises nine methods/51 fixture invocations, including payload protection during callbacks and between issues, no/partial fill, aliasing, late mutation, bad statuses/counts/pointers, duplicate APCs, timestamp rollback, fresh warm poison, allocation failure, timeout retention and all 24 selections. These use mocked public kernel services and count as host fault tests.

## Native setup boundary

The fixture reads exactly one selected case from the runner-prepared private FATX file:

```text
\Device\Harddisk0\Partition1\xemu_perf_tests\xemu_perf_tests_config.json
```

A minimal selection is `{"resolved_plan":{"tests":[{"id":"fatx-d0-q12-p900-synthetic.warm"}]}}`. Prepare it through the supported isolated FATX runner workflow, using a pinned clean seed and independent private HDD/EEPROM. Booting the ISO with an ordinary unprepared HDD fails selection; do not edit a shared HDD to make it pass.

This fixture is deliberately absent from `sources/native-regressions.json`. The simple CI loop boots common HDD inputs and does not prepare/verify this single-case FATX configuration; its memory matrix also exceeds the currently qualified 64 MiB scope. CI integration requires that preparation and isolation support first. Host fault coverage is discoverable now.

The [native qualification note](../../../docs/storage-replacement/IO-RECORDER-V3.md) records six successful warm dataset-0 leaves on the stated 64 MiB rig, including the largest resident slab and complete oracle. It does not qualify the remaining 18 supported leaves, the 12 other matrix families, native performance, counter frequency, durability or private counters.
