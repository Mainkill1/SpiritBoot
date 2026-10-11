# Boot Setup Implementation Plan

> For agentic workers: implement task-by-task with the executing-plans workflow.

**Goal:** An optional button-entered BIOS setup environment that leaves no
menu-owned RAM or background work after exit.

**Architecture:** Separate a bounded input gate, disposable menu engine and
coordinator-owned arena retirement. Native adapters and ROM linking remain an
explicit second stage; do not enable an unqualified stub in shipped firmware.

**Tech Stack:** Freestanding C11, host C tests, Python standard-library test runner.

**Spec:** `docs/superpowers/specs/2026-10-10-boot-setup-design.md`

## Global constraints

Start held 600 ms; 2,000 ms gate window; maximum valid sample gap 100 ms.
No core heap, mutable globals, controller thread or runtime menu callbacks.
Native transient arena budget 4 MiB; whole-kernel settled goal remains 512 KiB.
Do not write EEPROM on browse/cancel or treat partial persistence as success.
Do not modify shipped firmware until actual native integration is qualified.

## Review focus

Unplug/replug cannot combine hold durations or confirm a save.
Wrapping clocks cannot strand the boot or prematurely accept a backward timestamp.
Unknown settings/flags survive opening, editing other fields, and cancelling.
Uncertain writes cannot take the ordinary continue path.
Failed quiesce cannot scrub DMA-visible RAM; failed release cannot launch a title.

## Task 1: gate and settings/menu core

Files: `src/boot/setup/boot_setup.h`, `src/boot/setup/boot_setup.c`,
`tests/host/boot-setup/test_boot_setup.c`.
Interfaces: `sb_boot_gate_init/poll`, `sb_setup_open/input`,
`sb_setup_field_label/value`, staged `SbSettings`, `SbSettingsStore`.

- [x] Write failing gate tests (held boot key, short press, disconnect, source change,
  gap, timeout, late press, uint32 wrap/backward, sticky outcome).
- [x] Implement gate and verify tests.
- [x] Write menu tests (neutral entry, edges, confirmation, supported fields, unknown
  bits, unchanged save, changed-word mask, rejection and uncertain commit).
- [x] Implement editor and verify the real production bodies under sanitizers.

## Task 2: retirement and developer demonstration

Files: `src/boot/setup/boot_arena.c`, `tools/boot_setup_demo.c`, same test file.
Interface: `sb_boot_arena_retire(SbBootArena *, const SbArenaOps *)`.

- [x] Write failing lifecycle tests (stop-before-scrub, scrub-before-release,
  failed stop, failed release/retry, repeated release, invalid/overlapping spans).
- [x] Implement checked retirement with non-elidable clearing.
- [x] Add host text menu with simulated Start-hold input and memory-only settings;
  label it a demonstration, not an Xbox boot test.

## Task 3: reproducible host gate and handoff

Files: `tests/host/boot-setup/check.py`, `.github/workflows/boot-setup.yml`,
`src/boot/setup/README.md`.

- [x] Compile/run host tests with warnings-as-errors, ASan/UBSan and optimized code.
- [x] Compile i386 freestanding objects; check undefined symbols and writable
  globals; report code and stack sizes without calling them a runtime census.
- [ ] Verify demo, diff, and exact published file hashes; create draft PR.

## Task 4: native boot input, overlay and settings backend (merge blockers)

- [ ] Reconstruct current Roswell using the lock; implement temporary USB/XID input
  with bounded enumeration, stable device generation and real stop/DMA proof.
- [ ] Link and pack the overlay/assets separately; implement a bounded minimal NV2A
  renderer with owned framebuffer and complete scanout handoff.
- [ ] Add the coordinator at the verified boot phase, not in freed INIT code;
  integrate via a new ordered, hashed Roswell patch.
- [ ] Implement serialized, verified EEPROM transaction and recovery behavior;
  publish no fake success from existing cached readback.
- [ ] Return/scrub overlay, input, framebuffer, stack and page-table allocations;
  prove allocator ownership and warm-persistence preservation at both capacities.
- [ ] Run the spec's release/checked/native/game gates; record results before
  changing the draft status. Broader settings categories get independent changes.
