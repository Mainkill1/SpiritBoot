# Explicit advanced ATA settle experiment

## Scope

Patch `0152-emulator-advanced-controls.patch` keeps the reference-compatible
one-microsecond ATA device-select delay as the boot default. It also exposes an
operator-controlled emulator experiment that substitutes four Alternate Status
reads for that delay. No hardware or emulator identity enables the experiment.

The ATA IDENTIFY path still records whether an ATA hard disk model contains
`QEMU`. It excludes ATAPI devices. This detection is an unconsumed capability
signal reserved for future features, such as exposing host CPU capabilities;
it does not modify ATA timing or any current boot setting.

## Advanced controls

Hold X during boot to open Settings, then press Y for Advanced Settings. The
first row is **All advanced settings**:

- **Off** means every currently exposed experiment is disabled.
- **On** means every currently exposed experiment is enabled.
- **Mixed** means individual rows differ. Selecting the row from Mixed enables
  all experiments; selecting it again disables all experiments.

The individual rows remain available:

- **Advanced: contig cache** selects the experimental contiguous-allocation
  cache alias.
- **Emulator ATA acceleration** selects **Safe delay** or **All devices
  (test)**. Safe delay is the default. All devices replaces the select delay
  only after the operator explicitly enables it.

All advanced values are session-only and are never written to EEPROM. The
Advanced page is fully redrawn only when entering or leaving it. Selection and
value changes use the normal dirty-row rendering path. BACK still opens the
hidden credits page, while the main hint advertises Y for Advanced Settings.

## Failed automatic candidate

Release64 `08afa8ab25c48765f51390a8bdfb41ccde298dbef23eb4048642f131bf0d215c`
automatically accelerated IDENTIFY-proven QEMU HDD targets. The operator
reported freezing in auto mode. That image is a failed qualification and is
superseded. Its result is retained because it shows that an emulator model
string alone is insufficient evidence that changing guest-visible timing is
safe.

## Regression controls

`tools/check_ata_settle.py` checks the exact assembled source and rejects a
build unless:

- ordinary `ATA_IO_WAIT()` still calls `KeStallExecutionProcessor(1)`;
- only the explicit all-device flag can select the four-read barrier;
- the fast barrier has exactly four Alternate Status reads;
- the PATA timing helper does not consume the QEMU detection bitmap; and
- QEMU detection explicitly excludes non-`DEV_ATA` devices.

`tests/host/test_ata_stall_candidate.py` locks those rules and injects an
automatic-QEMU regression to prove the checker rejects it. The boot setup suite
covers Y input, Advanced-row isolation, Off/On/Mixed behavior, individual mode
cycling, session-only behavior, and the hidden credits hint. The native menu
renderer fixture rejects continuous Advanced-page redraws.

Real-game qualification remains required for explicit experiments. A synthetic
HDD result cannot establish correct optical timing, game loading, or title
behavior.
