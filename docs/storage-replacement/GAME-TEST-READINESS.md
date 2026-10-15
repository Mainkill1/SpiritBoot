# Live game test readiness

No fresh PGR2, Conker or complete DOA save-cycle pass is established by the current PR248 work. A bounded DOA human test is recorded below. The full replacement is not installed. The final pre-extraction release64 image, including the semaphore and public-kernel contract corrections, has SHA-256 `0f6e4f48269e0ef65bb27758e221b4bcdb707ef0cbf57c211d7e969866334d5e`. The earlier semaphore-only candidate `42ad0c392b97d195f6aacaa47b1c168f1f74038ddf3258257b21cfde99bcb647` is superseded; the published reference remains `c630d22f2353d3898024d510f0b402b64bccdb331781fe7885389f73d6200853`. API fixtures and allocation traces do not substitute for game tests.

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
