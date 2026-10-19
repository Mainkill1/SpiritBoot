# Fresh-boot BIOS validation protocol

This fixture is built and has been run repeatedly on release64 firmware. The
[four-run 0176 comparison](../../../docs/performance/evidence/forza-complex-cadence-20261017/candidate0176/README.md)
contains 32 passing sustained cases and improves every primary 450 µs pair.
The earlier [0171 comparison](../../../docs/performance/evidence/forza-complex-cadence-20261017/candidate0171/README.md)
demonstrates rejection when an apparent gain does not repeat. The
[baseline/0168/Complex comparison](../../../docs/performance/evidence/forza-complex-cadence-20261017/initial-poll/README.md)
contains 24 passing cases. These are generated-workload results, not proof of a
Forza gameplay fix. Candidate 0176 was later rejected by title acceptance; the
fixture is no longer sufficient to select firmware by itself. `release-identity.json` records the historical freeze before
those native runs; its source and artifact hashes remain the pinned identity.

## Required procedure

1. Freeze a release64 BIOS, the release emulator, this XISO, configuration and
   writable disk baseline. Record SHA256 identities and the exact patch stack.
   Keep the same emulator, 64 MiB setting, EEPROM, disk layout and generated-file
   setup procedure across the compared runs. Use an isolated writable HDD overlay
   with the appropriate firmware/EEPROM identity; do not substitute a game's
   differently keyed save/profile disk.
2. Start a **new emulator process** for each run. Boot the specified BIOS from
   reset. Do not load a RAM-bearing snapshot or saved VM state: that restores
   the saved kernel and invalidates a comparison of newly built firmware.
   Reusing an explicitly pinned disk baseline is distinct from restoring RAM.
3. Run all eight cases to completion, each for at least ten seconds. Collect
   complete COM1 output and process/runner outcome. Require the final success
   marker and a successful analyzer result before proceeding to the next run.
   A timeout, crash, missing record, oracle failure or unfinished request is a
   failed/incomplete qualification, not a performance sample to average.
4. For a candidate comparison, predeclare the order and keep the runner exclusive.
   The established order is control 1, candidate 1, control 2, candidate 2, with
   no other test jobs interleaved. Analyze each pair and retain both runs; a
   pooled average must not hide reversed effects or correctness failures.
5. Report reads/s, total bytes/s, weighted read-entry-to-return cost, per-size
   means and maxima, initial alertable-poll cost, first-read size mix and all
   failures. The primary synthetic deadline is 450 microseconds at both free-page
   targets. Report other budgets too. Investigate any regression over 20%; do not
   omit maxima merely because means improve. Eight-issue/33 ms limits cap the
   uncapped case, so its rate is not maximum storage bandwidth.
6. Preserve the input identities, runner configuration, serial logs, parsed
   summaries, comparison script/output and acceptance decision with the PR or
   tracking issue. Keep private ROMs, game payloads, RAM snapshots and credentials
   out of the published evidence.

Run the analyzer with:

```sh
python3 tests/xbe/forza-poll-budget/analyze.py SERIAL.log
```

The [fixture README](README.md) supplies build instructions, fixed artifact
hashes, the exact caller and callback contract, and expected records. The
[0176 reproduction script](../../../docs/performance/evidence/forza-complex-cadence-20261017/candidate0176/reproduce.py)
regenerates the selected four-run comparison and its acceptance decision.

## What passing proves

Every completed generated read is checked byte for byte. Buffer and IOSB guards,
callback identity/status/length/count, alertable-phase ownership and delayed
buffer reuse are checked. Memory pressure and read sizes are controlled. The
same release fixture and analyzer must be used on both BIOS images.

A function-level change also needs its own contract regression and automated
fresh-process title gates. Candidate0176 passed request-core, threaded ownership,
native-adapter, packet, owner, optical and sense tests, including sanitized
variants and a strict 14-to-7 lock-transition bound, yet failed title acceptance.
A native throughput pass does not replace those contract or title tests.

## Remaining coverage

The fixture does not render, drive a car, recreate every title allocation or
exercise every kernel export. Its first-read/nearby-read serial samples cover
only an early prefix of each case; the existing full-run totals do not isolate
those positions. A controlled spacing experiment with full-run position counts
is still needed to investigate the long-gap timing difference. It must be a new
fixture revision, compared against a freshly rerun control using that same
revision, rather than mixed with the frozen results.

A final fresh-boot Forza test remains necessary to claim improved world streaming.
Preserved scene replays are useful for diagnosing their original kernel only.
