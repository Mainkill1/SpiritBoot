# Public thread identity and terminal status

The thread identity repair and its IRP boundary follow-up pass the full
release/debug 64/128-MiB CI matrix and the native qualification below. Initial
v4 CI exposed a real IRP thread-pointer regression; v5 fixes that regression
and retains the failing evidence. This remains a draft for review, with the
explicit field and integration limits below.

## IRP boundary follow-up (v5)

PR233's exact checked64 CI run 38405100975 completed all 639 API tests,
including `io/threadirp` 505–508. Initial PR234 run 38408986927 stopped after
505: `IopQueueIrpToThread` treated public `Tail.Overlay.Thread` as native
ETHREAD and asserted in its guarded-region operation. The harness timeout
followed that runtime assertion; both release jobs also failed. These results
supersede any inference of full correctness from the earlier v4 release tests.

Patch `0109a-public-irp-thread-boundaries.patch` keeps the shared IRP and its
published thread field. Native consumers resolve a local pointer for queueing,
completion APC targeting, process/session lookup, hard-error handling, device
verification and FSRTL process reads. Native pointers with a negative address
residue avoid lookup. Public builders publish the identity on return. Dispatch
and all three StartIo entry paths publish before callbacks only for the
existing `TitleOwnedDriver` provenance flag. No packet access is added after a
callback that may pend, forward, retain, reuse or free it. Native-only packets
retain their original representation.

No packet allocation, reference or lifetime cache is added. The native IRP list
remains authoritative. Existing disassociation clears the shared thread field;
reinitialization clears ownership and list membership. The public intrusive
IRP list is not mirrored, and live scheduler fields remain outside this scope.

The new actual-source ASan/UBSan suite passes 69 assertions: both identities,
queue/unqueue, issuer/other-thread completion, cancellation, orphan cleanup
after actual disassociation, native→title→native forwarding, all StartIo
entries, freeing callbacks, MORE_PROCESSING_REQUIRED, reuse, and builder
success/failure. All 89 workflow source checks pass; an independent review
also reran the 69 new checks. Host dispatch/IRQL/allocation primitives are
models; the native receipts below independently qualify the public behavior.

The first Complex public oracle passed 57/57. An expanded fixture passed its
first 73 checks on Complex and v5, then used an invalid buffered read reporting
0x1234 bytes for a 32-byte request. That fixture is excluded from qualification
and preserved separately. A further reference-only run returned
STATUS_ACCESS_DENIED because the minimal title create handler had not set read
access. The final fixture uses public IoSetShareAccess, reports the actual byte
count and passes **77/77** on Complex,
v5 release64 and v5 checked64, with identical fixture hashes. It validates all
queue/builder/StartIo/retained-packet paths and native I/O manager dispatch
through the title driver to exact event/IOSB/data completion.

The exact release v5 ROM additionally passes **10,537/10,537** assertions:
async lifetime 7,833, zero IOSB 338, seek/mutation 2,071 and public wait blocks
295. Under a test-only 2-MiB/s HDD throttle, all 1,116 reads return pending;
1,097 still have unsignaled events on return. Close/delete/truncate contenders
start while reads remain pending. Eight issuer-exit cases complete exact data
and IOSBs without delivering an APC to the departed thread. Steady available
pages and pool pages remain flat at 15,633 and 47.

The [v5 CI matrix](https://github.com/Mainkill1/SpiritBoot/actions/runs/38415999040)
passes all five jobs at `62febdc2`: host tests and release/debug 64/128-MiB
firmware. Each profile completes all 639 API assertions (633 passes and six
preexisting TODOs, zero hard failures), including `io/threadirp` 505–508, and
the configured contracts, warm-reboot and performance-correctness guests.
Both release profiles pass clean rebuild verification. The checked CI image
has its own recorded ROM hash and the same pinned v5 source tree; it is not
relabeled as the locally built checked64 ROM below.

An uninstrumented, unthrottled A/B/B/A compares the previous packaged v4 ROM
with packaged v5, using the same public world replay, original emulator and
isolated HDD base. Every boot passes 19 checks and verifies SHA1 for all
12,288 reads. Total batch time across the 12 workloads is
986.382 / 1,008.887 / 1,014.631 / 1,014.022 ms. Candidate/control two-boot means
are **+1.16%**, with individual workload ratios from 0.9902 to 1.0360. The
last control overlaps the slower candidate; one short ABBA does not isolate
small overhead from run drift. This is neither a zero-cost claim nor a game
performance claim. The [full timings](evidence/public-thread-identity-20261013/irp-boundary-v5/world-cost-v5.json)
retain every workload rather than only the favorable samples.

The IRP follow-up adds 600 bytes of release `.text` and 40 bytes to `.bss`
layout relative to packaged v4. Section RVAs and `SizeOfImage` (585,728 bytes)
are unchanged, so it consumes no additional image page in this build. It adds
no per-IRP or per-thread allocation.

Exact source tree: `c5a4fb8a95538e2f976cfa933395857e38bd3d57`.
Release64 ROM: `d542171d60701f7fdab977b047458d27d40d713f235b7251c6af3eb88a27c2f9`.
Checked64 ROM: `77169666082d8c52d0960a6c4df094537d2a7680021d36d7aa811c8ddee6a4c5`.
These are distinct from the original v4 and combined async5 receipts below.
[CI failure excerpts, host and native receipts](evidence/public-thread-identity-20261013/irp-boundary-v5/)
retain that distinction, including the excluded fixtures. The standalone
[public IRP fixture](../../tests/xbe/thread-irp-identity/README.md) is maintained
with the other native probes. No merge or combined-runtime acceptance is
implied by the standalone v5 receipts.

## Original thread identity implementation and qualification

Public thread references previously exposed the native `ETHREAD`, while
`KeGetCurrentThread` returned a different, 0x80-byte public shadow. The public
`GetExitCodeThread` wrapper reads `HasTerminated` at 0x77 and `ExitStatus` at
0x120, so neither identity nor the required terminal fields were reliable.
The corrected public probe passes **166/166** on Complex and the prototype;
the unchanged async2 control passes **118/166**.

Patch `0109-public-thread-identity.patch` supplies a 0x140-byte public backing
view, one object identity, ID publication before creation notification, and
terminal status publication before native thread signaling. It translates
public thread pointers at object-reference, priority, suspension, APC, event
boost and wait boundaries. Native scheduling and reference counts continue to
belong to the canonical native object.

This branch is stacked on completion-overhead PR233, commit `d5e35d52`. The
critical-section owner repair in PR230 is a separate change and should be
included in combined runtime qualification. It is not duplicated here.

## Identity and lifetime

The view is initialized before it enters a 32-bucket exact-address registry.
The registry owns no reference and remains valid through termination and
handle closure while any object reference remains. Final `PspDeleteThread`
removes the identity before freeing native storage. Failed pre-initialization
deletions see zeroed registry links. Creation and exit notifications receive
the same public identity as real handles, the current-thread pseudo handle and
`KeGetCurrentThread`.

Complex retains the thread ID and old exit status during exit notification;
it clears public `UniqueThread` and publishes the terminal status before a
thread wait completes. The prototype follows that observed ordering. An early
probe incorrectly expected the ID to survive final termination; the original
failure and corrected evidence are preserved.

Pointer lookup does not inspect discriminator bytes, object headers or magic
values through untrusted caller addresses. An exact registry match establishes
ownership. Known referenced native objects can safely use their native type
when translating outbound object-reference results. Current-thread identity
has an independently known lifetime.

A monotonic 32-bit residue mask rejects impossible public addresses cheaply.
A set bit proves nothing and still requires exact identity. On this allocator,
native bodies are at least eight-byte aligned and the view offset is 4 modulo
8, so at most four low-five-bit residues can accumulate. Deletion leaves bits
set; even future denser alignment only increases false-positive lookup work.
A one-entry cache stores only a successful exact public address and is cleared
under interrupt exclusion before registry removal. It never pairs a stale
native pointer with a newly loaded public pointer. Valid pointer callers must
already hold the object's lifetime, as required by the object API.

## Caller wait blocks and user APCs

The native multiwait implementation remains responsible for WaitNext, alert
precedence, object consumption, dispatcher locking and scheduling. The adapter
maps the object array and invokes it once. It preserves the public immediate
wait-block contract: WaitAny initializes only the failed prefix and leaves the
winning block and suffix byte-exact; successful WaitAll forms a circle. The
same rules apply to abandoned-mutant results. Timeout/alert paths retain the
one-past-end next pointer observed on Complex.

A private native entry defers only multiwait's two explicit Xbox user-APC
calls. After the wait has unlinked native dispatcher blocks and restored IRQL,
the adapter repairs caller fields and delivers user APCs exactly once before
returning. The original native entry retains its original delivery behavior.
There is no per-thread toggle to leak into reentrant waits.

The exact public oracle passes **295/295** on Complex and v4. A valid v3 control
fails exactly 20 assertions: eight abandoned-result block cases and twelve
callback-time field observations. Tests cover Count 1/2/64, immediate and
actually queued user APCs, kernel-before-normal order, both callbacks at
PASSIVE_LEVEL, nested waits from a callback, mixed public thread/event objects,
WaitNext, sentinels and guards. Both callbacks observe public `Thread`, `Object`,
`WaitKey` and full SHORT `WaitType` fields. The initial test incorrectly assumed
NT-style APC_LEVEL for the kernel routine and passed NULL blocks; Complex runs
both routines at PASSIVE_LEVEL and bugchecks for the required public block
array. Those invalid receipts are retained separately. Native internal NULL
blocks remain covered by the host routing test.

## Memory and reference cost

Target-compiler layout grows KTHREAD from 576 to 776 bytes and ETHREAD from 736
to 936 bytes. Including the 24-byte object header and eight-byte pool header,
both use the existing 1024-byte bucket. There is no external view allocation.
The registry, mask and cache add 264 static bytes; the boot ETHREAD grows 200
bytes. Native measurements confirm no additional thread pool/page cost.

The caller-block backup and translated array require at most 1,792 dynamic
stack bytes for 64 objects, plus frames. The target compiler reports a 96-byte
adapter fixed frame; the native private entry reports 64 bytes and its wait
implementation 96 bytes. One/two-object calls reserve proportionally. The
native 64-object APC/reentrant case and the existing thread-stack contract pass.

The uninstrumented original emulator ran A/B/B/A, with three samples per boot.
Values below are within-boot medians in milliseconds per 32,768 pairs:

| Operation | async2 A1 / A4 | v4 B2 / B3 |
| --- | ---: | ---: |
| Current thread pointer ref/deref | 4.506 / 4.510 | 5.258 / 5.212 |
| Other thread pointer ref/deref | 4.429 / 4.523 | 5.138 / 5.125 |
| Event pointer ref/deref | 4.492 / 4.610 | 4.624 / 4.648 |
| File pointer ref/deref | 5.503 / 4.555 | 4.635 / 4.715 |
| Current thread handle ref/deref | 7.647 / 8.983 | 8.874 / 8.823 |
| Other thread handle ref/deref | 15.314 / 15.179 | 16.658 / 17.102 |
| Event handle ref/deref | 15.702 / 15.384 | 16.133 / 16.325 |
| File handle ref/deref | 15.384 / 15.582 | 16.182 / 16.886 |

The exact-address cache reduces v3's other-thread pointer cost from about
12.05 ms to 5.13 ms. The remaining translation cost is roughly 20 ns per thread
pointer pair and 40–60 ns per other-thread handle pair in this fixture. These
are measured correctness costs, not a zero-overhead claim. Cache misses still
perform an exact bucket scan; synthetic aligned layouts have maximum chains
1/1/1/2/4/8/16 at 8/16/32/64/128/256/512 registered threads.

Both v4 soak runs pass **139/139**. All 352 workers finish with correct public
identity and exit fields. After 64 warmup create/destroy iterations, 256 steady
iterations keep available/pool/stack pages flat. Async2 has the same footprint
and fails only the expected aggregate public identity/terminal-field assertion.
Thirty-two resident 16-KiB threads cost 128 stack pages plus eight pool pages in
both kernels; retired pool usage stays at the bounded peak.

## Validation and artifacts

The maintained patch includes actual-source host fixtures: registry identity,
cache invalidation, deletion/reuse, collisions and interrupt restoration
(**138,797 assertions**); wait routing, guards, immediate/queued and abandoned
statuses, Count 1/2/3/64, next pointers, private/native APC dispatch and internal
NULL blocks (**448,384 assertions**). Both use ASan/UBSan. The dispatcher is
modeled in these host tests; native public observations provide the behavioral
reference.

All 88 configured actual-source workflow checks pass (one target-layout check
required the recorded native compiler outside the host-test container). The
product unit suite passes 129 tests with three skips. The packaged source
also passes the existing thread-shadow, thread-stack,
thread-wait, I/O APC order, critical-section, object-handle fast path and cache
completion-wait host suites. CI runs the two new extraction tests on every
firmware profile. Standalone reproducible native fixtures are in:

- [thread identity](../../tests/xbe/thread-public-identity/README.md)
- [public wait blocks](../../tests/xbe/thread-wait-blocks/README.md)
- [reference cost and soak](../../tests/xbe/thread-reference-soak/README.md)

[Evidence and receipts](evidence/public-thread-identity-20261013/README.md)
include full TAP serial output, process results and exact BIOS/emulator/fixture
hashes. No proprietary binaries, code or disassembly are included.

Prototype v4 ROM: `faaa812c5262b5c67643bd4cf979ae6a4352174cad5093c4b0bfcbb9ac809a27`.
Packaged release64 ROM on PR233:
`38ba7640b7dd80de80b9a9d0736df6fc2ce9add3d2788b6a8c3ac518810319a8`.
Packaged source tree: `51cb877cc33530e6e5784377d4bc10e7ff1966e4`.
The prototype native receipts and packaged build/host receipts are distinct;
the combined owner-fix receipt uses its own exact identity below.

The combined async5 runtime (PR233 behavior + this v4 runtime + PR230 owner
repair) passes **11,640 functional assertions across 11 native fixtures**:
zero IOSB 338, seek/mutation 2,071, broad ABI 16, critical owner 36, contention
188, immediate delay 537, scatter 21, async lifetime 7,833, thread identity 166,
wait blocks 295 and quiet thread soak 139. Four A/B/B/A public world replays
also pass 19 checks each. This is public workload regression, not game
acceptance or a claimed game performance gain.

Combined ROM:
`7d190406537911e296931947b32c5c5efcfc7cecb00f6fa1b7e84d419074a4ef`.
Combined source: `642b25b303108d3f0616a98fa5333acb9d1495ac`.
The [combined receipt](evidence/public-thread-identity-20261013/combined-async5-qualification.json)
and [unmodified raw archive](evidence/public-thread-identity-20261013/combined-async5-evidence.tar.gz)
are distinct from the standalone packaged `38ba...` build. Archive SHA256 is
`4a1c79f0008014b41566b20810437137abf0a33f8f59d2ed3dd61243f4eabbe3`.
All 15 TAP plans/assertion sequences and per-run BIOS hashes were checked.
The parent also reran the 138,797 registry and 448,384 adapter host assertions
on the exact combined source. The packaged patch changes only comments and
adds tests relative to the v4 runtime in that combined image; the comment
comparison receipt records the three affected runtime files.

## Explicit limits

This repairs thread identity, ID and terminal-state behavior; it does not
implement every live Xbox KTHREAD/ETHREAD field. Public process/APC/mutant lists
are not a synchronized scheduler mirror. State, Priority and Quantum can be
stale after native scheduling, boost, delay or tick activity. Creation
SuspendCount/State/Quantum differ from Complex and remain open; CreateTime's
zero-in-callback/nonzero-at-return ordering is already correct and unchanged.
No native suspension ordering, non-Ex registration or quantum policy changes
are included.

Unrelated kernel APCs or observers examining caller blocks while they are
linked can still observe native fields. Queued-wait intrusive/timer-link
identity is not claimed equivalent; the qualified callback fields are listed
above. Live dispatcher-owner/list identity beyond the separate PR230 critical
owner correction requires its own public contract and qualification.
