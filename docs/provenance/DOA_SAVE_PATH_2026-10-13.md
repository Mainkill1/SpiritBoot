# DOA Xtreme save creation: FATX doubled separators

## Failure and disk contents

The reported sequence is: select a save slot and character, pass the intro,
buy an item, return to the menu, reset xemu, then load the slot. SpiritBoot
reports “Damaged game”; Complex can reload its save.

The title directory is `E:\UDATA\54430007`. In this reproduction the slot is
`42285B90C468`. SpiritBoot created the slot directory and `SaveMeta.xbx` (56 bytes),
but no `doaxuser.dat` appeared after the purchase. The independent older Complex
lab disk contained an 11,176-byte `doaxuser.dat`. The older disks have different
histories; their byte contents are not treated as a controlled BIOS comparison.

A public ABI trace supplies the causal observation: two attempts to open
`U:\42285B90C468\\doaxuser.dat` return `STATUS_OBJECT_NAME_INVALID` (`0xC0000033`)
and no handle. Both use `FILE_OPEN_IF`, access `0x40100080`, attributes `0x20`,
share 0, and options `0x60`. Slot metadata opens succeed. The doubled separator
between the save directory and filename prevents creation of the actual save.
The rejected operation occurs before a data write; this evidence does not show
bad bytes being written or a signature verification failure.

[The reduced trace](doa-save-path-2026-10-13/doa-create-failure.json) includes the
public arguments and return values. The trace reads no title or reference BIOS
instructions. Tracing began after boot and was restarted while reducing debugger
overhead, so it does not establish the first save attempt or every save trigger.
The captured failed attempts are in one uninterrupted segment.

## Reference comparison and fix

The same independently written XBE runs on Complex, v0.99.5, and the candidate
using the same emulator, 64 MB configuration, EEPROM and HDD backing image, with
fresh separate overlays. It uses synthetic data, not game content.

| Public file operation | Complex | v0.99.5 | Candidate |
| --- | --- | --- | --- |
| Canonical path create/read | succeeds | succeeds | succeeds |
| Doubled separator inside path | succeeds | NAME_INVALID | succeeds |
| Tripled separator | NAME_INVALID | NAME_INVALID | NAME_INVALID |
| Doubled separator at volume root | NAME_INVALID | succeeds | NAME_INVALID |
| New file via doubled path; canonical reopen | correct bytes | create rejected | correct bytes |

`VfatCreateFile` inherited a blanket rejection of adjacent separators. The patch
normalizes FATX's accepted doubled separators in the I/O manager-owned, counted
`FILE_OBJECT.FileName` buffer before validation and FCB lookup. It first rejects
triples and doubled volume-root separators without modifying the buffer. The
canonical spelling then shares the existing FCB, allocation and share state.
There is no allocation, title-specific exception or game-data change. Non-FATX
volumes retain their original path handling.

## Validation and provenance

- Baseline product: v0.99.5 / `f7667a545213f0a35a07a92713dbc9c1abca765e`.
- Public Roswell base: `1569e2e89fb47cc72b9c704a8884f98200432bd4`.
- Candidate assembled source tree: `04e3879e287135735111efdc8d25488d94a7793c`.
- Candidate release64 ROM SHA256: `1ed234ebaf8e95937225c3002b6eac26257b0f3d1ff8f3d6a3aabd464955fb0b` (524,288 bytes).
- XBE ISO SHA256: `f52509efd887041da7eecfd0998d06992544c85a0ba2ee23cf22814ab243a2d9`.
- xemu release SHA256: `14777b55740706608cdfde97349eefa3d5115ece4c889679c9c8b96641a85f2d`, source `f3c528eeec86db32c9f96a932267105e83f77375`.
- Native tests launched through interactive PowerShell in Windows user session 1.
- Baseline: 10 failing checks out of 28 executed; dependent checks cannot run after failed opens.
- Complex: 34/34. Candidate: 34/34. All three emulator processes exited normally.
- Product host suite: 130 tests passed, including three existing skips.
- Counted-string host test compiles the production function with address and undefined-behavior sanitizers.
- Independent code review: no critical or important findings; probe requires fresh overlays.

[Native TAP logs and launch provenance](doa-save-path-2026-10-13/) are committed.
The candidate's game run uses the optimized release emulator without a debugger.
Human save/reset/reload verification is pending.

## Limits and separate findings

Existing slot metadata without game data cannot reconstruct the missing save;
a new save must be written successfully. No key changes are included. The zero
placeholder title-signing master key is a separate compatibility question, not
the demonstrated cause of these rejected create calls.

The informational trailing-file-separator survey exposes a separate status
mismatch: Complex returns NOT_A_DIRECTORY, while SpiritBoot returns NAME_INVALID.
Neither accepts that regular-file path. It is recorded, not claimed fixed. Native
qualification here covers 64 MB xemu; no physical-console result is asserted.
