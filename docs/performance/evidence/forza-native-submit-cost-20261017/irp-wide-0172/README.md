# 0172: exact full-packet IRP reset with x86 dword stores

Experimental candidate on selected 0168. This directory does not select firmware.
The private `build-lock.json` differs from `sources/firmware-lock.json` only by
appending `0172-irp-wide-full-reset.patch` and its SHA256. Its inherited
`assembled_source_tree` identifies the baseline, not a newly verified candidate
tree; the root build must record the candidate assembled tree and final binary.

## Exact change

The patch changes only compatible GPL `ntoskrnl/io/iomgr/irp.c`. It adds the
private `IopClearIrpPacket` helper and replaces the initializer's one clear call.
On GNU x86, a dword-aligned buffer is cleared by `REP STOSL` with the truncated
word count. The instruction advances the destination; `RtlZeroMemory` clears
exactly the remaining zero to three bytes. Unaligned destinations and other
compiler/architecture configurations retain a full byte-exact `RtlZeroMemory`
path. `PacketSize` remains `USHORT`; no allocation extent is rounded up.
The inline assembly declares both changed pointer/count operands and a memory
clobber. It uses the normal x86 C ABI's clear direction flag convention.

All initializer header, stack, APC and thread-list assignments remain unchanged.
`IoReuseIrp` is byte-for-byte unchanged, including cancellation/list preconditions,
retained allocation flags and requested status. Original GPL notices remain in
the source; generated extraction fixtures preserve those notices as well.

For the independently observed 416-byte parent plus 164-byte child, the aligned
wide path executes 104 + 41 = 145 dword bodies instead of 580 byte bodies. This is
an instruction-body count, not a latency or overall performance result. The
linked i386 image now passes the built-candidate gate below. Release A/B/A/B
measurements remain required for performance conclusions.

## Validation

`check_irp_reset.py` extends the existing preparatory oracle without changing it.
It compiles the exact candidate helper, initializer and reuse bodies with the
existing deliberately opaque host IRP model. The byte oracle compares the entire
66,048-byte backing arena, including both poison margins. Its 3,072 helper cases
cover every offset 64–127, lengths 0–31, the observed 164/416-byte sizes, boundaries
around 256/512, and 65,528–65,535. Public API calls use only naturally aligned,
sufficiently sized IRPs; the existing 2,568 full-reset/reuse observations remain.

Results:

- Baseline fails the candidate-helper requirement (`baseline-red.log`).
- Baseline also fails the independent i386 `REP STOSL` gate
  (`native-baseline-red.log`); candidate passes (`native-candidate-green.log`).
- Clang and GCC each pass all 3,072 helper plus 2,568 API observations under
  ASan/UBSan (`candidate-green.log`, `gcc-green.log`).
- The forced non-GNU helper branch passes the same cases
  (`portable-fallback.log`). It undefines the GNU compiler marker only after
  host headers have been parsed, leaving the candidate body unchanged.
- `truncate-tail` fails at offset 64, length 1: byte 64 remains poisoned.
  `overrun-tail` fails at offset 64, length 1: byte 65 is overwritten.
- The patch dry-runs cleanly against the selected 0168 source. The private lock
  has precisely one appended patch; unchanged API portions are checked against
  that source (`source-validation.json`).

Inline assembly is not instrumented by sanitizers. Its tested writes are checked
by the independent complete-arena oracle; ASan/UBSan additionally cover the C
fallback and surrounding harness. These tests do not establish native IRP layout,
real IRQL/concurrency behavior, firmware linkage, or hardware performance.
`check_native_shape.py` compiles extracted bodies with a freestanding model using
GCC i386 `-march=pentium -Os`; its `native-*/receipt.json` records exact commands
and hashes. This proves extracted helper instruction shape, not final firmware
shape. Root coordinated the firmware build; the exact built-source owned suites now
pass as recorded below.

## Exact release64 build validation

Root's release64 image has SHA256
`db5d906bb298892c31a8bb1c737ede4bb53f2ae0033ce52d89933f5522a03b5a`.
Independent validation uses its actual assembled source at
`artifacts/forza-irp-wide-release64/work-0hku4mqt/source` and sibling unstripped PE.

All five unchanged owned host gates pass: core, adapter (42 groups each plain and
ASan/UBSan), packet (10 groups each plain, ASan/UBSan and MemorySanitizer), owner
(9 groups each plain and ASan/UBSan), and sense (plain and ASan/UBSan). The exact
built helper also passes all 5,640 reset observations. `built-host-validation.json`
records commands, compiler versions, script/log hashes and successful exit codes;
`built-*.log` preserves outputs. These run ordinary compiler defaults from each
script: host checks use their existing `-O1`, native primitive checks their
existing `-O2`, and sense its default. This does not apply the 0171 compiler
wrapper or change root's `-Os` firmware configuration.

`check_built_candidate.py` compares assembled Git index metadata and verifies
there are no unstaged, untracked or ignored source files. Only
`ntoskrnl/io/iomgr/irp.c` differs from selected 0168; reversing the intended helper
insertion and reset-call replacement restores that whole file exactly. No extra
source-identity metadata changes were present. This comparison reads full-tree
index metadata, not prohibited implementation bodies.

The final PE's named GPL initializer has exactly one `REP STOSL` at `0x840150ca`
and one byte fallback/tail repeat at `0x840150e0`. The baseline initializer has
no dword repeat. The gate archives both named-function disassemblies and PE,
source-index, IRP and flash hashes in `built-source-linked-validation.json`.
This completes the earlier receipt's source, owned-suite and final-code gates;
it establishes no release timing improvement.

## Release decision

The completed fresh-process control/candidate/control/candidate trial rejected
0172 for selection. Every generated byte, callback, canary, and memory target
passed, but the primary result did not repeat: the first pair regressed both
450 microsecond rates, while the second pair improved them. More decisively,
the 900-page 250 microsecond rate regressed in both adjacent pairs by 4.72% and
4.62%. Averaging the two runs gives a 4.67% regression for that case.

The two-run average at 783 pages improved 450 microsecond throughput by 3.40%
and weighted submission cost by 5.70%, but the 900-page average changed by
-0.28% and -2.12% respectively. These small, mixed results do not qualify a
pure performance improvement. The selected firmware therefore remains at
0168; the verified source and linked-code evidence is retained for future CPU
or emulator-specific work.

```sh
python3 docs/performance/evidence/forza-native-submit-cost-20261017/irp-wide-0172/check_built_candidate.py \
  --baseline artifacts/forza-bookkeeping-release64/work-14lo4o24 \
  --candidate artifacts/forza-irp-wide-release64/work-0hku4mqt \
  --output docs/performance/evidence/forza-native-submit-cost-20261017/irp-wide-0172
```

## Reproduce

Run from the repository root, with `candidate_source` set to a source tree with
the patch applied. The prepared scratch candidate is outside the repository:
`<private-irp-workdir>/source`.

```sh
evidence=docs/performance/evidence/forza-native-submit-cost-20261017/irp-wide-0172
python3 "$evidence/check_irp_reset.py" --source-root "$candidate_source"
CC=gcc python3 "$evidence/check_irp_reset.py" --source-root "$candidate_source"
python3 "$evidence/check_irp_reset.py" --source-root "$candidate_source" --force-fallback
python3 "$evidence/check_irp_reset.py" --source-root "$candidate_source" --mutation truncate-tail
python3 "$evidence/check_irp_reset.py" --source-root "$candidate_source" --mutation overrun-tail
python3 "$evidence/check_native_shape.py" --source-root "$candidate_source" --output "$evidence/native-candidate"
```

Both mutation commands must exit 1. The baseline uses
`artifacts/forza-bookkeeping-release64/work-14lo4o24/source`; both candidate
requirement gates must exit 1 there. `approved-inputs.json` records the restricted
source provenance and input hashes. This work inspected no prohibited MS-PL
ClassPnP/Disk implementation or proprietary title/BIOS implementation. This
statement describes this task's inspected inputs, not a broader historical
unexposed-personnel or whole-firmware license certification.
