# SYSVA and final memory audit, 2026-10-13

## Scope and source boundary

This investigation starts at product `7c92d97aff39446d245cf23bab9ade24248289e0`
and assembled open Roswell tree `694b0e2461558f6a5f7a774fd34c79bd7cdc111e`.
The 64 MiB baseline ROM is
`be180279642478d59bdd484abbaa3004d3efaf95a31194c838596341894c6827`.
Only maintained/pinned open implementation, public nxdk declarations and
Complex black-box observations were used. No proprietary source, firmware
disassembly, dumps or implementation-derived expression were consulted.

Issues: #214 bounded SYSVA work; #240 SYSVA/pinning gap and relocation
diagnostic blind spots. Product, source, fixtures and all failed experiments
are kept distinct below.

## Rejected bounded zeroing batch

The original `NxkSysVaAllocate` takes each data page with
`NxkPageSupplyTakeZero` (or the title-domain counterpart), under a separate
PFN lock. Zeroing therefore runs at PFN-lock IRQL, either through the live WB
direct alias or lock-owned hyperspace. Published pages have no owner entry.
Their immovability is intentional; a batch must not make them relocatable.

A production-body fixture first failed with
`SYSVA data zero must run outside PFN lock`. Its comparison mode checked the
existing PFN order, returned bytes, free-list accounting and exhaustion. The
candidate reserved at most sixteen ownerless frames. It appended only O(1)
kernel-list takes, stopping before another spill scan; the reserved-upper-RAM
profile appended only immediately consecutive free title frames. A short batch
was progress, not failure. One existing scan plus at most fifteen constant-time
unlinks bounded reservation work. Data zeroing used a newly checked WB alias or
the private writable SYSVA mapping after `invlpg`; one final CR3 reload remained.
Rollback returned at most sixteen frames per PFN lock. Normal free was unchanged.

Actual page-supply initialization, free lists, TakeAny/TitleAny, Return, pin and
unpin bodies were retained in the host fixture. It covered sizes 1/2/8/9/16/17/
1024/1025/4096, 64 MiB retail-shaped and 128 MiB layouts, reserved upper RAM,
direct/mapped/mixed aliases, alias remapping after reservation, PDE boundaries,
neighbors, shortage positions, retained empty PTs, allocation competition and
deferred pinned-frame return. Host lock transitions for 4096 kernel-class pages
fell from 4096 to 256, and data zeroing under the PFN lock fell to zero.

The candidate ROM was
`1cdd25e24514076b77686689bf68e1438006da381b09cf47a742ed7f5eb645ea`, source tree
`aa7123176f94991e7e43eacda1c0278bb4c1e2ec`. Seven alternating Windows user-session
pairs used unchanged portable ISO
`65da3568167cd7e25eec3da4baaffbe65c7fae931078659885297e657412a705`.
The analyzer checked all fourteen immutable launch receipts, 64 MiB profile,
Vulkan configuration, common EEPROM/backing/bootrom/executable hashes,
nonoverlapping order, every sample, checksum and all forty workloads.

| SYSVA pages | Baseline median us | Batch median us | Candidate change | Ranges |
| --- | ---: | ---: | ---: | --- |
| 1 | 12.7149 | 12.7242 | +0.073% | overlap |
| 16 | 53.7859 | 53.5266 | -0.482% | overlap |
| 1024 | 2826.503 | 2788.275 | -1.352% | overlap |
| 1025 | 2791.535 | 2785.311 | -0.223% | overlap |
| 4096 | 11330.311 | 11518.488 | +1.661% | overlap |

The batch did not demonstrate a SYSVA throughput gain. Of the forty workloads,
thirty-four ranges overlapped, five SHA ranges were faster, and `pin-1` slowed in all seven pairs, from median
1.01260 to 1.14180 us (12.76%), with separated ranges. No causal attribution to
the pin source is asserted: that source was unchanged. The complete table is
retained, including this regression. Reducing lock count alone did not meet
#214's throughput acceptance, so the batch is rejected for the selected firmware.

The first diagnostic ROMs used `DbgPrint`; their native serial logs contained
no lock observations. They do not prove native lock duration. Revised test-only
diagnostics emit aggregates directly to UART after lock release. Those ROMs are
excluded from performance aggregates.

## Initialization contract discovered by the stronger fixture

The stronger 64 MiB fixture
`171bb31a1950c87b306e95ed11ac2c9882ecaa7b05fae680a06bea41eafacfd8` passed all
70 assertions on original SpiritBoot and the batch candidate. Complex passed
59 and failed eleven assertions that demanded fully zeroed system memory.
These failures are retained in raw evidence, not counted as Complex passes.

The pinned public nxdk declaration exposes size and protection but provides no
zero-initialization guarantee. The owned production tree has no internal
`MmAllocateSystemMemory` consumers beyond the public export; existing consumers
in this tree are tests. SYSVA zeroing was thus a stronger SpiritBoot behavior,
not a demonstrated shared Xbox allocation contract. VM committed-page zeroing
and page-table zeroing remain separate correctness requirements.

The common-contract fixture
`138733b225a59eb9be6f735a38a428999777545b0134e23fc162bf43f82532a3` retains all
59 other assertions and explicitly reports initial zero contents as observations.
The original seventy-assertion fixture is retained to show the old stronger
SpiritBoot behavior. The existing frozen portable benchmark already writes and
checks each page and makes no zero-content assumption, so its workload and ISO
do not change for subsequent comparisons.

A separate minimal candidate replaces only the two data `Take*Zero` calls
with `Take*Any`. It keeps page-table zeroing, the per-page PFN lock path,
rollback, ownership, pins, publication and free unchanged. Its ROM is
`342b530dd0dc87baf4bbaa79c2a958fb8b5e9f643aadda4b52c2db0b29ac6f2a`, assembled
source `77a1dbaed5cb8985f2a3e9e83d2eedff0d640354`. Host production-body testing
confirms no data zeroing work and unchanged functional/accounting results.
The public wrapper already fell back to uninitialized pool allocations, so
even the earlier public API did not guarantee zero contents for every success.

Complex, original SpiritBoot and the minimal candidate all pass the 59 common
assertions. Seven further alternating triplets retain the same portable ISO,
profile and runtime inputs. All 21 receipts, forty workloads, sample order,
checksums and per-BIOS clock frequencies validate. The counter frequencies are
3374488 Hz for both SpiritBoot images and 13500000 Hz for Complex; timings use
each image's reported frequency.

| SYSVA pages | Original median us | Raw-data median us | Complex median us | Raw change vs original |
| --- | ---: | ---: | ---: | ---: |
| 1 | 12.7797 | 10.7794 | 1.79630 | -15.65%, overlapping ranges |
| 16 | 54.9343 | 23.1517 | 9.88889 | -57.86%, separated ranges |
| 1024 | 2799.832 | 738.779 | 635.556 | -73.61%, separated ranges |
| 1025 | 2792.720 | 700.254 | 603.556 | -74.93%, separated ranges |
| 4096 | 11347.203 | 2867.694 | 2864.889 | -74.73%, separated ranges |

All four multi-page improvements occur in all seven comparisons. The 4096-page
raw/Complex median ratio is 1.001 with overlapping ranges; this is no claim of
equivalence. Small allocations remain slower than Complex. Across the entire
forty-workload table, raw versus original has four separated improvements,
36 overlapping ranges and no separated regressions. Raw versus Complex still
has 31 slower and nine overlapping ranges. Measured-body total medians are
1.52534 s original, 1.45143 s raw (-4.85%, overlapping ranges), and 0.151668 s
Complex. The total includes all fixed iterations/samples and does not predict
game loading or frame rate.

Two separate phase diagnostics bracket each PFN-lock hold with the internal
NT HAL PIT counter (1125000 Hz), distinct from the title PM timer,
then emit to UART after release. Both pass all 59 common assertions. Counts
match in all 25 allocation/free observations. The first one-page allocation
includes a page table: two locks, maximum 94 ticks (83.56 us) original and
98 ticks (87.11 us) raw. The global observed maxima come from the inherited
bulk rollback on a failing 66,281,472-byte request: 3403 ticks (3024.89 us)
original and 2988 ticks (2656.00 us) raw, with 16,140 acquisitions each. These
are one instrumented run per image; interrupts and measurement overhead may
affect maxima. No general lock-duration reduction is inferred. The exact
structural result is removal of data zeroing inside each existing lock,
without new reservation/return critical sections. All observations remain in
`native/lock-observations.csv`, including the cold PT and failure path.

Selected patch `0122b` contains the minimal data-call change, not the rejected
batch. The old zero-reuse guest retains 38 guarded dirty-reuse/neighbor/free
assertions; its sixteen SYSVA zero-content predicates become explicitly labeled
observations. Its host adapter now supplies dirty initial contents and retains
all cleanup, fault and IRQL checks. The internal 41-workload benchmark initializes
and verifies the SYSVA bytes it uses, retaining every workload and checksum.
The separate `vm-zero-reuse` fixture has 52 assertions for full-byte fresh and
dirty-decommit/recommit VM zeroing and neighbor preservation. Page-table zeroing
is unchanged and independently asserted by the production-body host fixture.
Complex, original SpiritBoot and the minimal raw candidate each pass all 52
VM assertions with pinned 64 MiB launch/fixture/executable/config identities.

## Relocation diagnostic correctness

The old `mm/contig/placement_probe` tried a one-MiB exact window surrounding a
VM or pool page, then merely commented on NULL/success/content. A window may
also contain unrelated immovable kernel frames; its failure does not establish
that the live VM/pool page itself cannot move.

The new fixture asks for exactly the observed four-KiB physical frame. It
requires success, a changed owner PA, all live bytes unchanged, the old frame
owned by the contiguous result, and isolation from writes to that old frame.
It also requires a physical pin to block relocation. Original SpiritBoot,
the batch candidate and Complex all passed those assertions. No relocation
implementation repair is justified by the earlier ambiguous diagnostic.

## Demand-mapped SYSVA validity

`NxMmIsAddressValid` still treated the entire SYSVA window as statically valid,
although the allocator demand-maps it and free clears its PTE. A host fixture
using both the production wrapper and the production ARM3 validity walker
failed on an unbacked SYSVA address. Removing only that unconditional TRUE
branch makes never-mapped, empty-PT, nonpresent and freed SYSVA addresses invalid,
while a live mapping and the existing static device aperture remain valid.

The separate validity candidate is ROM
`611a5081a23ae751a88613f4578cd894402b0b270969a1ba2c06eb5f8cd44e53`; its focused
fixture is `1bf359dd0eea72295246925b12509a62c0f8640192fed812e2073ed701b91741`.
Complex and the candidate pass all seven assertions; original SpiritBoot fails
the unused-page predicate and both freed-page predicates (three failures).
This fixes a real stale fast path; it
does not change the unrelated static KSEG0/device policy.

## Final MM sweep and limits

- Pinning already validates a full request before publishing physical pin state;
  alias counts, rollback, sticky overflow and deferred release constrain further
  loop fusion. Large spans still retranslate beyond the small stack cache. No
  speculative geometry or partial-publication change is included.
- VM commit/decommit and protection retain the region mutex, fresh-page rollback,
  owner-PTE bookkeeping and zero/MEM_NOZERO distinction. Reusing an ownerless
  SYSVA batch there would violate relocatability and needs a separate proof.
- Pool pages retain owner PTEs; zeroing/relocation and large PFN-lock loops are a
  distinct transaction. The pool audit owns any class/refill changes.
- Page-supply spill and relocation searches can still scan many PFNs under the
  lock. Replacing placement policy with list-head selection would alter measured
  ascending PA order. No unmeasured allocator-policy redesign is included.
- The original SYSVA rollback has an allocation-sized return critical section.
  The selected minimal raw-data path inherits it; no claim is made that this old
  stall is resolved. Its caller still holds the SYSVA spinlock across the whole
  transaction.
- Requested SYSVA protection was already ignored by the maintained allocator;
  host checks preserve this policy for RW/RO/noaccess inputs. Correctly implementing
  those flags needs independent ABI evidence and fault tests. No temporary
  permissions/restoration claim is made.

### Ranked follow-up work

These are investigation priorities, not additional accepted optimizations. The
ranking separates measured elapsed time from source work counts.

1. **Profile and qualify warm, small SYSVA invalidation.** Raw `sysva-1` still
   measures 10.7794 us versus Complex 1.7963 us (about 6.0 times), for the identical
   allocation/write/check/free body. The first overall call can create a PT;
   subsequent pairs reuse that retained PT. A warm allocation at the aperture base reads
   one PDE and one PTE to find its hole, takes one data PFN, and writes one PTE.
   Free clears one PTE and returns one PFN. The pair acquires the SYSVA lock twice,
   acquires the PFN lock twice, and reloads CR3 twice. It performs no data zeroing.
   A successful aperture allocation returns directly through the public wrapper,
   without visiting the pool fallback. The unchanged benchmark has no retained
   SYSVA allocation between pairs. These facts make a large VA scan or routine
   pool fallback a poor explanation of this particular warm gap. They do not
   attribute the gap between lock overhead, CR3 reloads and emulator execution.
   First add observable per-phase counters that report the actual internal QPC
   frequency. Then evaluate an existing-PT small-span `invlpg` path separately
   from allocation batching, against cold/new-PT, stale mappings, PDE crossing,
   physical pins and interleaved reuse. Full CR3 reloads may have different costs
   on hardware; a native emulator result alone cannot select the hardware policy.
2. **Reduce pathological failure work and separately bound shared-lock returns.**
   The failed 66,281,472-byte request performs 16,140 PFN lock acquisitions in the
   instrumented run, followed by the allocation-sized rollback return scope. Its
   raw maximum is 2,988 internal ticks (2,656 us). Normal free already uses one
   `Return` per PFN lock; this maximum does not establish a 3 ms normal-free scope.
   The outer SYSVA spinlock remains held throughout allocation, free and rollback.
   Merely splitting PFN returns preserves DISPATCH_LEVEL under that outer lock and
   cannot establish a scheduler or DPC latency improvement. Domain-aware failure
   preflight and bounded returns should be isolated experiments, preserving
   retained PTs, title capacity, persistent frames, deferred pins, order and the
   public pool retry. The diagnostic scope covers SYSVA; it does not time the
   subsequent public fallback or its empty-bucket reclaim/retry. Any claim about
   shortening the entire elevated-IRQL interval also needs a proof for the outer
   reservation/publication lifetime.
3. **Measure fragmented SYSVA first-fit before adding occupancy metadata.** The
   production-helper fixture below confirms one PDE/PTE read for the warm one-page
   case, 4,096 of each behind 4,095 occupied pages, and 16,384 of each for an
   alternating free/occupied aperture that has no two-page hole. Entire unbacked
   PTs already skip 1,024 VAs: a full empty aperture needs only sixteen PDE reads.
   A word scan or occupancy summary could help fragmented, backed PTs, but must
   preserve first-fit addresses and authoritative PTE state under the same lock.
   No captured title fragmentation distribution justifies another resident index.
4. **Fuse safe pin translation work before enlarging the stack cache.** A valid
   lock of more than 64 pages calls validity once and physical translation twice
   per page; a span up to 64 pages uses the retained PFN cache and translates only
   once. A 4,096-page lock therefore makes 4,096 validity and 8,192 physical
   translation calls while holding one PFN lock. Unlock can avoid the second
   translation pass when no deferred release is needed; rejected requests and
   aliased deferred release need their restore/replay logic. A combined checked
   PDE/PTE walker is a candidate for independent tests. Increasing the 256-byte
   cache to 4,096 PFNs would consume 16 KiB of kernel stack and is not a sensible
   default. Preserve complete request validation, aliases, overflow and deferred
   release before attempting fewer passes.
5. **Keep default VM and page-table zeroing as a separate transaction.** The raw
   SYSVA result cannot justify removing VM zeroing: all 52 default VM zero/reuse
   assertions pass on Complex, baseline and raw candidate. VM fresh-page commit
   zeroes under its per-page PFN scope, publishes an owner PTE for relocation, and
   makes another pass to clear fresh markers; rollback drops only this call's
   fresh pages. Moving zeroing outside that scope needs private-frame, live-alias,
   temporary permission and publication proofs. PT pages must remain entirely
   zero before their PDE is published. The rejected batch's reduced transition
   count produced no throughput gain, so a similar count reduction is not enough
   to accept a VM change.

The helper read counter executes the extracted production function and wraps
only its PDE/PTE reads. It asserts all expected addresses and counts for eight
states. Run `evidence/sysva-bounded-20261013/count-hole-work.py SOURCE_ROOT OUT`;
the stored [work-count receipt](evidence/sysva-bounded-20261013/hole-work.json)
pins the unchanged helper and complete SYSVA file hashes. These are deterministic
host work counts, not native timings or a title workload trace.

### Storage and resident-memory accounting

The release64 ROM layout already executes immutable kernel spans from flash and
decompresses the prepared mutable image directly into its final RAM location;
there is no second whole PE output copy to remove. A denser XZ payload changes
flash size and decode work, not the mutable resident pages. Its one-shot decoder
arena is 48 KiB inside the permanently reserved 128 KiB release64 bootstrap range.
Those 32 pages protect persistent title contents from the next reset's early
writes. Shrinking that range requires measured maximum loader/decoder workspace
and cold/warm-reset persistence coverage; simply donating the arena after boot
would violate that lifetime rule.

The supply stores four bytes of links/owner state plus two bytes of physical pin
state per PFN: 96 KiB (24 pages) at 64 MiB, 192 KiB (48 pages) at 128 MiB. Pool
run lengths and VA bitmap add 8,704 bytes, allocated as three boot pages. Checked
pool free-attribution adds 16,384 bytes, making that metadata seven pages. Thus
these two boot-carved structures alone use 108/204 KiB in release64/128 and
124/220 KiB in checked64/128, in addition to image RAM and other live structures.
The normal pool page-state array is another 4,096 bytes already included in
image BSS. SYSVA PTs are lazy and retained: at most sixteen pages (64 KiB) for
the 64 MiB aperture. Reclaiming empty PTs would trade those frames against repeated
PT zeroing and self-map/TLB lifetime work, and needs its own sparse-lifetime proof.

The hot PFN fields already share free-list and owner encoding, and the full
16-bit pin word is used by nested counts, sticky overflow and deferred return.
General compression of this frequently mutated state is not a measured low-risk
improvement. The image-only totals below intentionally exclude these boot-carved
structures and demand-mapped PTs; they are not total firmware resident RAM.

Selected raw+validity release64 ROM
`d77cb49169679c6320829c5441cc95ab05450d5638855b35bfc69058eeb67c93`, source
`1a9a1d1f6c627c430d39998b880b3bbf3fe1b6d0`, retains 14 permanent image RAM pages
(56 KiB), identical to baseline. The rejected batch adds 64 bytes of transient
PFNs and no permanent metadata; the selected path adds neither. This is static
image accounting, not measured free runtime RAM. The final composed release
needs its own qualification and source pin after other independent changes.

Relevant existing fixtures passed: live zero-alias guard; 18,190 relocation
preflight cases; generic relocation destinations; sixteen GPU-instance cases
and VM teardown interleavings; nine MDL-pin assertions; zero-reuse success and
fault-injection cases. Product host suite: 134 tests, three expected skips.
64/128 MiB release and 64 MiB checked builds succeeded for batch+validity.
The selected raw+validity source also builds all four release/checked 64/128 MiB
profiles. Static permanent image RAM is unchanged in each: 56 KiB release64,
428 KiB release128, and 664 KiB checked64/128. The existing ROM64 CRC/layout
analyzer rejects non-ROM profiles at its NXIR-magic assertion; the separate
profile-aware PE audit handles those three profiles. It does not claim a ROM
span/CRC check for images that do not use ROM-backed kernel sections.
Physical Xbox and gameplay/save/reset verification remain outside this evidence.

The workflow's existing hardcoded source pin is owned by final combined
integration. It must be refreshed for the composed source before its CI gate;
the independent source identity above is not the final combined identity.

## Reproduction

The evidence directory is `docs/optimization/evidence/sysva-bounded-20261013/`.
The exact frozen portable source and native receipts are required; run
`native/analyze.py RESULTS PORTABLE_MAIN OUTPUT` to validate them before reading
`workloads.csv`. `native/analyze-raw.py RESULTS OUTPUT` validates the seven
triplets and emits all forty rows for all three comparisons.
`native/analyze-lock.py RESULTS OUTPUT` validates the separate PIT-clock
observations. `tests/host/system-va-raw/check.py OUTPUT --source-root SOURCE`
executes the selected real production bodies, including page-table zeroing,
pins, competition and rollback; `check-validity.py OUTPUT` executes both actual
validity wrappers. The rejected initial batch snapshot and its original build
receipt remain under `rejected/`; that patch is absent from the selected lock.

The source-stage artifact is not its pristine Roswell HEAD: assembled changes
are staged. Reproduce using the maintained ordered patches and pinned lock,
or the actual assembled filesystem; do not read pristine HEAD as the product.

## Accepted warm-small follow-up, 2026-10-16

Patch 0154 addresses the warm one-page gap identified above without reviving
the rejected zeroing batch. Ranges of one through four pages invalidate each
changed virtual address locally; larger mappings keep the global CR3 reload.
The release64 A/B/B/A workload reduces 8,388,608 verified operations per arm
from a 10.689900-second two-run mean to 1.584932 seconds, an 85.1736% reduction,
with identical checksums. The production-body fixture covers both memory
profiles, rollback, PDE crossings, frame-return ordering and the unchanged
large-range policy. Exact sources, requests and raw serial logs are retained in
[`../performance/evidence/sysva-local-invalidation-20261016/`](../performance/evidence/sysva-local-invalidation-20261016/).
