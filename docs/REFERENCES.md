# Reference Repository Map

Reference repositories live under `.reference/` and are excluded from version control. `sources/upstreams.json` records the canonical set and role of each checkout.

Run:

```bash
./scripts/fetch-references.sh
```

or on PowerShell:

```powershell
./scripts/fetch-references.ps1
```

## mborgerson/roswell

Repository: https://github.com/mborgerson/roswell

Primary starting point for:
- open xboxkrnl implementation;
- nxldr/open flash image;
- Xbox/NT ABI adaptation;
- direct xemu boot without a separate boot ROM;
- identifying already-mapped versus still-stubbed kernel exports.

## SnowyMouse/fancy-mouse-boot-rom

Repository: https://github.com/SnowyMouse/fancy-mouse-boot-rom

Use it for:
- the open MCPX-compatible 512-byte boot-ROM path;
- validating early protected-mode/32-bit setup;
- open verification/handoff behavior;
- hardware-faithful boot-chain testing.

## Mainkill1/xemu

Repository: https://github.com/Mainkill1/xemu

Primary SpiritBoot emulator integration target for:
- direct boot;
- kernel/boot tracing;
- compatibility automation;
- guest-work/performance counters;
- testing emulator-aware fast paths without making them mandatory on hardware.

## Cxbx-Reloaded/xbox_kernel_test_suite

Repository: https://github.com/Cxbx-Reloaded/xbox_kernel_test_suite

Use it as the main hardware-backed kernel conformance harness. SpiritBoot should correlate every kernel ordinal against available tests before assuming a mapped implementation is correct.

## Cxbx-Reloaded/XbSymbolDatabase

Repository: https://github.com/Cxbx-Reloaded/XbSymbolDatabase

Use it to identify statically linked XDK/runtime code in retail XBEs and to turn anonymous crash addresses into known software behavior.

## XboxDev/cromwell

Repository: https://github.com/XboxDev/cromwell

Use it to research:
- reset/BIOS image organization;
- low-level chipset and memory initialization;
- PCI/SMBus/video/storage bring-up;
- motherboard revision handling;
- behavior that already works on physical Xbox hardware.

Do **not** assume its Linux-loading policy or later runtime architecture solves retail XBE compatibility.

## xemu-project/xemu

Repository: https://github.com/xemu-project/xemu

Use it to research:
- emulated device/register behavior;
- reset state;
- MCPX/flash interactions;
- interrupt/timer behavior;
- deterministic test hooks and trace extraction;
- expected side effects of hardware accesses.

The first SpiritBoot integration work should identify the smallest xemu-side handoff needed for rapid firmware testing without baking emulator-only assumptions into SpiritBoot.

## Cxbx-Reloaded/Cxbx-Reloaded

Repository: https://github.com/Cxbx-Reloaded/Cxbx-Reloaded

Use it to research:
- XBE structures/loading;
- kernel API surface and title expectations;
- object/memory/thread/I/O behavior;
- compatibility edge cases discovered from real titles.

Important distinction: Cxbx-Reloaded translates/emulates behavior in a host environment. SpiritBoot needs guest-native implementations, so host-specific mechanisms should not be copied as architecture.

## XboxDev/nxdk

Repository: https://github.com/XboxDev/nxdk

Use it for:
- tiny open test XBEs;
- startup/runtime assumptions;
- open drivers and hardware definitions;
- targeted hardware exercisers;
- validation payloads that remove retail-game complexity from early debugging.

## XboxDev/xboxpy

Repository: https://github.com/XboxDev/xboxpy

Use it for:
- controlled hardware probing;
- comparing emulator and real-hardware behavior;
- extracting measurements rather than code.

## XboxDev/xbox-linux

Repository: https://github.com/XboxDev/xbox-linux

Use it as an additional historical source for:
- device support;
- platform quirks;
- hardware initialization knowledge.

## Reuse rule

A reference checkout is **not** permission to copy code.

Before adapting source from any project:
1. identify the exact file/commit;
2. inspect its license and file-level notices;
3. decide whether SpiritBoot's selected license is compatible;
4. record attribution/provenance;
5. prefer independent implementation from documented behavior where direct reuse is unnecessary.
