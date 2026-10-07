# SpiritBoot

**SpiritBoot** is an experimental, clean-room, open-source boot firmware and Xbox-compatible runtime project for the **original Xbox**.

The long-term goal is not merely to display a boot screen. The goal is to replace enough of the proprietary boot and kernel stack that an original Xbox title can be initialized, loaded, and run without requiring a Microsoft BIOS image in the SpiritBoot source tree.

> **Status:** bootstrap / research framework. No game-boot compatibility is claimed yet.

## Project goals

SpiritBoot should eventually provide:

1. A reproducible, open build that produces an Xbox bootable firmware image.
2. Early x86 entry and deterministic platform initialization.
3. Original Xbox chipset, memory, interrupt, timer, SMBus, PCI, video, storage, input, and other required platform bring-up.
4. A documented strategy for the MCPX boot stage so emulators can boot SpiritBoot without depending indefinitely on a dumped proprietary MCPX ROM.
5. An XBE loader capable of validating, mapping, relocating, and launching Xbox executables.
6. An open implementation of the Xbox kernel ABI and runtime behavior required by software launched from SpiritBoot.
7. Enough hardware and kernel compatibility to boot increasingly complex homebrew and retail titles.
8. Support for both emulator-first development and eventual testing on original hardware.
9. Built-in tracing and diagnostics so every boot stage can be measured and compared against documented hardware behavior.
10. A clean provenance trail for every implementation decision.

## Non-goals

SpiritBoot is **not** intended to:

- redistribute Microsoft BIOS, kernel, dashboard, MCPX ROM, XDK, game, or other proprietary binaries;
- depend on a copyrighted BIOS dump as source material;
- become an xemu fork or Cxbx-Reloaded fork;
- duplicate an emulator inside the firmware;
- claim retail compatibility before the required kernel behavior exists.

## Recommended implementation route

SpiritBoot will **not** begin by rewriting the entire Xbox software stack from zero. The initial implementation route is:

```text
FAST / DEVELOPMENT
Mainkill1/xemu -> Roswell flash/nxldr -> open xboxkrnl -> XBE

OPEN / ACCURATE
CPU reset -> Fancy Mouse Boot ROM -> Roswell/SpiritBoot flash -> open xboxkrnl -> XBE

REFERENCE
xemu/hardware -> user-supplied original firmware -> test XBE
```

Roswell is the initial open kernel/loader foundation. Fancy Mouse provides the open MCPX-compatible boot-ROM path. Cxbx-Reloaded and the Xbox Kernel Test Suite are behavioral references/test partners. SpiritBoot should fork or replace components only after the compatibility gap is measured.

## What “working” means

| Level | Target | Exit condition |
| --- | --- | --- |
| S0 | Build | Reproducible freestanding x86 build produces a deterministic image |
| S1 | Execute | SpiritBoot reaches its own entry point in an emulator and emits trace output |
| S2 | Bring-up | RAM, chipset, interrupts, timers, PCI/SMBus and basic video are initialized |
| S3 | I/O | ATA/DVD, FATX access, input and required device services work |
| S4 | XBE loader | A known open/homebrew XBE can be parsed, mapped and entered |
| S5 | Open kernel ABI | Required Xbox kernel exports and semantics exist for controlled test programs |
| S6 | First title | A simple retail title reaches meaningful executable/game code |
| S7 | Compatibility | Kernel/HAL behavior supports a growing compatibility suite |
| S8 | Hardware | The same design boots reliably across supported physical Xbox revisions |

A firmware image reaching S2 is useful research progress, but it is **not yet a replacement capable of booting retail games**.

## Proposed architecture

```text
MCPX / emulator handoff
        |
        v
+------------------------+
| stage0 / reset entry   |
+------------------------+
        |
        v
+------------------------+
| firmware bring-up      |
| CPU / RAM / chipset    |
+------------------------+
        |
        v
+------------------------+
| platform HAL           |
| IRQ / timer / PCI      |
| SMBus / ATA / USB      |
| NV2A / MCPX services   |
+------------------------+
        |
        v
+------------------------+
| Spirit kernel/runtime  |
| memory / objects       |
| threads / sync / I/O   |
| kernel export ABI      |
+------------------------+
        |
        v
+------------------------+
| XBE loader             |
+------------------------+
        |
        v
+------------------------+
| title / dashboard      |
+------------------------+

Trace hooks span every layer.
```

### Boot / stage0

- Establish a known CPU state.
- Establish stack and early memory assumptions.
- Detect how SpiritBoot was entered: hardware, modchip/TSOP, or emulator test path.
- Hand off to platform initialization with the smallest possible amount of policy.

### Platform / HAL

- Own hardware-specific register access and revision differences.
- Provide interrupts, timers, PCI, SMBus, ATA/DVD, USB/input, EEPROM access, and basic video bring-up.
- Keep raw hardware knowledge out of higher-level kernel code where practical.

### Kernel/runtime

- Implement the ABI and observable behavior expected by Xbox software.
- Provide memory management, threads, synchronization, objects/handles, I/O, timing, exceptions, and other required kernel services.
- Implement compatibility from tests and documented behavior rather than proprietary source.

### XBE loader

- Parse XBE structures.
- Validate address ranges and image metadata.
- Map sections and establish executable state.
- Resolve required kernel imports/exports.
- Transfer execution with a documented launch contract.

### Trace

- Make early boot observable.
- Record stage transitions, register/device initialization, kernel calls, timing, failures, and assertions.
- Support a low-overhead release-disabled mode and a verbose research mode.

## Reference projects

SpiritBoot is a clean-room integration and implementation project. Existing open projects contain years of Xbox hardware and software research and may be referenced, forked, or reused where their licenses and provenance permit. We should not rewrite solved components merely to call the result clean-room.

| Project | Why it matters |
| --- | --- |
| [mborgerson/roswell](https://github.com/mborgerson/roswell) | Primary open xboxkrnl/flash foundation. Already builds a flash image and can direct-boot in xemu without a separate boot ROM. |\n| [SnowyMouse/fancy-mouse-boot-rom](https://github.com/SnowyMouse/fancy-mouse-boot-rom) | Open MCPX boot-ROM replacement for the hardware-faithful boot path. |\n| [XboxDev/cromwell](https://github.com/XboxDev/cromwell) | Existing free/legal Xbox BIOS replacement and low-level hardware bring-up reference. It intentionally does not boot original Xbox games. |
| [Mainkill1/xemu](https://github.com/Mainkill1/xemu) | Primary SpiritBoot emulator integration, instrumentation, compatibility and performance target. |\n| [xemu-project/xemu](https://github.com/xemu-project/xemu) | Upstream hardware model/reference used to keep SpiritBoot integration separable from fork-specific work. |
| [Cxbx-Reloaded/Cxbx-Reloaded](https://github.com/Cxbx-Reloaded/Cxbx-Reloaded) | Useful reference for XBE loading, Xbox kernel/API behavior and title compatibility research. Its host-side HLE architecture is not a drop-in firmware implementation. |\n| [Cxbx-Reloaded/xbox_kernel_test_suite](https://github.com/Cxbx-Reloaded/xbox_kernel_test_suite) | Hardware-backed kernel API conformance tests; primary path for turning unknown behavior into repeatable evidence. |\n| [Cxbx-Reloaded/XbSymbolDatabase](https://github.com/Cxbx-Reloaded/XbSymbolDatabase) | XDK/static-library symbol identification for understanding retail XBE behavior without treating opaque addresses as unknown code. |
| [XboxDev/nxdk](https://github.com/XboxDev/nxdk) | Open Xbox SDK, startup code, drivers and a good source of small test payloads for validating SpiritBoot independently of retail software. |
| [XboxDev/xboxpy](https://github.com/XboxDev/xboxpy) | Hardware/software interaction tooling useful for real-console probing and behavioral comparison. |
| [XboxDev/xbox-linux](https://github.com/XboxDev/xbox-linux) | Additional historical hardware-driver and platform research. |

Use the helpers under `scripts/` to clone/update these into an ignored local `.reference/` directory. They are deliberately **not vendored into SpiritBoot**.

## Clean-room and provenance rules

### Do

- document the observed behavior being implemented;
- link the public/open reference or experiment that motivated a change;
- write focused tests before or alongside compatibility behavior;
- record hardware revision, emulator revision and test payload when behavior differs;
- keep implementation code separable from reference checkouts;
- record any copied/adapted open-source code and its license.

### Do not

- commit proprietary Microsoft BIOS, kernel, dashboard, MCPX or XDK binaries/source;
- copy disassembly or decompiled proprietary code into SpiritBoot source;
- commit Xbox secret keys or other unnecessary proprietary material;
- copy code from reference projects without first checking license compatibility and attribution requirements;
- describe guessed behavior as verified hardware behavior.

## MCPX strategy

MCPX is a separate early-boot problem from the flash/kernel compatibility problem. SpiritBoot should support three explicit modes:

1. **Fast/direct:** xemu supplies the documented entry/reset state needed to execute Roswell/SpiritBoot directly. No proprietary MCPX ROM is required.
2. **Open/accurate:** Fancy Mouse Boot ROM performs the open MCPX-compatible first-stage path and hands off to the open flash/kernel stack.
3. **Reference:** a user may supply original MCPX/flash images for black-box comparison. These are never distributed by SpiritBoot.

Direct boot is the default development path; Fancy Mouse is the accuracy/hardware path. Neither should block kernel conformance work.

## Kernel compatibility is the critical path

Cromwell demonstrates that an open Xbox BIOS can initialize the machine, and Roswell already provides an open Xbox kernel/flash foundation that boots some Xbox software. SpiritBoot should measure and extend that base rather than recreate solved NT/kernel plumbing. Retail game compatibility still requires substantial behavioral conformance work.

SpiritBoot must determine and implement the observable Xbox kernel contract used by titles, including at minimum:

- kernel export resolution;
- virtual/physical memory behavior;
- threads and scheduling;
- synchronization primitives;
- timers and timekeeping;
- exceptions and fault behavior;
- object/handle semantics;
- file/device I/O;
- executable launch state;
- interrupt/DPC/APC behavior where required;
- HAL services and hardware-facing kernel APIs.

Implementation should be driven by **usage and tests**, not an attempt to rewrite every service before the first title runs.

## Development phases

### Phase 0 — Bootstrap

- [x] Use GPL-2.0 for SpiritBoot-owned code; preserve upstream per-file licensing and attribution.
- [ ] Add freestanding x86 toolchain/build system.
- [ ] Produce a deterministic binary artifact.
- [ ] Add map/symbol outputs.
- [ ] Add an emulator launch/test wrapper.
- [ ] Add serial/debug trace output.

### Phase 1 — First execution

- [ ] Define reset/entry contract.
- [ ] Reach C code from early assembly.
- [ ] Validate stack, BSS/data initialization and memory assumptions.
- [ ] Add fatal/assert path visible in xemu.
- [ ] Record boot-stage timestamps.

### Phase 2 — Hardware bring-up

- [ ] CPU/chipset state.
- [ ] RAM sizing and initialization.
- [ ] PCI enumeration.
- [ ] Interrupt routing.
- [ ] Timer sources.
- [ ] SMBus/system-management devices.
- [ ] EEPROM access.
- [ ] Basic NV2A/display output.
- [ ] ATA/DVD.
- [ ] USB/input.
- [ ] Xbox revision detection and quirk table.

### Phase 3 — Storage and loader

- [ ] FATX read support.
- [ ] DVD/filesystem path required for test media.
- [ ] XBE parser.
- [ ] Section mapping/protection.
- [ ] Import/export resolution.
- [ ] Controlled homebrew entry.
- [ ] Reproducible loader tests using nxdk-built payloads.

### Phase 4 — Open kernel/runtime

- [ ] Define SpiritBoot kernel ABI boundary.
- [ ] Create an export database with implementation/test status.
- [ ] Implement memory primitives.
- [ ] Implement scheduler/thread primitives.
- [ ] Implement synchronization objects as demanded by tests.
- [ ] Implement object/handle manager behavior.
- [ ] Implement file/device I/O.
- [ ] Implement exception and interrupt behavior.
- [ ] Add behavioral regression tests.

### Phase 5 — Title compatibility

- [ ] Select a small compatibility ladder instead of random games.
- [ ] Record the first missing export/behavior for each failure.
- [ ] Add a regression test for every fixed boot blocker.
- [ ] Reach title initialization.
- [ ] Reach rendered frames.
- [ ] Reach input.
- [ ] Reach sustained gameplay.

### Phase 6 — Real hardware

- [ ] Define safe deployment path.
- [ ] Validate supported motherboard revisions.
- [ ] Validate RAM/video/storage/input.
- [ ] Compare trace ordering against emulator results.
- [ ] Add recovery strategy for failed/partial boots.
- [ ] Document flash/modchip/TSOP expectations.

## Test philosophy

Every compatibility fix should answer:

1. What observable behavior is required?
2. How do we reproduce it?
3. What is the smallest test that detects it?
4. Does the behavior agree in xemu and on hardware?
5. What regression would this test catch later?

Preferred ladder:

```text
host/unit test
    -> freestanding SpiritBoot self-test
    -> nxdk test XBE
    -> emulator integration test
    -> hardware integration test
    -> retail-title compatibility test
```

Retail games should be the final integration tests, not the only diagnostic tool.

## Repository layout

```text
SpiritBoot/
├── README.md
├── docs/
│   ├── ARCHITECTURE.md
│   ├── ROADMAP.md
│   ├── REFERENCES.md
│   └── provenance/
├── include/
│   └── spiritboot/
├── src/
│   ├── boot/
│   ├── platform/
│   ├── kernel/
│   ├── loader/
│   └── trace/
├── tests/
│   ├── host/
│   ├── xbe/
│   └── integration/
├── tools/
├── scripts/
│   ├── fetch-references.sh
│   └── fetch-references.ps1
└── .reference/              # ignored local checkouts
```

The exact binary/linker layout is intentionally not frozen until reset-vector and image-format requirements are verified.

## Immediate research queue

1. Determine the minimal execution contract at the BIOS handoff on each Xbox revision.
2. Trace Cromwell initialization and separate generally useful hardware bring-up from Linux-specific behavior.
3. Define an xemu SpiritBoot development mode with deterministic reset and trace capture.
4. Inventory Xbox kernel exports required by a minimal nxdk XBE and then a deliberately chosen first retail title.
5. Separate guest-visible behavior in Cxbx-Reloaded from Windows-host implementation details.
6. Identify nxdk startup/driver code useful as black-box tests versus candidates for licensed reuse.
7. Define the smallest useful open MCPX/emulator handoff contract.
8. Verify image layout, reset vector, linker layout, checksum/encryption expectations, and flash-size requirements.
9. Inventory Xbox revision differences that should be abstracted from day one.
10. Define trace points that turn a black screen into an actionable failure.

## First target

> **Build the open Roswell-based flash path, direct-boot it in Mainkill1/xemu without a Microsoft MCPX/BIOS dependency, run deterministic kernel tests/nxdk payloads, then prove the same kernel through Fancy Mouse as the open accurate boot path.**

That milestone validates the architecture without pretending the kernel compatibility problem is already solved.
