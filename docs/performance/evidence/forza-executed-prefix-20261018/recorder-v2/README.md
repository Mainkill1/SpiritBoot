# Bounded kernel-prefix recorder, version 2

This is a diagnostic repair, not a firmware change or a Forza performance fix.
The first recorder capture is rejected and preserved at
`../forza-prefix-capture-20261018/`. Its diagnostic binary/source remain frozen at
`../forza-prefix-recorder-20261018/`. `diagnose_v1.py` reproduces structural facts:
261,658 rows occupied 99.815% of the histogram, causing long linear probes; the
5,575 overflow reports cannot be full-histogram failures because 486 slots remained
free and v1 searched every slot. They came from descriptor and/or instruction
metadata allocation outside measured calls. The old counters cannot distinguish
those two sources or retrospectively explain its 954 invalid-prefix reports.
Its first 101 reads used warmup handle 0x2c0; only the next 111 used scene handle
0x42c. A first64 cap without a handle filter would have profiled warmup only.

## Admission and coverage

Version2 admits exactly the first up-to64 selected NtReadFile calls with public
handle0x42c, in addition to the existing pinned title caller/APC-context selector.
This handle is specific to the preserved baseline saved scene. Capture receipts
must independently prove all admitted entries fall inside the replay window.
At admission limit, further BEGIN events are skipped; admitted returns and all
existing lower/completion/callback observations continue. `admission_closed` means
only that64 BEGINs were admitted. It does not mean their callbacks have drained.
Qualification requires64 returns and64 successful selected callbacks, established
by the identity analyzer before quitting. A quiet open_api header alone is
insufficient. Unadmitted calls can continue in the game and appear as background
lower/completion/callback events.

Descriptors and decoded instruction PCs are allocated only for baseline owned
kernel text `[0x84001000,0x84055400)` and PAGE `[0x84069000,0x84069b08)`.
Every appended instruction PC is checked too; crossing a range fails closed.
INIT and title code are excluded. Every excluded TB still flushes the previous
prefix and installs an explicit excluded sentinel, attempted ordinal, REP counter
and runtime TB-entry PC. Excluded attempts are counted separately; they are never
mapped to owned symbols or treated as zero work. Its PC remains the TB-entry PC
when first>1, not the actual first instruction PC. Excluded blocks executing via
an owned-range CF_PCREL alias fail closed. Owned descriptors also retain v1's
runtime-PC-equals-descriptor-PC check. Unknown/exhausted descriptor0 is distinct
from intentional exclusion.

The file is schema version2. `prefix_meta`/`prefix_end` add excluded_rows.
`prefix_limits` records handle, max_api, admitted, returned, admission_closed and
range_count. `prefix_range` records the exact half-open ranges. `prefix_health`
records all allocated descriptors/instructions (including unused owned ones),
separate descriptor/instruction/owned-row/excluded-row exhaustion, and maximum
probe lengths. Both histograms stop after128 probes and report failure instead of
scanning an almost-full table. Counts are monotone and any failure rejects
attribution. `prefix_excluded` retains API, identity sequence, runtime entry PC,
first/last ordinal, executions, begun attempts and REP body iterations.

Invalid checks emit a per-reason count and at most two scalar samples per reason,
32 total. They count validation invocations; repeated checks can describe the same
bad state. Samples contain no code bytes or guest buffer contents. Reasons:

| Reason | Meaning |
|---|---|
| 1 | Invalid instruction append/id/REP marker |
| 2 | Noncontiguous descriptor instruction storage |
| 3 | Invalid finalized descriptor/count |
| 4 | Unknown owned descriptor |
| 5 | Progress/segment descriptor or type mismatch |
| 6 | Unfinished owned descriptor |
| 7 | Runtime entry PC differs from owned descriptor |
| 8 | Invalid attempted-ordinal frontier |
| 9 | REP body counter moved backwards |
| 10 | REP bodies changed in empty prefix |
| 11 | Invalid TB-entry descriptor/type |
| 12 | Unfinished descriptor at output |
| 13 | Excluded TB executing at owned runtime entry |
| 14 | Appended instruction outside owned ranges |
| 15 | Missing output path |
| 16 | Invalid excluded/owned type combination |

## Reproduction and limits

From this directory, `python3 ../verify_source.py /path/to/xemu` reconstructs
and verifies the exact three sources from public Git objects and the two archived
patches. `python3 run_tests.py /path/to/xemu` performs that reconstruction in a
temporary tree, exercises the actual identity/admission hook, core/glue tests
plain and under ASan/UBSan, and runs the three guard-removal mutations. It also
passes real recorder output through the independent archived parser. No private
staging directory or repository mutation is required.

`build-receipt.json` records the captured container build and executable identity.
A rebuilt emulator is a new diagnostic artifact; these source checks do not
claim bit-identical executable reproduction or native performance validation.

Enable `XEMU_SPIRIT_MENU_TRACE=1`, `XEMU_FORZA_IDENTITY=1`,
`XEMU_FORZA_PREFIX=1`, and distinct writable `XEMU_FORZA_IDENTITY_OUTPUT` and
`XEMU_FORZA_PREFIX_OUTPUT`. Restore the baseline add882 saved scene before replay.
Do not reset/loadvm during an admitted API: host recorder state is not restored
with guest state, and an exactly repeated thread/stack cannot be detected here.
Thread identity means cached execution context, updated after the baseline stack
switch at0x84001198 and verified against identity PCR reads. Same-thread DPCs and
interrupts remain included.

Begun counts include faulting attempts, not retired instructions. REP counts are
completed emitted string bodies, separate from attempts; a body exiting through a
fault or I/O debug exception before its counter is not counted as completed.
Translation records describe descriptor allocation attempts, not proof of installed
code/cache misses/invalidation. Instrumentation adds stores, C helper calls,
hashing and host page touches and can change queue state. Classify this capture
independently. Counts are not CPU cycles, exclusive request work or unperturbed
wall time. Missing footer, open admitted call, overflow, invalid-prefix, thread
mismatch or identity integrity error rejects the entire attribution.
