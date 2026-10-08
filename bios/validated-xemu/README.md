# Validated xemu BIOS images

These are the exact SpiritBoot images validated from implementation commit
`197041dce740cf0eadba215818222f10c5f3a3d0` on 2026-10-07.

| File | Size | Purpose |
| --- | ---: | --- |
| [SpiritBoot-release.bin](https://github.com/Mainkill1/SpiritBoot/raw/refs/tags/v0.1.0-xemu-test-baseline/bios/validated-xemu/SpiritBoot-release.bin) | 262,144 bytes | Reproducible release flash |
| [SpiritBoot-checked.bin](https://github.com/Mainkill1/SpiritBoot/raw/refs/tags/v0.1.0-xemu-test-baseline/bios/validated-xemu/SpiritBoot-checked.bin) | 524,288 bytes | Checked flash with kernel diagnostics |

Download both images from the immutable tag links above into a separate local folder, copy `SHA256SUMS.txt` there, then run `sha256sum --check SHA256SUMS.txt`. The historical images remain at their published tag; main retains these download instructions.
Use the documented Mainkill1 xemu revision, 128 MiB memory, and open-direct boot
configuration in [BUILD_AND_RUN.md](../../docs/BUILD_AND_RUN.md).

Both variants completed the full Mainkill1 XISO: 149 PASS records, complete
144/144 leaf receipts, clean shutdown, and 253 matching eligible cross-variant
hash checks. Both completed the open kernel suite with 625 passes, six known
TODOs and zero unexpected failures. Host tests and implementation CI passed.
See [XISO evidence](../../docs/provenance/XISO_SUITE_BASELINE.md) and
[open-kernel evidence](../../docs/provenance/OPEN_FIRMWARE_BASELINE.md).

This is an experimental emulator test baseline. An earlier intermittent GPU
polling assertion remains unresolved; repeated-run stability, Conker gameplay,
and physical Xbox flashing are unverified.

Corresponding kernel/loader source:
https://github.com/mborgerson/roswell/tree/1569e2e89fb47cc72b9c704a8884f98200432bd4 .
To reproduce this older baseline, use the build instructions and lock at its published tag. The current main lock builds the later kernel compatibility changes. Preserve
Roswell's per-file GPL/MIT/BSD/LGPL/CC0 licensing notices. No proprietary BIOS,
MCPX, game, SDK or EEPROM data is included.
