# Global ATA settle optimization: REJECTED

## Decision

Patch `0152-ata-400ns-status-reads.patch` is rejected and is not part of the
firmware lock. SpiritBoot retains `KeStallExecutionProcessor(1)` for
`ATA_IO_WAIT` on Xbox. The rejected patch remains here as negative evidence so
the same optimization cannot be rediscovered and accepted from synthetic HDD
results alone.

The rejection was triggered by sporadic missing or corrupt Forza menu data in
the final 64 MiB release candidate. Removing only 0152 restored the complete
profile menu in the same xemu, XISO, memory, and HDD-overlay setup. The other
integrated storage changes, 0146 through 0151, remained enabled.

## Root cause

The patch replaced the one-microsecond guest delay after ATA device/control
changes with four reads of Alternate Status. On physical ATA hardware those
serialized bus reads are the conventional way to consume at least 400 ns, and
they preserve a pending IRQ. That proves port and interrupt semantics, but it
does not prove time equivalence in an emulator.

In xemu, `ide_status_read()` returns the selected device status synchronously.
It does not advance virtual time for each port read. The four reads therefore
consume effectively zero elapsed guest delay. Optical ATAPI command selection
can reach its next status transition earlier than it did with
`KeStallExecutionProcessor(1)`. Forza loads its menu assets from the XISO on
that route, which was absent from the FATX HDD benchmark used to qualify 0152.

The optimization preserved the returned status and IRQ-acknowledgement shape
while violating the required temporal behavior. This is why the prior protocol
model, disassembly check, and HDD workload all passed while the game failed.

## Reproduction and isolation

| Image | SHA-256 | Result |
|---|---|---|
| Integrated 0146--0152 release64 | `00aa2536dbda14ee851665be98e903c32c9705996832b335bbab72ab81c8ead6` | Forza profile menu intermittently omitted the existing profile and details |
| Same image with only 0152 removed | `412bb8a53312777709f0a855e7d1e36d590f5ed0caf770fee39051e61bd13991` | Complete profile menu restored; user confirmed the run worked |

The failing and restored screenshots are in `../forza-menu-corruption/`. The
full source audit and alternative isolation-arm hashes are recorded in
`../forza-menu-corruption/AUDIT.md`.

## Why the original tests missed it

The 0152 tests asserted:

- four Alternate Status reads were emitted;
- the reads did not acknowledge the IRQ;
- command/status ordering was unchanged;
- a 1,024-read FATX HDD fixture completed without data or queue failures; and
- the adjacent synthetic measurement improved.

They did not assert that the replacement consumed elapsed guest time in xemu,
and they did not exercise an optical ATAPI/XISO load. Treating a hardware bus
idiom as emulator-time equivalent was the test-design defect.

## Permanent regression coverage

`tools/check_ata_settle.py` inspects the exact assembled source in every
release64 and release128 CI build. It requires the Xbox PATA header to retain
`KeStallExecutionProcessor(1)` and rejects the context-based zero-time port-read
form. `tests/host/test_ata_stall_candidate.py` verifies the guard itself,
ensures 0152 is absent from the active lock, and locks this rejection report.

The full firmware workflow still runs the optical and storage regression XBEs.
Real-game Forza qualification remains required for release candidates because
no repository fixture contains retail game data. A future ATA settle
optimization must demonstrate all three properties before integration:

1. status and IRQ equivalence;
2. elapsed-time equivalence on the supported emulator; and
3. optical ATAPI/XISO behavior in addition to FATX HDD behavior.

## Performance disposition

The earlier adjacent run reported a 1.14% end-to-end APC improvement and the
three-run mean reported 4.13%. Those numbers are retained only as historical
measurements of the rejected behavior. They are not valid release gains because
the candidate achieved them by deleting effective wait time and failed a game
load. Patches 0146 through 0151 retain their independent correctness and
performance evidence.

The later [explicit Advanced design](EXPLICIT-ADVANCED-ATA.md) keeps this
rejection intact. Every ordinary boot retains the delay. Four status reads are
available only after the operator enables the session-only experiment. QEMU
IDENTIFY detection remains recorded for future capabilities but does not alter
timing.

