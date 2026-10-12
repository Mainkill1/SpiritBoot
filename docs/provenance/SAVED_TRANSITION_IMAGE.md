# Saved transition image across a quick title relaunch

## Question

Which public kernel sequence retains Morrowind's transition image while a title
rebuilds its memory, and which part differs on SpiritBoot?

## Environment and evidence

October 12, 2026: operator-triggered New Game on Morrowind, 64 MiB, Windows xemu
`dcc536830deba245eec36cd009db5860ca04884c`, Vulkan. Separate HDD overlays and
EEPROM copies were used for Complex 4627 and SpiritBoot main
`83b61b7cd58226dcbd577650146638601d9e6400` / v0.99.2. Only public PE exports,
public ABI arguments/returns, and title-owned saved-buffer data were observed.
No reference instructions or disassembly were read. Private traces and game
inputs are kept outside the product repository.

The observed outgoing calls were:

1. Query the prior saved address.
2. Program a 640x480, 32-bit, 2560-byte-pitch image with `AvSetDisplayMode`.
3. Persist its contiguous allocation with `MmPersistContiguousMemory(..., TRUE)`.
4. Publish the allocation base with `AvSetSavedDataAddress`.
5. Persist a launch-data page and call `HalReturnToFirmware(2)`.

The relaunched title queries encoder settings, sets its next display mode,
queries the saved address, then unpersists/frees the old saved allocation and
clears the address before enabling its new display. Complex returns a relocated
saved-buffer address. SpiritBoot returns null and therefore misses reclamation.
The address need not remain numerically identical; the image and its ownership
must remain valid at the returned address.

An independent guest creates a recognizable image and a 64-byte surface record
using observed public resource/format/size fields. No game pixels or assets are
used. It reproduces the outgoing calls and queries before setting the next mode.
On the same Linux xemu `63f53af93c2d84f5ce1a11e277138cbaf5cca7aa`, Complex passes
all nine checks. Baseline SpiritBoot passes seven: it retains every pixel and
allocation ownership, but loses the saved address and points scanout elsewhere.

## Independent repair requirements

- Preserve the saved allocation's discoverable address on a valid quick launch.
- Restore the active image address and pitch after firmware video initialization.
- Use the existing validated RAM/launch handoff; stale or unowned pointers must
  not become saved images after a cold boot or a rejected persistence handoff.
- Capture display state after shutdown callbacks have completed.
- Let the next title clear, unpersist, and free its saved allocation normally.
- Keep ordinary cold initialization and launches without a saved image working.

Implementation uses SpiritBoot's own persistence, AV, and initialization paths.
Required convergence is confined to public API ordinals/calling conventions,
NV2A register addresses, and the observed surface metadata used by the test.
This is behavior-only black-box research by one investigator/implementer, not a
claim of personnel-separated clean-room certification.

## Regression and limits

The maintained two-boot saved-image guest checks slot replacement/clear,
discoverability, pixel preservation, allocation ownership, exclusive physical
ownership, scanout, and final clear. Native Morrowind verification is required
before claiming the visible transition is repaired. A stage-two scanout check
alone cannot prove an uninterrupted image throughout the emulator's device reset.

The candidate 64 MiB release BIOS `cc3e075bf995075b8a28cc13f0b931c726584f4b2a9c68f66191cef0fc0194cf`
passes all nine checks with the exact same guest used for the failing baseline.
Its reconstructed source tree is `c5cef281b35d546d43e36912cd52d3ac3b7b451b`.
The production AV host fixture passes admission, adjacent selected allocations,
missing/short persistence, invalid ranges, scanout bounds, and clear cases under
UBSan. The existing warm staging and AV encoder fixtures pass; the product host
suite passes 129 tests, with three optional environment checks skipped.
