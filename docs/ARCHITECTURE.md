# SpiritBoot Architecture

This document defines the initial component boundaries. It is deliberately more rigid about **ownership** than implementation detail; exact image layout and reset behavior still require verification.

## Design rules

1. Hardware-specific behavior belongs behind the platform/HAL boundary.
2. The XBE loader does not become a kernel.
3. Kernel compatibility is implemented as observable guest behavior, not host-emulator behavior.
4. Trace/diagnostic code must be usable from the earliest practical boot stage.
5. Research-only reference repositories never become implicit build dependencies.
6. Every compatibility workaround should eventually have a reproducer or regression test.

## Components

### boot

Owns the earliest instructions executed by SpiritBoot.

Responsibilities:
- reset/handoff contract;
- CPU mode and basic machine state;
- temporary/early stack;
- relocation/copy steps required before normal runtime;
- handoff to platform initialization;
- fatal early-boot trace path.

It should not contain title policy, filesystem logic, or large device drivers.

### platform

Hardware Abstraction Layer for original Xbox revisions.

Expected subareas:
- chipset/host bridge;
- physical memory discovery/configuration;
- PCI;
- interrupts;
- timers;
- SMBus;
- EEPROM/system management;
- ATA/DVD;
- USB/input;
- NV2A display bring-up;
- MCPX-facing services where required;
- revision/quirk handling.

Register definitions should be centralized and named by hardware function rather than scattered magic constants.

### kernel

Implements the guest-visible kernel/runtime contract expected by XBEs.

Initial areas:
- export table;
- virtual/physical memory;
- thread/scheduler state;
- synchronization;
- timers;
- object/handle manager;
- I/O manager/device namespaces;
- exception handling;
- interrupt/DPC/APC-related behavior where required;
- HAL-facing kernel exports.

Implementation order should follow test/title demand rather than export ordinal order.

### loader

Owns XBE parsing and launch.

Responsibilities:
- file/header validation;
- section mapping;
- address/protection checks;
- kernel import/export binding;
- executable/TLS initialization as required;
- launch-state construction;
- controlled transfer to entry point.

The loader should be host-unit-testable using synthetic/open test images wherever possible.

### trace

Trace is a first-class subsystem, not a later debugging add-on.

Proposed event shape:

```text
sequence | timestamp | stage | subsystem | event | arg0 | arg1 | arg2
```

Early output may be a simple debug port/serial-like sink. Later sinks can include memory ring buffers and emulator extraction.

Build modes should eventually include:
- `TRACE_OFF`: compile out expensive tracing;
- `TRACE_BOOT`: stage/failure events only;
- `TRACE_VERBOSE`: register/device/kernel-call research detail.

### tests

Three distinct categories are expected:

- **host**: parsers, tables, pure algorithms, image tooling;
- **xbe**: small open test payloads built using nxdk or another open toolchain;
- **integration**: full emulator/hardware boot tests and trace assertions.

## Development execution paths

### Emulator-first path

```text
xemu test entry -> SpiritBoot boot -> platform -> kernel -> loader -> test XBE
```

The first xemu integration should minimize dependency on opaque proprietary boot state. If a direct research handoff is added to xemu, its contract must be documented and kept narrow enough that real-hardware assumptions are still testable later.

### Physical-hardware path

```text
on-board MCPX -> supported flash/modchip/TSOP path -> SpiritBoot -> platform -> kernel -> loader
```

Real hardware is a compatibility target, not the first place basic failures should be debugged.

## ABI boundary

The kernel export layer should eventually maintain a machine-readable inventory containing at least:

```text
ordinal/name
implementation state
known callers/tests
behavioral notes
reference evidence
last regression result
```

That inventory can become the primary compatibility burn-down rather than using game boot success as the only progress metric.
