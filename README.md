# SpiritBoot

**SpiritBoot** is an experimental, clean-room, open-source boot firmware and Xbox-compatible runtime project for the **original Xbox**.

The long-term goal is not merely to display a boot screen. The goal is to replace enough of the proprietary boot and kernel stack that an original Xbox title can be initialized, loaded, and run without requiring a Microsoft BIOS image in the SpiritBoot source tree.

> **Status:** open-firmware build and emulator integration. Retail game compatibility is not yet verified.

## Build and run

SpiritBoot's initial executable path uses the pinned GPL-2.0 Roswell loader and
Xbox kernel with the Mainkill1 xemu fork. The tooling builds release/checked flash
images, records provenance, captures boot diagnostics, and grades an open test XBE.
Conker: Live & Reloaded is the first retail target.

See [build and launch instructions](docs/BUILD_AND_RUN.md) and
[reproduced baseline evidence](docs/provenance/OPEN_FIRMWARE_BASELINE.md).
The [direct XISO suite evidence](docs/provenance/XISO_SUITE_BASELINE.md) records
Mainkill1's matched qualification suite, complete guest results, and the earlier
intermittent GPU polling assertion.
Six independently implemented kernel features now cover shutdown notifications,
warm-reset memory persistence, page locking, one-request scatter/gather I/O,
live IDE callbacks and a bounded debugger prompt. See the
[feature guide](docs/CLEAN_ROOM_FEATURES.md),
[source review](docs/clean-room-kernel-review.md) and
[final build and runtime evidence](docs/provenance/CLEAN_ROOM_XEMU_BASELINE.md).
The build needs no Microsoft BIOS or MCPX ROM. Runtime/game progress is measured
separately from a successful firmware build.

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

SpiritBoot integrates the open Roswell loader/kernel rather than recreating the
entire runtime. Existing open projects are references, test partners, and licensed
implementation foundations with recorded provenance.

| Project | Why it matters |
| --- | --- |
| [XboxDev/cromwell](https://github.com/XboxDev/cromwell) | Existing free/legal Xbox BIOS replacement. Primary reference for low-level boot and hardware bring-up. It intentionally does not boot original Xbox games. |
| [xemu-project/xemu](https://github.com/xemu-project/xemu) | Hardware model and primary emulator-side bring-up target. Useful for tracing device behavior and creating a BIOS/MCPX-independent development path. |
| [Cxbx-Reloaded/Cxbx-Reloaded](https://github.com/Cxbx-Reloaded/Cxbx-Reloaded) | Useful reference for XBE loading, Xbox kernel/API behavior and title compatibility research. Its host-side HLE architecture is not a drop-in firmware implementation. |
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

The MCPX boot ROM is a separate problem from the flash BIOS.

Initial development should not block on replacing it. SpiritBoot should support an emulator research path that can enter the SpiritBoot reset/stage0 environment directly or through a small open handoff.

Long term, the project should define and test:

1. **Physical Xbox path:** work with the MCPX behavior already present in the console and reach SpiritBoot from a supported flash/modchip/TSOP configuration.
2. **Emulator path:** allow xemu or another test harness to boot SpiritBoot without requiring users to provide a proprietary MCPX dump where technically possible.
3. **Open stage0 research:** document exactly which MCPX-visible behaviors are actually required before deciding whether an open substitute is necessary or beneficial.

## Kernel compatibility is the critical path

Cromwell demonstrates that an open Xbox BIOS can initialize the machine. Retail game compatibility requires substantially more.

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

- [x] Select GPL-2.0 as the umbrella license; preserve upstream per-file licenses.
- [x] Add open x86 firmware build tooling.
- [ ] Produce a deterministic binary artifact.
- [ ] Add map/symbol outputs.
- [x] Add an emulator launch/test wrapper.
- [x] Capture upstream loader/kernel serial diagnostics.

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

> **Build SpiritBoot, enter it in xemu without a Microsoft BIOS image, initialize enough hardware to emit deterministic trace output, and launch a tiny nxdk-built XBE through our own loader/runtime path.**

That milestone validates the architecture without pretending the kernel compatibility problem is already solved.
