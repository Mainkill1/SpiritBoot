Native performance evidence, 2026-10-13

The evidence archive contains 94 serial native runs: baseline/reference timer
reproduction; individual DES and rejected pin trials; the two-change integration;
seven validated-pin pairs; I/O completion-policy diagnostics; and final three-
change qualification. Windows runs used interactive PowerShell, one emulator at
a time, separate HDD overlays and EEPROM copies, 64 MB RAM, and no debugger.

Recompute from a fresh directory using Python 3 (standard library only):
  unzip evidence.zip -d evidence
  cd evidence
  python3 analyze-performance.py --inputs inputs.json --output recomputed
  python3 analyze.py
  python3 analyze-memory.py

The first command validates all 25 final runs and the actual bundled firmware,
build identity and five frozen ISOs, then produces every API leaf and every
supplementary workload. The other commands validate the earlier seven-pair
standalone campaigns, including the rejected consecutive-frame optimization.
Earlier timer+DES integration CSVs/JSON are retained as intermediate evidence;
analyze-final.py supplies the shared frozen contracts to the memory analyzer.
Its default workspace artifact paths are documented in the script; it is not
the final candidate analyzer.

Recompute completion-policy diagnostics:
  python3 io-policy/analyze.py results/probe-io-policy-*/serial.log

For supported fixture names, every sample is required. Analyzer acceptance
requires BIOS/XISO/emulator hashes, interactive session, complete TAP/checksum
contracts, process exit, no run overlap, and the specified alternating order.
Five API skips are frozen identically. Four existing TODO failures remain
excluded from speed aggregates. Inherited skip-reason labels do not establish
an emulator root cause for the two floating-point exception exclusions.

flash.bin is the final SpiritBoot 64 MB test candidate, not a tagged release.
No Complex ROM, game image, save, HDD image or EEPROM is included. The archive
contains open test inputs, SpiritBoot firmware, benchmark receipts and source.
The source fixture archive is the frozen full-suite input; timer and I/O-policy
sources are also included. The product patch lock defines the firmware source.

See ../../optimization/native-performance-2026-10-13.txt for conclusions,
limitations, changes, retained regressions and next targets. SHA256SUMS covers
the archive and loose reports. CSVs report observed distributions, not formal
confidence intervals. Test-body aggregate speed is not a game FPS benchmark.

The authoritative final image tables are performance-all-leaves.csv and
performance-full-fixtures.csv. The retained final-*.csv files describe the
earlier timer+DES image. The I/O fixture README records its build-time pending
state; io-policy/NATIVE-ANALYSIS.txt and results.json supersede that statement.
