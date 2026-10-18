# Forza baseline request identity and submission cost

This buffered capture establishes which lower request starts during each sampled
Forza native read. All 498 selected calls use handle `0x42c`, have one direct
lower dispatch, one lifetime PATA start, one mapping-ready observation and a
successful matching callback. The selected file is independently identified as
[asynchronous, noncached HDD/FATX](../forza-budget-attribution-20261017/STORAGE-MEDIUM.md).
No selected call uses the filesystem partial-IRP fallback.

The capture does not establish a complete game fix or a private Complex queue
implementation. It supplies an identity check missing from the older nested
phase counts: every start inside a selected API interval belongs to that call's
own request. None belongs to an older queued request in this replay.

## Queue and hardware-start routine boundaries

| Selected lower path | Calls | Median native interval |
| --- | ---: | ---: |
| No queue-path return; own PATA start before native return | 407 | 176.7 us |
| Queue path returns pending; own PATA start before native return | 15 | 210.2 us |
| Queue path returns pending; own PATA start after native return | 76 | 58.3 us |

Thus Spirit does have a pending queue path. All 76 calls with no PATA start inside
the native interval subsequently start their own recorded child generation.
There are no other-only, mixed-own/other, or unresolved selected intervals.
PataStartIo entry means reaching that routine, not proof of successful ATA command
issue. The queue epilogue's pending result does not by itself exclude cancellation
or prove that a request remains queued indefinitely.

The requested length alone does not explain this partition:

| Bytes | No-queue/start-before median (n) | Queued/start-after median (n) |
| ---: | ---: | ---: |
| 512 | 178.4 us (162) | 58.0 us (54) |
| 43,520 | 153.4 us (36) | 67.05 us (4) |
| 65,536 | 217.1 us (32) | 83.2 us (8) |

For the 407 no-queue calls, the three disjoint intervals are:

| Population | Entry → lower bind median | Lower bind → PATA entry median | PATA entry → native return median |
| --- | ---: | ---: | ---: |
| All 407 | 89.9 us | 27.2 us | 57.4 us |
| 512 bytes, n=162 | 90.5 us | 27.3 us | 58.2 us |
| 65,536 bytes, n=32 | 130.15 us | 27.8 us | 57.55 us |

Each request's three intervals partition its measured native call. Their
population medians are not additive. The first span includes filesystem and
adapter work before lower dispatch; the middle spans lower dispatch to PATA
entry; the last includes the PATA routine and all remaining unwind, interrupts,
completion and scheduling work before return. It is not an isolated PATA body
measurement. The observations locate substantial remaining work before lower
bind and after PATA entry, without assigning exclusive CPU costs.

These are instrumented, differently situated requests, not controlled exclusive
cost differences. Median entry-to-lower-bind / lower-bind-to-return intervals are
89.9 / 84.8 us for the 407 no-queue calls, 37.2 / 166.0 us for the 15 queued calls
that start before return, and 36.55 / 21.5 us for the 76 that start later. Medians
of separate scopes need not add to the median whole call. These spans include
interrupts, scheduling and observation work.

## Whether the previous read had finished

The previous selected read's final child-completion entry falls:

| Relative to the current selected call | Calls |
| --- | ---: |
| Before current native entry | 381 |
| During current call, before its lower bind | 23 |
| During current call, after its lower bind | 17 |
| After current native return | 76 |
| No preceding selected read in this replay | 1 |

At native entry, 382 calls have zero **tracked started-but-not-child-completed**
generations and 116 have one. Before their own lower bind the counts are 405 and
93. Of those 93, 91 traverse the queue path; two start without that queue return
while the prior child's completion entry has not yet been observed.

This is not a hardware-tag occupancy counter. The owned lower path can release
a tag and start its next request before entering completion for the old child.
The two cases above show why substituting child-completion lifetime for tag
occupancy would give the wrong conclusion. Most immediate own-start calls
already follow a completed selected read before entry; only 23 show the preceding
completion moving across the pre-bind part of the current call.

Seven completion entries have no corresponding observed dispatch/root mapping;
they remain unassigned. Pre-replay and bypassing lifetimes are not reconstructed
by guessing from pointer values. All 537 observed PATA starts, including background
requests, do have matching recorded child/SRB generations.

## Filesystem mapping and visible completion

Of the selected calls, 374 have an extent-hit mapping-ready observation; 124
perform a validated mapping walk. All 124 walks succeed. Median inclusive mapper
time is 28.4 us, total 6,232.2 us, with a 2,277.7 us maximum in the first selected
read. That outlier walks only eight steps and has a 4,464.2 us whole native
interval. It cannot be described as exclusive CPU work.

Ninety-one walks take two steps; the maximum is 42. The source's much larger
possible walk bound is therefore not exercised by these samples. Successful
mapping-ready is recorded before user-buffer locking; the independently matched
direct dispatch proves that all 498 selected reads subsequently forward.

Every native call returns `STATUS_PENDING`. Every title IOSB begins with status
zero and information zero. At native return, 462 retain those sampled values;
36 contain the full requested byte count and have already crossed their matching
parent-completion entry. Those 36 are all 512-byte extent hits. Status remains
zero in both populations, so IOSB status alone cannot distinguish them. These
are ordinary title values, not controlled sentinels; unchanged samples cannot
prove that no write occurred. Parent-completion entry and completed IOSB-tail
publication are separate boundaries.

Together with the [fixed pump deadline](../forza-budget-attribution-20261017/README.md),
the observation explains why immediate lower-start work can consume submission
opportunities. It does not establish that deferring starts would preserve the
required semantics, identify all exclusive costs, or qualify a scenery fix.
Complex's internal request identity and storage medium remain unmeasured here.

## Validation and reproduction

The normal baseline boot precedes a verified empty `loadvm` monitor response;
the saved scene runs for the requested twelve seconds and is verified paused.
A normal exit flushes the buffer. The runner is verified idle afterward. The
capture has 4,646 events and zero overflow, failed reads, reentry, lost slots,
open APIs or open mapper scopes. Every recorded event falls within the replay
receipt interval because selection begins at the first matching title read.

```sh
python -m unittest discover -p 'test_*.py'
gcc -std=c11 -Wall -Wextra -Werror -fsyntax-only syntax-check.c
python analyze_identity.py spirit-identity.log replay-receipts.jsonl --output spirit-identity-analysis.json
python analyze_timeline.py spirit-identity.log replay-receipts.jsonl --output spirit-timeline.json
python verify_manifest.py
```

There are 26 synthetic tests, including queued older requests, callback-before-
return, child/SRB and IOSB reuse, split requests, VFAT partials, thread switches,
mapper initialization, receipt boundaries and malformed/incomplete captures.
The independent reviewer checked the exact owned ABI sites, generation joins
and mapper facts. The source-level observer and all analyzer output are retained.

`xemu-cumulative-observer.patch` now includes the complete observation helper,
declaration and translation bindings against the pinned public Mainkill1/xemu fork commit.
[Source reproduction](SOURCE-REPRODUCTION.md) provides clean application, exact
source-hash verification and the captured build configuration. The older
`stage.py` and `observer.patch` retain the incremental review history. Identity
mode selects twelve sites and bypasses the prior nine-phase timing probe. The
separately controlled RDTSC log flag must remain unset.
Events occupy a bounded 10 MiB host buffer; formatting and writing happen at exit.
No guest memory is changed by the observer. Instrumentation still perturbs work.

The established container build succeeded. A preceding host ninja invocation
failed before compilation because the build used container paths; it also
rewrote the newer ninja log, causing the container to rebuild 1,905 targets.
[The build receipt](build-receipt.json) preserves this failure and the final
executable hash. This was a diagnostic emulator build, not a firmware build.

[Capture provenance](capture-provenance.json) binds the baseline, executable,
source, input hashes, receipts and restored-scene identity. Receipt directories
and details are removed from this package. Only scalar observations, independent
observer/analyzer source, synthetic tests and hashes are included. RAM, firmware
and game bytes, disassembly, screenshots, private assets and credentials remain
excluded. No proprietary BIOS implementation was inspected. No firmware code or
commits were changed by this investigation.
