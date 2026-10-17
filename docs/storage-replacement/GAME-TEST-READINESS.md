# Live game test readiness

No fresh PGR2, Conker or complete DOA save-cycle pass is established on the
current final PR248 image. A bounded earlier DOA human test is recorded below.
The independent replacement is installed in the complete-candidate release
link. Its current safe-default release64 SHA-256 is
`bcc3145cd832beef0918d5ca99244009b56f98b7e59673e074a2b1cebe5f9b33`
from assembled tree `76266ba77fdf73210b3d4dea47ed7922bdc6b0cf`.
Ordinary boots retain the delayed ATA path. Acceleration requires an explicit
session-only Advanced setting. Repeated race/loading qualification remains
pending because the original missing-data symptom was sporadic.
The final pre-extraction image
`0f6e4f48269e0ef65bb27758e221b4bcdb707ef0cbf57c211d7e969866334d5e`
is now the historical game-test control; the published reference remains
`c630d22f2353d3898024d510f0b402b64bccdb331781fe7885389f73d6200853`.
API fixtures and allocation traces do not substitute for game tests.

## Rejected automatic-QEMU operator result, 2026-10-16

The operator tested interim release64
`45e8c609d6e35688ff54690d4a79430618ed190016fc5fd0262b6ddebfb75392`.
The Advanced page visibly refreshed continuously because its full-page render
condition stayed true while the page remained active. The operator also
reported one recoverable guest crash and reset the guest successfully; no host
xemu crash was reported. The operator described behavior as improved, but this
run is a failed release qualification and does not establish the crash cause.

Release64
`08afa8ab25c48765f51390a8bdfb41ccde298dbef23eb4048642f131bf0d215c`
fixed the redraw condition but automatically accelerated a detected QEMU HDD.
The operator later reported freezing in that automatic mode, so the image is a
failed qualification. Release64
`6f4070f788355d88cf44f37b792a6aceb1e9ead91bc441fe04df800c0a0fc077`
removes all automatic activation, restores the safe delay by default, and adds
an explicit top-row toggle for all current Advanced experiments. It also adds
the measured small-SYSVA local-invalidation path. A follow-up game run remains
required. That image is now rejected after the operator reported worse Forza
corruption. The current candidate rolls back local SYSVA invalidation and keeps
asynchronous XDVDFS reads on the established ordered path.

The exact final image has completed two independent release-only Steam Deck
runs of the full 144-leaf/five-group XISO: 149/149 records passed per run with
no applicable oracle failures or functional-hash changes. The only initial
leaf above the 20% performance review threshold was cleared by a 4,096x-work
ABBA rerun (1.95% slower, all four outcomes passing). This closes the broad
synthetic gate while leaving the human game routes above pending.

A read-only Windows catalog refresh on 2026-10-15 found these assets marked ready. Actual input hashes and the USER desktop/input route must be verified in each new candidate run.

| Title | Registered disc asset | Preparation |
| --- | --- | --- |
| Project Gotham Racing 2 USA/Asia | `pgr2-usa-readonly-v1` | SpiritBoot-created save seed `spiritboot-pgr2-save-20261008-compact-v1` is available as disk contents, without loading VM state. |
| Conker: Live & Reloaded USA | `conker-usa-readonly-v1` | Reuse the fresh-boot/menu input procedure. A historical menu snapshot cannot validate candidate boot. |
| Dead or Alive Xtreme Beach Volleyball USA En/Ja | `doaxbv-usa-readonly-v1` | No registered save-specific seed was found. Use a fresh isolated slot and retain its same HDD and EEPROM through purchase, menu return, reset and reload. |

Existing recipes pin older BIOS/emulator binaries and direct launch. Reuse their input procedures only, with fresh candidate bindings and the current Windows USER desktop wrapper. Preserve paired EEPROM and private writable state. Capture boot, navigation, loading and gameplay outcomes separately; for DOA verify that the purchased item survives reset and no damaged-save message appears. These are pending tests, not inferred passes from historical recipes.

## DOA fixed-emulator human result, 2026-10-15 UTC

The operator reported "I was unable to crash it" for Windows job `doa-fixed-release64-human-20261015-v2`, run `20261015-013327716-b729c0833ee74c93949e9396719f98c6`. This used the existing 64 MiB BIOS `c630d22f2353d3898024d510f0b402b64bccdb331781fe7885389f73d6200853` and release/O2/LTO xemu `14777b55740706608cdfde97349eefa3d5115ece4c889679c9c8b96641a85f2d` (source `f3c528eeec86db32c9f96a932267105e83f77375`, main plus xemu PR356), Vulkan, fresh private HDD/EEPROM, through the Windows USER desktop pipe.

No crash was reported in this human attempt. Purchase persistence through reset/reload was not explicitly confirmed. This is not a replacement-driver pass or a performance measurement, and does not establish the cause of the earlier reported freeze. Retain the same HDD and EEPROM for subsequent save checks.

The run ended at 01:45:32 UTC with wrapper exit code 0 and `incomplete_plan`: the process exited before the long human-test plan finished. The reason for that exit is not established by the receipt. This does not override the operator report or turn the incomplete managed plan into a complete automated pass. All 55 eligible artifacts were collected and retained with the private HDD/EEPROM.
