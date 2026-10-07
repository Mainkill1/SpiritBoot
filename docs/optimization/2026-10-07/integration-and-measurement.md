# Kernel optimization integration and measurement

This packages the independently reviewed public source at commit
`87aba89a6ba9b2a58f2edd6e52d5e3aa1e8649d7`, tree
`f7adb302a762ed1945cc07d9c2ff428c643ba959`. The frozen source passed Task 1
specification and quality review. Runtime qualification and publication of new
BIOS images remain pending controller acceptance. No guest timing or throughput
improvement is asserted here.

## Reproducible source inputs

The existing build driver clones the pristine public Roswell base
`1569e2e89fb47cc72b9c704a8884f98200432bd4` into an isolated work directory,
validates the ordered lock entries and applies them to its index. Both patches
must apply cleanly; `git write-tree` must equal the approved tree above.
The second patch is exactly `git diff --binary 291ad9759f7993cb1f96d73bfa1c6f333c2bef34 87aba89a6ba9b2a58f2edd6e52d5e3aa1e8649d7`
from the public source repository. It includes source, host fixtures and the
public performance guest, with no generated executables or media.

| Order | Patch | SHA256 |
|---|---|---|
| 1 | `patches/roswell/0001-clean-room-kernel.patch` | `747a5974ac714bcf76a6516fc1ed3ced148880907bd41a3f3f62fbd3d60b168f` |
| 2 | `patches/roswell/0002-kernel-call-optimization.patch` | `0e8147f370fc591c1f6b440344d1271aa5d040291e54a15fba650a88ad8ff1f7` |

The first patch and historical BIOS files remain unchanged. Historical release:
262144 bytes, SHA256
`154276a142c7df727ea46f1a35ee9a896f7369221f10d07f21757a61bc8e6d60`;
historical checked: 524288 bytes, SHA256
`7f7cb55be972308b570415863222ff8285e0f4de2d324a12425ee5e33c568ceb`.
The build manifest records the base revision, ordered patch hashes, actual
patched tree, tested source directory, tool versions and output hash.

## Changes and preservation obligations

1. Pin scratch cleanup clears at most 64 successful or rejected prefix pages
   individually, retaining the bulk reset above that threshold. The existing
   PFN lock, translations, preflight, overflow and ownership checks remain.
   Rejected short prefixes can add up to 64 cleanup translations; the budget
   requires controller timing qualification.
2. Pool first-fit search advances beyond the actual conflicting page, preserving
   candidate ordering, hint wrapping and backing allocation behavior.
3. System virtual allocation skips the remainder of an absent PDE span while
   preserving first-fit ordering and boundary behavior.
4. Known custom-object types avoid speculative registry allocation/free. An
   unknown type snapshots the count under the first lock and rechecks duplicates
   under the second only when that count changed. This is conditional on the
   source proof that registry nodes remain distinct, allocated and never removed:
   the 32-bit address space cannot contain 2^32 nodes, so the counter cannot wrap.
   Allocation/free remain outside the lock, lazy initialization follows successful
   allocation, and same/different-type allocation reentrancy remains covered.
5. Modular exponentiation omits the final square whose result is never consumed;
   odd conversion and even result paths still consume the accumulator.
6. SHA context loading copies only the live buffered prefix. Full transforms and
   padding initialize consumed bytes; reserved bytes and caller tail semantics
   remain equivalent, including supported overlapping buffers.
7. DES six-bit reversal uses fixed arithmetic shifts, retaining mutable and
   unaligned table reads, round outputs and CBC feedback/tails.

No ordinal, arity, calling convention, public structure, mutable crypto vector,
hardware ordering, callback, mapping policy, warm persistence or shutdown unwind
policy changes. There is no kernel FPU/SSE fast path. Full pin invariants are an
opt-in diagnostic (`DBG && NXK_PIN_BATCH_DIAGNOSTICS`); ordinary checked and
release builds omit the scans. The host fixture independently verifies scratch
slots on every exit in both ordinary and diagnostic modes.

## Host work evidence

[host-work.json](host-work.json) is copied byte-for-byte from controller-retained
`artifacts/optimization/host-work.json`, produced by the actual-source fixtures
on the frozen source and public baseline. It contains operation counts and
complete caller-state differential hashes. These establish reduced work in
specific source workloads; they are not guest timings. Slot meanings and
compiler options are in patched source `tests/host/kernel-performance/README.md`.

| Operation | Baseline | Candidate |
|---|---:|---:|
| One-page successful pin scratch bytes | 65536 | 2 |
| 64-page successful pin scratch bytes | 65536 | 128 |
| 65/4096-page successful pin scratch bytes | 65536 | 65536 |
| Rejected prefix 32: translations / cleared bytes | 32 / 65536 | 64 / 64 |
| Rejected prefix 64: translations / cleared bytes | 64 / 65536 | 128 / 128 |
| Rejected prefix 65: translations / cleared bytes | 65 / 65536 | 65 / 65536 |
| Pool periodic-blocker search: bitmap reads / probes | 493696 / 3841 | 4096 / 16 |
| All-absent system 4096-page search: PDE reads | 4096 | 4 |
| Cold 64-type registry: comparisons / allocations | 2016 / 64 | 2016 / 64 |
| Known 64-type repeats: comparisons / allocations / frees | 2080 / 64 / 64 | 2080 / 0 / 0 |
| Odd W1 E3 ModExp: multiplies / squares / copied bytes | 6 / 2 / 28 | 5 / 1 / 24 |
| SHA Update r0 Len1: loaded bytes / compressions | 92 / 0 | 28 / 0 |
| DES decoded bit-loop iterations / six-bit groups | 768 / 128 | 0 / 128 |
| 3DES decoded bit-loop iterations / six-bit groups | 2304 / 384 | 0 / 384 |

Implementer evidence reports 88 clean-room host assertions on each source,
30,978 differential optimization assertions, 204 baseline pin assertions and
7,307,629 candidate pin assertions in each mode. Scratch-slot checks account
for most pin assertions; these counts do not describe independent scenarios.
Controller source host logs are retained under
`artifacts/optimization/source-host-evidence/`. Guest lifecycle/native ownership
coverage is still required; host extraction does not model real page tables,
IRQL, backing rollback or native callbacks.

## CI correctness and direct runtime qualification

The firmware workflow builds both variants in the pinned toolchain, checks
`git write-tree` of the manifest source directory, runs existing clean-room
host checks and the new `check.py --optimized`, `pins.py --optimized` and
`pins.py --optimized --diagnostics`. It retains logs and `work.json` as artifacts.
Guests `api-regression`, `clean-room-contracts`, `clean-room-warm-reboot` and
`kernel-performance` build from that same tested source, using pinned nxdk.
All run directly in xemu at 128 MiB with snapshots. The performance guest is a
strict correctness smoke: clean exit, TAP 42/42, zero TODO/SKIP/errors, 41
ordered workloads, valid samples and terminal PASS. CI does not compare its
single runtime with another image. This workflow has been checked locally for
YAML and shell syntax; a new CI pass has not yet been observed.

Controller qualification also retains the existing direct API, contracts,
warm-reboot and matched XISO suites. No HTTP test runner is introduced. The
corrected baseline smoke already passed 42/42; the earlier pool-query fixture
failure remains retained as evidence. The guest now uses public
`ExQueryPoolBlockSize`. Candidate runtime results belong to controller evidence.

## Paired dataset and analyzer

Build the performance guest once from the approved manifest source directory;
freeze its ISO hash and reuse the identical media for both release images.
Collect at least seven sequential pairs, alternating baseline-first on pair 0,
candidate-first on pair 1, and so on. Each capture directory contains the direct
driver `run.json` and `serial.log`. The driver metadata must report 128 MiB,
`open-direct`, `expect_tap=true`, `snapshot=true`, `status=passed`, return code 0
and completely positive TAP without TODO/SKIP/errors.

Use this `pairs.json` schema; paths are absolute or relative to the JSON file:

```json
{
  "pairs": [
    {"baseline": "pair-0-baseline", "candidate": "pair-0-candidate"},
    {"baseline": "pair-1-baseline", "candidate": "pair-1-candidate"}
  ],
  "execution_log": [
    {"pair": 0, "variant": "baseline", "capture": "pair-0-baseline", "started_utc": "2026-10-07T23:00:00.123456Z", "completed_utc": "2026-10-07T23:00:07.123456Z"},
    {"pair": 0, "variant": "candidate", "capture": "pair-0-candidate", "started_utc": "2026-10-07T23:00:08.123456Z", "completed_utc": "2026-10-07T23:00:15.123456Z"}
  ],
  "asset_path_map": {"/work/artifacts/optimization/guests/final-benchmark.iso": "/absolute/controller/guest.iso"}
}
```

The abbreviated example must be expanded to seven complete pairs and fourteen
log entries. Controller timestamps bracket each synchronous driver call at
microsecond precision and must prove chronological nonoverlap. Driver start
stamps have one-second quantization allowance; elapsed duration must fit within
the controller interval. The analyzer never adds elapsed duration to a floored
start stamp to infer execution overlap.

`runtime-inputs.json` must include `baseline_release`, `candidate_release`,
`xemu`, `api_seed` and `benchmark_dvd`, each with `sha256` and `bytes` (or
`size`). Candidate release also includes `source_tree` equal to the approved
tree. Preserve original records and append the final candidate/DVD identities.
Hashes and sizes for xemu/HDD/DVD must match every capture; both flash images
must be release-sized, the baseline hash fixed above, and the candidate distinct
and consistent. An optional `--candidate-build` binds the candidate to its
`build.json` output and exact source tree as well. Literal accessible asset paths
are verified against file bytes. Container paths are resolved only through an
explicit controller `asset_path_map`; the analyzer never guesses mounts.

```sh
python3 scripts/analyze-kernel-performance.py artifacts/optimization/pairs.json \
  --runtime-inputs artifacts/optimization/runtime-inputs.json \
  --candidate-build artifacts/optimization/final-release-v1/build.json \
  --baseline-hash 154276a142c7df727ea46f1a35ee9a896f7369221f10d07f21757a61bc8e6d60 \
  --candidate-hash CANDIDATE_RELEASE_SHA256 \
  --output artifacts/optimization/performance-report.json \
  --markdown artifacts/optimization/performance-report.md
```

PERF metadata fixes guest version 1, the `KeQueryPerformanceCounter` clock,
positive uint64 frequency and three samples. Every workload has samples 0–2,
except `object-cold-64` with sample 0 only. Iteration counts and workload order
match the frozen guest contract. Samples have uint64 ticks, correctness 1 and
eight-digit semantic checksums; checksums must agree within and across captures.
The independent guest KAT and lifecycle assertions supply correctness; analyzer
checks cannot create missing correctness evidence. Missing/duplicate/malformed
PERF lines, changed clock/ISO/checksums, bad TAP, terminal or summary are refused.

The JSON report retains every raw sample, normalized sample, asset record,
controller execution log and input/code hashes. For each workload it reports
all trial medians, per-variant min/max/median, paired differences and median
paired percentage change. Empty-loop overhead is reported explicitly and is
never silently subtracted. Negative percentage means less candidate time.

A timing improvement requires positive baseline-minus-candidate overall median,
a reduction strictly greater than the maximum observed per-variant range
(including raw normalized sample variation), and improvement in at least six
of seven pairs. For more pairs, at least `ceil(6*N/7)` must improve. A symmetric
rule classifies consistent regressions; all other outcomes are timing
inconclusive. Inconclusive timing supports only separately verified work-reduction
claims. No aggregate FPS, gameplay or universal throughput claim follows.

## Deferred correctness work and limits

The [audit](README.md), JSON/CSV row coverage and stub inventory remain preserved.
Fatal generated exports, release/checked no-ops and mutable crypto dispatch are
unchanged. Existing multiple-wait and mutant reference findings remain separate
correctness work. Deferred handle/query/NLS/FPU/APC/shutdown changes require their
own contracts and proof; these optimizations do not certify all kernel behavior.

Benchmark backing allocation/zeroing and crypto validation costs can hide scan
savings. Cold registration is single-sample by design; short rejected pins may
pay added translations. Seven matched trials and the conservative range rule
constrain measurement claims but do not predict a game's frame rate. Final
runtime qualification, budget retention decision, CI results and new BIOS
publication are still controller-owned steps.
