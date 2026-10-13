SpiritBoot release candidate hardening — 2026-10-13

The combined candidate fixes read-only flush and FATX file-size contracts,
retains the DOA save/performance fixes merged in PRs 239 and 241, and improves
SHA-1 compression. It is prepared for user gameplay testing, not published as
a release. The full comparison is not a claim that every operation got faster.

Firmware
  Release 64 MB SHA256:
  be180279642478d59bdd484abbaa3004d3efaf95a31194c838596341894c6827
  Assembled source tree: 694b0e2461558f6a5f7a774fd34c79bd7cdc111e
  Windows: C:\xemu-lab\incoming\release-qualification-20261013\final64.bin
  Release/debug 64/128 MB builds use the same assembled source tree.

What changed and why

NtFlushBuffersFile rejected read-only file and volume handles at a generic NT
access check before dispatching to the filesystem. Public calls on Complex
accept these handles. Xbox now dispatches the flush normally, retaining
filesystem errors and completion behavior. Generic NT retains its access gate.

FATX resize returned INVALID_PARAMETER for positive lengths at or above 4 GiB,
where Complex returns DISK_FULL. Negative lengths could instead reach low-word
size handling. FATX now rejects both before changing the chain: negative sizes
return INVALID_PARAMETER; unrepresentable positive sizes return DISK_FULL.
Rejected growth preserves EOF, data and free clusters. Generic FAT is unchanged.
The standalone native fixture passes 48/48 on Complex and the candidate; the
baseline fails six checks. Production resize/rollback tests cover both builds.
See ../storage-boundaries-2026-10-13.txt for the cause and reproduction details.

SHA compression uses bounded five-round groups, reducing loop conditions from
81 to 19 per block while preserving the circular schedule and public context.
The first candidate was rejected: seven native triplets showed a SHA gain but
40–55% higher DES costs. Owned-code assembly had unchanged DES instruction
counts, but the expanded inline SHA shifted frequent DES helper calls across
a 4 KiB page boundary. Keeping SHA compression out of line restores helper
locality. That explains a plausible mechanism; native measurements establish
performance. See ../../optimization/SHA_BOUNDED_ROUNDS.txt and the separate
../../optimization/final-layout-micro-review-2026-10-13.txt for the final
correctness, layout and timing evidence.

The earlier broad flush/overwrite slowdown did not reproduce in seven pairs.
The targeted fixture separates whole-leaf cost from individual operations and
checks status, size and bytes after every sample. Warm leaf ranges overlap;
a small flush-only timing trend remains recorded. No speculative write-path
change was made. See ../../optimization/write-performance-investigation-2026-10-13.txt.

Qualification and measured limits

The final gate validates 28 serial Windows user-session runs: three alternating
pairs for each of the frozen API, kernel microbenchmark, stream and sync ISOs;
30 focused timer checks; 48 focused storage checks; and the updated API ISO on
candidate and Complex. Exact BIOS/XISO/xemu hashes, TAP results, ordered samples,
checksums, configuration, run order and non-overlap are checked by the analyzer.

API: 639 planned, five fixed exclusions, 634 enabled. Candidate passes 632,
with two existing process/thread TODO failures; baseline passes 630; Complex
passes all 634 enabled checks. The two storage fixes are ordinary assertions
in the updated ISO. Timings use the unchanged original ISO and exclude all
four baseline TODOs from comparable work, preserving 630 comparable leaves.

Common API cost median: 12.42693 -> 12.39772 seconds (-0.24%); mean:
12.43379 -> 12.42869 seconds (-0.04%). Ranges overlap. Of 630 comparable leaves,
33 have lower observed ranges, 31 higher, and 566 overlapping. Every leaf and
all exclusions appear in performance-all-leaves.csv, including slower cases.
For example, subdirectory reopen is 3.9% higher and device-object dismount
42% higher (about 0.90 ms); these observations remain performance targets.
Three pairs do not establish a causal regression or statistical significance.

Across six alternating pairs in two cohorts, all six SHA workloads improve
in every pair. The 1 MiB median is about 23.4% lower. DES block/CBC medians still
trend about 2–6% higher, with overlapping ranges. The earlier 40–55% slowdown
is resolved; the candidate is not described as regression-free or uniformly
faster. The final full-suite stream elapsed medians are 156 -> 163 ms without
pressure and 150 -> 152 ms under pressure, with overlapping ranges. Sync costs
are broadly unchanged. All stream/sync correctness assertions pass. See the
complete workload CSV and final microbenchmark report for exact distributions.

Memory: permanent image RAM remains 14 pages (56 KiB). The extra mapped image
page is ROM backed. Warm-stage requirement is 178 of 505 pages; payload slot
free space is 75,276 bytes. ROM span CRCs, tables, loader identity and source
pins were independently checked. No RAM saving is claimed from alignment noise.

Local product tests: 134 run, three skipped, zero failures. Combined production
source host checks pass, including 13,410 SHA differential/oracle checks, FATX
resize/rollback, DES, cache, pins, timer, loader and other firmware checks.
All four firmware profiles build. The native analyzer has eight mutation tests
and an independent review; the archived evidence was successfully reanalyzed.
CI status is recorded on PR #242 rather than inferred from these local checks.

Remaining scope

Two pre-existing API failures remain: new-thread process priority inheritance
and the published process thread list. The five frozen comparison exclusions
remain unchanged; the two FP exceptions fail on both BIOS images in this lab,
which by itself does not prove an emulator root cause. Larger streaming/SYSVA
and the slower measured operations remain in issue #240, not silently closed.

Native measurements use one optimized xemu build on one Windows machine,
launched through interactive PowerShell with fresh HDD overlays and copied
EEPROMs. They are elapsed costs, not game FPS or physical-console guarantees.
The base HDD is identified by path/size/mtime, not a full content hash. xemu
rewrites TOML on exit; normalized values are checked and pre/post raw hashes
are retained separately. The user's final gameplay/save/reset check is still
required before publication.

Reproduce

Extract evidence.zip and run:
  python3 analyze-release.py --inputs qualification-inputs.json --output reanalysis
  python3 test-analyze-release.py

The archive includes the tested own firmware, build manifests, open fixtures
and sources, Windows runners, raw receipts and source check logs. It includes
75 total campaign receipts, of which 28 constitute the final gate; rejected
SHA and diagnostic campaigns are preserved separately. The first two storage
receipts (without v3 in their names) used a file-information query unsupported
by Complex: their apparent EOF failures are fixture errors, not BIOS defects.
No proprietary BIOS or game image is distributed in the archive.
