# Xbox kernel call optimization design

The user requests an optimization branch and a performance assessment for every
kernel call. The starting point is the validated clean-room firmware baseline;
its contracts, public ABI and existing published images must remain intact.
Earlier permission to use independent implementation agents, avoid approval
questions, run the XISO suite directly and publish validated BIOS files persists.

## Scope and method

Audit every export declared by the actual kernel build input:
`ntoskrnl/xb/xboxkrnl.exe.def`: 371 exports, comprising 337 callable entries and
34 data entries. Seven unused ordinal slots are recorded separately. Map each
entry through `ordinals.map`, its active definition and its shared backends.
This covers the callable Xbox kernel ABI and the internals reached behind it;
unused ReactOS desktop/other-architecture code is outside the build. This is a
source-guided cost audit, not a claim that every possible runtime call site or
game workload has been profiled.

Three independent read-only workers assess disjoint sets: memory/RTL/cache,
scheduler/objects/synchronization, and I/O/HAL/crypto/debug/image loading. Each
export receives a specific decision, source reference and rationale. Candidate,
already minimal, missing behavior and data-only cases remain distinguishable.
The controller checks complete, duplicate-free coverage against the generated
inventory and selects improvements in active shared paths. Then a separate
implementation plan specifies the selected code, benchmarks and regression
checks. One source implementer owns mutations at a time, followed by independent
review. Merely changing every routine is not an acceptance criterion.

## Sources and isolation

Product branch: `perf/kernel-call-optimization`, starting at
`a88247760c91de599a14342158561373b072dfce`.
Public kernel source snapshot: `291ad9759f7993cb1f96d73bfa1c6f333c2bef34`, tree
`8ba32f2153b4716c8cac269bad06a78553f98ded`.
Public nxdk ABI reference: `14d5ee97e73347c973f1f57b68b79ec08c9e77f2`.
Fresh agents receive only public source, behavior requirements and their briefs;
no community firmware, extracted data, disassembly or analyst context. Shared
filesystem separation is a workflow rule, not an enforced security boundary.

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

## Measurements and acceptance

Choose bounded candidates backed by concrete avoidable work. Measurements must
execute the actual changed implementation and preserve identical observable
results. Verify allocation/scan/copy/dispatch counts when those are the claimed
benefit. For timing, use fixed workloads and the same compiler, emulator,
configuration, immutable inputs and guest ISO for baseline and candidate.
Run at least seven paired trials, alternate order, retain all samples and report
median and variation. A timing speedup must exceed observed run variation;
otherwise report only verified work reduction. Existing full XISO timings do
not by themselves measure kernel-call improvements.

Cover normal and worst representative sizes, empty and invalid requests,
alignment/overflow, fragmentation or contention relevant to the selected path,
and independent completion/lifetime. Reject unjustified complexity or changes
that merely move cost, break behavior, or worsen representative workloads.
Small leaf routines and hardware operations may correctly receive no change.

## Delivery

Publish the branch, a complete per-export audit, ranked opportunities, reviewed
optimization patch(es), reproducible build identity and before/after evidence.
Run covering host checks, API and clean-room guests, and the pinned full XISO
qualification for resulting release/checked BIOS images before publishing them.
Keep failures visible. Conker gameplay, physical hardware/64-MiB support and
attached debugger input remain unverified unless independently tested.
