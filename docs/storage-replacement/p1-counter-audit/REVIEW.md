# Bounded P1 counter and simultaneous pool peak audit

The inspected product has no qualified complete collector for the five frozen
private structural counters or storage-owned aggregate peak. The public recorder
explicitly returns private_structural_counters=None. Its structural coverage
artifact says not_yet_captured. The comparator validates supplied actual evidence;
it cannot create that evidence. Existing pool_native.py/pool_audit.py analyze
previous pool-allocator checkpoints and are not P1 workload-window collectors.
Keep otherwise qualified untraced timing usable; combined P1 remains open.

## What can be reused now

* build_firmware already accepts pool_audit=True and selects both NXK_POOL_CENSUS
  and NXK_POOL_AUDIT. Use a new release64 diagnostic legacy-reference output; the
  selected exact untraced reference remains pool_audit=False. Bind the diagnostic
  source/patch/header/compiler/kernel/ROM and collector hashes before capture.
* Pool census records actual allocator allocation/free events, per-tag/bin/domain
  live allocation counts/peaks, global bin counts, bucket-page current/peak and
  explicit overflow/miss/saturation counters. It is preallocated diagnostic state.
  Its header requires reading only while the guest is stopped, with an even stable
  sequence. One-in-64 lifetime sampling is not complete allocation-lifetime proof.
* Primary storage ISR entries already increment the owned IDE bridge's
  IdexChannelObject.InterruptObject.ServiceCount before dispatching its virtual
  callback when the hardware handler/context exist. IdexChannelObject is exported
  data ordinal 357 and is retained in the selected unstripped kernel. A diagnostic
  fixture can snapshot this existing field around its actual workload without a
  new kernel counter. Qualify actual primary route/handler continuity, public ABI
  layout, wrap/reset behavior and the issue-to-consumer-ready brackets. This is
  primary connected ISR-entry count, not completed commands or useful interrupts.

Pool census can supply integrity-checked actual allocation deltas for unambiguously
owned keys. It does not classify a generic IRP/MDL tag as storage ownership, does
not retain exact bytes for each allocation and does not track the sum of selected
storage allocations at every event. Private bucket-page peak is pool-wide small
bucket backing, including empty retained pages; it excludes large allocations.
No existing field inspected here establishes total storage resident/peak bytes.

## Smallest diagnostic-only hooks

Use one newly owned fixed diagnostic record plus an address/lifetime ledger,
compiled out of ordinary release. Kernel/ATAPI sites below are the eligible measurement boundaries. FATX, XDVDFS
and PCIIDEX sites additionally identify observed event semantics; a measurement
edit there needs its own narrow root scope admission, which this audit does not
grant. No excluded class body change is needed or proposed. No implementation
has been written in this audit.

| Metric | Exact source boundary | Actual event and qualification requirement |
| --- | --- | --- |
| New pool allocations/frees | ntoskrnl/xb/mm/pool.c:419–435,523–546,598–613,652–678; existing poolcensus.c allocator hooks | Observe successful Ex pool allocation results, exact charged block/page extent, address and matching free. Failed allocation and lookaside checkout are distinct. Add explicit owner/context association; generic tags alone are insufficient. |
| Upper worker executions | vfatfs/misc.c:229–238,345–394 and rw.c:867–883; generic io/iomgr/iowork.c:13–30, ex/work.c:156–165 and fsrtl/stackovf.c:45–60,128–143 | Count each actual upper storage request executed by a worker, including every FATX overflow-loop iteration and stack-overflow/deferred execution. A queued item or worker callback can drain several requests, so generic callback count is only supporting telemetry until that relation is qualified. |
| Physical command attempts | retained pciidex/chipset/pata_io.c:850,873 | Count actual command-register issue events for ATA and ATAPI packet paths, including retries. ATA_WRITE is a channel abstraction, so the frozen method must bind the actual retained hardware/MMIO route. A StartRequest/SRB count is not this unit. Record command/direction/channel and accepted/rejected/retried context separately. |
| ISR entries | owned ntoskrnl/xb/ide.c:97–106, existing ServiceCount | Reuse actual connected-primary ISR counter; qualify counter width, no reset/wrap and runtime route. Polling, spurious entry, command and DMA completion are separate facts. Secondary/other routes require explicit coverage if present. |
| Bounce operations/bytes | owned ntoskrnl/xb/scattergather.c:99–105,194–207; admitted xdvdfs.c edge-buffer copy:814–827; HAL generic/dma.c SARCH_XBOX branch:2167 onward | Count actual explicit bounce-copy operations and bytes in required routes. Cache copies and PIO port transfers are not bounce operations. Xbox hardware SG avoids the generic slave/software-DMA copy branch. Any unreviewed additional class copy route remains ambiguous, not zero. |

For a kernel/ATAPI-only implementation, class-level copies/worker batching and
physical command-register issuance are not automatically covered by a generic
start/work-item hook. Bind actual executed routes or retain those metrics as
unknown. Extra source edits require a separate scoped measurement approval.

The I/O-manager allocation wrappers can provide explicit IRP/MDL lookaside
checkout/return records and distinguish them from underlying new pool calls.
IoAllocateMdl's lookaside-versus-pool split is visible in iomdl.c:42–63; analogous
IRP wrappers are in irp.c. Hooking wrappers must not count every successful checkout
as a new allocation. Driver/device/parent associations can enrich provenance but
must be measured and retained, not inferred from a public call total.

These sites give executable partial telemetry. Complete coverage still requires
an exact ownership/correspondence review. In particular, generic kernel allocation
tags and generic work-item callbacks have mixed ownership; retained class-private
worker batching/copy routes are not resolved by this audit. Do not expand to
excluded class expression or assert zero for those unknown routes. Use compiled
source attribution/actual driver/request association only where it is established;
mark unclassified events and missing routes as ambiguous and keep the gate open.
No complete source-owner map can be certified from the inspected counters alone.

## Aggregate high-water is a separate event-consistent quantity

For each actual selected storage allocation, retain its identity, owner, charged
extent and allocation/free ordering. Initialize the workload peak to the actual
storage live set at the start; update its current sum and peak on every ownership,
allocation and free event. Track setup-retained objects and large allocations,
not only objects created after BEGIN. A chronological event stream or a maintained
aggregate updated at the allocator boundary can do this; snapshots alone can miss
short overlapping lifetimes. Reject overflow, missed free, duplicate allocation,
unknown owner or ambiguous shared charge rather than defaulting any amount to zero.

Report requested live bytes, charged live block/page bytes and shared allocator
backing/slack separately under frozen rules. Pool bucket pages may contain several
tags; allocating a storage block does not give storage exclusive ownership of its
whole bucket. Generic IRP/MDL lookaside backing and borrowed/shared buffers require
an explicit predeclared ownership charge. A live block sum does not silently prove
all physical backing/resident storage. Diagnostic ledger/census memory and stack
must also be identified separately. Existing release P5 native footprint remains
unknown until this complete ownership/accounting contract is qualified.

Independently chosen numeric example: tag A has 1000 bytes live at one time and
returns to 0 before tag B reaches 1500. The aggregate peak is 1500, whereas sum of
per-tag peaks is 2500. If both are live simultaneously, aggregate peak can be 2500.
The same two individual peak values allow both histories; summing them cannot
choose the actual concurrent peak. Summing live values from one coherent snapshot
is a valid current total, but not a guaranteed peak between snapshots.

## Concrete next job, after root review

1. Freeze the counter-owner/coverage and aggregate charge rules before candidate
   values. Keep the existing frozen five units and case correspondence; implement
   only the diagnostic record/hooks/owner ledger, not replacement code. Resolve
   mixed-owner keys narrowly; any unresolved route explicitly sets incomplete
   coverage. Existing ISR is a first usable counter even before the complete ledger.
2. Build a separate 64 MiB release legacy-reference diagnostic via existing
   tools.firmware.build_firmware(..., variant='release', memory_mib=64,
   pool_audit=True, storage_backend='legacy-reference'). Pass the pinned Roswell
   input and frozen lock explicitly and use a new output directory. The return
   manifest must identify that diagnostic change; do not replace published ROM.
3. Prepare one healthy small-HDD case on Deck through the existing owned native
   runner/guard. Use a distinct process/overlay/job and declare debugging/tracing.
   Add two owned diagnostic fixture boundaries: after preparation/warmup immediately
   before first caller issue, and after last consumer-ready validation/APC/event
   drain. Stop/arm/snapshot through the declared debugger route at those boundaries.
   Serial poll arrival alone cannot establish exact guest operation boundaries.
4. Retain before/after records, event/owner ledger, complete coverage/loss counts,
   actual fixture request bytes/order/depth/cache preparation, successful terminal
   integrity and actual primary IRQ/command route proof. Counts and case joins
   remain actual observations; diagnostic times never become acceptance samples.
5. Independent review qualifies exact collector/source/build/method/route/workload
   correspondence/interference before that job runs. A diagnostic fixture or ROM
   change requires that qualification; larger diagnostic state may alter memory
   pressure/path selection and cannot be hand-waved away. Record its footprint.
6. If the smoke capture is complete, run the declared structural companions in
   scheduled healthy-case order separately on each host, without overlap with
   acceptance timing. Feed actual rows through storage_perf_compare's existing
   structural-results/evidence interface. Missing ownership/copy/worker coverage
   makes structural/combined P1 INCONCLUSIVE even if useful timing/counters exist.

This is a finite diagnostic implementation/capture path. There is no already
runnable full five-counter/native-storage-peak capture that can be promoted to
qualified evidence from the artifacts inspected here. The first executable job
can reuse the existing ISR counter and pool census, but complete P1 needs the
narrow owner-qualified hooks/ledger and review above. No native action, Git change,
replacement implementation or performance qualification was performed.
