# Steam Deck retained-SG Forza function census

This directory is the compact, reviewable subset of the reproducibility bundle
for the first marker-bounded 1,024-read phase from the owned Forza public
request replay on the Steam Deck. It uses the accepted release64 retained-SG
BIOS `f7f22399…a84ef` and an optimized plugin-enabled xemu at commit
`dcc536830deb`. The emulator is a diagnostic binary; profiler overhead makes
its wall/CPU duration unsuitable for release performance claims.

The original complete archive, including the exact BIOS, unstripped kernel,
XISO, compressed serial log, JIT map and built plugin, has SHA-256
`06bc9f9979ac8aee03ef3a1b971015c802ba5131332521725eef6e1cbd3aa38d`.
Those large generated binaries are identified in `MANIFEST.json` and omitted
from this source repository. This directory keeps the raw marker counters,
complete function ledger, analysis/build source, runner request and config.

## Result

- Correctness passed: 1,024/1,024 reads, 10,871,296 bytes, QD12, 900 pressure pages, zero oracle failures.
- `results/executed-kernel-function-ledger.csv` contains all 191 nonzero rows: 190 exact entry hits and one range-only interrupt-template attribution.
- `results/all-kernel-function-performance-ledger.csv` accounts for all 1,684
  final release kernel entry symbols. It carries the measured disposition for
  190 observed entries and explicitly marks the other 1,494 as unmeasured in
  this workload, requiring a relevant full-XISO leaf or game route before any
  performance claim or rewrite. The retained-SG census had 191 rows; patch
  0151 removes the separate `NxAtapiCacheWriterReset` entry by replacing its
  general definition call with direct request-owned initialization. That
  retirement is explicit in `results/final-function-renames.json`.
- Guest-instruction leaders were `_pump` (10.45%), `_VfatTryMapRead` (10.29%), `@KfLowerIrql@4` (5.88%), `_KeStallExecutionProcessor@4` (4.01%), and `_NxNativeAdapterSubmit` (3.29%).
- Primary dispositions: {"next_candidate": 16, "optimized_in_batch": 21, "required_hardware_correctness_path": 154}. Review-category columns explicitly cover optimize, required hardware, correctness, emulator, and diagnostic attribution. Emulator is `no` for every row because this is a guest-kernel census; no host `perf` sample was captured.
- No counter overflow or lost records occurred. All counters are 64-bit; maxima and runner drop/overrun counters are recorded in `MANIFEST.json`.
- No Linux `perf record` sample was taken. `-perfmap` was enabled and the exact
  JIT map is retained in the complete archive. Host sampled-CPU attribution is
  therefore explicitly unsupported.

## Marker semantics

`profile_phase_begin` at guest PC `0x000110e0` runs immediately before the unchanged `run_batch(12)`. `profile_phase_end` at `0x000110f0` runs after the final APC/batch return and before post-batch verification. The plugin records only the first complete window; the remaining 15 fixture passes are ignored. Both marker calls sit outside the fixture's own RDTSC interval. `fixture-source/marker-only.patch` is the complete delta from the original recorder.

## Reproduction

1. Supply the private assets named and hashed in `MANIFEST.json`: EEPROM, clean FATX HDD asset, and boot ROM. The bundle deliberately does not redistribute them.
2. Supply the exact plugin-enabled xemu binary identified by SHA-256 `95bf0ae6…342e459`, or rebuild commit `dcc536830deb` with plugin support. The 31.6 MB binary is omitted to keep this bundle compact.
3. Verify this subset with `SHA256SUMS`. To replay it byte-for-byte, first
   restore the large generated artifacts identified by `MANIFEST.json`, then
   use `runner/request.json` with the xemu test runner or follow the exact
   build/submit/analysis commands in the manifest.
4. Validate the final serial TAP line and the plugin `complete` record. The collected originals are under `evidence/`; large serial and perf-map files are deterministically gzip-compressed.

`MANIFEST.json` is authoritative for identities, commands, marker placement,
counter integrity, and attribution limits. `results/summary.md` is the short
review view; the CSV is the complete disposition ledger.
