# Direct asynchronous FATX reads

SpiritBoot posts an ordinary asynchronous, noncached FATX read to a filesystem
worker even when its complete disk extent is already known. The worker waits
for child I/O before retiring the request. This adds scheduling and request
management work to streaming reads. An observation of the public IDE channel
callbacks on the same standalone request replay found that Complex started all
12,288 commands on the issuing thread; the earlier SpiritBoot build started
most commands on filesystem workers.

This change submits eligible requests directly from their issuing thread. It
improves the measured replay, but does **not** establish that Forza's delayed
scenery is fixed, nor does it yet match Complex's performance. The user's
earlier contiguous-allocation-extent candidate did not improve the game.

## Eligibility and lifetime

The new path applies only to ordinary asynchronous, noncached reads of regular
FATX files. A request must fit wholly within both file size and valid data, have
an aligned buffer and sufficient kernel stack, and map to one contiguous run.
Paging, volume, FAT, page-file, directory and synchronous requests retain their
existing paths. A canceled request, cached file, completed cleanup, resource
contention, recursive acquisition, allocation failure, or unsuccessful buffer
pin also retains the existing path.

The issuing thread acquires a fresh shared MainResource lease before examining
mutable file bounds or metadata. After it pins the buffer, it transfers this
single lease to a tagged, independently allocated completion context. That
context lives until the storage request actually completes, including error
and cancellation. Truncate and cleanup cannot alter the protected extent while
the request is active. Issuer termination alone does not release the lease.

The parent IRP goes to the existing storage stack, with its offset translated
and its lower FileObject cleared. The filesystem dispatcher relinquishes
completion ownership. The completion routine propagates pending state, releases
the tagged lease, and frees its context exactly once. It does not unlock or free
the I/O manager's MDL, substitute a file-object reference, or use the dispatcher
context after submission. The public return remains STATUS_PENDING even if the
lower driver completes immediately; lower status and byte count are preserved.

## Resident mapping and seek checkpoints

The mapper requests only resident FAT metadata and validates every consumed
link, including the outgoing link of the final requested cluster. It rejects
fragmentation within the requested run, invalid clusters, malformed geometry,
cache misses and mapping exceptions. A traversal is bounded to 8,192 clusters,
processed in batches of at most 256 links. Rejection falls back to the existing
worker path without issuing the direct read.

The mapper never requests metadata backing I/O. That is a narrower guarantee
than being strictly nonblocking: existing cache mutex acquisition and cache
descriptor allocation can still block.

An optional 128-byte checkpoint sidecar remembers validated positions in large
files. Its measured allocation occupies a 256-byte pool bucket; the existing
FCB remains in its original bucket. Allocation failure simply disables the
hint. MainResource and LastMutex protect publication, and resize/delete
invalidate the positions. The direct path does not trust the older, separately
published LastCluster hint. Checkpoints avoid repeated long prefix walks; they
do not bypass validation of the requested contiguous run.

The direct path restores the same noncached-read statistics as the worker path.
It changes no ATA wait, interrupt, timeout, DMA, cache-coherency, or title-memory
contract. Desktop builds retain their existing read path.

## Controlled performance evidence

The standalone replay uses two captured sequences of 1,024 world-file reads,
preserving offsets, lengths and buffer alignment. It verifies every dataset
against its previously recorded SHA-1 and requires exactly one APC per read.
Queue depths are 1, 4 and 12. Each sequence runs with normal memory and with
available memory brought to 900 pages; allocation and hashing are outside the
timed batches. Every process gets a separate HDD overlay and EEPROM copy.

An early software-framebuffer fixture introduced host rendering-lock waits.
The reported results below use the corrected GPU-backed fixture and the
original emulator, with tracing disabled. A separate owner-attribution control
confirmed that software-framebuffer upload waits no longer occur during this
workload. Instrumented attribution runs are not performance acceptance runs.

At depth 12 and 900 available pages, elapsed milliseconds per 1,024 requests were:

| Build | Dataset 0 | Dataset 1 | Comparison |
| --- | ---: | ---: | --- |
| Earlier extent candidate | 124.1–127.6 | 112.9–122.9 | Six-run extent/async1/Complex/Complex/async1/extent control |
| Direct-read prototype, without checkpoints | 80.5–90.1 | 77.7–79.0 | Same six-run control |
| Complex | 41.6–45.8 | 40.6–42.1 | Same six-run control |
| Direct-read prototype, with checkpoints | 77.9–80.6 | 75.7–78.5 | Separate Complex/async2/async2/Complex control |
| Complex | 45.6–47.2 | 43.5–44.9 | Same async2 control |

The first prototype also moves all 12,288 observed command starts onto the
issuer. Removing the worker round trip accounts for a useful measured
improvement. Checkpoints add a smaller improvement. The remaining gap is being
investigated separately; these intervals include scheduling and completion
interruptions and must not be described as exclusive CPU costs.

No game assets, reference firmware, or proprietary implementation code are
included. Comparison uses public APIs, public object layouts and public device
callbacks. This implementation was derived from owned source and behavioral
observations.

## Correctness coverage

Host tests execute the actual production functions with controlled external
services, rather than an independent implementation of the fast path:

- 106 VfatRead/completion checks cover delayed and immediate completions,
  errors, cancellation, lifetime, fallback eligibility and statistics.
- 178 resident-mapper checks cover exact translated offsets and start clusters,
  malformed links, fragmentation, mapping failures and bounded work.
- 20,795 checkpoint checks use independent fragmented maps, allocation failure,
  invalidation and high-offset cases.
- Five composed scenarios execute the real mapper, checkpoint helpers and
  VfatRead together. They check an earlier hint, a nonzero cluster offset,
  a multi-cluster read, endpoint reuse, a backward seek and invalidation.
  A mutant returning the wrong start cluster fails both mapper and composed
  tests. All existing FATX host tests also pass.

Native tests use the actual I/O manager and storage stack. The dedicated owned
FATX lifetime XBE passes 7,833 checks on each of Complex, the extent candidate,
and the direct-read candidate. All 1,116 ordinary reads return STATUS_PENDING.
It covers four simultaneous issuers on one handle; exact data, guards, IOSB and
APC identity; explicit-offset file-position preservation; issuer exit; and
close, truncate and delete while a read is observed pending. Repeated-read page
and pool counts stay flat. A QMP read throttle makes lifetime overlap observable
only in this test; it is not used in the performance replay or proposed as a
product setting.

The native probe does not identify which internal branch executed for each
request. Host branch coverage and native lifetime coverage establish different
parts of the evidence. Additional native probes pass 338 zero-IOSB/APC checks,
2,071 seek/mutation checks, and 16 broad API checks.

The lifetime test also found preexisting public thread-object discrepancies:
nxdk's ID and exit-code wrappers report incorrect values on both earlier and
candidate SpiritBoot builds. That is tracked separately. Final storage checks
use public waits, issuer identity and worker results while retaining the wrapper
diagnostics. The discrepancy is not attributed to this read change.

## Reproduction and limits

Build the pinned firmware using `scripts/build-firmware.py`. The firmware CI
workflow runs the new host tests against the exact assembled source in all four
64/128 MiB debug/release builds. See `tests/xbe/fatx-async-lifetime/README.md` for
the standalone native fixture. Native measurements here are on 64 MiB xemu;
physical Xbox qualification and game-level acceptance remain outstanding.

The provenance JSON beside this document records candidate, emulator and
fixture hashes, source trees, run identities and archive hashes. A test-only
packaging rebuild must reproduce the already qualified runtime ROM before it
can inherit the native results.
