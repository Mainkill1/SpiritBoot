# Boot setup menu draft

**Status: host-tested core and integration design, not enabled in the BIOS.**
There is no shipped button-entry path yet. No native controller/GPU/EEPROM test
or post-title physical-memory result is claimed by this directory.

The menu engine and gate are freestanding C11 with no heap calls or mutable
globals. `boot_arena.c` is the separate coordinator primitive that must remain
outside the menu's code/data/stack when retiring it. The test build reports its
i386 object footprint and frame sizes, not an entire firmware RAM footprint.

## Proposed startup and controls

Hold **Start for 600 ms** within a **2-second** bounded boot-input window.
Release all buttons before navigating. D-pad selects/edits, A activates, X
requests save, B requests discard. Save and discard of changed values require
confirmation. A held key cannot serve as both selection and confirmation.
Absent input times out; disconnection/generation change cannot combine holds.

The initial fields are language, screen shape, 480p/720p/1080i permissions,
PAL60 preference, audio mode, AC3 and DTS. The platform supplies supported fields;
unknown values and unrelated bits are preserved. These are preferences, not a
promise that SpiritBoot's boot display implements every output mode.

The settings store interface is deliberately not a raw EEPROM byte writer.
Browse/cancel/unchanged save makes no commit call. A verified commit requests
reboot. Rejected/no-mutation writes stay editable; uncertain writes block normal
boot until verified recovery. A rejected retry cannot erase earlier uncertainty.
Full network/time/fan/storage/recovery features remain separate work, listed in
the design, rather than nonfunctional switches in this menu.

## Run the host demonstration

```sh
python3 tests/host/boot-setup/check.py --output /tmp/spiritboot-setup
/tmp/spiritboot-setup/boot-setup-demo
```

The demo maps `h` to a synthetic Start hold; `w/s` to rows, `a/d` to edits, `e`
to A, `x` to Save, and `b` to Discard. Press Enter after each command. It uses
in-memory settings and an 8 KiB host arena; it never accesses Xbox hardware or
writes a real EEPROM. Try `h`, `e`, `x`, `e` to stage a language change and save,
or `h`, `e`, `b`, `e` to discard. No-button boot does not allocate that arena.

`check.py` runs the production C bodies with ASan/UBSan and optimization, then
compiles i386 freestanding objects and rejects hidden dependencies/writable
globals. It additionally checks the demo's skip/save/discard routes. Requirements:
Python 3.10+, a C compiler supporting i386 object output, GNU nm and size. No
32-bit runtime libraries or third-party Python packages are required.

## Native integration still required before merge

Implement a real bounded controller adapter and minimal video renderer; independently
link/package the ROM overlay; install the coordinator at the verified boot phase;
provide serialized, verified persistence; drain callbacks/DMA and transfer display
ownership; retire all allocations and code/stack/PT pages; build and test actual
64/128 MiB firmware. The default native transient arena design budget is 4 MiB;
no menu allocations or callbacks may remain at title entry. Shared runtime EEPROM,
AV and device APIs are not disposable UI code.

Only owned allocator-backed memory may be scrubbed. The executor, stack, arena
descriptor, release callback and its whole context must live outside the arena.
The portable function checks basic ranges and overlap, not page mapping, hardware
quiescence or ownership. The native coordinator supplies those proofs. A failure
in quiesce or allocator release blocks handoff; clearing bytes is not reclamation.
The release callback must be all-or-nothing: on false the caller still owns every
page, allowing a release-only retry without a double free.

See [design](../../../docs/superpowers/specs/2026-10-10-boot-setup-design.md) and
[implementation plan](../../../docs/superpowers/plans/2026-10-10-boot-setup.md).
