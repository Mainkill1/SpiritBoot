# Optimized xemu BIOS images

These exact images passed direct xemu qualification at 128 MiB. Release is
262144 bytes (DBG=0); checked is 524288 bytes (DBG=1, KDBG=FALSE). Both use public
kernel commit `87aba89a6ba9b2a58f2edd6e52d5e3aa1e8649d7`, tree
`f7adb302a762ed1945cc07d9c2ff428c643ba959`, reconstructed by the pinned Roswell
base and the two ordered hashed patches in the
[historical publication lock](https://github.com/Mainkill1/SpiritBoot/blob/9bd0d975346603ecb28e3d54bba87d6fe982551c/sources/firmware-lock.json).
Current main builds additionally apply later correctness patches; these
archived images do not contain those fixes. Use the current CI artifacts
and their build manifests when testing main.

Download the [release image](https://github.com/Mainkill1/SpiritBoot/raw/9bd0d975346603ecb28e3d54bba87d6fe982551c/bios/optimized-xemu/SpiritBoot-release.bin),
[checked image](https://github.com/Mainkill1/SpiritBoot/raw/9bd0d975346603ecb28e3d54bba87d6fe982551c/bios/optimized-xemu/SpiritBoot-checked.bin),
and [checksum manifest](https://github.com/Mainkill1/SpiritBoot/raw/9bd0d975346603ecb28e3d54bba87d6fe982551c/bios/optimized-xemu/SHA256SUMS.txt)
into one directory, then run `sha256sum --check SHA256SUMS.txt` there.
The binary payloads are archived rather than stored on main. Release rebuilt byte-identically
locally and on GitHub CI. Both variants passed 626 API checks with six expected
TODOs, 23 contracts, five warm-reboot checks, and the complete XISO suite:
149 PASS records, COMPLETE 144/144 leaves, zero applicable oracle failures and
253 matching eligible hashes against the validated baseline and each other.

Seven alternating benchmark pairs demonstrate six small pin-workload gains;
35 workloads remain timing inconclusive. See the [measurement report](../../docs/optimization/2026-10-07/integration-and-measurement.md)
and [raw qualification evidence](https://github.com/Mainkill1/SpiritBoot/blob/9bd0d975346603ecb28e3d54bba87d6fe982551c/docs/evidence/optimization-2026-10-07/README.md).
Use the pinned Mainkill1 xemu revision and open-direct configuration described
in [BUILD_AND_RUN.md](../../docs/BUILD_AND_RUN.md). Conker gameplay, physical
hardware, 64-MiB support and attached interactive debugger input remain unverified.

Complete corresponding GPL-2.0 source, including existing per-file notices:
[source snapshot](https://github.com/Mainkill1/SpiritBoot/tree/kernel-source-optimization-2026-10-07)
and [source archive](https://github.com/Mainkill1/SpiritBoot/archive/refs/tags/kernel-source-optimization-2026-10-07.tar.gz).
No proprietary BIOS, MCPX, game, SDK, EEPROM or keys are included. Historical
`bios/clean-room-xemu` and `bios/validated-xemu` images remain unchanged.
