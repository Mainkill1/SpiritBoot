# Boot setup menu

**Status: native implementation and exact-ROM qualification complete.** The
ordered firmware patch enables the setup prompt before the boot display is
retired. A controller can enter the menu, edit settings, verify an EEPROM save,
reboot, and observe the saved values. With no input, boot continues after the
fixed three-second guest-time window.

The menu engine, gate, and OHCI descriptor helpers are freestanding C11 with no
heap calls or mutable globals. The native adapter lives in the kernel's
discardable INIT section. It owns one 4 KiB low-memory DMA page, stops the OHCI
controller, scrubs and frees that page, and returns before INIT is discarded.
There is no resident menu worker, callback, allocation, or title-time polling.

## Proposed startup and controls

Hold **X** during the fixed **3-second** bounded splash/input window.
Release all buttons before navigating. D-pad selects/edits, A activates, X
requests save, B requests discard. The controller's dedicated **Back** button
(not the B face button) opens project credits while editing. D-pad Up/Down or
Left/Right changes credits pages; **Back** or **B** returns to the menu without
saving or discarding edits. Save and discard of changed values require
confirmation. A held key cannot serve as both selection and confirmation.
Absent input times out; disconnection or a device-generation change disarms menu
controls until a fresh neutral report arrives.

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

The demo maps `h` to a synthetic held X input; `w/s` to rows, `a/d` to edits, `e`
to A, `x` to Save, and `b` to Discard. Press Enter after each command. It uses
in-memory settings and an 8 KiB host arena; it never accesses Xbox hardware or
writes a real EEPROM. Try `h`, `e`, `x`, `e` to stage a language change and save,
or `h`, `e`, `b`, `e` to discard. No-button boot does not allocate that arena.

`check.py` runs the production C bodies with ASan/UBSan and optimization, then
compiles i386 freestanding objects and rejects hidden dependencies/writable
globals. It additionally checks the demo's skip/save/discard routes. Requirements:
Python 3.10+, a C compiler supporting i386 object output, GNU nm and size. No
32-bit runtime libraries or third-party Python packages are required.

## Native implementation

`patches/roswell/0089-boot-settings-menu.patch` adds a bounded, boot-only owner
for xemu's Xbox OHCI/XID topology. It walks nested hubs to a maximum depth of
four, accepts one original-Xbox 20-byte input report, and treats missing or
unsupported input as an ordinary bounded boot. The DMA allocation is constrained
to the verified low direct-map range; the adapter does not start the resident USB
stack or leave an input device behind for the title.

The renderer is deliberately isolated in `BsRenderMenu`. It uses the existing
boot-display text primitives and does not own a second framebuffer. A future
semi-animated boot presentation can replace or surround this function without
changing controller enumeration, menu state, or EEPROM transactions. Keep future
art, animation state, and rendering helpers in INIT (or a separately admitted ROM
overlay), and preserve the same teardown boundary before title launch.
The credits view uses three paginated INIT-only text pages and the same logo.
It does not alter EEPROM settings; full project/license credits are tracked
in [CREDITS.md](../../../docs/CREDITS.md).

The static fox remains visible in the menu's lower-right quadrant using the
same discardable bitmap resource; opening setup does not allocate or decode a
second copy.

Saving writes only setting words 7, 8, and 9 through the shared kernel API, then
rereads the complete EEPROM user section and verifies its checksum and values.
Any incomplete result stays in recovery rather than launching a title. Discard
and unchanged-save paths perform no EEPROM writes.

The locked 64 and 128 MiB release builds pass the resident-to-INIT reference
audit. Relative to the matched 64 MiB main build, the complete menu and static
splash add 37,888 linked kernel bytes and 7,348 compressed ROM bytes. Most of
the linked delta is the discardable 32 KiB image resource. The resulting 256 KiB
image retains 36,036 bytes in its kernel slot for later work.

The exact 64 MiB splash build is
`sha256:69c1f8982b79aec46fc2089cbdee970d09cf39ea423b1d61bb06c73c5777552f`.
The matching 128 MiB build is
`sha256:da17c1b6d8bdea0c1bb553d4750bf9e441709099a20c2ebf1ad51ebf7f4312cf`.
The exact final 64 MiB ROM passed both native Steam Deck routes: held X entered
setup, the lower-right fox remained visible, English changed to Japanese, the
EEPROM save was verified, and Japanese survived reboot; a separate no-input run
displayed the fox, brand, and prompt before reaching the Conker title normally.

See [design](../../../docs/superpowers/specs/2026-10-10-boot-setup-design.md) and
[implementation plan](../../../docs/superpowers/plans/2026-10-10-boot-setup.md).
