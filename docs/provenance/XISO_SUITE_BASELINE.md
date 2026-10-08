# Mainkill1 direct XISO baseline — 2026-10-07

SpiritBoot's release and checked flashes each completed the published `xemu-perf-tests`
`eng523-report-query-oracles-v2` suite directly in xemu: **149 PASS records,
144 leaves and five groups**, with a matching `COMPLETE` resolved-plan receipt
and clean emulator shutdown. Every catalog ID appeared exactly once with the
expected kind and revision. No applicable built-in oracle failed.

The checked run took 272.027 seconds and release took 264.130 seconds on software
OpenGL. This is a functional
execution result, not a qualified performance or framebuffer-reference
comparison. An earlier cold boot hit an intermittent GPU polling assertion;
that failed diagnostic remains part of the evidence below.

## Matched inputs

[xiso-suite-lock.json](../../sources/xiso-suite-lock.json) records the exact ISO,
catalog, and release-manifest URLs, sizes, and SHA-256 identities. The guest source
is `baf221e339f40801fee9ddd3abf1e1a6d21a1f0a`. Its catalog contains 144 executable
leaves and five structural groups (149 full-suite records). These counts belong
to this release, not to newer source catalogs from another release.

The checked flash is
`2aeb8cbe690b49b76d265a84e36e8b8531b724b954afdc29c3ba4dfd37c12f5a`;
release is
`63b6e70fff47b464140bbff65fbe7090c6c4ea648106e12ba552640ae0945963`.
The emulator, public HDD fixture, 128 MiB memory, software OpenGL, dummy audio,
and empty MCPX/EEPROM paths match the
[open firmware baseline](OPEN_FIRMWARE_BASELINE.md). Every run starts cold with a new snapshot overlay or private HDD.

## Observations and failure

- The 120-second capture reached `GameLoadComposite` workloads. It retained
  57 `TEST_BEGIN` and 30 `TEST_END` serial markers. These are raw marker counts,
  not verified catalog coverage. The capture ended at its deadline.
- A second cold boot closed `BusyPfifo::PFIFOSaturation`, then asserted in
  `BusyPfifo::PgraphPatternPolling` at `busy_pfifo_tests.cpp:201`:
  `ASSERT FAILED: 'invalid_reads == 0'`. The guest stopped making progress. The diagnostic was stopped after 568
  seconds; xemu returned zero on host termination, which does not turn the
  assertion into a pass.

The assertion checks reads of the PGRAPH pattern-color register while GPU work
is queued: each observed value must equal the current or previous generation.
The first capture progressed beyond this test, so the failure is intermittent
in this configuration. These two observations do not isolate firmware, emulator,
test assumptions, or host scheduling as the cause. No kernel workaround or
benchmark exclusion was added.

The release's published validation describes its publisher's runs; it is not
SpiritBoot validation. The first two local captures retained serial and emulator
logs only; their guest output was discarded with the snapshot overlays. The
subsequent direct run retained complete guest JSON and its receipt.

## Full-run verification

The extracted `results.txt` is byte-exact (178,782 bytes), SHA-256
`9f4ede2f21861953272531bded2d5cf91dd4f009689a5983d759b018e3ec342e`.
The guest configuration read back exactly matches the prepared configuration.
The receipt reports 144 selected and 144 emitted leaves, `COMPLETE`, and the
same plan identity. The capture reports exit code zero. No missing, extra,
duplicate, wrong-kind, wrong-revision, or non-PASS record was found.

Release independently produced 149 PASS records, with the same catalog and
configuration checks, 144/144 `COMPLETE` receipt, and exit code zero. Its exact
result SHA-256 is
`8b18c20862a637460de0301490f49b45760aa179dacd652f9f7c26b9a5cc7071`.
It ran through the final private-disk flattening implementation. Both input
seeds and the original open HDD fixture remained unchanged.

The pinned suite's `utils/hash_compare.py` compared these two complete result
files: **253 eligible hash checks, zero mismatches, no missing or extra records**.
This establishes consistency between firmware variants for this fixed workload,
not an independent hardware oracle or a timing comparison. The two undefined
queued-write framebuffer observations below were correctly ineligible.

Two serial `S3TC_FACTOR_ORACLE status=FAIL` diagnostics require their accompanying
metadata, rather than a blanket text-match verdict:

| Leaf | Readback differences | Contract classification |
| --- | ---: | --- |
| `game_load.s3tc_sync_factor.dxt1_same_address_queued` | 10 | `oracle_applicable=false`, framebuffer comparison ineligible |
| `game_load.s3tc_sync_factor.rgba8_same_address_queued` | 2 | `oracle_applicable=false`, framebuffer comparison ineligible |

The pinned `game_load_composite_tests.cpp` explains this classification:
“unsynchronized same-address writes have no defined per-draw source generation.”
These counts are from checked; release retained ten differences for DXT1 and
zero for RGBA8. Their guest outcomes are PASS under that contract. Differences are retained
in `verification.json`; they are not evidence of correct per-draw colors.
All applicable oracle-status records passed with zero failure counts. Report-query
leaves also closed with PASS outcomes and their structured evidence intact.

The bundled older framebuffer reference covers 141 records from a different ISO,
emulator and measurement configuration, and lacks all eight report-query leaves.
It cannot qualify a comparison against this 149-record run. No retail-Xbox
correctness, Conker gameplay, or performance comparison is claimed.

## Direct execution

The user selected direct xemu execution. No HTTP test runner is required.
The first two snapshot captures are diagnostic only; their guest output was
not retained. The direct full run uses a dedicated prepared HDD seed and
`--preserve-hdd`. This run used the initial implementation, a byte copy of the
verified standalone seed in the exclusive capture directory. The final driver
uses `qemu-img convert` to flatten backing chains and external data into a
standalone private QCOW2 before launch; the seed stays intact. A real relative-
backing QCOW2 regression was flattened and compared byte-for-byte at the virtual
disk level. Release used this final implementation. New manifests record the private image hashes before and after use.

The guest configuration enables immediate autorun and shutdown on completion,
sets two warmup iterations, enqueue completion mode, and multiplier one, and
selects all 144 leaf IDs from the matched catalog through a schema-v2 resolved
plan. The exact configuration is retained as `full-guest-config.json`; its plan
identity is
`sha256:5539b7b44304173e8bed11288c2cf8c0e02516d6db313ec3e9645ed899218fe4`.
The XISO itself is unchanged. Results are extracted offline after xemu exits;
a hang or assertion remains a failed/incomplete run regardless of its exit code.

The private seed was prepared from the hash-pinned open HDD fixture using
`qemu-img convert -O raw`, `pyfatx==0.0.8` to write the configuration at
`E:/xemu_perf_tests/xemu_perf_tests_config.json`, then `qemu-img convert -O qcow2`.
Preparation and extraction act only on new private files while the emulator is
stopped. Do not apply those operations to a user HDD or a running guest.

To prepare a fresh seed on a host with `qemu-img` and `pyfatx==0.0.8` installed
(the firmware container supplies `qemu-img`), first convert the pinned open HDD
to a **new** raw path, then write the immutable archived configuration:

```sh
curl -fL https://raw.githubusercontent.com/Mainkill1/SpiritBoot/f3f2e2d60122a4f3c3b3256c0c52c0770561ab3c/docs/evidence/xiso-2026-10-07/guest-config.json \
  -o artifacts/xiso-suite/guest-config.json
qemu-img convert -O raw artifacts/xbox_hdd.qcow2 artifacts/xiso-suite/new-seed.img
python3 - <<'PY'
from pathlib import Path
from pyfatx import Fatx
fs = Fatx('artifacts/xiso-suite/new-seed.img', drive='e')
assert not any(x.filename.lower() == 'xemu_perf_tests' for x in fs.listdir('/'))
fs.mkdir('/xemu_perf_tests')
data = Path('artifacts/xiso-suite/guest-config.json').read_bytes()
fs.write('/xemu_perf_tests/xemu_perf_tests_config.json', data)
assert fs.read('/xemu_perf_tests/xemu_perf_tests_config.json') == data
PY
qemu-img convert -O qcow2 artifacts/xiso-suite/new-seed.img artifacts/xiso-suite/full-seed.qcow2
```

Use previously nonexistent output paths for these conversion commands; they are
preparation utilities, not the capture driver's exclusive-output guard.

A direct launch uses the same Xvfb container setup as BUILD_AND_RUN.md:

```sh
DISPLAY=:99 python3 scripts/run-firmware.py \
  --xemu artifacts/squashfs-root/usr/bin/xemu \
  --flash artifacts/final-debug/flash.bin \
  --hdd artifacts/xiso-suite/full-seed.qcow2 \
  --dvd artifacts/xiso-suite/suite.iso \
  --output artifacts/xiso-suite/direct-full --timeout 1800 --preserve-hdd
```

`captured` means the emulator exited cleanly; it does not grade XISO results.
After confirmed exit, convert only the retained private QCOW2 to a new raw file
and use `Fatx(raw_path, drive='e').read('/xemu_perf_tests/results.txt')` to copy
the exact guest bytes. Retrieve `resolved-plan-result.json` and
`xemu_perf_tests_config.json` from the same directory. Parse copies on the host;
do not alter the retained guest output.
Verify the byte-exact guest JSON, all selected catalog IDs/revisions, leaf/group
counts, per-record outcomes, built-in oracle failures, and the resolved-plan
receipt separately. Framebuffer regression comparison additionally requires a
matched immutable reference; missing reference leaves cannot be counted as
passes. No performance comparison is claimed here.

## Retained evidence

- `artifacts/xiso-suite/debug-boot/`: initial capture and `run.json`.
- `artifacts/xiso-suite/debug-boot-summary.json`: raw marker summary.
- `artifacts/xiso-suite/debug-long-capture/`: second capture and assertion log.
- `artifacts/xiso-suite/direct-full/`: checked full-run capture and private HDD.
- `artifacts/xiso-suite/direct-release/` and `direct-release-results/`: release
  capture, private HDD, byte-exact results, and verification.
- `artifacts/xiso-suite/direct-full-results/`: byte-exact guest results, config,
  receipt, and verification summary.
- `artifacts/xiso-suite/`: matched downloaded release artifacts.

Byte-exact guest results, configuration, capture identity, receipt, and the
verification summary remain in the
[immutable XISO archive](https://github.com/Mainkill1/SpiritBoot/tree/f3f2e2d60122a4f3c3b3256c0c52c0770561ab3c/docs/evidence/xiso-2026-10-07).
Main retains the reproduction instructions rather than raw result records.
Large disks and raw capture directories remain ignored build outputs. The PR records these limits
and the fixture pin. The earlier assertion remains unresolved; one complete
run per firmware variant does not establish repeated-run stability.
