# Optimized xemu BIOS images

These exact images passed direct xemu qualification at 128 MiB. Release is
262144 bytes (DBG=0); checked is 524288 bytes (DBG=1, KDBG=FALSE). Both use public
kernel commit `87aba89a6ba9b2a58f2edd6e52d5e3aa1e8649d7`, tree
`f7adb302a762ed1945cc07d9c2ff428c643ba959`, reconstructed by the pinned Roswell
base and two ordered hashed patches in `sources/firmware-lock.json`.

Run `sha256sum --check SHA256SUMS.txt` here. Release rebuilt byte-identically
locally and on GitHub CI. Both variants passed 626 API checks with six expected
TODOs, 23 contracts, five warm-reboot checks, and the complete XISO suite:
149 PASS records, COMPLETE 144/144 leaves, zero applicable oracle failures and
253 matching eligible hashes against the validated baseline and each other.

Seven alternating benchmark pairs demonstrate six small pin-workload gains;
35 workloads remain timing inconclusive. See the [measurement report](../../docs/optimization/2026-10-07/integration-and-measurement.md)
and [raw qualification evidence](../../docs/evidence/optimization-2026-10-07/README.md).
Use the pinned Mainkill1 xemu revision and open-direct configuration described
in [BUILD_AND_RUN.md](../../docs/BUILD_AND_RUN.md). Conker gameplay, physical
hardware, 64-MiB support and attached interactive debugger input remain unverified.

Complete corresponding GPL-2.0 source, including existing per-file notices:
[source snapshot](https://github.com/Mainkill1/SpiritBoot/tree/kernel-source-optimization-2026-10-07)
and [source archive](https://github.com/Mainkill1/SpiritBoot/archive/refs/tags/kernel-source-optimization-2026-10-07.tar.gz).
No proprietary BIOS, MCPX, game, SDK, EEPROM or keys are included. Historical
`bios/clean-room-xemu` and `bios/validated-xemu` images remain unchanged.
