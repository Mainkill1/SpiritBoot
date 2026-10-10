# ROM memory-type diagnostic

Addresses SpiritBoot issue #139. This standalone nxdk guest runs with unchanged
RAM-only or optional PR #118 BIOS builds. It is not a game benchmark and changes
no official inputs, firmware mappings, MTRRs, PAT, cache controls or release code.

Build with the existing nxdk toolchain:

```sh
make NXDK_DIR=/path/to/nxdk
```

The dedicated CI workflow builds with immutable nxdk image
`ghcr.io/xboxdev/nxdk@sha256:bab707b7ed2544e9956d51e7b411a4575ab66120bd608b3237698495203d15f7`.
The UART emitter reuses the pinned Roswell API-regression emitter, including
SpiritBoot's record-serialization repair. No reference BIOS code is reused.

Boot the generated ISO with 64 MiB, TCG, the ordinary diagnostic UART device
(`-device lpc47m157 -serial file:serial.log`), and disposable HDD/EEPROM copies.
The guest requires a non-PAE Intel-compatible CPU exposing TSC, MSRs, MTRRs and
PAT. Unsupported configurations terminate with FAIL. The diagnostic leaf must
match the five-byte, self-contained `RtlUlongByteSwap` implementation in the
owned SpiritBoot build; a different leaf fails before copying or executing it.
Do not use this guest to inspect another firmware implementation.

## Outputs and checks

- CPU features, physical address width (architectural P6 fallback: 36 bits),
  CR0/CR3/CR4, MTRR capability/default, PAT and every supported variable MTRR.
- Actual page-table entries and physical translations for the public kernel
  leaf, its RAM copy and both pages of a crossing RAM copy. Cross-checks the walk
  with `MmGetPhysicalAddress`; large and ordinary pages are distinguished.
- Identical leaf bytes and 1,024 independent byte-swap results checked before
  timing. Every timed pair and page-crossing loop must have the same checksum.
- Seventeen rounds of 32,768 calls/reads, with kernel/RAM call order alternating.
  Serial formatting occurs after intervals. Round zero is retained but is **not
  a proved cold-cache sample**: correctness checks already executed every leaf.
- CPUID-serialized RDTSC intervals, an empty indirect-call control, a crossing
  instruction control and matched 128-byte volatile-read loops. Use the same
  non-inlined loop for every function. Empty-loop controls are diagnostic,
  not a license to report negative or artificially precise subtracted latency.

Analyze the completed serial capture from the repository root:

```sh
python3 tools/rom_memory_types.py serial.log
```

The analyzer requires a single complete PASS block, all reported variable MSRs,
four unique translation-consistent page records, supported CPU/paging mode,
and all 17 ordered sample rounds with the exact workload/checksum. Intel SDM
volume 3A tables 11-7/11-11 define
the MTRR/PAT combination. Ambiguous overlaps, fixed ranges below 1 MiB, invalid
types and non-normal CR0 cache mode remain UNKNOWN. This tool reports the page
being accessed, not the cacheability of the temporary page-table alias.

## Interpretation limits

TCG does not model physical Xbox flash latency or instruction-cache misses.
Guest RDTSC intervals under xemu reflect its virtual clock and host scheduling;
they are not exclusive host CPU cycles, title frame time or game FPS. Retain
exact BIOS/xemu/guest identities, serial results and run order outside product
main. Run balanced fresh processes for emulator-cost comparisons.

The RAM crossing copy spans a **4 KiB instruction alignment**. The observed
RAM mappings use one 4 MiB PDE, so these captures do not cross a guest
translation-page boundary. xemu's TCG translation blocks use 4 KiB boundaries;
keep that execution boundary distinct from guest page-table geometry.

Physical hardware, cold I-cache/working-set eviction and ROM page-crossing
execution still require separate qualification. This guest does not map or
execute the upper BIOS mirror, modify MCPX overlay state, clear issue #120,
qualify PR #118 for release or establish that #140's alias change is safe.

Architectural reference:
[Intel SDM, volume 3A](https://www.intel.com/content/dam/www/public/us/en/documents/manuals/64-ia-32-architectures-software-developer-vol-3a-part-1-manual.pdf).
