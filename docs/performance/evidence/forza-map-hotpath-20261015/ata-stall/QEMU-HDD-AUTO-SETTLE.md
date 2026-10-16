# QEMU HDD automatic ATA settle acceleration

## Scope

Patch `0152-qemu-ata-advanced-controls.patch` restores a narrowly gated
version of the device-select optimization. It does not revive the rejected
global timing change.

After a successful IDENTIFY, the ATA driver decodes the model string and marks
the target only when both conditions hold:

1. the device type is `DEV_ATA`, so it is a hard disk rather than ATAPI; and
2. the decoded model contains `QEMU`.

Subsequent device selects for that identified HDD use four Alternate Status
reads as the ordering barrier. The first IDENTIFY remains on the delayed path
because the target has not been proved yet. Optical/XISO traffic retains
`KeStallExecutionProcessor(1)` automatically, including a QEMU optical drive.
Physical and unknown HDD models also retain the delay.

This removes the emulator-only delay from the hot HDD route without applying
the zero-elapsed-time substitution to the optical route implicated in the
sporadic Forza menu corruption.

## Advanced controls

Hold X during boot to open Settings, then press Y for Advanced Settings.
`Emulator ATA acceleration` has three session-only modes:

- **Auto (QEMU HDD)** is the default. Only IDENTIFY-proven QEMU ATA HDD targets
  use the fast barrier.
- **Safe delay** forces the one-microsecond delay for every device.
- **All QEMU devices (test)** forces the four-read barrier for every selected
  device. This is an explicit experimental comparison mode and can reproduce
  the unsafe optical timing shape, but only after a QEMU HDD has first been
  identified. It remains inert on physical or unknown hardware.

The setting is never written to EEPROM. Safe delay takes precedence if flags
are malformed. The normal Settings screen advertises Y for Advanced Settings.
The BACK credits action remains implemented but is no longer shown in the
controls hint.

The first native menu candidate repainted the entire Advanced page on every
10 ms input-loop iteration. The corrected renderer performs a full content
draw only when entering or leaving Advanced. Selection and value changes use
the same dirty-row path as the main menu.

## Regression controls

`tools/check_ata_settle.py` checks the exact assembled source and rejects a
build unless:

- the ordinary `ATA_IO_WAIT()` still calls
  `KeStallExecutionProcessor(1)`;
- safe mode dominates the experimental all-device mode;
- automatic acceleration is gated by the identified target bitmap;
- the fast barrier has exactly four Alternate Status reads; and
- QEMU detection explicitly excludes non-`DEV_ATA` devices.

`tests/host/test_ata_stall_candidate.py` tests the checker, patch lock, QEMU
HDD gate, optical exclusion, and preserved rejected-patch evidence. The boot
setup suite separately tests Y input, advanced-row isolation, mode cycling,
session-only behavior, and the hidden credits hint. The assembled native menu
renderer check verifies that changing menu pages clears only its content
region and leaves the logo intact. It also rejects the continuous Advanced-page
redraw condition.

These checks close the missing static contract that allowed the global 0152
change through. Repeated Forza optical/game qualification is still required
because the original title symptom was sporadic and retail data is not stored
in the repository.
