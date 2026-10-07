# Task 1 implementation report

Status: IMPLEMENTED, ready for independent controller review. All seven bounded
families are present. Host verification passes on the public baseline and
candidate. Kernel builds, candidate guest regressions, paired timings and the
64-page crossover decision remain controller-owned acceptance steps; no timing,
throughput or gameplay improvement is claimed here. No NEEDS_CONTEXT blocker
was found. Only the allowed public source, public nxdk, brief and candidate list
were used. No Docker or emulator call was made by this implementer.

## Commits and changed files

- `e0c02d14309b91f71fe15ea1022bb4e414a58864`: bounded production changes,
  actual-source host fixtures and public performance guest.
- `5644b070e0ca11d3f0e27273f071d5e2cdb07fec`: correct guest pool-size assertion
  to public `ExQueryPoolBlockSize`, following controller baseline smoke evidence.
- `a7316cbde30d60fe184a7d077c14015005e12c4d`: explicit rejected pin prefix
  32/64/65/128 crossovers and unaligned endpoints.
- `87aba89a6ba9b2a58f2edd6e52d5e3aa1e8649d7`: correct host SHA alias storage
  bounds for context offsets 1–3; final full differential rerun passes.

Final source/test HEAD is `87aba89a6ba9b2a58f2edd6e52d5e3aa1e8649d7`, tree
`f7adb302a762ed1945cc07d9c2ff428c643ba959`; `git status --short` is empty.

Production: `ntoskrnl/xb/crypto.c`, `ntoskrnl/xb/mm/api.c`, `mm.h`,
`pagesupply.c`, `poolpages.c`, `sysva.c`, `ntoskrnl/xb/obcreate.c`.
Tests: `tests/host/kernel-performance/{README.md,check.py,pins.c,pins.py}`,
`tests/xbe/kernel-performance/{Makefile,README.md,main.c}`. Only source/tests are
committed; controller-generated ISO/XBE/object files remain ignored. Working
branch is `perf/kernel-call-optimization`; starting public commit is
`291ad9759f7993cb1f96d73bfa1c6f333c2bef34`. No prior patch or BIOS was edited.

## Commands and verification

Commands run from `/workspace/SpiritBoot-optimization-kernel` unless absolute:

```sh
mkdir -p /tmp/spiritboot-opt-baseline
git archive 291ad9759f7993cb1f96d73bfa1c6f333c2bef34 ntoskrnl/xb tests/host sdk/include sdk/lib/cryptlib hal/halx86 | tar -x -C /tmp/spiritboot-opt-baseline
tests/host/clean-room/run.sh /tmp/kernel-old-suite-candidate > /tmp/kernel-old-suite-candidate.log
/tmp/spiritboot-opt-baseline/tests/host/clean-room/run.sh /tmp/kernel-old-suite-baseline > /tmp/kernel-old-suite-baseline.log
tests/host/clean-room/run.sh /tmp/kernel-old-suite-final > /tmp/kernel-old-suite-final.log 2>/tmp/kernel-old-suite-final.err
python3 tests/host/kernel-performance/check.py . /tmp/kernel-perf-report-final --optimized --compare /tmp/spiritboot-opt-baseline > /tmp/kernel-perf-report-final.log
python3 tests/host/kernel-performance/pins.py . /tmp/kernel-pin-final-complete --optimized > /tmp/kernel-pin-final-complete.log
python3 tests/host/kernel-performance/pins.py . /tmp/kernel-pin-final-complete-checked --optimized --diagnostics > /tmp/kernel-pin-final-complete-checked.log
python3 tests/host/kernel-performance/pins.py /tmp/spiritboot-opt-baseline /tmp/kernel-pin-final-complete-baseline > /tmp/kernel-pin-final-complete-baseline.log
gcc -std=c11 -fsyntax-only -D'__declspec(x)=extern' -I/workspace/SpiritBoot-public-nxdk/lib -Wall -Wextra -Wno-multichar -Wno-attributes -Wno-unknown-pragmas tests/xbe/kernel-performance/main.c
git diff --check
```

The archive is 42 MiB, avoiding a full clone. Existing clean-room suite:
88/88 assertions per source root (persistence 18, shutdown 9, IDE 24, HAL 24,
pins 13). Its existing host HAL noreturn warnings occur in both versions;
there are no failing checks. Full optimization fixture: 30,978/30,978
assertions across both source roots, including optimized work assertions and
complete SHA/DES caller-state differential. Pin fixture: baseline 204/204
assertions; candidate 7,307,629/7,307,629 assertions in release-style and opt-in
diagnostic modes. Millions of pin assertions are individual scratch-slot
checks, not millions of independent workload scenarios. GCC public-header
syntax-only check and whitespace check pass; syntax-only is not an nxdk
compile/link claim.

Source extraction compiler commands are constructed reproducibly by fixtures:
`cc -std=c11 -O2 -g -shared -fPIC -DSARCH_XBOX -Wall -Wextra -Wno-multichar
-Wno-unused-function generated.c -o generated.so` for scan/registry/crypto;
`cc -std=c11 -O2 -Wall -Wextra` with existing clean-room include directories
for pins. Diagnostic pin run additionally uses `-DDBG=1
-DNXK_PIN_BATCH_DIAGNOSTICS`. Counters are injected only into exact extracted
production operations, never into shipping code. The pool subject is its
exact search region plus named `NxppTestRange`; remaining subjects are named
functions or supply/API regions. Allocator oracles enumerate first-fit order;
`pow`, `hashlib.sha1`, FIPS DES and public 3DES known answers are independent
crypto oracles. No optimized algorithm is duplicated as the subject.

Initial red evidence: baseline `--optimized` runs exit 1 at pool 4096-read
expectation and zero-on-pin-exit expectation. Reproduced logs are
`/tmp/kernel-pool-red.log` and `/tmp/kernel-pin-red.log`. Recorded baseline
work independently fails optimized expectations for system PDE reads,
registry allocation count, final ModExp square, SHA load bytes and DES bit
iterations as shown in the next table. Earlier Python fixture issues (signed
ctypes result and oversized integer diagnostic formatting) were corrected
before oracle runs passed; these were fixture defects, not production fixes.

Scenario coverage per root includes 432 pool searches (dense, alternating,
periodic blockers, empty and seeded mixed bitmaps; rotating hints including
wrap/cross-hint; Counts 0/1/2/4/16/256/1024/4096/4097), 40 system searches
(absent/present/mixed PDEs and page-boundary holes; Pages
0/1/16/1024/1025/4096/16384/16385), registry 1/8/64 types with lazy OOM and
same/different-type allocation reentrancy, and 819 ModExp calls with Words
0/1/2/32/64/512/513, odd/even/zero/modulus-one, exponent zero, bounded
Words-512 exponents, full-width highbit/dense Words 1/2/32, random full-width
operands, all output/input aliases and OOM. SHA covers 2304 remainder/length/
offset streams, seeded random splits, count carry and caller input/digest
aliases. DES covers 512 packed-value/box cases, all sixteen round outputs,
independent vectors and 1728 CBC cipher/op/length/offset/in-place cases.
Pin profiles cover all requested sizes 0/1/2/16/32/64/65/128/256/4096, aliases,
first/middle/last invalid pages, explicit rejected-prefix crossovers,
increment-then-reject underflow, invalid PFN, overflow address, nested counts,
sticky overflow and pending return.

## Measured actual-source work

Raw arrays and full caller-state hashes are retained in
`/tmp/kernel-perf-report-final/work.json`; slot meanings are documented in the host
README. Pin raw profiles are in the three final pin logs above. These are
operation counts, not timings.

| Workload/operation | Baseline | Candidate |
|---|---:|---:|
| One-page successful pin scratch bytes | 65536 | 2 |
| 64-page successful pin scratch bytes | 65536 | 128 |
| 65/4096-page successful pin scratch bytes | 65536 | 65536 |
| Rejected translated prefix 32: translations / clear bytes | 32 / 65536 | 64 / 64 |
| Rejected translated prefix 64: translations / clear bytes | 64 / 65536 | 128 / 128 |
| Rejected translated prefix 65: translations / clear bytes | 65 / 65536 | 65 / 65536 |
| Pool 256-page periodic-blocker search: reads / probes | 493696 / 3841 | 4096 / 16 |
| All-absent system 4096-page search: PDE reads | 4096 | 4 |
| Cold 64-type registry: comparisons / allocations | 2016 / 64 | 2016 / 64 |
| Known 64-type repeats: comparisons / allocs / frees | 2080 / 64 / 64 | 2080 / 0 / 0 |
| Odd W1 E3 ModExp: multiplies / squares / copy bytes | 6 / 2 / 28 | 5 / 1 / 24 |
| Odd W1 E3: 64-bit products / factor products | 12 / 6 | 10 / 5 |
| Even W1 E3: multiplies / squares / copy bytes | 4 / 2 / 20 | 3 / 1 / 16 |
| Even W1 E3: products / reduction steps | 4 / 288 | 3 / 224 |
| SHA Update r0 Len1: load bytes / compressions | 92 / 0 | 28 / 0 |
| SHA Update r63 Len1: load bytes / compressions | 92 / 1 | 91 / 1 |
| DES decode bit iterations / six-bit groups | 768 / 128 | 0 / 128 |
| 3DES decode bit iterations / six-bit groups | 2304 / 384 | 0 / 384 |

Both alias and non-alias pin profiles show the same bounded cleanup modes.
Large rejected prefixes perform one bulk reset with no cleanup translations.
Known registry repetitions with 1 and 8 types likewise remove 1 and 8
allocation/free pairs respectively. Full caller-state differential hashes
match: SHA `9a3f0942140c8f0d4ac5cab9f252a7008c1d2dad6b822233d9cc06cdf04383e3`;
DES/CBC `35cf3acd82ec8ad4f1517296f1c71e8105e8071798d9db26de15d24b44c50bd0`.

## Preservation proof and self-review

1. Supply initialization zeroes pins and multiplicity scratch. The only batch
   producer is `MmLockUnlockBufferPages`; it retains the PFN lock across all
   translations, preflight, mutation and cleanup. Translated-prefix count is
   incremented before `RecordPin`, so increment-then-reject is included. Small
   success clears after complete preflight in the existing apply walk; small
   failures translate at most 64 known-valid VAs again, with range-checked PFN
   clears. Larger prefixes clear once at exit. Early Size-zero/overflow exits
   never touched scratch. Scratch zero induction is checked across every API
   exit; count/overflow/pending-return implementation is unchanged. Optional
   full diagnostic scans are excluded from ordinary checked and release hot
   paths. The 64-page budget is explicitly provisional.
2. Pool range conflict i makes every intervening candidate cover that same
   bit, so advancing to i+1 cannot discard an admissible earlier run. Both
   original rotating/wrap boundaries, including wrapped candidates extending
   past the hint, and original bounds/Count-zero behavior remain. Mapping,
   owner recording, statistics, PFN operations and unwind code are untouched.
3. System search skips only the remaining span of an observed absent PDE,
   clipped to the aperture, while retaining RunStart and continuity. Present
   PDEs still perform volatile PTE reads. Pages-zero still returns zero.
   Existing lock, backing zeroing, owner operations, rollback and CR3 behavior
   are unchanged.
4. Registry entries retain distinct allocated nodes forever. Its 32-bit
   address space cannot contain 2^32 such nodes, proving count cannot wrap.
   A local count snapshot under the first lock proves unchanged-count unknown
   remains unknown under the second; changed count performs the original full
   duplicate recheck. Allocation/free remain outside the spinlock. Lazy list
   initialization occurs only after successful allocation, preserving silent
   first-registration OOM. Same/different-type reentrant allocation is tested.
5. After the final accumulator multiply, no later exponent bit consumes Val.
   Odd result conversion overwrites Val with one and consumes Acc; even result
   consumes Acc alone. Tmp/Scratch final square contents are unused. Setup,
   allocation failures, output stores, exponent-zero/modulus edge semantics
   and public dispatch are unchanged; no FPU/SSE path is introduced.
6. SHA Update begins with the live prefix and fills every remaining byte
   before a full transform. Final padding fills each block including length,
   then zeros all 64 bytes before the unchanged full store. Partial Update
   store preserves inactive caller tail and reserved bytes. Whole contexts,
   count carry and supported overlapping caller buffers match baseline.
7. Each masked input bit b contributes exactly output bit 5-b. Exhaustive
   six-bit values at every packed box/round prove equivalence. Fixed shifts
   introduce no secret-indexed table/cache. Mutable/unaligned table reads,
   cipher/op policies and CBC feedback/tails remain unchanged.

Self-review inspected the full seven-file production diff, source call sites,
fixture instrumentation and guest cleanup. No exported ordinal, calling
convention, public structure/vector, security check, hardware ownership,
warm-reset/shutdown/IRP behavior or mapping policy is changed. Existing API
guest coverage remains necessary for backing/rollback, object lifecycle and
RSA/public mutable-vector/alignment behavior; those guest runs are not claimed
by host mocks.

## Guest handoff and remaining concerns

Public-only guest Makefile matches the existing nxdk pattern. Driver usage is
documented in `tests/xbe/kernel-performance/README.md`: build once, freeze
ISO hash, call `tools/run-xemu --flash VARIANT --dvd IMMUTABLE_ISO --mem 128
--serial file:RAW_LOG` through the controller's direct environment. It emits
TAP 42, `PERF-META` clock/frequency, fixed workload/sample/iteration records,
correctness flags and semantic checksums, followed by `PERF-SUMMARY` and the
terminal `== kernel-performance end PASS|FAIL ==`. Each record is:

```text
# PERF workload=<stable-id> sample=<zero-based> iterations=<count> ticks=<uint64> correct=<0|1> checksum=<8hex>
```

Raw monotonic public performance-counter differences include measured
empty-loop overhead without subtraction. Workloads cover all seven families,
pin rejection prefixes 0/32/64/65 against a verified uncommitted guard,
bounded failed fragmented pool search, system sizes across PDE boundaries,
cold/warm custom types, ModExp sizes through 512, SHA through 1 MiB, and
DES/3DES block/CBC. Three samples per workload are retained except the single
genuinely cold 64-type registration. Checksums exclude VAs, PFNs and uptime.
Setup/cleanup is outside timing; backing zero checks and crypto round-trip
validation within workload intervals are documented. Search-only savings may
be hidden by unchanged backing/zeroing/cryptographic work.

Controller reported its first pinned-nxdk compilation succeeded and its
baseline smoke reached TAP 42 in 6.753 seconds with 38 pass / 4 fail. The four
ordinary pool cases used an incorrect fixture assertion:
`MmQueryAllocationSize` only reports contiguous/restored allocation size.
Public nxdk and existing `mm/bigpool.c` establish `ExQueryPoolBlockSize` as
the pool query. Commit `5644b070` makes that single fixture correction;
the earlier failed smoke must remain retained at controller artifact
`artifacts/optimization/benchmark-smoke-baseline/serial.log`. No kernel
behavior was changed in response. Rebuild/recheck results belong the
controller's acceptance record, not this implementer's executed tests.

Remaining acceptance work: independent review; sequential kernel build;
existing API guest (including public vector/RSA/alignment regression); candidate
benchmark smoke; at least seven paired alternating-order trials using one
immutable ISO; retention of every sample; median/min/max and paired difference
analysis. Claim a timing gain only outside observed variation with consistent
sign in at least six of seven pairs. Small rejected pins add up to 64 cleanup
translations, unknown registry misses add a second lock interval, and existing
backing costs can hide scan savings. The controller must validate/reconsider
the illustrative 64-page budget on those timings. No universal speedup or
complete runtime correctness certification is asserted by this report.

Final self-review correction: overlapping SHA input aliases at context offsets
1–3 require up to 135 readable bytes (offset + 68 + length 64). The host fixture
now allocates 136 rather than 132 bytes for those cases. Final full differential
rerun passes 30,978 assertions with the updated SHA hash above. This corrects
host fixture bounds and changes no production or guest source.

Controller subsequent evidence: corrected pinned-nxdk guest rebuild and baseline
smoke pass TAP 42/42, 41 workloads, zero failures, and clean emulator exit.
Retained output: `artifacts/optimization/benchmark-smoke-baseline-v2`. Both
controller nxdk builds report only the existing lld `.edata` merge warning.
The first failed smoke remains preserved. These controller results are reported
as controller evidence, not implementer-executed emulator commands.
