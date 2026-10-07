# Task 1 independent specification and code-quality review

Reviewed candidate `87aba89a6ba9b2a58f2edd6e52d5e3aa1e8649d7` against public starting commit `291ad9759f7993cb1f96d73bfa1c6f333c2bef34`. The review package is the full starting-commit-to-candidate diff, including all four implementation/fixture commits; this is not an incremental `HEAD~1` review.

**Specification verdict: PASS for the Task 1 implementation and fixture handoff.** All seven active production families are implemented, and the preservation arguments are supported by the actual source. Controller-owned candidate builds, guest regressions, matched timings and final qualification remain outstanding Task 3 work.

**Code-quality verdict: PASS WITH ONE MINOR FINDING.** No Critical or Important finding; one nonblocking host-fixture assertion weakness. No production correctness defect found.

## Scope and evidence

Read the Task 1 brief, final implementation report and entire supplied review diff, then inspected the seven changed production files, their directly relevant callers/core routines, all new host/guest fixtures and public nxdk declarations. Candidate HEAD matches the reviewed commit and its working tree is clean. The diff contains exactly the seven production files and seven source/test/documentation files listed in the report. No export definition, ordinal map, public ABI layout, prior patch or BIOS file is in that diff.

Only the allowed public candidate, public nxdk, coordination material and the report's retained host/controller evidence were accessed. No access to `/workspace/SpiritBoot`, community firmware, private/reference/reverse-engineering inputs, Docker, emulator or subagents. No previously passing check was rerun. The only write in this review is this report.

Inspected retained evidence:

- `/tmp/kernel-old-suite-baseline.log` and `/tmp/kernel-old-suite-final.log`: the existing 88 assertions pass in both roots (18 persistence, 9 shutdown, 24 IDE, 24 HAL, 13 pins).
- `/tmp/kernel-perf-report-final.log`: 30,978/30,978; `/tmp/kernel-perf-report-final/work.json` contains both roots' counter arrays and matching complete SHA/DES differential hashes.
- `/tmp/kernel-pin-final-complete-baseline.log`: 204/204; candidate release-style and opt-in diagnostic logs: 7,307,629/7,307,629 each. The report correctly identifies the millions of scratch-slot assertions as such, not independent workloads.
- `/tmp/kernel-pool-red.log` and `/tmp/kernel-pin-red.log`: baseline fails the new bounded-pool-work and zero-scratch-on-exit assertions. These are meaningful red assertions for the intended structural/invariant changes.
- Controller `artifacts/optimization/benchmark-smoke-baseline-v2/serial.log`: corrected baseline smoke reaches TAP 42/42, 41 workloads, 121 raw samples, zero failures and terminal PASS. Its maximum recorded measured interval is 1,617,827 ticks, below the 24-bit timer's 16,777,216-tick wrap. This is baseline controller evidence, not candidate qualification or a performance comparison.

## Findings

### Critical

None.

### Important

None.

### Minor M1 — assert all affected pin counts in larger nonalias profiles

References: `tests/host/kernel-performance/pins.c:50`, `:54`, `:57`, `:66`, `:75`, and `:85` in the public candidate.

The profile loops exercise larger nonalias mappings, but most success/nested/unlock/rejection state assertions inspect only `NxpPins[16]`. `clean()` at line 39 verifies every scratch slot, not every pin count. A regression that preserves the first PFN while incorrectly skipping or changing a later PFN could pass those particular profiles. The existing clean-room fixture checks a second PFN in its smaller alias scenario, and the reviewed production control flow still demonstrates all-or-nothing preflight; therefore this does not block the current implementation.

Concrete improvement: for nonalias profiles, assert the expected count for every PFN `16 .. 16+n-1` after each successful/nested/unlock call, and verify the complete pin array remains unchanged on rejection. Preserve the separate scratch and work-counter assertions. This would directly substantiate the large-profile state claim instead of extrapolating from the first PFN.

## Production preservation assessment

### 1. Hybrid pin scratch reset

References: `ntoskrnl/xb/mm/api.c:76`, `ntoskrnl/xb/mm/pagesupply.c:158`, `:259`, `:271`, `:293`, `:298`, `:314`, and `ntoskrnl/xb/mm/mm.h:218`.

Initialization zeroes both pin counts and multiplicity scratch at pagesupply.c:167. Searches of the public MM sources confirm `MmLockUnlockBufferPages` is the only scratch-producing batch caller; the other new helper is the bounded reset. The API retains the PFN lock through translation, complete preflight, mutation and cleanup. Size-zero and address-overflow exits precede any scratch write. Translated count increments before `RecordPin`, covering its increment-then-reject underflow case. Invalid PFNs never reach scratch indexing in `RecordPin`, and cleanup independently range-checks them.

Small success clears in the existing apply translation walk after complete preflight; duplicate aliases can clear the same slot repeatedly because mutation no longer consumes multiplicity scratch. Small rejection retranslates exactly the already translated prefix, at most 64 entries. Larger translated prefixes clear once at exit and add no cleanup translations. There is no entry bulk clear and no double bulk reset. The initial-zero/exit-zero induction holds across these paths. Sticky overflow, pending returns, supply ownership and pin mutation routines themselves are unchanged. Diagnostic scans are limited to `DBG && NXK_PIN_BATCH_DIAGNOSTICS`. The added small-failure translations and provisional threshold are documented and measured as work, without claiming a timing optimum.

Counter evidence agrees: one-page success clears 65,536 -> 2 bytes; 64 pages -> 128; 65 and 4096 retain one 65,536-byte reset. Prefix 32/64 rejection doubles translations to 64/128 while clearing 64/128 bytes. Prefix 65/128 retains 65/128 translations and one bulk reset. Alias profiles agree.

### 2. Rotating pool first-fit

References: `ntoskrnl/xb/mm/poolpages.c:114`, `:171`.

On first conflict at bit i, every candidate start between the current start and i still includes i; advancing to i+1 cannot skip an earlier admissible run. The two original search boundaries are preserved, including wrapped starts below the hint whose runs extend beyond it. Count-zero search behavior is unchanged, and the helper's uninitialized Next on success is never consumed because that branch breaks. Bitmap locking, bounds, mapping, owner recording, statistics and backing rollback outside the search remain unchanged. The independent oracle enumerates the baseline rotating candidate order, not the optimized skip algorithm.

Periodic-blocker Count 256 evidence: 493,696 -> 4,096 reads and 3,841 -> 16 probes. This is search work only.

### 3. Absent-PDE system-VA search

References: `ntoskrnl/xb/mm/sysva.c:63`, `:124`, `:194`.

The skip occurs only after the existing volatile absent-PDE read. Span is clipped to the current PDE and aperture, RunStart survives adjoining free spans and present-PDE free runs, and Pages-zero retains no-hole behavior. Present PDEs still require the original volatile exact-zero PTE reads. Run cannot overflow in the existing 16,384-page aperture. Allocation/free retain NxSysVaLock serialization; no mutable occupancy cache is introduced. Backing, zeroing, owner/supply operations, unwind and CR3 behavior are untouched.

All-absent Count 4096 evidence: 4,096 -> 4 PDE reads, with the same earliest VA. Independent mixed-boundary oracles cover continuity and exact results.

### 4. Monotonic known-type registry

References: `ntoskrnl/xb/obcreate.c:52`, `:60`, `:137`.

Every count increment corresponds to insertion of a distinct retained `XB_TITLE_TYPE` node. Source search finds no removal, reset or decrement of the production registry. The Xbox's 32-bit address space cannot contain enough simultaneously retained nodes to reach either signed-LONG overflow or ULONG wrap (each node contains a LIST_ENTRY and pointer). The unchanged count under the second lock therefore proves no insertion occurred between lock intervals. If the count changed, the full duplicate scan runs before insertion. The snapshot is local, not an unchecked cache of mutable state.

Known types return before pool allocation. Unknown allocation remains outside the spinlock, as does redundant-node free. The list is lazily initialized only after a successful allocation, preserving silent initial OOM. Controlled allocation reentrancy tests cover both same-type redundancy and different-type insertion; the allocation shim asserts no pool allocation under the registry lock. The preliminary registry lock adds a bounded cold-miss cost, correctly left to runtime assessment.

Evidence: cold 64 types remain 2,016 comparisons / 64 allocations; known repeats preserve 2,080 comparisons while removing 64 allocations and 64 frees.

### 5. Final ModExp square/copy liveness

References: `ntoskrnl/xb/crypto.c:343`, `:412`, `:434`.

Only the square/copy after the last exponent bit is omitted. Acc has already incorporated that bit, and no subsequent bit consumes Val. Odd conversion overwrites Val with one and overwrites Tmp with the final Montgomery multiplication; even output reads Acc alone. Scratch contents after the skipped final square are not observed. Setup, conversion, output timing/aliases, allocations/frees, Words bounds, modulus rejection and exponent-zero behavior are unchanged. ExpBits is bounded by 512*32, so i+1 is safe. No FPU/SSE path or secret-indexed cache is added.

Independent Python pow cases and output aliases are appropriate. Odd W1 E3 work changes 6 -> 5 multiplies, 2 -> 1 squares, 28 -> 24 copy bytes; even changes 4 -> 3, 2 -> 1, 20 -> 16. The report explicitly bounds large-word exponent coverage rather than claiming exhaustive arithmetic verification.

### 6. SHA local tail initialization and caller state

References: `ntoskrnl/xb/crypto.c:41`, `:56`, `:122`, `:134`; actual core `sdk/lib/cryptlib/sha1.c:148`, `:191`.

Load initializes state/count and exactly the Count[1]&63 live prefix. Partial Update initializes any bytes included in its partial store. Before a transform, Update copies all remaining bytes in that block; the core's in-place word schedule therefore reads a fully initialized buffer. Final appends padding and length through Update, making complete initialized blocks, then zeroes all 64 local buffer bytes and resets state/count before the unchanged whole-buffer store. No local inactive tail is read or copied out before initialization. Reserved bytes and inactive caller bytes retain the original partial-store semantics.

Caller Data remains in caller storage while the core operates on a separate local context; reducing local tail copies does not change caller input/context overlaps. Final digest/context overlaps retain the existing digest-write then context-store order. Independent hashlib digests, all remainders, splits, offsets, carry, full caller-state differential hashes and corrected 136-byte alias backing are relevant evidence. The final fixture's maximum alias reach of offset+68+64 fits that allocation.

Load evidence: r0/Len1 92 -> 28 bytes; r63/Len1 92 -> 91, with unchanged compression counts and full-state differential hashes.

### 7. DES six-bit reversal

Reference: `ntoskrnl/xb/crypto.c:910`.

Each low input bit b is placed at output bit 5-b by fixed masks/shifts; all other bits are excluded. The packing/table loads are unchanged bytewise operations, including wrap positions and unaligned/mutable tables. The exhaustive fixture independently constructs packed slots and compares all 64 values across eight boxes and sixteen rounds. FIPS DES and published three-key EDE answers provide an independent crypto oracle; CBC tail/feedback/in-place behavior is separately compared to baseline. No new secret-indexed table or cache. Work evidence removes 768/2,304 per-bit iterations for DES/3DES while preserving decoded-group counts.

## Fixture and guest assessment

Host subjects are the exact production functions/regions with host-only operation instrumentation, not copied optimized algorithms. Pool/system models independently enumerate first-fit occupancy; ModExp uses Python pow; SHA uses hashlib; DES/3DES uses published vectors and independently encoded reversal expectations. Synthetic SHA alias/carry and mutable CBC full-state differential comparisons appropriately preserve baseline behavior rather than standing in for independent digest/cipher oracles. Compiler commands and deterministic roots/seeds are reproducible. Host shims do not establish real page-table, callback, IRQL, backing rollback or hardware behavior, and the report acknowledges this.

The guest uses existing public exports/declarations and the existing nxdk/TAP Makefile pattern, with no new kernel ordinal or shipping counter. It emits stable machine-readable per-workload ticks, correctness flags and semantic checksums; public timer implementation serializes its hardware read/wrap extension. Empty overhead is recorded, fixed workload order/buffers are used, setup and release occur outside measured intervals where intended, and the cold 64-type workload inserts fresh types 64..127 once while warm types 0..63 are established separately.

Rejected pin workloads end at the checked uncommitted guard and cover 0/32/64/65. Fragmentation fills the actual bounded pool window, frees only page phases 0/1 modulo four, and requires a failed four-page probe before timing; the remaining occupied phases divide the released pages into holes shorter than four, so a successful probe identifies a surviving large free run and rejects setup. The guest frees retained fragments after measurement. System samples include unchanged backing/zeroing and are explicitly not claimed to establish pristine internal absent-PDE state. Crypto checks, callback checks and semantic checksums are documented as part of measured work. Corrected public pool-size query is supported by public nxdk and baseline smoke, with the original failed smoke retained in the controller record.

The guest is a measurement fixture and public smoke, not a substitute for existing dispatch/vector/RSA/memory/lifecycle guest coverage. The report does not overclaim throughput, gameplay gains or completed runtime qualification. Native IRQ, cancellation/completion, security checks, ownership, warm-reset/shutdown/APC behavior and hardware access code outside these seven narrowly scoped regions are not modified; existing baseline/candidate host preservation evidence supports the relevant unchanged contracts.

## CannotVerify / controller acceptance boundaries

- Candidate nxdk/kernel compile/link, candidate public API regression guest, candidate benchmark smoke, seven alternating paired trials and the full matched XISO qualification suite are Task 3 work. They were not executed here and are not prerequisites falsely claimed completed by Task 1.
- Runtime measurement stability and the final 64-page crossover cannot be established from operation counts or the baseline-only smoke. The baseline smoke bounds its measured intervals below timer wrap, but the candidate and final repetition matrix still need controller validation.
- Exact physical backing/rollback, real callback scheduling, mutable public vector dispatch, native IRQ/cancel/security and warm-reset/shutdown behavior are beyond extracted host shims. Preserve the required existing guest qualification instead of inferring hardware certification from these counts.
- The Task 1 diff shows no prior patch or BIOS changes, but this review did not rehash all previously validated BIOS/patch artifacts or perform the later broad integration review. Those artifact-preservation checks and final branch review remain controller-owned.
- The implementation report's historical claims about implementer tool use/provenance cannot be independently reconstructed solely from committed source and retained result logs. This review itself used only the specified allowed material.

Task 1 may advance to controller-owned build/runtime acceptance. M1 is a nonblocking improvement to host assertion coverage, not a request to alter production semantics.
