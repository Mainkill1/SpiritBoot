# Forza asynchronous FATX read path

## Selected state

The firmware lock ends at patch 0168. Patches 0172–0187 that changed the hot
read path are rejected. In particular, 0180–0184 caused an early PGR2 crash
without improving the reported Forza streamed-world load, and 0185–0187 failed
controlled release-build performance gates. No rejected path is present in a
release image.

Selected release64 identity:

| Field | Value |
| --- | --- |
| Assembled Roswell tree | `2716b75a7159254904b4c7a9282f2c51961ee510` |
| Firmware SHA-256 | `2d43d91ca5a4474a365e308b2117a642a94a2d7c7da6a3004409c267173680e6` |
| Last selected patch | `0168-coalesce-native-adapter-bookkeeping.patch` |

The selected state is a safe rollback point, not a claim that Forza streaming
is solved.

This work uses public I/O contracts, SpiritBoot-owned source and black-box
timing observations. No Complex implementation body was inspected or copied.

## Known behavior

The retained real-title traces show that the delayed scenery is not explained
by slow media completion alone:

| Observation | Result |
| --- | ---: |
| Native submit to completion, human run | 0.284 ms median |
| FATX worker admission | 0.017 ms median |
| Success/byte-count joins | 803 / 803 |
| Outstanding native requests at the missing-world pause | 0 |
| Free physical memory at that pause | 783 pages / 3.059 MiB |
| Successive world-read issues | 29.810 ms median |
| Completion to title APC dispatcher, replay | 30.108 ms median |
| Dispatcher arrival after the next alertable wait | 0.034 ms median |

Forza reads `FarmersLipShort.res` from FATX/HDD. Representative requests
complete below one millisecond, while the title commonly observes completion
on a later frame. A release trace measured a title submission pump near 456.8
microseconds. The black-box reference admitted about 2.017 reads per productive
pump and selected SpiritBoot about 1.245. The saved scene measured mean public
read-call cost near 70 microseconds for the reference and 164 microseconds for
SpiritBoot. These figures localize a submission-side difference, but do not
assign the cost to one function.

The user-visible failure requires normal driving with a fast car. Earlier
automated runs stopped at the grid with a D-class Civic, so they were useful
for crash and corruption screening but could not establish streamed-world
performance. A candidate must now pass an automated R-class route before any
manual qualification.

## Selected read path

1. `NtReadFile` references the file object, creates the parent IRP and direct
   I/O MDL, probes and locks pages, and records completion state.
2. FATX allocates its request context and tries `VfatTryAsyncRead` for an
   asynchronous noncached read.
3. The FATX fast path acquires the file resource, resolves the requested range
   through the seek cache and FAT cache, verifies a contiguous range, and sends
   the original IRP to nxstorage. Cold, fragmented or busy metadata uses the
   established posted-worker path.
4. `NxNativeAdapterSubmit` acquires a retained envelope, installs cancellation,
   enqueues the parent in FIFO order and admits it to the request core.
5. The request core validates and plans bounded commands. The retained child
   packet is prepared and sent through the ATA stack.
6. The IDE interrupt and completion DPC retire the lower command. Nxstorage
   publishes the exact lower status and byte count, completes the parent, and
   preserves frozen-queue recovery, quarantine, cancellation and removal
   ordering.
7. FATX releases the file resource. The I/O manager unlocks the MDL and queues
   the kernel and title APC completion work.

Patch 0168 only coalesces proven native-adapter bookkeeping lock handoffs. It
does not add a second planner, packet lifetime, completion path or delayed
admission protocol.

## Rejected paths

### 0172: wider IRP reset

Clearing a wider region in `IoInitializeIrp` repeatedly regressed the
900-page/250-microsecond workload by 4.67%. Mixed microbenchmarks did not
justify an all-I/O regression.

### 0173–0176: admission lock transfers

These candidates reduced synthetic lock handoffs. Their end-to-end Forza
results tied selected 0168, so the alternate ownership protocol was excluded.

### 0177–0179: FATX locking and deferred admission

Extent-lock coalescing showed no observable title improvement. Adapter-DPC and
FATX-worker admission variants were neutral or slower. They did not explain
the common read cost.

### 0180–0184: direct native read

The direct route duplicated planning, packet ownership, cancellation,
quarantine and removal state. Review found and repaired several lifetime gaps,
but the resulting firmware still crashed early in PGR2 and did not materially
improve Forza. The complete stack is rejected.

### 0185: three-read cohort

All four release Forza routes completed, but the candidate averaged 38.7405
seconds versus 38.3950 seconds for selected 0168: 0.90% slower.

### 0186: 12-read deferred window

The candidate delayed transport by two milliseconds. Candidate A measured
39.442 seconds, versus 39.313 and 38.788 seconds for adjacent controls. It was
0.33% and 1.69% slower, so Candidate B and title testing were stopped.

### 0187: inline-completion deferral

This candidate started the ordinary transport immediately and deferred only a
successful FATX read that completed while `IofCallDriver` remained active. It
passed its host ownership tests but targeted at most 36 of 498 observed reads.
In the first controlled release pair, weighted public read-call cost regressed
from 73.267 to 75.853 microseconds (+3.53%) while aggregate reads per second
changed from 155.343 to 155.456 (+0.07%). All eight long cases and data oracles
passed, but the hard performance gate rejected it. Candidate B and title runs
were stopped.

## Required next evidence

No further firmware change may be inferred from aggregate call cost. Release
instrumentation must attribute exclusive time across these boundaries:

- `NtReadFile` entry, object reference, IRP/MDL allocation, and page probe;
- FATX dispatch, resource acquisition, seek-cache lookup, and extent mapping;
- adapter envelope acquisition, FIFO admission, core planning, and packet prep;
- ATA dispatch/start and the return to the public API;
- interrupt or DPC work that preempts any measured segment.

The counters must also record extent hit/walk, queue depth, dynamic allocation,
free pages and completion-before-return. Results are aggregated in memory and
written after the route so event formatting cannot become the measured cost.
Tracing-on versus tracing-off release runs establish perturbation.

The release gate then uses fresh private overlays and an automated fast R-class
route on the default track. It rejects a candidate for any PGR2/Halo/DOA crash,
menu or payload corruption, read error, incomplete route, result within normal
variation, or performance regression of 0.5% or more. A performance candidate
must improve the repeated streamed-world metric by at least 3% or one second
and beat both adjacent controls.

## Evidence

- [0172–0176 submission cost investigation](evidence/forza-native-submit-cost-20261017/README.md)
- [0177 extent-lock experiment](evidence/forza-fatx-extent-lock-20261018/README.md)
- [0178–0179 deferred admission](evidence/forza-deferred-native-admission-20261018/README.md)
- [0180–0184 direct route](evidence/forza-direct-native-read-20261018/README.md)
- [0185 three-read cohort](evidence/forza-fatx-timer-batch-20261018/README.md)
- [0186 deferred window](evidence/forza-fatx-deferred-window-20261018/README.md)
- [0187 inline completion](evidence/forza-inline-fatx-completion-20261018/README.md)
