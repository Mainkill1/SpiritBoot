# Full XISO leaf comparison — 2026-10-13

SpiritBoot DOA-save candidate, 64 MiB, versus Complex 4627 v1.03 on the same Windows xemu release build. This is the full API regression XISO, with per-leaf timing, plus separate portable microbenchmarks, streaming and synchronization fixtures. It is not a game-ISO sweep.

## Coverage and correctness

All **639 registered leaves are accounted for**: **634 enabled**, five explicitly disabled identically on both BIOSes. Eight sequential alternating pairs completed: pair 0 is the pilot/warmup, pairs 1–7 are measured. That is 10,144 actual leaf executions across sixteen completed full-suite runs. Every measured Complex run passed 634 enabled assertions; every SpiritBoot run passed 630 and failed the same four pre-existing TODO assertions. A TAP end-PASS banner includes TODO failures and must not be read as full correctness.

SpiritBoot-only failures, retained in the results rather than disabled:

- `io/bad-ptr/set_eof_beyond_free_space`
- `io/storage/flush_volume_readonly`
- `ke/procprio/a_new_thread_starts_at_the_process_priority`
- `ke/procprio/the_process_lists_its_threads`

Only the **630 leaves passing on both BIOSes in all seven pairs** enter the aggregate timing. All 639 leaves, their correctness counts, timings and exclusions are in [all-leaves.csv](all-leaves.csv); group totals are in [groups.csv](groups.csv).

## Whole-suite execution time

Median sum of those 630 test bodies: **Complex 17.206 s; SpiritBoot 12.892 s**, a **25.1% shorter suite runtime**. Ranges: Complex 16.991–17.320 s; SpiritBoot 12.828–12.923 s.

This is a regression-suite runtime, not general kernel throughput or predicted game-loading speed. It includes setup, cleanup, assertions, internal diagnostic output, deliberate waits, and adaptive memory-pressure workloads. Large pressure-test differences dominate the total. Passing assertions do not establish every underlying behavior is equivalent.

Using the conservative descriptive rule that all seven measurements on one BIOS must lie below all seven on the other: **83 leaves faster, 217 slower, 330 with overlapping ranges**. This rule is not a formal significance test. Sub-microsecond leaves are especially sensitive to timer overhead and quantization.

Largest repeatable increases in test-body time:

| Leaf / workload | Complex ms | SpiritBoot ms | SB / Complex |
|---|---:|---:|---:|
| `ex/timer/a_user_mode_apc_runs_on_expiry` | 50.764 | 502.249 | 9.89× |
| `io/cc-write/write_heavy_no_deadlock` | 142.072 | 329.248 | 2.32× |
| `mm/cache/read_churn` | 251.898 | 423.000 | 1.68× |
| `mm/cache/eviction_two_files` | 157.654 | 291.165 | 1.85× |
| `io/cc-write/many_files_flush_on_close` | 60.871 | 139.898 | 2.30× |
| `io/cc-write/subdir_small_reopen` | 21.274 | 59.233 | 2.78× |
| `io/cc-write/small_file_reopen` | 6.616 | 25.434 | 3.84× |
| `io/fatx16/write_read_multicluster` | 15.110 | 30.268 | 2.00× |
| `xc/rsa/modexp_even_modulus` | 0.092 | 14.276 | 154.42× |
| `mm/cache/truncate_purges_dirty` | 11.415 | 24.467 | 2.14× |

Largest repeatable decreases in test-body time:

| Leaf / workload | Complex ms | SpiritBoot ms | SB / Complex |
|---|---:|---:|---:|
| `mm/pressure/ramp_with_file_io` | 3933.577 | 446.608 | 0.11× |
| `mm/pressure/repin_after_release` | 1241.266 | 74.071 | 0.06× |
| `mm/vmcontract/statistics_track_commit` | 144.938 | 33.749 | 0.23× |
| `xc/privkey/the_value_is_one_word_wider` | 112.541 | 22.688 | 0.20× |
| `mm/contig/low_floor_probe` | 142.439 | 56.780 | 0.40× |
| `mm/pressure/commit_ramp_under_pin` | 95.498 | 25.192 | 0.26× |
| `io/mdl/buffered_1m` | 130.121 | 64.412 | 0.50× |
| `xc/privkey/decrypts_the_public_operation` | 60.335 | 12.686 | 0.21× |
| `xc/privkey/the_primes_are_not_interchangeable` | 56.366 | 10.795 | 0.19× |
| `xc/privkey/the_answer_carries_eight_zero_bytes` | 56.536 | 11.060 | 0.20× |

## Behavioral findings that a PASS banner misses

- `ex/timer/a_user_mode_apc_runs_on_expiry`: approximately 50 ms on Complex versus 500 ms on SpiritBoot. The fixture waits alertably for an event with a 500 ms timeout, schedules an APC at 50 ms, and checks APC count/context, but ignores the wait return status. The timing exposes a likely wait/APC semantic discrepancy; this campaign does not establish its root cause.
- Contiguous-memory relocation diagnostics report successful relocation on Complex and NULL on SpiritBoot for the VM-page/pool-page probes, while their broad assertions still pass. Therefore memory-test speed differences require semantic review before being claimed as optimizations.
- The four TODO failures cover out-of-space status, read-only volume flush, thread priority inheritance, and the process thread list. They are not hidden by the compatibility exclusions.

## Supplementary performance

Seven alternating pairs each, all completed with no reported correctness failures. These supplementary pairs have no discarded pair-0 warmup. Their original pilots were run separately. CSV timings are microseconds per workload iteration for kernel/synchronization cases and the explicitly named total/percentile for streaming.

| Leaf / workload | Complex ms | SpiritBoot ms | SB / Complex |
|---|---:|---:|---:|
| `phase0/completion_p50` | 0.043 | 0.056 | 1.30× |
| `phase0/completion_total` | 51.581 | 123.553 | 2.40× |
| `phase0/elapsed` | 85.000 | 156.000 | 1.84× |
| `phase0/submit_p50` | 0.009 | 0.024 | 2.67× |
| `phase0/submit_total` | 11.867 | 47.402 | 3.99× |
| `phase1/completion_p50` | 0.043 | 0.056 | 1.30× |
| `phase1/completion_total` | 49.859 | 122.098 | 2.45× |
| `phase1/elapsed` | 84.000 | 156.000 | 1.86× |
| `phase1/submit_p50` | 0.009 | 0.025 | 2.78× |
| `phase1/submit_total` | 11.254 | 47.559 | 4.23× |

Synthetic streaming is slower on SpiritBoot with both normal memory availability and 900 free pages. This is a 16 MiB synthetic file with 1,024 varied noncached reads per phase; it does not identify a game-specific cause or reproduce human driving.

| Leaf / workload | Complex ms | SpiritBoot ms | SB / Complex |
|---|---:|---:|---:|
| `des-cbc-4096` | 0.422 | 34.239 | 81.09× |
| `des3-cbc-4096` | 1.011 | 102.569 | 101.46× |
| `modexp-512-e1-odd` | 0.083 | 350.137 | 4220.40× |
| `pin-4096` | 0.046 | 2.205 | 47.70× |
| `sha-1MiB` | 23.796 | 64.281 | 2.70× |
| `sysva-4096` | 2.820 | 11.408 | 4.05× |

See [microbenchmarks.csv](microbenchmarks.csv) and [synchronization.csv](synchronization.csv) for every workload. Crypto and pinning gaps are substantial, despite the faster aggregate API suite. These are differences against Complex; no pre-save-fix SpiritBoot performance baseline was run, so they must not be attributed to the save fix as regressions.

The original 41-workload kernel fixture had Complex-incompatible assumptions: bounded SpiritBoot pool capacity, zero-filled raw SYSVA allocations, and SHA context-reset/opaque-byte requirements. Raw pilot failures are retained. The portable companion removes the pool-capacity case, writes/verifies SYSVA markers, and initializes SHA for every independent operation without asserting opaque state. Its 40 workloads pass on both BIOSes. It is not represented as an unchanged original-fixture pass.

## Disabled leaves

- `io/finfo/rename_dos_root`: Complex rejects the DOS-root rename contract asserted by this fixture
- `hal/av/guess_field`: Complex bugchecks on this fixture optional NULL result query
- `io/dismount/a_device_with_no_volume_still_succeeds`: Complex rejects the raw-device success contract asserted by this fixture
- `ke/exceptions/x87_divide_by_zero`: xemu TCG does not deliver the unmasked FP exception expected by this fixture
- `ke/exceptions/sse_divide_by_zero`: xemu TCG does not deliver the unmasked FP exception expected by this fixture

The FP skips reflect failures seen on both BIOSes in this xemu setup; this campaign alone does not independently establish the emulator as their root cause. The other three exclusions are exact fixture contracts Complex rejects or crashes on, not claims that Complex lacks the entire API.

## Reproduction and evidence

- BIOS: SpiritBoot candidate SHA256 `1ed234ebaf8e95937225c3002b6eac26257b0f3d1ff8f3d6a3aabd464955fb0b`, assembled source tree `04e3879e287135735111efdc8d25488d94a7793c`, DOA fix PR #239. Complex SHA256 `1de4c87effe40d44f95581d204f9fa0600fbd5fe2171692316dcf97af0f4113f`.
- xemu release SHA256 `14777b55740706608cdfde97349eefa3d5115ece4c889679c9c8b96641a85f2d`, source `f3c528eeec86db32c9f96a932267105e83f77375`, Vulkan, 64 MiB, interactive Windows PowerShell session, no debugger. Existing game sessions were paused.
- One emulator benchmark at a time; fresh HDD overlay and copied EEPROM from the same baseline for each run. BIOS order reverses each pair. Host file caches are not explicitly evicted; order alternation reduces but does not eliminate host-cache effects.
- `run-one.ps1`, `leaf-paired.ps1`, `paired.ps1` and fixture source archive reproduce the work. Build with nxdk and analyze with `python analyze.py` after exporting run logs under `results/`.
- The analyzer verifies expected BIOS/executable hashes, nonzero interactive session, local fixture SHA versus launch records, matching leaf/skip sets, completed runs, and duplicate leaf trial rejection. `artifact-identities.json` records fixture hashes. Counter ticks use each run's own reported frequency.
- A post-run audit of all 58 measured-campaign/pilot leaf and supplementary overlays confirms identical normalized TOML settings, the same backing path, and one EEPROM hash matching the source EEPROM. This audit records backing-file size/mtime, not a before/after hash of the entire backing chain; full immutable-chain attestation remains a limitation. See `input-audit.json`.
- `results.zip` preserves all serial, launch and result evidence, including the original Complex crash and incompatible-fixture pilots. `summary.json` records aggregate measurements. No proprietary BIOS or game image is included in the evidence archive.
- These results characterize this xemu Windows build, not physical Xbox performance. Additional correctness assertions and fixed-workload probes are needed before treating all apparent leaf speedups as valid optimizations.

The DOA save fix remains narrowly scoped to doubled FATX path separators. Human reload validation succeeded, and all PR #239 CI checks passed. The timing and semantic gaps above remain open follow-up work; this report does not claim to resolve them.
