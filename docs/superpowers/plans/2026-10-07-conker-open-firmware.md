# Conker Open Firmware Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. The user explicitly waived further approval gates.

**Goal:** Build and verify an open Xbox flash image and provide repeatable xemu test and game captures.

**Architecture:** SpiritBoot owns Python standard-library orchestration and tests. Pinned Roswell sources supply nxldr and xboxkrnl; pinned Mainkill1/xemu supplies the emulator. Ignored artifacts record hashes and raw results.

**Tech stack:** Python 3.11+, Git, CMake, Ninja, i686 MinGW GCC; Ubuntu 24.04 Docker build environment where host tools are unavailable.

**Spec:** `docs/superpowers/specs/2026-10-07-conker-open-firmware-design.md`

## Global Constraints

- Open boot only: no proprietary BIOS or MCPX dependency.
- Default runtime memory is 128 MiB; snapshot disk writes preserve supplied HDDs.
- Pin full source revisions and preserve per-file licenses.
- Flash images are exactly 262,144 bytes (release) or 524,288 bytes (checked); failed builds cannot publish stale outputs.
- Timeout, missing TAP, and a running emulator do not prove compatibility.
- Game data stays local and untracked. No merge or physical hardware flashing.

## Review Focus

- Spaces, quotes, and special characters in paths must preserve subprocess arguments and TOML semantics.
- Wrong or modified source revisions must be rejected before producing an attributed build.
- Existing flash outputs must not survive a failed build as current artifacts.
- Incomplete TAP, TODOs, multiple boots, and timeout must never count as an open-XBE pass.
- Emulator processes and children must terminate on timeout; logs remain available.

### Task 1: Pinned firmware build

**Files:** `sources/firmware-lock.json`, `tools/firmware.py`, `scripts/build-firmware.py`, `tools/Dockerfile.firmware`, `tests/host/test_firmware.py`.

**Interfaces:** `load_lock(path) -> dict`, `build_firmware(source, output, variant, lock_path) -> dict`; CLI accepts `--source`, `--output`, `--variant release|debug`, `--lock`.

- [ ] Write tests for strict lock validation, pinned clean source, stale output invalidation, failure propagation, correct image size, hash/provenance, and spaced paths using real synthetic subprocess fixtures.
- [ ] Run `python3 -m unittest discover -s tests/host -v`; observe failures before implementation.
- [ ] Implement standard-library build driver, lock file, and reusable Docker toolchain.
- [ ] Run host tests; build release/debug from pinned Roswell, then repeat release in a clean build tree and compare SHA-256.
- [ ] Commit verified tooling and record results.

### Task 2: Observable xemu launch and TAP grading

**Files:** `scripts/run-firmware.py`, `tools/firmware.py`, `tests/host/test_firmware.py`.

**Interfaces:** `run_firmware(xemu, flash, hdd, dvd, output, timeout, tap) -> dict`, `grade_tap(text) -> dict`; CLI adds `--xemu`, `--flash`, `--hdd`, `--dvd`, `--output`, `--timeout`, `--expect-tap`.

- [ ] Add failing tests for explicit config, escaped paths, snapshot writes, missing inputs, immutable existing output directory, emulator failure, deadlines, termination, complete/incomplete TAP, TODOs, duplicate tests/boots, and result provenance.
- [ ] Run host tests and observe the new failures.
- [ ] Implement input checks, TOML config, process-group cleanup, retained logs/manifests, and strict TAP grading. Return nonzero for deadline or incomplete/failing tests.
- [ ] Run all host tests and commit.

### Task 3: Open runtime verification and delivery

**Files:** `docs/BUILD_AND_RUN.md`, `docs/provenance/OPEN_FIRMWARE_BASELINE.md`, `README.md`, `.github/workflows/firmware.yml`, `LICENSE`, `.gitignore`.

**Interfaces:** Task 1's build manifest and Task 2's run manifest are the evidence format.

- [ ] Obtain pinned xemu and nxdk tools, build the upstream open API-regression XBE, prepare an openly distributed HDD fixture, and run release/debug test captures.
- [ ] Record actual test outcomes and artifact hashes; identify blockers using raw evidence. Never claim Conker results without the game image.
- [ ] Document exact local and container commands and add CI for host tests and firmware builds.
- [ ] Run host tests, firmware checks, and available integration tests; review the complete branch, fix material findings, then create a draft PR without merging.

## Execution ledger

Progress and rulings are recorded in ignored `artifacts/implementation-progress.md` and the committed baseline evidence document. Existing clone is already a task-specific workspace and feature branch; no extra worktree or approvals are needed.
