# SpiritBoot Roadmap

The roadmap is ordered to maximize observability and reduce black-screen debugging.

## M0 — Research bootstrap

Acceptance:
- reference repos can be fetched with one command;
- clean-room/provenance rules are documented;
- architecture boundaries are agreed;
- GPL-2.0 is selected for SpiritBoot-owned code and upstream per-file licenses/provenance are preserved.

## M0.5 — Open-stack baseline

Acceptance:
- Roswell builds a reproducible `flash.bin`;
- Mainkill1/xemu direct-boots that image without a proprietary MCPX ROM;
- Fancy Mouse builds as the open MCPX-compatible first stage;
- xbox_kernel_test_suite builds and produces deterministic logs;
- the 379-slot kernel inventory is regenerated from pinned Roswell/Cxbx revisions;
- every experiment records exact upstream revisions.

## M1 — Deterministic build

Acceptance:
- freestanding i386 build is reproducible;
- ELF/map/symbol output exists before flat/flash packaging;
- image generation is deterministic;
- build metadata identifies the source revision.

## M2 — Earliest execution

Acceptance:
- a controlled xemu path reaches SpiritBoot entry;
- early trace emits a build ID and stage markers;
- stack/data/BSS assumptions are validated;
- failures remain observable rather than becoming silent hangs.

## M3 — Minimal platform

Acceptance:
- memory/chipset state is known enough for normal C execution;
- PCI and core device discovery work;
- interrupts and one reliable timer work;
- basic SMBus/system-management access works;
- basic display or another deterministic visible/debug output works.

## M4 — Storage + XBE

Acceptance:
- required ATA/DVD path works;
- FATX or test-media filesystem path works;
- XBE parser has host-side tests;
- a small open test XBE is mapped and entered.

## M5 — Kernel minimum viable runtime

Acceptance:
- the 379-slot kernel export inventory exists and distinguishes mapped, stubbed, data-scaffold and missing-export states;
- minimal memory/thread/synchronization/timer/I/O services required by the first test payloads work;
- each newly implemented behavior has a reproducer or regression case;
- failure reports identify the missing export/behavior instead of only reporting a crash.

## M6 — First retail title

Acceptance:
- a deliberately selected low-complexity title reaches meaningful title code;
- the exact blockers encountered are documented;
- no proprietary runtime code is embedded in SpiritBoot;
- trace is sufficient to distinguish loader, kernel, and hardware failures.

## M7 — Compatibility ladder

Build a progression of titles selected to expand different subsystems rather than selecting only popular games.

Track at least:
- boot stage reached;
- missing/incorrect kernel behavior;
- required hardware subsystem;
- rendered-frame state;
- input state;
- storage/save state;
- audio state;
- regression status.

## M8 — Hardware bring-up

Acceptance:
- safe recovery/deployment process is documented;
- multiple motherboard revisions are identified correctly;
- emulator and hardware trace sequences can be compared;
- revision-specific quirks are contained behind platform boundaries.
