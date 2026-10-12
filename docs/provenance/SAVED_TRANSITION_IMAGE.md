# Saved transition image across a quick title relaunch

## Problem and BIOS differences

Morrowind's New Game transition retains a loading image while the title rebuilds
memory. Public API traces establish that it uses `HalReturnToFirmware(2)`.
SpiritBoot v0.99.2 retains the image's persisted pixels but loses the saved-address
slot and active scanout. The incoming title receives null instead of a valid saved
allocation and skips normal image reclamation.

A second difference explains the leftward squish reported after address retention
was repaired. Morrowind requests mode `0x88070701`, format `0x1e`, and a 2560-byte
pitch. SpiritBoot's `AvSetDisplayMode` updates pitch and scanout but leaves its
720-pixel boot viewport active. The requested mode is 640x480 in
[nxdk's public mode table](https://github.com/XboxDev/nxdk/blob/master/lib/hal/video.c).
A 720-pixel, 32-bit row cannot fit the requested pitch.

A separate ownership defect was found by extending the independent guest:
neighboring persisted allocations become a maximal admitted run during warm
restore. Without adopting the saved image's exact extent, querying or freeing
that image can include adjacent owners. Complex preserves these ownership
boundaries in the same public API test.

## Observation and environment

October 12, 2026: operator-triggered New Game, Morrowind, 64 MiB, Windows xemu
`dcc536830deba245eec36cd009db5860ca04884c`, NVIDIA Vulkan. Complex 4627 and
SpiritBoot main `83b61b7cd58226dcbd577650146638601d9e6400` / v0.99.2 used separate
HDD overlays and EEPROM copies. Only public PE exports, public ABI arguments and
returns, title-owned saved-buffer bytes, and display registers were observed.
No reference instructions or disassembly were read. Private BIOSes, game inputs,
and raw game traces stay outside the product repository.

The observed outgoing calls are:

1. Query the prior saved address.
2. Set the transition image's display mode, 32-bit format and 2560-byte pitch.
3. Persist its contiguous allocation with `MmPersistContiguousMemory(..., TRUE)`.
4. Publish the allocation base with `AvSetSavedDataAddress`.
5. Persist a launch-data page and call `HalReturnToFirmware(2)`.

The incoming title queries encoder settings, sets its next display mode, gets the
saved address, then unpersists and frees the old allocation and clears the saved
slot before enabling its new display. Complex returns a relocated address;
SpiritBoot initially returns null. Convergence requires valid contents and
ownership at the returned address, not a numerically identical pointer.

The original independent nine-check guest passes 9/9 on Complex and 7/9 on
baseline SpiritBoot. The failures are saved-address discovery and retained
scanout. Every generated pixel and physical ownership already survive.

## Repair

The existing validated warm handoff now includes the saved allocation's address
and exact size, display mode, source format, pitch, scanout, active width and
height, pixel-format register, and general-control register. Capture runs after
shutdown callbacks, before the RAM handoff is hashed. Early restoration publishes
only an admitted owned pointer and restores display state only when the full
visible frame fits the allocation. Cold boots, rejected admission and invalid
ranges do not publish stale saved images.

After staged INIT/workspace copies finish, the memory manager adopts the image's
page-rounded extent independently of its neighbors. This ordering matters:
early adoption removes admission bits still needed by staged copies. The next
title can query, clear, unpersist, free and reclaim the entire allocation while
adjacent persisted owners remain intact and exclusive.

`AvSetDisplayMode` now programs active width, height and depth for the exact 28
supported IDs from nxdk's public table. The CRTC helper preserves protected and
unrelated register bits. Known 15-bit and 16-bit formats also set the matching
general-control selector. The observed title format `0x1e` selects the exercised
32-bit path; this is not a claim to implement an undocumented surface format.
Unsupported modes and formats keep their previous geometry behavior. Scanout is
published after pitch, geometry, depth and the existing interlace setup. Warm
restoration retains the actual captured geometry, including a valid custom
viewport, rather than deriving it from pitch.

The implementation uses SpiritBoot's own AV, persistence and initialization
paths. Convergence is confined to public ABI contracts, NV2A register addresses,
and observed surface metadata. This is behavior-only black-box research by one
investigator/implementer, not personnel-separated clean-room certification.

## Failed geometry candidate and improved probe

The operator confirmed that the first repair retained the correct static image
but shifted it left; gameplay returned to normal resolution. An intermediate
probe explicitly programmed 640x480 itself, then checked warm retention. Capturing
and restoring CRTC geometry passed that 13-check probe at 64 and 128 MiB, but
native Morrowind still shifted left and then showed corruption.

The public trace showed 720 active pixels at both entry and return of the title's
640x480 mode call, and again at `HalReturnToFirmware(2)`. The geometry-only repair
captured those 720 pixels, rejected them against the 2560-byte pitch, and left
scanout at the firmware boot buffer (`0x03c00000`). Saved-address recovery and
normal unpersist/free/clear still completed. A matching 4096-byte prefix hash
establishes preservation of that prefix only, not every game pixel.

The maintained XBE now relies on the public mode API alone. It reads CRTC state
but never programs geometry or depth to manufacture a passing starting state.
An added outgoing-mode check gives 14 checks. With the same guest, Complex
passes 14/14 and the geometry-only candidate passes 11/14, failing outgoing mode
geometry, retained geometry and scanout. This reproduces the native failure
without a game or operator navigation.

## Regression and validation

The maintained guest is `tests/xbe/saved-image` in the reconstructed kernel. It
generates its own 640x480 ARGB pattern, stores a 64-byte surface record, persists
neighboring pages, and performs one optical quick title relaunch. It checks:

- Saved-slot set, replacement, clear and discovery after relaunch.
- Every generated pixel, page-rounded allocation size and exclusive ownership.
- Scanout address, retained width/height/depth and outgoing mode geometry.
- Incoming clear, full image reclamation, and both neighbors' contents and ownership.

Deploy it as `default.xbe` at the root of the mounted optical volume, normally by
mounting its generated `saved-image-probe.iso`. Its relaunch path is explicitly
`\Device\CdRom0\default.xbe`; HDD self-relaunch is outside this fixture's contract.
TAP 14 output uses COM1 at 115200 baud. The guest drains the UART and shuts down
after completion; a successful run requires all 14 rows and the completion marker.

Final reconstructed source tree: `7d06947151aa0b30d87bce4421ab88dca5fe397c`.
Release BIOS SHA-256:

| Memory | SHA-256 |
| --- | --- |
| 64 MiB | `322d40a595d5a00156929994561ed932946b8548e1c8b5b6858b31fc72f263fe` |
| 128 MiB | `edb0f11049da3d582804612de1b04af59d319c8c810c08d64dfc9f1a90154f88` |

On Linux xemu `63f53af93c2d84f5ce1a11e277138cbaf5cca7aa`, fresh matched inputs
and independent disks give 14/14 on both BIOSes at both 64 and 128 MiB, with
completion markers, no timeout and normal exit. The final 64 MiB BIOS also passes
14/14 against Complex on Windows NVIDIA Vulkan. That visual-duration guest adds
only ten-second pauses before and after reset; its assertions are identical.
Windows UART and register checks establish 640x480/depth 3 at both checkpoints.
Automated rendered-image captures are unavailable because this xemu build does
not expose QMP `screendump`.

The production AV host fixture passes under UBSan. It covers seven representative
recognized mode IDs, rejected near-alias IDs and 1080i, padded and short pitches, 15/16/32-bit
formats, full frame bounds, invalid and missing persisted pages, adjacent owners,
and late adoption and failure. Independent production-body review separately
checked all 28 supported IDs against the pinned public nxdk table. Warm staging,
AV encoder and actual boot-layout fixtures pass. The 129-test product host suite
passes with three optional environment skips. Both firmware CI source gates
and native guest gates require this exact reconstructed tree and 14 checks.

On the final native Morrowind check, the operator reported that the retained
image appeared corrected. The public trace confirms 640x480/depth 3 before and
after reset, matching owned-buffer prefix hashes, saved-address recovery and
normal unpersist/free/clear. It detached with zero owned breakpoints, no pending
calls and no cleanup errors.

About four seconds afterward, Windows xemu aborted on
`parameter < NV2A_VERTEXSHADER_CONSTANTS` in its
`NV097_SET_TRANSFORM_CONSTANT_LOAD` handler. The host assertion and Windows
Application Error confirm an actual emulator process exit; no tool closed that
Morrowind window. This establishes the corrected static image but leaves gameplay
continuation unverified. The cause of the later GPU command failure is not yet
established; an untraced isolated retry is pending.

The Open firmware matrix on product commit
`7fa7533a097fc21d5ee1ddfcc7930807031539af` passed all four release/debug 64/128 MiB
variants, including the actual kernel host fixtures, 14-check guest, native
regression suite and release reproducibility.
[CI run 38304266187](https://github.com/Mainkill1/SpiritBoot/actions/runs/38304266187)
records the exact tested source tree. The separate host, boot-setup and profiler
checks also pass on that commit. These probes establish the exercised 640x480
xemu contract. Physical encoder timing, interlace fidelity, 1080i, unsupported mode
families and hardware behavior remain unverified.
