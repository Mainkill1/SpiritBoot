# Scalar page-pin release experiment, 2026-10-15

## Decision

Accept the candidate for PR248 integration. The authoritative uninstrumented
release workload shows a repeatable scalar-path gain with exact semantics:

| Workload | Baseline median | Candidate median | Median change | Paired median | Faster pairs | Range relation |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| physical valid | 0.413008 us | 0.377493 us | -8.60% | -9.53% | 10/10 | candidate wholly lower |
| physical reject, device page | 0.199106 us | 0.180942 us | -9.12% | -8.56% | 10/10 | candidate wholly lower |
| scatter accepted, sustained | 497.710704 us | 486.832318 us | -2.19% | -0.80% | 7/10 | overlap |
| scatter reject after 32 pages | 21.285130 us | 17.585567 us | -17.38% | -17.11% | 10/10 | candidate wholly lower |
| scatter reject after 64 pages | 40.289388 us | 34.032507 us | -15.53% | -17.11% | 10/10 | candidate wholly lower |

The accepted-scatter distribution overlaps, so it is recorded as directional
evidence and is not claimed as an isolated gain. It does not show a material
regression. The scalar valid route and all rejection routes are faster in every
matched pair; their candidate ranges are wholly below the baseline ranges.

The product patch contains two source changes. It inlines the scalar
`NxkPageSupplyPin` eligibility predicate while leaving `TryUnlock` eligibility
out of line. It also retains the previously validated scatter/gather
`NxkPageSupplyCommitPin` operation after a successful same-lock eligibility
check. The scalar route is therefore not literally the only product source
change. Every other file in the integration manifest is workload, test,
provenance, workflow, coverage, or evidence material.

## Identity

The isolated SpiritBoot worktree was detached from PR248 commit
`a56f614f77c4bcd14c6b165c72abd701b2bcde95`. Before this experiment it
received the required local 0143 production-gate correction. The SHA-256 of
that file's Git diff is
`46effb1552ec1fe8c6eb6e63b3b8af6168447c75a9f9d73d07f3cddeb746f1a4`.

| Artifact | SHA-256 or tree |
| --- | --- |
| final assembled Roswell source tree | `8b350fa2ee031d2ddfe148c73056587f51ad1cc8` |
| Roswell source revision | `1569e2e89fb47cc72b9c704a8884f98200432bd4` |
| Roswell source worktree digest | `ca1558f0d48289b730eb7aeaacfe53e282a167d3d0b21ac8bccef13fb3819949` |
| firmware lock | `0be542d222306e197be7f8242553d20225f861d08775ed4bb1d7a1e42970fff7` |
| 0144 native workload patch | `76d3256b797c17d6f30ecd05bb3cbd373c4eb38206f65591ae5b4f43d612862d` |
| 0145 product/hot-path patch | `45124339b795bb9fe4ae7150c0810b5d5a911e30ad347757f8903e00f559d585` |
| baseline release 64 MiB BIOS | `4b132b78cbcbd92aa0969919b38c5e804c9f1496f0267132a69457ba0c636319` |
| candidate release 64 MiB BIOS | `d1404fe3d869df1c9cbce30f54db50f72e06e800bc6ccf8d5cd9f91ec7f9821d` |
| baseline unstripped kernel | `77c101003441107b3d9f55302b77e88f04c38080531655863b7132d2040544b1` |
| candidate unstripped kernel | `719bd47cbddc3e97894ee2ad8c38a477e0a1263d28ca4750cff4d02c1094d9b1` |
| page-pin workload XISO | `e293d32ba8bcf9f2adbbe88afa6d91fd02ad543dd79cba36f52c6eebf012a8a5` |
| xemu executable | `3790019a2ccab47df1f67982e05856b2a345ec8ce5393967d1ed2187528aada2` |
| seed HDD | `00d7df7a2bc235f8801764f00b7f40e194d1e392f7a9619d6b2396c89770f6dd` |

The candidate receipt records `release`, 64 MiB,
`complete-candidate` requested and actual, and a successful build.

## Native workload and method

Patch 0144 adds a native release XBE with five measured paths:

- `physical-valid`: 1,048,576 lock/unlock pairs per sample.
- `physical-reject-device`: 1,048,576 rejected calls per sample.
- `scatter-accepted-sustained`: 2,048 calls of 64 pages, or 512 MiB of
  accepted scatter traffic per sample.
- `scatter-rejected-32`: 2,048 calls per sample, rejecting after 32 accepted
  pages and following each rejection with an accepted control.
- `scatter-rejected-64`: 2,048 calls per sample, rejecting after 64 accepted
  pages and following each rejection with an accepted control.

Every workload emits seven samples. A final exact physical-range reallocation
checks that rejected and successful cleanup left no leaked pins. Each run has a
TAP plan of seven.

The comparison used ten matched pairs. Odd pairs ran baseline then candidate;
even pairs ran candidate then baseline. All 20 runs used release firmware,
64 MiB, `-snapshot`, no debugger, and no translation-block profiler. All
20 runs passed TAP 7/7. The analyzer validated all 700 measurement records,
`correct=1`, stable per-workload checksums, immutable assets, and AB/BA order.
Each number above is the median of seven samples for a run and then the median
across ten runs. No control subtraction was used.

Paired candidate changes, in pair order, were:

- physical valid: `[-9.69, -7.39, -4.97, -9.59, -13.09, -11.48, -7.51, -10.47, -9.46, -7.56]%`
- physical reject: `[-10.92, -6.37, -4.34, -7.80, -14.11, -9.47, -8.48, -7.57, -8.63, -11.13]%`
- accepted scatter: `[-3.64, +6.04, -0.57, +7.18, -6.65, -0.38, -3.78, -1.03, +3.20, -10.10]%`
- reject after 32: `[-17.97, -17.60, -17.88, -16.18, -15.78, -16.87, -17.35, -27.68, -13.23, -16.15]%`
- reject after 64: `[-20.52, -19.04, -14.07, -16.14, -10.64, -16.04, -18.59, -29.07, -13.18, -18.08]%`

The complete machine-readable distributions are in `analysis.json` and
`analysis.csv`. `analyze.py` validates the raw capture set before recreating
those files and `summary.txt`.

## Semantic and build gates

Both optimized and diagnostic pin extractions passed 672/672 assertions and
the 1,134/1,134 whole-state differential. The cases cover success, rejection,
overflow, deferred free, aliasing, bounds, and cleanup. The production
scatter/paging DMA fixture passed all 116 cases, including rejection on the
third page after two commits and exact cleanup of allocations, IRPs, MDLs,
references, locks, and pins. The focused product suite passed 93 tests; one
root-only ownership fixture was skipped. Full host discovery passed 509 tests
in 453.288 seconds with 26 environment-specific skips: the root ownership
fixture and PowerShell-only Windows clock/DVD guards. The page-pin source-shape
gate passed.

The exact correctness commands were:

```sh
python3 .scratch/author-v1/tests/host/page-pin-hotpath/check.py .scratch/author-v1
python3 .scratch/author-v1/tests/host/kernel-performance/pins.py .scratch/author-v1 .scratch/evidence/host/final-pins --optimized --vector
python3 .scratch/author-v1/tests/host/kernel-performance/pins.py .scratch/author-v1 .scratch/evidence/host/final-pins-diagnostics --optimized --vector --diagnostics
python3 .scratch/author-v1/tests/host/dma-lifetime/check.py .scratch/evidence/host/final-dma-lifetime
python3 -m unittest tests.host.test_page_pin_scalar_candidate tests.host.test_nxstorage_production tests.host.test_kernel_performance tests.host.test_firmware -v
python3 -m unittest discover -s tests/host -v
```

The XISO build command was:

```sh
docker run --rm \
  -v "$PWD/.scratch/author-v1:/source" \
  -e PATH=/usr/src/nxdk/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  -w /source/tests/xbe/page-pin-performance \
  ghcr.io/xboxdev/nxdk@sha256:bab707b7ed2544e9956d51e7b411a4575ab66120bd608b3237698495203d15f7 \
  make NXDK_DIR=/usr/src/nxdk
```

The candidate firmware build command was:

```sh
docker run --rm \
  -v /home/codex/xemu-shader-workbench-handoff:/work \
  -w /work/.scratch/spiritboot-scalar-pin-candidate-20261015 \
  spiritboot-toolchain \
  python3 scripts/build-firmware.py \
    --source /work/.scratch/roswell-pristine-1569 \
    --output /work/.scratch/spiritboot-scalar-pin-candidate-20261015/.scratch/evidence/candidate/firmware-release64-v4 \
    --variant release --memory-mib 64 --storage-backend complete-candidate
```

Each benchmark arm used this command, with the exact arm BIOS and pair/arm
output directory substituted:

```sh
SDL_AUDIO_DRIVER=dummy xvfb-run -a python3 scripts/run-firmware.py \
  --xemu /home/codex/xemu-shader-workbench-handoff/.scratch/spiritboot-game-profile-20261015/deck-package/xemu \
  --flash "$ARM_BIOS" \
  --hdd /home/codex/xemu-shader-workbench-handoff/.scratch/pr248-final-broad-xiso-20261015/pins/xbox_hdd.qcow2 \
  --dvd "$PWD/.scratch/author-v1/tests/xbe/page-pin-performance/page-pin-performance.iso" \
  --memory-mib 64 --output "$PAIR_ARM_OUTPUT" --timeout 240 --expect-tap
```

The checked-in analysis command is:

```sh
python3 docs/optimization/evidence/page-pin-scalar-20261015/analyze.py \
  .scratch/evidence/native-pairs-sustained \
  --output docs/optimization/evidence/page-pin-scalar-20261015
```

## Code shape

The final release disassembly verifies the intended boundary:

| Symbol | Baseline | Candidate | Effect |
| --- | ---: | ---: | --- |
| `NxkPageSupplyCanPin` | 68 bytes | 68 bytes | exported wrapper retained |
| `NxkPageSupplyPin` | 116 bytes | 136 bytes | predicate instructions inline; no `CanPin` call |
| `NxkPageSupplyCommitPin` | not emitted separately | 40 bytes | scatter commit helper emitted |
| `MmLockUnlockBufferPages` | 696 bytes | 648 bytes | 48 bytes smaller; unlock validation still calls `CanPin` |
| `XbScatterGather` | 1,632 bytes | 1,628 bytes | four bytes smaller |

This confirms that `TryUnlock` eligibility stayed out of line and that only
the scalar pin route received predicate inlining.

## Retained local evidence

The untracked raw evidence is under `.scratch/evidence/` in the isolated
worktree. The key paths are:

- `native-pairs-sustained/`: all 20 immutable run manifests, serial logs, and
  xemu configurations.
- `host/final-page-pin-hotpath.log`, `host/final-pins.log`,
  `host/final-pins-diagnostics.log`, `host/final-dma-lifetime.log`, and
  `host/final-focused-unittest.log`: focused correctness results.
- `host/final-full-unittest.log`: full 509-test host discovery result.
- `candidate/firmware-release64-v4/build.json`: complete build receipt.
- `candidate/final-disassembly-pin.log`: baseline/candidate symbol sizes and
  scalar disassembly.

These generated binaries and raw logs are evidence artifacts and are not files
to port into PR248. The precise source integration set is in
`INTEGRATION-MANIFEST.md`.
