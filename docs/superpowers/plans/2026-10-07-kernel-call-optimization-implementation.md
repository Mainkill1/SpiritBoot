# Kernel call optimization implementation plan

Spec: docs/superpowers/specs/2026-10-07-kernel-call-optimization-design.md.
Audit input: complete371-export audit from the preceding audit plan. Seven bounded active families selected: pin scratch, pool range scan, absent-PDE scan, known custom type, ModExp final square, SHA live prefix, DES bit reversal. Shared backends can benefit multiple exports; this does not assert all calls should change.

## Global constraints

- Preserve exported ordinals, arity, calling conventions, data layout, documented behavior, and the existing 128-MiB xemu configuration.
- Preserve memory/page/IRP ownership, physical pins, warm-reset persistence, shutdown unwind/APC policy, native IRQ ownership, cancellation/completion, security checks, ordering and volatile hardware accesses.
- No proprietary firmware, keys, binary-derived implementation or instructions that provide community artifacts to implementers/reviewers.
- No HTTP test runner; all guest checks and the matched XISO suite execute directly in xemu.
- Keep prior source patches and validated BIOS files unchanged; append an independently authored optimization patch against the validated source.
- Run Docker builds, guest builds and emulator runs sequentially because each VFS container consumes several GiB of transient storage.
- No unchecked cache or fast path may change errors, zero-length/overflow behavior, callbacks or visibility of mutable state.
- No kernel SSE/FPU optimization without an existing safe context-preservation contract.
- Do not claim throughput or gameplay gains from structural changes or unmatched timings.

## Task 1 — kernel changes and measurement fixtures

Fresh public-source implementer reads .superpowers/sdd/2026-10-07-kernel-call-optimization-implementation/task-1-brief.md and selected-candidates.json. Implements seven bounded families with actual-source counter/differential/oracle checks and a public-ABI guest benchmark. Commit, report, independent task review. No parallel source implementers.

## Task 2 — source integration and exhaustive audit publication

After Task1 review, append optimization patch against validated tree and extend pinned firmware source lock. Preserve prior patch and BIOS. Publish complete normalized per-export audit JSON/CSV and ranked decisions, including explicit deferrals and actual existing stub behavior. Integrate benchmark reproducible build into docs/CI as appropriate; no HTTP runner. Validate patch application/manifest source tree and covering tool checks. One integration agent owns product mutations.

## Task 3 — measurement, firmware qualification and publication

Controller builds release/checked sequentially with pinned toolchain. Verify release rebuild reproducibility and source identity. Compile new immutable benchmark ISO against public nxdk; run >=7 paired baseline/candidate release trials alternating order, preserve all samples, report medians/variation and measured actual-source work counts. Tune/reject changes with representative regressions; changes must return through scoped implementation/review. Run API, clean-room contract and warm reboot guests and full direct pinned XISO suite on both variants. Final whole-branch independent review once. Publish optimization branch/source snapshot, report/evidence and validated images only after covering tests pass. Keep old BIOS/patch unchanged and all encountered failures visible. No gameplay claims.
