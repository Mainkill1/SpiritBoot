# Native packet preparation hot-path report

Date: 2026-10-16

## Result

Patch `0150-native-packet-prepare-hotpath.patch` is ready after patch 0149. It
changes only SpiritBoot's independently authored packet primitive and owned
host tests. The initial draft was rejected: its default CDB arm copied 16 bytes
for zero-length RELEASE_QUEUE, and its `uint32_t` host page expressions wrapped
at `ByteOffset=4095, ByteCount=UINT32_MAX`. The final regression fails that
superseded draft in both places and passes the corrected patch.

The final release-only Steam Deck A/B/B/A profile made exactly 1,024 calls to
`nx_packet_prepare` in every arm. Candidate results were identical across both
runs: 247,808 weighted guest instructions versus 371,712 baseline (-33.33%) and
44,032 TB executions versus 63,488 (-30.65%). Diagnostic function-attributed
CPU averaged 42.065 ms versus 53.363 ms (-21.17%). Every run completed one
marker window with zero clock errors, reached the final TAP success after all
16 guest passes, exited normally, and deleted its private HDD.

Whole-phase wall and CPU measurements varied with host load (+7.76% and +8.08%
in this sequence), while callback counts were within 0.03%. They are not used as
patch performance claims. Exact per-function translated instruction counts were
stable in both orders and isolate the changed range.

## What changed

The page proof now uses `uintptr_t`. It covers the full host-visible admitted
range without wrap and remains native 32-bit arithmetic on i386. The exact i386
page region falls from 28 to 14 executed instructions with no divide or helper.

CDB transfer uses fixed-size GNU `aligned(1), may_alias` word operations. An
explicit zero arm performs no source access, 16 has its own exact copy arm, and
the defensive default performs no access. MemorySanitizer poisons the entire
zero-length source and each 6/10/12 suffix. The common READ10/WRITE10 path is
kept first because release disassembly showed a balanced switch would put three
length comparisons ahead of it. It remains 11 executed instructions versus
about 86 for the former byte loop.

SRB and next-stack clearing directly emits `rep stosl` after compile-time proofs
that both native object sizes are word multiples and both alignments are at
least four. Arbitrary sense storage retains the byte-safe helper. Baseline had
three generic clear calls on each request; the candidate has two total calls.

Safety arms increase the full function from 884 to 924 bytes (+4.52%), 269 to
287 static instructions, and 45 to 50 static branch instructions. These are
uncommon-path costs. The measured common route removes two calls and one third
of dynamic translated instructions.

## Correctness evidence

From exact assembled post-tree `63ce2832cea9bf6fe9fd7b93bc42a7c4d5a59674`:

- packet: 10/10 plain, 10/10 ASan/UBSan, and 10/10 MSan under clang;
- the same runner with `CC=gcc`: 10/10 plain and sanitized, plus 10/10 MSan via
  independently discovered clang;
- native adapter: 28/28 plain and 28/28 sanitized;
- request core: 50/50 plus 8/8 pthread scenarios;
- owner/cache/geometry suites: 13, 20, 16, and 34 groups passed;
- release64 firmware built successfully;
- patch applies with `git apply --check --whitespace=error-all` to the exact
  through-0149 source.

An interleaved 31-pair host benchmark pinned to one CPU, with two million
preparations per sample, measured medians of 22.196 ns before and 18.497 ns
after (-16.66%). Median absolute deviations were 0.147 ns and 0.088 ns. This is
supporting host evidence; the Deck guest instruction census is target-specific.

## Exact integration identity

Baseline through patch 0149:

- source tree: `a8f3fc46e27bc8e0f51f23708a02a73237565b2e`
- BIOS SHA-256: `07c52600c710adb5a7ca7748904603a13174e261ce2ce24923dafb0df4b2277a`

Applying only final patch 0150:

- source tree: `63ce2832cea9bf6fe9fd7b93bc42a7c4d5a59674`
- release64 BIOS SHA-256: `c0eaf3a73f75c7a57865a62a3df47cbece1d1c5a3d43b19ed1fd2d0bef08e4ec`
- patch SHA-256: `f2c9ecaa623e27d42c070f6c86d57a726917b9800a20741be8e5fc1cfa928b2d`

Later patches can change the combined tree and BIOS identities. Keep this
artifact ordered as 0150 and rerun final release qualification after combining.

## Measurement limits

Weighted instructions count translated block instructions, not TCG helper cost
or xemu storage-worker CPU. Entry hits use per-arm function maps from each
unstripped kernel. LTO-inlined functions cannot be separately attributed.

UART output concatenated some CASE/END records. Marker-window integrity,
function hits, final TAP success, runner exit, input hashes, and cleanup all
qualified. General 16-pass serial timing is therefore not claimed.
