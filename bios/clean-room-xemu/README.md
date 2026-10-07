# Independent kernel xemu BIOS images

These are the exact release and checked images qualified on 2026-10-07 from
public Roswell `1569e2e89fb47cc72b9c704a8884f98200432bd4` plus the checked source
patch in `sources/firmware-lock.json`. The resulting source tree is
`8ba32f2153b4716c8cac269bad06a78553f98ded`.

| File | Bytes | Purpose |
| --- | ---: | --- |
| SpiritBoot-release.bin | 262144 | Reproducible release flash |
| SpiritBoot-checked.bin | 524288 | DBG=1 diagnostic flash; KDBG=FALSE |

Verify with `sha256sum --check SHA256SUMS.txt` from this directory. Both images
pass 626 API checks with six known TODOs, 23 targeted checks, five warm-reboot
checks and the complete XISO suite: 149 PASS records, COMPLETE 144/144 leaves,
zero applicable oracle failures and 253 matching eligible hashes. See
[the qualification report](../../docs/provenance/CLEAN_ROOM_XEMU_BASELINE.md)
and [feature explanations and limits](../../docs/CLEAN_ROOM_FEATURES.md).

Use the documented Mainkill1 xemu revision and 128-MiB open-direct configuration
in [BUILD_AND_RUN.md](../../docs/BUILD_AND_RUN.md). Conker gameplay, physical Xbox
flashing and 64-MiB support are unverified; an older intermittent GPU assertion
remains unresolved. Attached interactive debugger input is unverified.

Complete corresponding kernel source is available in the
[source snapshot](https://github.com/Mainkill1/SpiritBoot/tree/kernel-source-2026-10-07)
and [source archive](https://github.com/Mainkill1/SpiritBoot/archive/refs/tags/kernel-source-2026-10-07.tar.gz).
Its packaging commit preserves exactly the source tree above. Alternatively,
the pinned public upstream and this repository's hashed patch/build instructions
reconstruct it. Preserve GPL-2.0 and existing per-file licensing notices.
No proprietary BIOS, MCPX, game, SDK, EEPROM or key blob is included.
The previous `bios/validated-xemu` v0.1.0 files remain unchanged.
