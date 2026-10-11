# Boot setup menu design and implementation record

## Intent and status

The requested feature is a button-entered BIOS setup menu. Temporary boot RAM may
be substantial, but the editor, input resources, graphics buffers, temporary
stacks and loaded code must not remain resident when a title starts. The wider
firmware goal remains 512 KiB settled overhead; this feature must not claim that
its own low state size achieves that whole-system goal.

The implementation provides a freestanding gate/menu core, staged settings,
host tests, a temporary native OHCI/XID owner, boot-display rendering and verified
EEPROM persistence. It is integrated by ordered patch 0089 and built at both
64 and 128 MiB. Exact-ROM Steam Deck qualification covers save/readback/reboot,
persisted display, and the no-input title handoff.

Reviewed product base: `375a2c16d1e5ae230bfa46bd4805be301094cd1f`. Production kernel
changes use the ordered Roswell patches and firmware lock. Do not edit the old
source snapshot or silently enable this standalone component in release firmware.

## Chosen behavior

Hold controller **X** during a fixed **3,000 ms** splash/input window.
One fresh valid report enters setup immediately. Invalid reports are ignored and
input at or after the deadline cannot extend boot. Time arithmetic tolerates
uint32 millisecond wrap, not a backward clock jump.
The adapter uses a finite enumeration deadline; no controller cannot stall boot.
These are initial design defaults, not claimed existing Xbox firmware settings.

A held-at-power-on button is valid; the activation sample is consumed. The menu
requires a fresh neutral report before accepting navigation. D-pad selects or
edits; A activates; X requests save; B requests discard/continue. Confirmation
requires a second press, not a held button carried over from the prior screen.
Only one button action is accepted per report; no automatic key repeat initially.

Normal boot loads no menu renderer, font, framebuffer or settings editor. The
small boot gate and any input probe allocations are also retired after use.
There is no in-game setup hotkey, resident polling thread or menu service.

## Settings and persistence

First implemented menu model: language; normal/widescreen/letterbox preference;
480p, 720p and 1080i permissions; PAL60 preference; mono/stereo/surround; AC3; DTS.
These modify only three standardized setting words: language (index 7), video
flags (8), audio flags (9). Unknown bits are preserved. Preference flags do not
promise that the boot renderer implements the corresponding mode.

The adapter supplies a supported-field bitmap. Unsupported entries remain visible
but cannot be edited. Initial EEPROM values, including unknown/unset values, are
not normalized just by opening the editor. Browse/cancel causes **zero writes**.
Changes are staged until a separate Save and reboot confirmation.

The store interface receives original words, edited words and changed-word mask.
Success means actual durable write plus independent readback/checksum verification,
not merely a cached ExQueryNonVolatileSetting result. Rejection guarantees no
persistent mutation. An uncertain/partial write blocks title launch and leaves a
retry/recovery path; Cancel must not turn an uncertain write into apparent success.
Changing a value back to its original value is not dirty and requires no write.
The portable core does not claim that EEPROM updates can be made power-fail atomic.

Before an EEPROM adapter is enabled, serialize writers; compare the original
values; preserve the rest of the complete user section; update affected data and
checksum in a tested order; independently reread the device; repair/invalidate
kernel shadows on failure. Use a separate, durable recovery journal if a power-loss
recovery guarantee is offered. Do not alter factory identity, HDD keys, sealed
regions or hardware calibration as an incidental menu save.

Additional categories remain planned, not fake working switches: timezone/clock,
parental controls, DVD preferences, network configuration (including HDD-backed
network state), boot paths, fan/LED policy, storage configuration, diagnostics and
recovery. Firmware-specific settings use a versioned configuration store, not
unallocated-looking EEPROM bytes. Arbitrary timing/register edits, flash writes,
partition changes and HDD-security operations require separate implementations.
A future fan curve needs a bounded resident service; a one-time SMC setting does
not. Emulator renderer/acceleration options belong to a negotiated xemu interface.

## Placement and memory ownership

The first native version chooses INIT placement and the existing boot-display
primitives. It does not allocate a second framebuffer or load a general GUI.
Private menu, input, and rendering code is discarded at the established INIT
boundary. The splash is displayed immediately after boot-video initialization
and remains unchanged throughout the gate, with `Spirit Boot` below the image
and `Hold X to enter setup` in the bottom-right corner. The controller adapter
owns one temporary 4 KiB DMA page, constrained to the verified low direct-map
range, and releases it after resetting OHCI.

When setup opens, the same bitmap is redrawn in the lower-right quadrant while
the settings remain above and to its left. It is referenced directly from the
discardable resource section; the menu does not decode or retain another copy.

Presentation is isolated in `BsRenderMenu`. A future semi-animated boot may
replace or surround that function while reusing the same input, state machine,
and persistence interfaces. Animation code and assets remain boot-only and must
fit the measured ROM budget or use a separately reviewed overlay. The current
static image is a 32,886-byte 4-bit indexed bitmap. It resides in the
discardable resource/INIT span. The 64 MiB release image retains 36,036 bytes in
the fixed kernel slot after the complete feature;
enlarging the flash format is a separate compatibility decision.

A later renderer experiment may compare a vertex-colored triangle mesh and a
small shading texture against DXT5 at the actual displayed size. DXT5 texture
data is 16 KiB at 128x128 or 64 KiB at 256x256. Selection must use measured ROM,
temporary RAM, setup cost and visual quality; the original Xbox shader pipeline
cannot directly use a modern procedural GLSL shader.

Keep shared runtime exports (EEPROM query/save, SMBus, AV etc.) resident. Move only
menu-private editor/parser/assets and boot-only adapters into the overlay. Menus
must not root all video/USB libraries permanently through function pointers.
Default transient arena budget: **4 MiB**, accounted separately from settled RAM;
reject or simplify the UI if the actual admitted arena cannot satisfy its budget.
This is a proposed native budget, not an allocation made by the portable core.

Retirement sequence, on success and every failure/skip path:

1. Return from menu code and its stack into a resident/ROM boot coordinator.
2. Stop input submissions and timers; drain callbacks, USB/DMA and pending I/O.
3. Fence menu GPU work and retarget/disable scanout before freeing its framebuffer.
4. Destroy menu-owned objects and clear registrations while the overlay still lives.
5. Copy only a small pointer-free exit result to coordinator-owned storage.
6. Scrub and release all menu arena pages through the real allocator; also retire
   the loaded overlay, temporary stack and extra page tables. Clearing bytes alone
   is not freeing memory; a nonzero allocator count is a failed handoff.
7. Continue or reboot only after successful reclamation. Do not return through
   overwritten code, reuse its stack, or invoke a released callback.

`sb_boot_arena_retire` demonstrates ordered quiesce -> scrub -> release, refuses
unsafe overlaps and retains failed-release state for a release-only retry. Its
coordinator, executing stack, descriptor, release callback and callback context
must live outside the retired span. It cannot independently prove GPU or page-table
ownership; the native adapter must supply those proofs. Allocator release must be
all-or-nothing: false retains every page, so a release-only retry cannot double
free a partially returned span. It must never scrub all
RAM or guessed fixed addresses, including warm-persisted title pages.

## Existing integration boundaries

- `sources/firmware-lock.json`: current main already includes direct image loading,
  warm INIT preservation, reclaimed reset workspace and reduced metadata. Preserve
  patches 0049-0054 and their admission tests; do not revive older reservations.
- Roswell `ntoskrnl/ex/init.c`: boot orchestration and XeRunInitialTitle boundary.
  Resolve the exact current patched order. An INIT menu must run before its own
  sections and boot display are retired; an overlay may run later using explicitly
  owned graphics resources. A call immediately before XeRunInitialTitle is not by
  itself proof that bootvid or controller services remain available there.
- `patches/roswell/0044-bootvid-framebuffer-lifetime.patch`: respect terminal display
  ownership. Never reactivate a stale framebuffer as a menu or bugcheck shortcut.
- `patches/roswell/0051-reclaim-reset-workspace.patch`: ROM early-warm code precedes
  boot RAM writes and accounts for persistent pages. Allocate from the admitted
  supply after restoration, or extend its bounded staging proof before earlier use.
- Roswell `ntoskrnl/xb/eeprom.c`: existing cached query/save is shared runtime ABI;
  add a verified writer boundary, not raw UI writes behind the shadow.
- Patch 0089 supplies its own bounded pre-title USB/OHCI/XID owner. It does not
  depend on a callable kernel XInput API and must complete its stop/reset/fence
  handoff before the resident USB stack or title can take ownership.

## Qualification record

The portable suite runs 39 sanitizer and optimized cases covering controller
descriptors, gate timing, reconnect discipline, settings edits, commit outcomes,
and retirement ordering. Locked 64 and 128 MiB release builds pass the post-link
resident-to-INIT reference audit. The complete 64 MiB feature build adds 37,888
linked kernel bytes and 7,364 compressed bytes relative to matched main. Most of
the linked delta is the discardable static image.

On the Steam Deck, the exact final 64 MiB ROM entered through held X on an
OS-visible Xbox controller, retained the fox in the lower-right menu, changed
English to Japanese, displayed the save confirmation, verified the EEPROM
transaction, rebooted, and displayed Japanese after re-entry. A separate
neutral-input run displayed the centered fox, `Spirit Boot`, and bottom-right
prompt, then timed out and reached the Conker title automatically. The first
historical timeout attempt was clipped by its job deadline and remains recorded
as a test-harness failure; the corrected final 75-second job completed.

Physical Xbox USB topology, injected SMBus failures, and a future animated
presentation remain follow-up qualification. They do not change the bounded xemu
menu contract proven here.

## Sources

- Product lock and patches at the exact reviewed commit above.
- https://github.com/Mainkill1/SpiritBoot/blob/kernel-source-optimization-2026-10-07/ntoskrnl/xb/eeprom.c
- https://github.com/mborgerson/roswell/blob/1569e2e89fb47cc72b9c704a8884f98200432bd4/ntoskrnl/CMakeLists.txt
- https://github.com/mborgerson/roswell/blob/1569e2e89fb47cc72b9c704a8884f98200432bd4/tools/init-force-resident.list
- https://xboxdevwiki.net/EEPROM (public setting encodings; flag availability is
  not evidence of a supported hardware output mode).
