# Boot Setup Implementation Plan

> For agentic workers: implement task-by-task with the executing-plans workflow.

**Goal:** An optional button-entered BIOS setup environment that leaves no
menu-owned RAM or background work after exit.

**Architecture:** Separate a bounded input gate, disposable menu engine and
boot-only native adapter. The implementation uses the existing boot display and
places all private code in INIT, which is discarded before title launch.

**Tech Stack:** Freestanding C11, host C tests, Python standard-library test runner.

**Spec:** `docs/superpowers/specs/2026-10-10-boot-setup-design.md`

## Global constraints

Held X enters setup during the fixed 3,000 ms gate window. A report at or after the deadline
does not extend boot.
No core heap, mutable globals, controller thread or runtime menu callbacks.
Native transient arena budget 4 MiB; whole-kernel settled goal remains 512 KiB.
Do not write EEPROM on browse/cancel or treat partial persistence as success.
Do not modify shipped firmware until actual native integration is qualified.

## Review focus

Unplug/replug cannot carry an entry press into menu confirmation.
Wrapping clocks cannot strand the boot or prematurely accept a backward timestamp.
Unknown settings/flags survive opening, editing other fields, and cancelling.
Uncertain writes cannot take the ordinary continue path.
Failed quiesce cannot scrub DMA-visible RAM; failed release cannot launch a title.

## Task 1: gate and settings/menu core

Files: `src/boot/setup/boot_setup.h`, `src/boot/setup/boot_setup.c`,
`tests/host/boot-setup/test_boot_setup.c`.
Interfaces: `sb_boot_gate_init/poll`, `sb_setup_open/input`,
`sb_setup_field_label/value`, staged `SbSettings`, `SbSettingsStore`.

- [x] Write failing gate tests (held-at-boot, one press, invalid report, timeout,
  late press, uint32 wrap/backward and sticky outcome).
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
- [x] Add host text menu with simulated held-X input and memory-only settings;
  label it a demonstration, not an Xbox boot test.

## Task 3: reproducible host gate and handoff

Files: `tests/host/boot-setup/check.py`, `.github/workflows/boot-setup.yml`,
`src/boot/setup/README.md`.

- [x] Compile/run host tests with warnings-as-errors, ASan/UBSan and optimized code.
- [x] Compile i386 freestanding objects; check undefined symbols and writable
  globals; report code and stack sizes without calling them a runtime census.
- [x] Verify demo, diff, and exact published file hashes; create draft PR.

## Task 4: native boot input and settings backend

- [x] Reconstruct current Roswell using the lock; implement temporary USB/XID input
  with bounded enumeration, stable device generation and real stop/DMA proof.
- [x] Reuse the existing boot display without a second framebuffer; keep the
  presentation behind one replaceable render function for later animation work.
- [x] Add the coordinator at the verified boot phase, before INIT and boot display
  retirement;
  integrate via a new ordered, hashed Roswell patch.
- [x] Implement serialized, verified EEPROM transaction and recovery behavior;
  publish no fake success from existing cached readback.
- [x] Stop OHCI, clear controller ownership, scrub and return the only temporary
  4 KiB DMA page before title launch; discard all private code with INIT.
- [x] Build locked release firmware at 64 and 128 MiB; pass the post-link INIT
  audit, native edit/save/readback/reboot/persistence, and no-input title handoff.

Broader settings categories and a semi-animated boot presentation remain
independent follow-ups. They must preserve this input, persistence, and teardown
contract.
