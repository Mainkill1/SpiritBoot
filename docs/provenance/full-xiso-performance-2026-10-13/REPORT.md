# Two-campaign full XISO comparison — 2026-10-13

Tracking issue: [SpiritBoot #240](https://github.com/Mainkill1/SpiritBoot/issues/240).

The second complete campaign confirms the principal streaming, cache, crypto, pinning, SYSVA, and timer/APC gaps. It uses unchanged ROMs, emulator, fixture images, disabled-leaf list, and starting-disk recipe. This is a performance baseline for future work, not evidence that the DOA save fix caused these differences.

## Coverage

Each campaign runs the full 639-leaf API XISO with 634 enabled and five identical explicit skips. Eight alternating BIOS pairs per campaign include pair 0 as pilot/warmup; pairs 1–7 are measured. Both campaigns together completed 32 full-suite runs and 20,288 enabled leaf executions. The supplementary 40-workload kernel, streaming, and synchronization fixtures each ran seven alternating pairs per campaign; these have no discarded pair-0 warmup.

In all fourteen measured runs per BIOS, Complex passes all 634 enabled leaves; SpiritBoot passes 630 and fails the same four pre-existing TODO assertions. No correctness failure contributes to performance aggregates. All supplementary campaigns report zero correctness failures. TAP end-PASS includes TODO failures and is not a declaration of full parity.

## Requested average

Primary arithmetic average: calculate each campaign's mean of its seven measured test-body totals, then average the two campaign means equally. With equal sample counts this is also the mean of all fourteen measured totals. **Complex 17.190 s; SpiritBoot 12.873 s**, **25.1% shorter** for the common-passing 630 test bodies.

| Campaign | Complex mean | SpiritBoot mean | Complex median | SpiritBoot median |
|---|---:|---:|---:|---:|
| First | 17.157 s | 12.882 s | 17.206 s | 12.892 s |
| Repeat | 17.223 s | 12.865 s | 17.225 s | 12.866 s |
| Equal-weight average | 17.190 s | 12.873 s | 17.216 s | 12.879 s |

All 639 rows appear in [averaged-all-leaves.csv](averaged-all-leaves.csv), with both campaign means/medians/ranges, average means/medians, correctness counts, and skip reasons. Group totals appear in [averaged-groups.csv](averaged-groups.csv).

Repeatability rule: a leaf is classified faster or slower only when all seven measurements on one BIOS lie below/above all seven on the other **in each campaign**, in the same direction. For the 630 common-passing leaves: **75 not confirmed in both campaigns, 196 slower, 292 overlapping ranges, 67 faster**. Overlapping ranges and unconfirmed directions remain visible. This is a conservative descriptive rule rather than a formal significance test; very short leaves are sensitive to timer quantization and measurement overhead.

The suite total includes waits, cleanup, assertions, diagnostics, and adaptive pressure work. Large pressure-test decreases dominate it. It does not establish general kernel or game-loading speed. Contiguous relocation probes also expose behavior differences hidden by broad PASS assertions, so apparent allocation wins need semantic review.

## Confirmed targets

Full-leaf rows below use arithmetic means and their equal-weight two-campaign average:

| Target | Complex 1 / 2 (ms) | SpiritBoot 1 / 2 (ms) | Average Complex (ms) | Average SB (ms) | SB / Complex |
|---|---:|---:|---:|---:|---:|
| `ex/timer/a_user_mode_apc_runs_on_expiry` | 50.863 / 50.856 | 501.881 / 500.473 | 50.860 | 501.177 | 9.85× |
| `io/cc-write/write_heavy_no_deadlock` | 141.913 / 142.739 | 330.327 / 331.138 | 142.326 | 330.733 | 2.32× |
| `mm/cache/read_churn` | 252.252 / 252.911 | 421.486 / 422.349 | 252.581 | 421.917 | 1.67× |
| `mm/cache/eviction_two_files` | 158.119 / 159.101 | 290.863 / 284.887 | 158.610 | 287.875 | 1.81× |
| `io/cc-write/many_files_flush_on_close` | 60.904 / 60.843 | 139.485 / 138.111 | 60.873 | 138.798 | 2.28× |
| `io/cc-write/small_file_reopen` | 6.614 / 6.592 | 25.699 / 24.478 | 6.603 | 25.088 | 3.80× |
| `xc/rsa/modexp_even_modulus` | 0.100 / 0.097 | 14.225 / 13.993 | 0.099 | 14.109 | 143.06× |

Supplementary rows use each campaign's median per workload, averaged equally; ratios divide averaged times rather than averaging ratios. Streaming elapsed rows cover 1,024 reads per phase; crypto/memory values are per complete workload iteration, not necessarily one API call.

| Target | Complex 1 / 2 (ms) | SpiritBoot 1 / 2 (ms) | Average Complex (ms) | Average SB (ms) | SB / Complex |
|---|---:|---:|---:|---:|---:|
| `phase0/elapsed` | 85.000 / 85.000 | 156.000 / 160.000 | 85.000 | 158.000 | 1.86× |
| `phase1/elapsed` | 84.000 / 83.000 | 156.000 / 151.000 | 83.500 | 153.500 | 1.84× |

| Target | Complex 1 / 2 (ms) | SpiritBoot 1 / 2 (ms) | Average Complex (ms) | Average SB (ms) | SB / Complex |
|---|---:|---:|---:|---:|---:|
| `sha-1MiB` | 23.796 / 23.497 | 64.281 / 62.580 | 23.647 | 63.431 | 2.68× |
| `des-cbc-4096` | 0.422 / 0.424 | 34.239 / 33.156 | 0.423 | 33.698 | 79.66× |
| `des3-cbc-4096` | 1.011 / 1.015 | 102.569 / 98.564 | 1.013 | 100.566 | 99.30× |
| `modexp-512-e1-odd` | 0.083 / 0.087 | 350.137 / 347.989 | 0.085 | 349.063 | 4112.00× |
| `pin-4096` | 0.046 / 0.045 | 2.205 / 2.245 | 0.046 | 2.225 | 48.64× |
| `sysva-4096` | 2.820 / 2.849 | 11.408 / 11.357 | 2.835 | 11.382 | 4.02× |

Every supplementary workload is included in [averaged-microbenchmarks.csv](averaged-microbenchmarks.csv), [averaged-streaming.csv](averaged-streaming.csv), and [averaged-synchronization.csv](averaged-synchronization.csv). These gaps repeated in the same direction. Absolute trial ranges and campaign differences remain in the CSVs.

## Correctness and semantic targets

- `io/bad-ptr/set_eof_beyond_free_space`: SpiritBoot status mismatch.
- `io/storage/flush_volume_readonly`: SpiritBoot behavior mismatch.
- `ke/procprio/a_new_thread_starts_at_the_process_priority`: priority inheritance mismatch.
- `ke/procprio/the_process_lists_its_threads`: process thread-list mismatch.
- `ex/timer/a_user_mode_apc_runs_on_expiry`: approximately 50 ms versus 500 ms; fixture checks APC count/context but ignores the alertable wait status. Prove the wait/APC divergence with stronger assertions before changing it.
- VM/pool contiguous relocation probes report success on Complex and NULL on SpiritBoot while broad assertions pass. Prove equivalent placement/movement work before claiming allocation speedups.

## Exclusions and reproducibility

The five disabled leaves remain unchanged: DOS-root rename, AV optional-NULL query, raw-device dismount contract, and two FP exception tests that fail on both BIOSes in this xemu lab. See [the first campaign's writeup](campaign1/REPORT.md) for exact names, reasons, original pilot failures and portable-fixture changes. SpiritBoot-only failures remain enabled.

Both campaigns used the same SpiritBoot DOA-save ROM `1ed234ebaf8e95937225c3002b6eac26257b0f3d1ff8f3d6a3aabd464955fb0b`, Complex ROM `1de4c87effe40d44f95581d204f9fa0600fbd5fe2171692316dcf97af0f4113f`, and xemu executable `14777b55740706608cdfde97349eefa3d5115ece4c889679c9c8b96641a85f2d`. Settings: Vulkan, 64 MiB, interactive Windows PowerShell session, no debugger, one benchmark VM at a time, fresh overlays and copied EEPROM, alternating BIOS order. Fixture image SHA identities match across campaigns.

Post-run audits verify normalized configuration, backing paths, and EEPROM identity. The source backing-file size and modification time match the first campaign's recorded values. This is not full before/after hashing of the entire backing chain. Host caches were not explicitly evicted; alternating order reduces but does not eliminate cache effects. These measurements characterize this xemu build rather than physical Xbox performance.

Raw serial, launch, exit results and input audits are retained for both campaigns. `average.py` recomputes the requested means from raw per-leaf counter ticks normalized by each run's frequency; it verifies complete campaign coverage and excludes any leaf failing in either campaign. Per-campaign `analyze.py` verifies exact BIOS/executable/fixture identities and enabled/skip sets. Fixture changes and source are preserved from the first campaign. [REPRODUCE.md](REPRODUCE.md) gives commands to recompute every average from the archived evidence.

Follow-up implementations must establish the deviating calls, strengthen correctness coverage, exceed repeat-run variation on fixed workloads, and retain asynchronous, memory-pressure, lifetime, and error semantics. Every fix should have a focused PR and writeup. Existing related work: [direct MDL I/O #212](https://github.com/Mainkill1/SpiritBoot/issues/212), [SYSVA batching #214](https://github.com/Mainkill1/SpiritBoot/issues/214).
