# SpiritBoot Roadmap

The roadmap is ordered to maximize observability and reduce black-screen debugging.

The current Roswell integration provides a reproducible release flash and verified
open-XBE execution in xemu, plus checked builds and retained serial diagnostics.
See [the reproduced baseline](provenance/OPEN_FIRMWARE_BASELINE.md). Conker is the
first retail target; its gameplay remains unverified. The phases below describe
the broader compatibility and hardware work, not completed acceptance claims.

## M0 — Research bootstrap

Acceptance:
- reference repos can be fetched with one command;
- clean-room/provenance rules are documented;
- architecture boundaries are agreed;
- project license is selected before code reuse occurs.

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
- kernel export inventory exists;
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
