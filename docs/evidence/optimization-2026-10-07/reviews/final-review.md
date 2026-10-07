# Final whole-branch optimization review

**Specification compliance: PASS. Code quality: PASS WITH MINOR FINDINGS. Ready to publish the qualified optimization-branch BIOS files; do not merge main.**

Finding counts: **0 Critical, 0 Important, 2 Minor**. M1 is the explicitly deferred Task 1 finding, independently triaged below. M2 is a documentation correction. Neither requires rebuilding or rerunning qualification before delivery. There is no outstanding production correctness or evidence-integrity blocker in the reviewed change.

## Reviewed identity and scope

Product full range: `a88247760c91de599a14342158561373b072dfce..52807f85d70927920f4c38e3efb48f3c4fe1db92`. Public kernel full range: `291ad9759f7993cb1f96d73bfa1c6f333c2bef34..87aba89a6ba9b2a58f2edd6e52d5e3aa1e8649d7`, final tree `f7adb302a762ed1945cc07d9c2ff428c643ba959`.

Read the final brief, specification, full-range packages, ledger, Task 1 review and implementation evidence, original Task 2 rejection and scoped fix approval, final source/integration tooling and retained qualification evidence. The kernel package exactly matches its full `git diff --binary -U10`; the product package is its exact full diff followed by a one-line range-identification footer. Both inspected working HEADs match the supplied candidate identities. This is the single broad final review, not a last-commit review.

Only permitted public product/kernel material and coordination records were accessed. Review operations were source reads, metadata/content comparisons, hashes, and a public source-tag lookup. No implementation edits, subagents, Docker builds, emulator runs, or reruns of already-passing tests were performed. This report is the reviewer's sole written artifact. Historical BIOS files were read only for explicitly requested byte identity checks.

## Findings

### Minor M1 — larger nonalias pin profiles assert only the first PFN

Public kernel `tests/host/kernel-performance/pins.c:50`, `:54`, `:57`, `:66`, `:75`, `:85`; scratch checker at `:39`.

The large profiles run the actual implementation but generally inspect only `NxpPins[16]`. Their whole-array checks cover multiplicity scratch, not all pin counts. A later-PFN mutation regression could therefore evade those particular assertions. This is the same Task 1 M1, not a newly discovered production defect.

**Disposition: retain as a nonblocking deferred fixture improvement.** The complete production preflight precedes all pin mutation; the apply loop still visits each page under the PFN lock. The source review establishes this directly. The fixture additionally checks both PFNs for an unaligned two-page request at `:93`, covers alias multiplicity, invalid PFNs, overflow and pending return, and the executed contract/API guests supply actual runtime ownership checks. These facts justify delivery without presenting the million scratch checks as complete pin-state coverage.

Action: for each nonalias profile, assert every affected PFN's expected count after initial/nested lock and each unlock; compare the full pin array before/after rejected calls. Keep scratch/work-count assertions separate. Validate that focused fixture when implementing this follow-up. A future alteration to batch traversal or pin-state mutation should include this improvement before claiming broad state coverage.

### Minor M2 — static-audit landing page retains a stale qualification status

Product `docs/optimization/2026-10-07/README.md:37` says, “Runtime qualification and new BIOS publication remain pending.” Runtime qualification is now complete, as the appended results and linked final evidence demonstrate. The preserved baseline audit scope is clear elsewhere, but this present-tense sentence makes the current status contradictory.

Action: replace it with a current statement that runtime qualification is complete and link the final evidence; describe publication according to the actual delivery state. Preserve baseline-anchored source references and the historical preimplementation assessment. Validation is a documentation read/diff check; no build, qualification run, or broad re-review is needed. This does not block BIOS publication because the BIOS README and final evidence already state the precise qualified results.

## Export audit and selection

Independently parsed the actual baseline `ntoskrnl/xb/xboxkrnl.exe.def`, including fastcall-decorated names. All **371** unique audit ordinals, names and kinds match: **337 functions, 34 data entries**. The seven unused slots are exactly **367–373**. JSON and CSV ordinal/name/kind/verdict sequences match. Every row has source references, backend, rationale and risk; every referenced baseline file/line exists. Candidate rows have an opportunity and measurement proposal. Baseline references correctly remain anchored to tree `8ba32f2153b4716c8cac269bad06a78553f98ded`.

Decisions remain **37 candidate, 288 no-change, 12 stub/no-op, 34 data**. All fifteen candidate families are accounted for: seven implemented/selected and eight explicitly deferred. Minimal leaves, hardware accesses and required lifecycle work are not changed merely to increase the number of modified exports. Missing/fatal stubs remain distinguished from intentional no-ops and release/checked differences. Mutable crypto-vector dispatch is not replaced by default implementation assumptions.

The deferred VM-query, Unicode, handle, FPU, APC, name-scratch, shutdown and HMAC opportunities retain their respective boundary, lifetime, error and measurement obligations. The documented preexisting multiple-wait and mutant-reference correctness concerns remain separate work, not claims of optimization-induced breakage or complete kernel correctness.

## Production preservation and code quality

The actual kernel diff changes seven production files and contains the seven intended families plus their fixtures/docs. No export definition, ordinal map, calling convention, exported layout or public arity changes. No FPU/SSE optimization, persistent decoded cache, IRP lifecycle, IRQ ownership, shutdown policy or security bypass is introduced.

- **Pin scratch:** `ntoskrnl/xb/mm/api.c:76`, `mm/pagesupply.c:158`, `:293`, `:298`, `:314`, `mm/mm.h:218`. Initialization clears scratch. Search confirms the public batch API is its only producer. The same PFN lock covers translation, complete preflight, application and cleanup. Zero length/overflow precede scratch writes. Increment-before-record includes increment-then-reject cleanup. Invalid PFNs are guarded. Sparse success clears during the existing application pass; sparse rejection retranslates at most 64 translated pages; larger prefixes clear once in bulk. Alias repeats cannot consume already-cleared multiplicities after preflight. Sticky overflow and pending-return mutation are unchanged. Full diagnostics are explicitly opt-in, not ordinary checked overhead.
- **Pool search:** `ntoskrnl/xb/mm/poolpages.c:114`, `:171`. Advancing past the first occupied bit cannot omit an admissible intervening start because each such candidate still contains that bit. Original rotating boundaries, wrapped candidates crossing the hint, bounds and successful early exit are preserved. `Next` is consumed only after a failed range test writes it. Mapping, supply ownership, statistics, lock order and failure unwind are outside the change.
- **System VA:** `ntoskrnl/xb/mm/sysva.c:63`, `:124`. An absent PDE proves the clipped span is free while the allocation lock serializes occupancy. Run continuity and first-fit return remain intact across PDE boundaries. Present PDEs retain volatile exact-zero PTE checks. Zero-page handling is explicit and the fixed aperture bounds accumulation. Backing, zeroing, rollback and CR3 behavior remain unchanged.
- **Type registry:** `ntoskrnl/xb/obcreate.c:52`, `:137`. The first search and observed count are protected by the existing lock. No production removal/reset/decrement exists; each increment retains a distinct node. The 32-bit address space cannot retain enough nodes to reach signed count overflow, much less wrap, so equal counts prove no intervening insertion. A changed count forces the second duplicate scan. Allocation/free stay outside the lock; silent initial OOM and lazy initialization remain. Controlled same/different-type reentrancy fixtures substantiate the proof.
- **ModExp:** `ntoskrnl/xb/crypto.c:343`, `:412`, `:434`. Only the final unconsumed square/copy is removed. Odd conversion overwrites `Val` before use; even output consumes `Acc`. Word/zero-modulus guards, exponent-zero behavior, allocation/failure/output ordering and aliases are unchanged. `i+1` is bounded by at most 512 words times 32 bits.
- **SHA:** `ntoskrnl/xb/crypto.c:41`, `:56`, `:122`, `:134`; core `sdk/lib/cryptlib/sha1.c:148`, `:191`. State/count and live prefix are initialized. Update fills a complete local block before transform; partial store copies only initialized live bytes. Final initializes padding/length, transforms, clears the whole local buffer and resets state before the unchanged whole-context store. No inactive local tail is exposed. Caller input/context overlap still uses a separate local context; digest/context ordering is preserved.
- **DES:** `ntoskrnl/xb/crypto.c:910`. Fixed masks map each of six low bits to its reverse position. Packing, bytewise unaligned loads and mutable caller tables remain unchanged. No new secret-indexed table/cache or cipher/CBC policy change appears.

Host checks extract actual production bodies/regions and instrument only host translation units. First-fit oracles independently enumerate admissible candidates; ModExp uses Python `pow`; SHA uses `hashlib`; DES uses public known answers and exhaustive independent bit packing. Full-context/cipher differential hashes cover caller-visible state beyond mathematical output. Inspected retained logs report 30,978 optimization oracle assertions, 88 original contract assertions on each tree, and 7,307,629 candidate pin assertions per ordinary/diagnostic mode. These are retained passing evidence, not reviewer reruns. Host shims do not replace guest memory, lock, callback or hardware qualification.

## Measurement and final integration

`tools/kernel_performance.py:199` reconstructs normalized values from integer ticks/iterations as `Fraction`. Medians, raw/intertrial ranges, paired differences, sign counts and strict variation comparisons remain exact through the decision at `:208`. Float conversion is presentation-only. The original Task 2 Important I1 is therefore **resolved**, including its symmetric regression boundary. The retained adversarial tests cover uint64 one-tick deltas hidden by a 1023-tick range and rational normalization. No open Important finding is inherited from the original rejection.

All fourteen final captures retain **42/42** TAP and **121 samples each**; their run/serial hashes match the final report. Source inspection confirms strict workload order, sample count, checksums, uint64 bounds and clean terminal enforcement. Controller execution records alternate seven synchronous baseline/candidate pairs, using the same guest ISO, xemu and seed; capture/build identities bind the candidate to the approved tree. Public guest setup, guard checks, fragmented pool construction, callbacks and independent known answers exercise the changed paths through exported ABI. No HTTP runner is involved.

Final classification is **6 small-pin timing improvements, 35 inconclusive, 0 consistent regressions**. Six other families have directly measured source-work reductions without claimed wall-time gains. SHA slower medians and mixed paired signs remain visible. Large-word ModExp timing uses bounded small numeric modulus inputs, not a representative RSA-throughput claim. XISO elapsed times are explicitly unqualified performance evidence. The small/rejected-pin measurements support retaining the provisional 64-page budget; larger/crossover timings do not establish a universal optimum. The original four-failure pool-query smoke and corrected 42/42 smoke are retained and excluded from formal pairs.

The shipping patch is byte-identical to the full reviewed public-source diff: `0002-kernel-call-optimization.patch`, SHA256 `0e8147f370fc591c1f6b440344d1271aa5d040291e54a15fba650a88ad8ff1f7`. The lock retains 0001 first and appends 0002. Build manifests for release, release repeat and checked all record the exact approved source tree and outputs. Public remote `kernel-source-optimization-2026-10-07` resolves to commit `87aba89a6ba9b2a58f2edd6e52d5e3aa1e8649d7`, matching the reviewed local tree and source links.

Direct hashes of both new BIOS files match the manifest:

| Image | Bytes | SHA256 |
|---|---:|---|
| Release | 262144 | `48c3ee940d55628a74e17333a1e76966ad6ade5e44a41915d2d53348a37fdc74` |
| Checked | 524288 | `4016974c0b0a07a6d560c8afa13cd33026368bf2f7cbc3d967dc769bd4d9d2e8` |

All five historical patch/image entries in `final-verification.json` match their recorded hashes and bytes at the product baseline. All **159** entries in the evidence checksum manifest match their retained files. Release repeat identity is recorded locally and the retained CI log contains the same release hash. Both CI runs **37702363272** and **37702368565** completed successfully at the fixed analyzer commit; later product commits add final evidence/images without changing production code. CI runs direct guest validation and preserves failure evidence; no single CI runtime is treated as a performance comparison.

## Qualification strength and limits

Both variants' API captures record **626 PASS plus 6 expected TODOs**, contracts **23/23**, and warm reboot **5/5**. Full XISO raw result arrays independently contain **149 unique PASS records: 144 leaves and 5 groups**. Both receipts are **COMPLETE 144/144**, configuration-matched, with zero applicable oracle failures. Comparison records contain **253 checked hashes, zero mismatches, no missing/extra records** for each baseline comparison and the cross-variant comparison. Nonapplicable S3TC diagnostics remain visible (release 16, checked 11).

The qualification command/configuration records show direct xemu at **128 MiB** with the qualified BIOS identities. Builds, benchmark collection and guest runs are retained controller evidence, not runs newly performed by this reviewer. Original runtime executables/HDD seeds and the full external XISO media outside the allowed directories were not opened; their recorded identities, receipts and preserved result records define that provenance boundary. The four published guest ISO files are the public-source test media described by the source, build logs and guest manifest.

This supports publication of the exact reviewed branch BIOS with its corresponding source and evidence. It does not establish physical Xbox hardware, 64-MiB operation, Conker gameplay, attached interactive-debugger input, universal throughput gains or complete correctness of unchanged kernel subsystems. Shared filesystem source separation remains procedural. Retain those explicit limits and deferred M1 in delivery.
