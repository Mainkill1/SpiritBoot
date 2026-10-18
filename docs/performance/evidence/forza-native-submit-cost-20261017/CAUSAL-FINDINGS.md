# Why Forza issues fewer streaming reads

The demonstrated failure mechanism is excessive time spent issuing reads within
a title-controlled deadline. It is not yet a complete attribution of every
microsecond or a qualified fix for missing scenery. The evidence below separates
the caller's actual exit condition, the firmware path that consumes the budget,
and changes whose effect has been measured on an independently generated workload.

## Caller behavior

The read-only title investigation identified a streaming pump whose timer begins
before its initial zero-duration alertable wait. Its observed budget is 335,000
title timer ticks, approximately 456.818 microseconds under the measured clock
conversion. The pump checks elapsed time between requests. Exhausting that
budget stops new submissions even while the observed title outstanding count
is below its limit. The
other observed exit gates are an empty work queue and an outstanding-request
limit of 512. The final alertable wait is outside the measured pump interval.

In the preserved-scene v11 comparison, neither firmware reached the outstanding
limit: observed maxima were four for Complex and two for SpiritBoot. Every
productive pump ended at its time limit. Complex issued 2.017 reads per
productive pump; SpiritBoot issued 1.245. The snapshots represent similar but
different scenes, so their total read counts do not establish a throughput
ranking. These observations establish that expensive request submission limits
further submissions in that pump, without a drive
returning bad data or an allocation failing at that exit gate.

Sources: [caller-budget evidence](../forza-budget-attribution-20261017/README.md)
and its checked scalar records. This does not rule out memory pressure elsewhere
in the game, nor prove the entire visible symptom is attributable to this pump.

## Firmware behavior

The baseline submission route enters the owned native adapter, reserves a
request envelope, admits a core slot, prepares the lower packet, calls the lower
driver, and reconciles pending/completed state before returning. The general
request engine dispatches adapter operations through a runtime callback table.
The normal retained, pending, non-cancelled read takes 16 adapter lock entries
in the baseline; candidate0168 reduces this to 14 without moving external calls
inside a lock.

Lock release lowers IRQL. If a software interrupt is pending, `KfLowerIrql`
dispatches it before returning. The lower device-completion DPC and adapter
completion DPC can therefore run while the title is still inside `NtReadFile`.
The active request pump may then retire and complete the request before the
original submission returns. An asynchronous request does not imply that its
submission call performs only queue insertion.

The submit-active and deferred-completion gates protect lower callback unwind
and child-packet reuse. Removing them, holding dispatch level across the entire
call, or forcing completion later would change behavior; none is justified by
the measured cost alone. The code-level chain and lock-site audit are in
[owned-submit-path.md](owned-submit-path.md).

The more heavily instrumented v12b replay locates substantial inclusive time in
adapter submission and the request pump. It also observes 191 completed reads
with no DPC retirement interval, whose median API duration is still 253.9 us.
This rules out observed DPC retirement as the whole cost; it does not exclude
completion work through other paths. The earlier matched request-lifecycle
trace separately distinguishes parent-completion entry before and after API
return, as recorded below.
Packet preparation accounts for only 3.76% of aggregate instrumented API time.
Those nested scopes include observer and emulation effects; they are not
exclusive CPU times or release-performance predictions. See
[owned phase evidence](../forza-budget-attribution-20261017/OWNED-PHASES.md).

In [the matched v5 request-lifecycle cohort](../forza-budget-attribution-20261017/COMPLETION-ORDER.md),
all selected reads return `STATUS_PENDING`. The matching parent-completion
entry occurs before API return for 77 of 493 Spirit reads and none of 236
Complex reads. Among calls whose parent completion is observed after return,
the instrumented API medians remain 173 us for Spirit and 31.5 us for Complex.
This separates a completion-overlap contribution from the remaining submission
penalty; other requests' completion work can still occur during those calls.

## Idle start versus queued admission

The owned lower ATA driver has one hardware request tag. If the tag is already
occupied, its submission path can enqueue the request and return pending. If
the tag is free, the call translates the command, allocates the hardware slot,
builds scatter/gather descriptors and enters `PataStartIo`. Lower completion
releases that tag and can start the next queued request before completing the
old child IRP. Therefore having requests already queued changes which public
call pays the hardware-start cost.

The class adapter performs its envelope, core-slot and packet preparation work
before reaching that lower queue. The v12b scopes show one adapter submission,
packet preparation and port submission in each of 373 selected game reads;
349 scopes include one PATA start and 24 include none. Scope counts are not
request identities: a completion interrupt can start another request during a
call. They must not be reported as 349 proven starts of the currently issued
request. The [owned queue-path audit](owned-queue-path.md) records the precise
source route and reproduces these partitions.

The existing release fixture's early, fully sampled 450 us frames expose a
matching public distinction. Complex's first-read median is 33–42 us; its later
reads are approximately 3 us, including later 64 KiB reads. Spirit0168's first
reads are 132–157 us and later reads 21–25 us. These prefix populations are
small and deadline-censored, not full-run distributions. They identify both
idle-start and subsequent admission cost as investigation targets, without
claiming a proven private Complex queue implementation. See
[the ordinal analysis and next discriminating test](../forza-budget-attribution-20261017/PUBLIC-REQUEST-STATE-PROPOSAL.md).

## Exact request identities in the preserved scene

A subsequent [identity capture](../forza-request-identity-20261017/README.md)
connects each native IOSB through the original IRP, adapter child IRP and SRB to
its own PATA start. The complete replay has 498 selected reads with no lost,
ambiguous or open observations. All have one direct filesystem-to-class dispatch
and one PATA start over their lifetime; none uses the filesystem worker/partial
IRP fallback. The optional partial-IRP edge is observed for unrelated I/O and is
not silently assigned to the title's selected reads.

| Selected request route | Calls | Median instrumented API duration |
| --- | ---: | ---: |
| No lower queue return; own drive start before API return | 407 | 176.7 us |
| Lower queue return, then own drive start before API return | 15 | 210.2 us |
| Lower queue return; own drive start after API return | 76 | 58.3 us |

No selected API interval starts an older request. The 76 cheap intervals are
confirmed queued submissions, rather than an inference from missing timing
scopes. All 498 calls return `STATUS_PENDING`; only 36 have matching parent
completion entry before API return and matching completed IOSB information.
Those 36 are 512-byte extent hits. The other calls remain expensive without
their own parent completion having entered before return.

The immediately previous selected child's completion precedes the next API
entry in 381 cases; it occurs during the next API before lower dispatch in 23,
after dispatch but before return in 17, and after return in 76. One call has no
prior selected read. Thus slower pre-dispatch work is not shown to drain an
otherwise occupied lower queue on every call: most observed submissions already
follow the previous child's completion. The lower driver releases its tag and
can start another command before completing that child, so child lifetime counts
must not be labeled exact hardware queue occupancy.

All 124 observed filesystem mapping attempts succeed. Ninety-one walk two FAT
entries, and the maximum walk is 42. Their inclusive median is 28.4 us; a single
2,277.7 us outlier occurs despite only eight steps. That outlier does not establish
CPU work proportional to chain length. Long walks or worker fallback do not
explain this replay's general submission penalty. Mapping and synchronization
still cost time, and this scene does not characterize every file layout.

This narrows the engineering target to the ordinary synchronous submission
route: public IRP/MDL setup, filesystem resource/mapping work, class admission and
packet preparation, lower command/DMA setup, hardware programming and return
bookkeeping. Completion overlap adds cost in a subset; it is not the whole
explanation. These instrumented intervals include observer and scheduling effects.
They identify routes and ordering, not exclusive CPU times or a qualified new
firmware speedup. The prior release fixture remains the performance acceptance
measurement.

### Preparation cost is also associated with inter-call spacing

[The controlled pre-bind analysis](../forza-request-identity-20261017/PREBIND-CONTROLS.md)
compares 512-byte extent hits with the same direct-start outcome and previous
selected child already completed. The 145 calls following gaps of at least
10 ms have median entry-to-bind cost 90.4 us; five nearby calls following gaps
of 100 us to 1 ms have median 38.3 us. Queued/start-later hits have median
36.45 us, but all follow short gaps and have different completion state.
Long-gap excess appears both before and after mapping-ready. It cannot be
attributed to a mapper miss or to the later lower-queue decision alone.

This is an observational association, with only five nearby direct controls.
Its mechanism is unresolved: extra executed work, interrupts, cache state and
emulator scheduling have not been distinguished. The next attribution must
compare executed paths within these state-controlled groups rather than assume
that the aggregate direct-versus-queued timing difference is one firmware cost.

## Controlled release evidence

The separate initial-poll fixture charges the first alertable poll to its
deadline, checks the deadline before every read, and issues generated 64 KiB
and 512-byte reads with byte, canary and callback verification. It uses the same
release xemu and frozen XISO across firmwares. The 450 us setting is a nearby
experimental budget, not a claim to reproduce the whole title.
The generated file is on FATX `E:`. Read-only metadata from the preserved
Spirit snapshot now establishes that world handle `0x42c` is a file on HDD
`HarddiskVolume3`, mounted as FATX16. This matches the broad medium/filesystem
class, but does not establish the same drive letter, partition, cache state or
file placement. Complex handle `0x1f8` remains of unknown medium; see the
[object and volume metadata evidence](../forza-budget-attribution-20261017/STORAGE-MEDIUM.md).

| Free pages | Baseline reads/s | 0168 reads/s | Complex reads/s | 0168 read-call mean | Complex read-call mean |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 783 | 135.354 | 145.623 | 200.800 | 77.670 us | 7.845 us |
| 900 | 135.522 | 150.030 | 201.356 | 75.633 us | 7.461 us |

All 24 cases across the three images pass their byte/callback oracle. Candidate
0168 improves this workload by 7.6–10.7% but still trails Complex by 25.5–27.5%.
The initial poll costs approximately 12–15 us per pump in all three variants;
it does not account for the large native-read-call gap. Longer-budget cases are
mixed and capped at eight issues per pump. Their similar rates are **not** proof
of equal maximum device bandwidth. This is one observation per image, with
repeats of the next isolated change recorded separately.

Source and reproduction:
[initial-poll release comparison](../forza-complex-cadence-20261017/initial-poll/README.md).

## Mistakes addressed and remaining proof

* The original engine scanned inactive slots and performed two redundant lock
  round trips on the ordinary retained submission path. The active-slot index
  and candidate0168 remove that work while retaining cancellation, completion,
  removal and ordering contracts. The repeated 0167 result is mixed; the single
  0168 initial-poll run measures a 7.6–10.7% gain over the original baseline.
* The production engine retains runtime port dispatch even though the native
  build has a fixed adapter implementation. Experimental0169 removed those
  indirect calls and passed host and native correctness, but its repeated
  release comparison did not establish a gain. It is not selected in the
  firmware stack. Fewer dispatch instructions did not demonstrate that this
  was the dominant cost; see [the experiment and decision](static-port-binding.md).
* Isolated candidate0170 removed two more core lock round trips (14 to 12
  adapter acquisitions), with host lifetime/reentry/removal gates passing. Four
  consecutive release runs did not establish a consistent gain at the primary
  450 us deadline. It remains unselected; the [complete paired comparison](../forza-complex-cadence-20261017/candidate0170/README.md) retains every case,
  including an unexplained 28.03% per-size read-cost regression. Reducing a
  counted operation is not sufficient evidence that it limits native loading.
* Experimental0171 applied `-O2` only to three owned submission translation
  units. Actual final linking inlined some helpers but added kernel lock-helper
  calls and 5,216 bytes of text. All 32 sustained release cases passed the
  generated-data/callback oracle, but the first pair's 450 us improvements
  reversed in the second pair at both memory levels. It remains unselected;
  see [compiled scope and shape](compiler-0171/README.md) and
  [all paired results](../forza-complex-cadence-20261017/candidate0171/README.md).
  These three rejected micro-optimizations require a return to dynamic path
  attribution before another dispatch, lock or compiler change.
* The old cadence benchmark began its budget after the initial poll. That did
  not match the title's budget boundary. The separate frozen initial-poll
  fixture corrects the experiment without rewriting earlier results.

The remaining task is to reduce the measured read-return cost with preserved
contracts, then qualify a fresh-boot Forza run. Restoring the old saved scene
restores the old kernel and cannot validate a new BIOS. No full-game resolution,
global memory-pressure exclusion, or 90%-of-workloads performance claim follows
from these results.
