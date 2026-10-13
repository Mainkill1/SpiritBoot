# Final MM metadata, thread lifetime and pool sweep

This read-only sweep covers combined release-64 source tree
`c24c8ce13b2395c4748305d191fb5ec02e204722`, ROM SHA-256
`003982e8b96be4a12699d67f1046d48a562eb2baa5cedb4c48ff2e13ac7ed79a`.
It adds no runtime policy. Inputs are the assembled pinned open kernel, owned
host fixtures, and the owned pool guest's existing native receipts. No game
allocation census, proprietary implementation, or disassembly was inspected.
The root workflow owns the final combined native matrix; earlier pool receipts
qualify the pool-only ROMs identified in
[the pool decision](POOL_SIZE_CLASSES_AND_REUSE_SCAN.md).

## Permanent physical bookkeeping

The source-derived bounds below come from `NxkPageSupplyInitialize`, the MM
boot carve, and `NxPoolPagesMetadataSize`. They are not runtime PFN snapshots.
The collector records the exact source-file hashes and PE section metadata in
[metadata-layout.json](../optimization/mm-final-sweep-2026-10-13/metadata-layout.json).

| Allocation | 64 MiB release | 64 MiB checked | 128 MiB release | 128 MiB checked |
|---|---:|---:|---:|---:|
| Shared free-list/owner entries, 4 bytes per frame | 65,536 B | 65,536 B | 131,072 B | 131,072 B |
| Pin state, 2 bytes per frame | 32,768 B | 32,768 B | 65,536 B | 65,536 B |
| Supply carve | 24 pages | 24 pages | 48 pages | 48 pages |
| Pool run-length table plus used bitmap | 8,704 B | 8,704 B | 8,704 B | 8,704 B |
| Checked pool last-free attribution | 0 B | 16,384 B | 0 B | 16,384 B |
| Pool metadata carve, separately rounded | 3 pages | 7 pages | 3 pages | 7 pages |
| Combined supply and pool boot carve | 27 pages | 31 pages | 51 pages | 55 pages |

The frame array covers the full hardware frame range, including initially
reserved framebuffer frames that later return to the supply. Sizing it only
from the original free-memory descriptors would underallocate. On reserved
128 MiB builds the supply still tracks all 32,768 frames, with separate
eligibility/accounting for the title and private domains.

Free links and live owners already share the same 32-bit entry. Free entries
need two 15-bit frame indices and the free flag; live entries use a 20-bit
self-map PTE index. Owner zero represents a private/unregistered immovable
frame, not a free frame. A separate full owner array would duplicate permanent
state. Pin state carries a 14-bit count, sticky overflow, and deferred return;
truncating it to a Boolean would break nested pins and delayed-free ownership.
Relocation requires a nonzero owner and zero pin state, then republishes the
owning PTE under the PFN lock. These contracts preclude an unqualified metadata
width reduction.

The ARM3 PFN database is **already backed by one shared 4 KiB data frame**.
Its virtual range remains mapped for residual code, but it is not a physical
`sizeof(MMPFN) * frame_count` allocation. Its mapping page tables and other
kernel structures are separate from the carve totals above. Thus a proposal
to remove a full resident PFN array would double-count a saving already made.
No ready-zero reserve or zero thread is maintained; zero pages are supplied on
demand. The optional supplier API `TakeZeroIfReady` returns zero.

The 4,096-entry pool page-state array consumes 4,096 image bytes; the generated
class map consumes 257. Nine shared-domain free heads consume 36 bytes, or 72
with reserved domains. The measured 272/320 classes add 12 nominal bytes on
shared builds and 20 on reserved builds over the seven-class table. On the
qualified release-64 build they fit existing alignment padding and add no
resident page. Pool census and scan counters compile out normally; the initial
diagnostic kernel added 27 resident pages and its copied guest record added
another 27. Those pages must never be counted as normal-release overhead.

The combined kernel has `.text` virtual size 349,320 B, `.rdata` 27,616 B,
`.data` 2,056 B and `.bss` 44,792 B. These are file-layout measurements, not an
aggregate RAM census: immutable prepared-image spans are backed by flash, and
INIT is retired. The collector deliberately records section metadata without
copying image contents. Further code shrinking must show which RAM or flash
page boundary it actually crosses.

## Title thread lifetime and reclamation

The title view is 320 bytes of complete public ETHREAD storage embedded in the
native thread object, including its 272-byte KTHREAD prefix. Its 8-byte registry
link is also embedded. There is no second pool object for the view. The exact
identity registry uses 256 bytes of list heads, a 4-byte monotonic negative
filter and a 4-byte cached public pointer; the public process uses 28 bytes.
Neither the registry nor process membership owns a native object reference.
The process membership change reuses the public view's existing list entry.

Creation publishes the initialized identity before exposure and links title
process membership before notification. Termination removes public process
membership before signaling but keeps identity available for legitimate
references to a terminal object. Final object deletion invalidates the cached
identity before unregistering it. The execution/reaper reference frees the
stack and then permits object deletion; held handles and independent references
correctly defer only object deletion. Failed creation also runs idempotent
registry/process cleanup. This ordering agrees with the reviewed title thread
contract and does not add permanent per-thread metadata.

Xbox's dead-stack cache limit is already zero. Both ordinary reaping and the
failed-creation delete path use the stored custom stack size, so large stack
tails are included in release. The earlier Phase1 reference repair recovered
one 1,024-byte `Thre` pool block, with no physical page saving; it must not be
reported as another whole-page optimization.

Every one of the seven normal pool triplets observed 32 live guest workers
increase stack ownership from 37 to 165 pages and return it to 37 after all
handles/references retired. That is **128 pages / 512 KiB returned** per run.
With the selected classes, pool backing grows 38 to 45 pages and stays 45 after
retirement. This is retained allocator capacity, not evidence that 32 native
thread objects leaked. The integrity-clean first diagnostic census independently
records live `Thre` objects 7 to 39 to 7: 32 new allocations and 32 corresponding
frees. The live count stays 7 through IRP/file/ladder/churn checkpoints. This
checks native object retirement as well as stack release; its
[exact tag rows](../optimization/mm-final-sweep-2026-10-13/thread-census.json)
retain the serial identity. These captures establish
one 32-worker lifetime cycle per launch, not an unbounded thread soak or a game
lifetime proof. Full view backing must not be shortened based on a lower subset
of fields presently touched by a guest.

## Independent SYSVA production review

Reviewed patches `0122b-system-va-uninitialized-data.patch` and
`0123-system-va-mapping-validity.patch` have no blockers in their scoped changes.
The exact selected source and combined source have identical `sysva.c`,
`iospace.c`, `pagesupply.c`, `api.c` and actual ARM3 `mmsup.c` validity walker.
Hashes and independently executed fixture commands are in
[sysva-peer-review.json](../optimization/mm-final-sweep-2026-10-13/sysva-peer-review.json).

Patch 0122b changes only the two data-page supplier calls from zeroing to their
corresponding uninitialized suppliers. Each old zero helper first called that
same supplier and then zeroed. Frame choice, domain, free-list unlink, owner
zero, available accounting and failure behavior therefore remain unchanged.
Page-table acquisition still uses `TakeZero`. SYSVA hole finding, per-page PFN
lock acquisition, publication, rollback, free and TLB handling remain unchanged.
Zeroed VM commit paths still use zero suppliers. There is no batching or reduced
PFN-lock count in this patch.

Patch 0123 removes the blanket validity result for the demand-mapped system-VA
aperture. It then uses the existing actual PDE/PTE present-bit walker. Existing
static direct, write-combined and device aperture guards remain unchanged.
The independent real-body supplier/SYSVA fixture passes both domain modes,
PDE crossings, backing pressure, partial failures, owner/pin and delayed-return
conditions; the independent actual validity wrapper/walker fixture passes
absent PDE, absent PTE, live PTE and freed PTE cases. Their receipts are saved
beside the review JSON. Host substitutions are documented by the fixture and
do not establish complete emulator timing or title coverage.

## Measured remaining leads and stop decisions

The largest retained pool observation is the synthetic mixed ladder's 80 empty
bucket pages, 320 KiB. Issue 135 deliberately retains mapped hot pages and
reclaims them when backing allocation fails. Immediate last-free retirement
would change that policy and can turn each hot IRP cycle into a refill; no
measurement here supports that change. The owned IRP/file and 4,096 warm churn
phases add no fallback reuse scans. Keep the established reuse/reclaim policy.

The next useful measurement is a pressure/lifetime capture that records retained
empty pages, reclaim events, refills and allocation failures, together with
available/title/private pages after repeated thread, streaming and mixed-size
cycles. Existing opt-in pool counters already cover much of this. A supplier
diagnostic can count private owner-zero frames, pinned/deferred-return frames,
spill-scan entries and relocation work, then report after the workload and
outside timing/lock regions. Actual sustained pressure or lifetime growth is
needed before a new retention policy, supplier index or pin representation is
justified. The bounded SYSVA host pressure fixture exposes a worst tested supply
walk of 8,170 entries, so supplier scan work is a concrete instrumentation lead,
not a demonstrated native hotspot.

Pool run-length packing is a small theoretical metadata lead: 0..4096 requires
13 bits, so a packed table would occupy 6,656 bytes rather than 8,192; with its
512-byte bitmap, the release carve could fall from three to two pages. Its
upper bound is one 4 KiB page, before additional code/state costs. This sweep does
not implement it: boundary, rollover, run-start truth, checked attribution,
publication and latency proofs would be required. The much larger measured
retention envelope makes pressure attribution a better next investigation.

The broader seed class table fails the boot packing comparison and adding 1536
strands a page. The minimal 272/320 table is the qualified capacity change.
The compatible-empty count filter eliminates nearly all measured fallback
entry checks but regresses common alloc/free batches; it stays only in rejected
owned evidence. No bitmap, more classes, eager retirement, dead-stack cache,
shorter ABI view or narrower pin counter is justified by this sweep.

## Precise pool issue closure statements

Issue 213 is implemented as a **bounded RAM-capacity improvement**: the measured
272/320 classes save one complete physical pool page at normal 64 MiB boot and
two after owned thread/IRP/file phases, with all seven repeats showing equal
other ownership and matching available-page gains. Truthful public capacities,
all request boundaries, non-power-of-two carving, both domains, failure/reclaim
and diagnostics are covered. The final pool-only release-64 rebuild (source tree
`6ae95feb5bf13252a50c52fef535ab98befd7a74`) is byte-identical to the qualified
classes ROM; its checked/release 64 and reserved 128 build matrix passes.
Class batch timing is inconclusive, with paired medians about +1.10%, +0.34%, +0.68%
and ranges crossing zero. This is neither a speedup nor formal latency
equivalence. The original issue's game census, per-call p95/p99, lock ticks and
native 128 runtime coverage were not collected. Closing the implementation
requires stating this narrower qualification explicitly, rather than claiming
those broader experiments passed.

Issue 218 is investigated and the index is **not beneficial for the measured
workloads**. The baseline performs 125 searches among 6,385 pool allocations;
107 full negative scans account for 438,272 of 438,831 entries. Successful
fallbacks require 559 entries total, while steady IRP/file/churn adds no fallback
work. A correct 4-byte shared-domain count candidate reduces all fallback work
to 559 entries with unchanged backing, but regresses requests 64 and 280 in all
seven pairs: median +9.73%/+9.58%, minimum +7.47%/+7.07%. Its improvement for 200
does not offset those regressions. Keep the existing compatible-head preference
and linear fallback plus optional diagnostics. A bitmap's own performance was
not measured and no universal no-index theorem is claimed. Reopen for an actual
workload with sustained hidden-empty searches or independently qualified common
path improvement. Root integration owns final issue writes and broader native
qualification.
