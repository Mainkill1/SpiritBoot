# Independent kernel compatibility baseline — 2026-10-07

## Result and scope

The six independent compatibility changes are described in
[the feature guide](../CLEAN_ROOM_FEATURES.md). A fresh implementation agent
received a behavior-only specification, pinned public Roswell source and
public nxdk declarations. A fresh source reviewer checked the resulting code;
a separate agent integrated the hashed patch and another reviewed the build
integration. These agents did not receive community firmware, disassembly,
extracted data or the analyst's conversation. The shared filesystem did not
enforce this separation; this is a record of inputs and work, not legal
certification.

The complete implementation is distributed as a checksummed source patch.
The [complete corresponding source snapshot](https://github.com/Mainkill1/SpiritBoot/tree/kernel-source-2026-10-07)
and its [downloadable archive](https://github.com/Mainkill1/SpiritBoot/archive/refs/tags/kernel-source-2026-10-07.tar.gz)
preserve exactly that tree. The packaging-only root commit is
`291ad9759f7993cb1f96d73bfa1c6f333c2bef34`; it adds no source edits.
The base remains public Roswell `1569e2e89fb47cc72b9c704a8884f98200432bd4`;
applying the patch produces tree `8ba32f2153b4716c8cac269bad06a78553f98ded`.
Patch SHA-256: `747a5974ac714bcf76a6516fc1ed3ced148880907bd41a3f3f62fbd3d60b168f`.
Public nxdk ABI reference: `14d5ee97e73347c973f1f57b68b79ec08c9e77f2`.
Implementation revision: `f67f2b1d21f249e1dec8efa652f8747551fae844`.
Integration implementation revision: `0894900624c0639553d51f549b0a8fc4656eaaf5`.

## Builds and reproducibility

| Variant | Bytes | SHA-256 |
| --- | ---: | --- |
| Release | 262144 | `154276a142c7df727ea46f1a35ee9a896f7369221f10d07f21757a61bc8e6d60` |
| Checked, DBG=1 and KDBG=FALSE | 524288 | `7f7cb55be972308b570415863222ff8285e0f4de2d324a12425ee5e33c568ceb` |

Two clean release builds in distinct source/build directories are byte-for-byte
identical. Checked build reproducibility is not claimed; its diagnostics include
build paths. All three manifests record the reviewed tree, patch checksum,
compiler versions and `SOURCE_DATE_EPOCH=1788155396`. The original reference
checkout remains clean. The manifests' `/work` paths name the container mount;
the retained evidence copies those manifests without rewriting them.

The Docker toolchain is `spiritboot-toolchain:verified`, image ID
`sha256:f770af86ab18f86ca6eaac9e491e7deef92eeaca496882229cf8ce3e712f5e44`.
It uses CMake 3.28.3, Ninja 1.11.1, i686 MinGW GCC 13-win32, host GCC 13.3.0 and
Python 3.12.3. Root execution verifies Git trust for the foreign-owned reference;
unprivileged execution verifies the CI ownership configuration. Integration
builds first exposed a container Git-discovery defect; the fix and regression
are documented in [the integration review](../clean-room-integration-review.md).
A parallel build attempt also exhausted this environment's VFS Docker storage.
Successful final builds were sequential and used fresh output directories.

## Host and direct guest checks

All 88 kernel host checks pass from the actual patched build source:
persistence 18, shutdown 9, IDE lifecycle 24, HAL power 24 and physical pins 13.
These are source-level models with test stubs, not hardware or full scheduler
proofs. Build tooling passes 42/42 under root; unprivileged host execution passes
41 and skips the root-only ownership check.

The API, contracts and warm-reboot guest ISOs were freshly built from that same
patched source, using pinned nxdk container
`ghcr.io/xboxdev/nxdk@sha256:bab707b7ed2544e9956d51e7b411a4575ab66120bd608b3237698495203d15f7`.
Both BIOS variants pass these complete plans and exit cleanly:

| Direct guest | Release | Checked |
| --- | --- | --- |
| API regression | 626 PASS, 6 known TODO, 0 unexpected failures / 632 records | Same |
| Targeted contracts | 23/23 PASS, no TODO or skip | Same |
| Two-stage warm reset | 5/5 PASS, no TODO or skip | Same |

Contracts cover eligible low physical-page pinning, overflow safety, detached
prompt, live IDE callbacks during real DVD I/O, pending reverse-order independent
scatter/gather completions, error/cancellation notifications, offsets, short
reads, event and APC behavior. Warm reset uses the unchanged public noreturn
firmware API and verifies same physical address and bytes, callback priority,
duplicate/removal behavior, restored ownership and nested owner unwind followed
by remaining callbacks. Native normal-APC boundary coverage is modeled by the
host tests; the guest does not exhaust every scheduler transition.

Earlier independent probes are retained to show regression detection rather
than only passing fixtures. A pristine baseline relocates the intended pinned
page and stops at the old fatal debugger prompt. On the pre-review independent
implementation, the later 23-contract probe reports 19 PASS / 4 FAIL and the
five-check warm probe reports 3 PASS / 2 FAIL. These older probes differ from the
final freshly built ISO in build bytes; their original identities and outputs
are preserved. They are historical failures, not results of the published BIOS.

All direct runs use Mainkill1 xemu
`458730bf5373f1f0d027450fef7443e3af7a3ae1`, extracted ELF SHA-256
`3790019a2ccab47df1f67982e05856b2a345ec8ce5393967d1ed2187528aada2`,
128 MiB RAM, open-direct boot, empty MCPX/EEPROM paths, Xvfb, Mesa llvmpipe and
dummy host audio. API/targeted runs use snapshot overlays on the unchanged open
HDD fixture. Runtime and guest ISO identities are recorded with each capture.
The HTTP test runner was not used.

## Full XISO qualification

Both final BIOS images complete the pinned Mainkill1 suite with 149 PASS records
(144 leaves, five groups), a COMPLETE 144/144 receipt, zero applicable built-in
oracle failures and clean emulator exits. Guest configuration is byte-identical
to the baseline. IDs, revisions, kinds, duplicate/missing/extra records and the
resolved-plan receipt were checked against the pinned catalog. Release took
268.577 seconds and checked took 264.365 seconds; these elapsed times are not
qualified performance measurements.

The public pinned suite's `hash_compare.py` verifies 253 eligible hashes for
each variant against v0.1.0, and 253 across the two new variants: zero mismatches,
missing or extra records. These are regression comparisons, not speedups.
The S3TC same-address queued diagnostic remains marked `oracle_applicable=false`
by the pinned suite. Its failure counts are 11 for release and 15 for checked;
these diagnostics are retained without rewriting outcomes or adding a waiver.
The comparison excludes the suite's ineligible framebuffer hashes.

Full runs use the immutable catalog/suite in
[the XISO lock](../../sources/xiso-suite-lock.json), suite SHA-256
`10ca07f227ae4e1d03510fcc1d3237304ff4291741d4c552ab33991e71de1738`,
catalog SHA-256
`a5c22393acfab742af570e9a7a7aba8cffae13eaf87ce4e6151d5ec3b9511e87`,
and unchanged full-plan seed HDD SHA-256
`f48103f12382c021cea9d43ad4252c86b7fd4b30fdf56ef48fbeaff9d2705536`.
They retain writes in separate private HDDs. After each emulator exited and the
QCOW2-to-raw conversion completed, FATX extraction copied exact guest results,
configuration and receipt bytes. The saved analysis script records all grading
conditions; `captured` alone is not treated as a pass. The evidence includes
raw records, receipts, verification JSON and complete hash-comparison reports.
The grading script's original workspace defaults are recorded as analysis;
external reproductions must supply matched fixtures using `--baseline-root`.

The earlier intermittent GPU polling assertion remains unresolved. Both final
captures completed on their first attempts; one complete run per variant does
not establish repeated-run stability. GitHub host CI and the checked firmware job pass. The independent release
firmware job for the integration implementation is still running at this record:
[CI run](https://github.com/Mainkill1/SpiritBoot/actions/runs/37689569960).
Local final-source verification is complete; remote completion is not claimed.

Validated files and checksums are in
[`bios/clean-room-xemu`](../../bios/clean-room-xemu/README.md), distributed as
[v0.2.0-xemu-clean-room-baseline](https://github.com/Mainkill1/SpiritBoot/releases/tag/v0.2.0-xemu-clean-room-baseline).


## Limits

Conker: Live & Reloaded gameplay remains untested because no game image was
supplied. Physical Xbox operation, 64-MiB support, attached interactive debugger
input, cancel-routine race stress and measured I/O throughput remain unverified.
The one-IRP scatter/gather design reduces dispatch structurally; it is not a
measured speedup. See the feature guide for persistence replay/boundary behavior,
conservative pin overflow, bounded IDE scheduler exposure and shutdown APC/SEH
cleanup requirements. Other debugger exports and public-key data are outside
these six changes; no proprietary keys were introduced.

## Source, evidence and reproduction

[Build instructions](../BUILD_AND_RUN.md) fetch the public pinned base, verify
and apply the patch in an isolated clone, and build the BIOS. Existing licensing
and per-file notices are retained. No Microsoft BIOS, MCPX, game, SDK or EEPROM
binary is distributed. The earlier v0.1.0 baseline and its images remain unchanged.

[Archived evidence directory](https://github.com/Mainkill1/SpiritBoot/tree/a88247760c91de599a14342158561373b072dfce/docs/evidence/clean-room-2026-10-07) retains exact build/capture
manifests, build and raw emulator/TAP logs, guest identities, source separation,
and host results. Large HDD snapshots and extracted raw disks remain ignored
local artifacts. Paths in manifests refer to the original captures.

## Publication verification

The [release](https://github.com/Mainkill1/SpiritBoot/releases/tag/v0.2.0-xemu-clean-room-baseline)
is published at commit `109ebf603cfe31b9bf9e58235c71c1c1e1e6e8ba`;
[draft PR #9](https://github.com/Mainkill1/SpiritBoot/pull/9) targets the existing
release baseline. Both BIOS files and the checksum file were downloaded from
the public tag and compared byte-for-byte with the locally validated files.
GitHub's attachment endpoint returned HTTP 401, so the release notes link to
the exact binaries tracked in Git. The earlier baseline remains unchanged.
Publication identity and download hashes are retained in the evidence directory.
The publication/evidence-only commits skip redundant CI; source CI runs against
`0894900`, which contains the exact validated implementation and build tooling.


## Main integration qualification — 2026-10-08

The unchanged original PR head `a88247760c91de599a14342158561373b072dfce`
passed [exact-head CI](https://github.com/Mainkill1/SpiritBoot/actions/runs/37773461840).
Both builds reconstruct the same reviewed kernel tree and patch identity above.
Each variant passes 626 API cases plus the six existing TODOs, 23 contracts,
and five warm-reset checks. CI also verifies a second clean release build.
This closes the historical pending-CI observation; it does not rewrite that
observation or add a new gameplay/performance claim.

The fresh release flash matches the historical release hash above. The fresh
checked flash has SHA-256
`6c917a8bb0258a435f6584a3a7618d44f7a81d756b8f25cb7bbb68e3b8eeab43`.
Checked diagnostics contain build paths, so checked-image byte reproducibility
is not claimed. The fresh checked image passed its own native guest checks.
Historical binaries and raw build/guest evidence remain at their immutable
publication references; main contains source, build tooling, regression tests
and these concise provenance instructions. Later title fixes on PR #29 are
separate changes and are not credited to this earlier kernel baseline.
