# SpiritBoot: Conker open-firmware execution in xemu

## Intent and success criteria

The user wants SpiritBoot to run Xbox games in xemu, with **Conker: Live &
Reloaded** as the first retail target. The approved direction is to use Roswell's
existing open Xbox kernel and loader, integrate a repeatable firmware build and
launch path, validate an open XBE, and fix demonstrated Conker blockers.

The first deliverable is a buildable, observable open-firmware integration.
Conker compatibility is a separate evidence gate: it is complete only after a
fresh boot reaches its menu and a playable scene, with working controller input
and audio, followed by a ten-minute run without a kernel crash or reset. Record
visual defects and measured frame cadence; this specification sets no 30 FPS
requirement. Launching xemu or reaching an XBE entry point does not prove game
compatibility.

## Current evidence

- SpiritBoot `main` at `4cc47b2` contains documentation and reference-fetching
  scripts, but no firmware implementation or build system.
- Open foundation PR #2 proposes Roswell, Fancy Mouse, and the Mainkill1 xemu
  fork. It is not merged. Integration must preserve this work and avoid merging
  or overwriting that PR implicitly.
- The `research/kernel-correlation` branch inventories exports and test gaps.
  Export resolution is not evidence of behavioral compatibility.
- Roswell at `1569e2e89fb47cc72b9c704a8884f98200432bd4` documents direct boot
  without an MCPX ROM and Halo gameplay in xemu. Its README's 1 MiB image claim
  is stale: the linker and generator specify 256 KiB release / 512 KiB checked.
  Its documentation does not establish Conker support. These are upstream
  reports, not results reproduced in this workspace.
- Mainkill1/xemu `main` observed at
  `e3798f995b9cbe1de3095b189a9370044a7db466` has existing Conker renderer work.
  Issue #285's game and performance evidence does not validate Roswell firmware.
- Execution uses the pinned public release at
  `458730bf5373f1f0d027450fef7443e3af7a3ae1`, after current-main Actions artifact
  access failed. See baseline evidence for the exact runtime and results.
- No Conker image, HDD image, or runnable xemu binary is present in the inspected
  workspace. The MinGW cross compiler, CMake, and Ninja are also absent.

## Selected approach and alternatives

Use Roswell's existing `nxldr -> xboxkrnl -> XBE` boot chain, with the user's xemu
fork as the compatibility target. Pin both repositories to full revisions.
Keep upstream checkouts under ignored `.reference/`; SpiritBoot owns integration
scripts, tests, manifests, and evidence. Any kernel changes belong in a separately
reviewable Roswell fork or revision-bound patch series with preserved notices.

Writing a new kernel from scratch adds extensive scheduler, memory, I/O, and ABI
work before testing the game. An immediate Fancy Mouse boot-ROM integration adds
another boot stage without proving Conker behavior. Both are deferred; direct
boot is the chosen development contract. A future accurate boot-ROM path must
have its own validation.

## Build contract

- Linux is the first supported build host. Use the upstream i686 MinGW GCC
  toolchain, CMake, Ninja, multilib host compiler, and upstream-required tools.
  Record their versions. Do not substitute native GCC or Clang silently.
- Produce release and checked builds using Roswell's toolchain file. Checked
  builds use `DBG=1` for serial diagnostics. Default runtime memory is 128 MiB;
  64 MiB and physical hardware are not acceptance targets for this milestone.
- Build Roswell's `flash` target and validate a fresh 262,144-byte release or
  524,288-byte checked output, as specified by the pinned loader linker script.
  Record the image SHA-256, upstream revisions, build options, tool versions,
  and local patch identity. Never accept an old output after a failed build.
- Verify two clean builds with identical inputs produce identical flash hashes.
  If upstream metadata prevents that, identify and fix or explicitly report the
  cause before claiming deterministic output.
- Proposed SpiritBoot files: `sources/firmware-lock.json`,
  `scripts/build-firmware.py`, and `docs/BUILD_AND_RUN.md`.

## Launch and evidence contract

- `scripts/run-firmware.py` accepts explicit xemu, flash, HDD, optional DVD,
  output-directory, and timeout paths/options. Paths containing spaces work.
  Validate inputs before launch and invoke subprocesses without shell expansion.
- Open-firmware runs configure an empty boot-ROM path, a generated/default
  EEPROM, 128 MiB RAM, and the selected flash image. Do not require proprietary
  MCPX or Microsoft BIOS files. Test this on the pinned xemu fork.
- Use xemu snapshot disk writes so the supplied HDD is preserved. Start from
  cold boot; saved states from another kernel cannot establish compatibility.
- Capture serial boot/kernel output and emulator stdout/stderr. Store commands,
  asset hashes, revisions, options, elapsed time, and process exit information
  in `artifacts/<run-id>/run.json`, alongside logs. Artifacts remain ignored.
- A timeout is a bounded capture result, not a passing boot. Keep failures and
  partial logs. Distinguish launch failure, kernel failure, test failure, and
  capture deadline. Never infer successful gameplay solely from process uptime.
- Game binaries and user EEPROMs are supplied locally and remain untracked.
  Download only openly distributed fixtures from recorded sources. Do not
  upload game images, disks, EEPROMs, or raw user artifacts to GitHub.

## Verification ladder

1. Host tests exercise lock parsing, missing inputs, argument handling, output
   freshness, manifest recording, nonzero subprocess exits, timeouts, and paths
   with spaces. Use synthetic fixtures for these tests.
2. Clean build verification establishes flash size, provenance, and repeatability.
3. Build and run Roswell's open API-regression XBE with a pinned nxdk toolchain.
   Require a complete TAP plan, matching result count, no unexpected failures,
   and no repeated test boot. List TODO cases separately from passes. Preserve
   raw output rather than relying on upstream's temporary-log cleanup.
4. Cold-boot the user's Conker XISO with the verified flash and an isolated HDD.
   Record entry, menu, playable-scene, input, audio, and stability observations.
   Use screenshots/video or human observation where logs cannot prove a stage.
5. Reduce each failure to its first observable boot, loader, kernel, or device
   blocker. Add a focused regression before modifying that component. Repeat
   the open-XBE suite and affected game stage after each fix.

## Scope and review boundaries

The initial implementation plan covers pinned build/run integration and the
open-XBE baseline. Game-specific kernel and emulator changes are driven by the
captured failure and receive focused plans once that evidence exists. Do not
invent missing API behavior or alter the unrelated renderer/performance PRs.

GPL-2.0 is the existing foundation branch's selected umbrella license; preserve
upstream per-file licenses and attribution for reused code. Keep proprietary
source, ROMs, keys, games, and SDK material out of tracked changes.

Local implementation and draft PR preparation are within the requested work.
Do not merge existing PRs, publish compatibility claims, or flash physical
hardware as part of this milestone. When runtime assets are unavailable,
complete build/tooling work and state exactly which execution gates remain
unverified.

## Evidence sources

- https://github.com/Mainkill1/SpiritBoot/pull/2
- https://github.com/Mainkill1/SpiritBoot/tree/research/kernel-correlation
- https://github.com/mborgerson/roswell/tree/1569e2e89fb47cc72b9c704a8884f98200432bd4
- Roswell `README.md`, `docs/building.md`, `docs/design.md`,
  `tools/run-xemu`, `tools/api-regression-run`, `.github/workflows/build.yml`
- https://github.com/Mainkill1/xemu/issues/285

## Approval boundary

The user approved the direction and explicitly instructed continued execution
without further approval requests. Review artifacts are maintained alongside
implementation; that instruction overrides skill approval gates.
