# Forza missing-world investigation, 2026-10-17

Tracking: [SpiritBoot issue #250](https://github.com/Mainkill1/SpiritBoot/issues/250).
Status: delay localized; paired synthetic comparison recorded; real-title cause
and firmware fix remain open.

**Follow-up, 2026-10-17:** The [paired release Complex/SpiritBoot cadence
comparison](../forza-complex-cadence-20261017/README.md) finds matching tested APC
wait semantics. Complex also shows callback occupancy on the roughly 33 ms
frame scale under the controlled polling cadence. The roughly 30 ms interval
below is therefore not, by itself, evidence of a SpiritBoot-specific delivery
defect. SpiritBoot has higher small-read submission cost, but the fixture
results are mixed: its 64 KiB throughput and frame-cadence cases are similar
or faster. A separate eight-slot experiment now shows a large issue-rate gap
under explicitly synthetic 250/500 µs burst budgets, largely closing at 1 ms
or uncapped. The actual title budget remains unproven. No firmware fix or
real-title streaming improvement is claimed.

The operator drove a class-R Porsche and paused while multiple portions of the
world were missing. The 64 MB release BIOS was
`add882b6f50e9c9ae49705bb8374be5646e44ed1b72f0e2eb4b77bdedeeaf296`.
The preserved scene shows 115 MPH and race time 00:10.333. A private snapshot
named `forza-missing-world` preserves the position without more operator driving.

## What the captures establish

The largest measured interval for these world reads occurs after native storage
completion and before title callback delivery. The captured resource is
`FarmersLipShort.res`; the submit callsite is `0x0026741a`, the title thread is
`0xc1008c20`, the dispatcher is `0x8402695c`, and the title callback is
`0x001103e0`. These are bindings for this exact firmware/title combination.

| Capture / stage | Samples | Median | p95 | Maximum |
| --- | ---: | ---: | ---: | ---: |
| Human gameplay, native submit to completion | 430 | 0.284 ms | 0.702 ms | 4.174 ms |
| Human gameplay, completion to kernel I/O APC | 430 | 0.033 ms | 0.123 ms | 2.060 ms |
| Human gameplay, successive world-read issues | 429 | 29.810 ms | 35.595 ms | 87.880 ms |
| Restored-scene replay, native submit to completion | 803 | 0.371 ms | 0.724 ms | 1.499 ms |
| Replay, completion to title APC dispatcher | 803 | 30.108 ms | 34.931 ms | 90.360 ms |
| Replay, first subsequent alertable delay entry to dispatcher | 745 | 0.034 ms | 0.085 ms | 0.211 ms |
| Replay, dispatcher to actual title callback | 803 | 0.013 ms | 0.021 ms | 0.147 ms |

QEMU virtual-clock completion-to-dispatcher measurements agree with the host
clock: median 30.1089 ms, p95 34.9318 ms. These are diagnostic timings with
instrumentation overhead, not uninstrumented frame-rate or comparative speed
claims. The replay was allowed to proceed without new driving input and later
reached a wall; it is not a repeat of the original human driving route.

All 803 fully joined replay world reads returned `STATUS_PENDING`, completed
with success, and supplied the requested byte counts to the actual title
callback. None had multiple native submissions. This is status/count evidence;
it does not independently prove payload contents or that the title published
the corresponding scenery.

For 502 reads, the first alertable delay call after submission had a zero
64-bit interval and occurred before the read completed. The analyzer validates
both interval halves from the captured stack, rather than inferring zero from
the low word. Those polls cannot deliver an unfinished read's callback.

Between native completion and dispatcher entry, 745 reads had one observed
`KeDelayExecutionThread(UserMode, TRUE, ...)` entry and 58 had none. None had
two or more. The zero-entry cases may complete while a drain is already active;
entry probes alone do not establish that explanation. This audit does not show
a skipped eligible delay entry. It is not a complete audit of every possible
APC delivery point or wait implementation.

Example: a 65,536-byte request at offset `0x011aec00`, IOSB `0x0079b9f8`,
completes 0.270 ms after an immediate alertable poll. Its next alertable entry
is 32.406 ms after completion, and dispatcher entry follows 0.041 ms later.
This explains how a sub-millisecond storage operation can occupy a title
request slot for roughly a frame. It does not establish why another BIOS or
firmware revision might avoid that timing, or whether the title has another
publication/decompression bottleneck after the callback.

## Memory and queue evidence

The original boot-to-pause trace completed 12,207 native requests with success
and had zero outstanding native requests at the missing-world pause. It
observed no virtual or contiguous allocation failure at the instrumented
returns. Free physical pages reached 746 (2.914 MiB), with 783 (3.059 MiB) at
the pause. The replay's world-read submissions had a median of 783 free pages.

The original 361 FATX worker admissions had a median queue delay of 0.017 ms,
p95 0.025 ms and maximum 0.490 ms. There is no long FATX worker backlog in
this capture. The gameplay tail comprised 430 world reads totaling 1,640,448
bytes. The initial map load had substantially more concurrency and throughput;
it must not be used as a substitute for the in-race interval.

No `MmQueryStatistics` entry was seen in the replay window. This does not rule
out an earlier memory-budget decision, internal title allocator limits,
fragmentation, eviction or decompression work. A free-page count is not a
measurement of the title's available streaming pool. Memory pressure remains
an open causal question, although no failed allocation or stuck native read
was observed at this pause.

## Why the existing XBE did not settle this question

`tools/storage_io_long16/recorder.c::run_batch` repeatedly issues requests and
polls `KeDelayExecutionThread(UserMode, TRUE, zero)` in a tight loop. It does
not put a frame of non-alertable work between polls. Its direct C completion
routine also differs from the game's `NtUserIoApcDispatcher` route.

In this firmware, `IopCompleteRequest` selects UserMode APC delivery for that
dispatcher even though Xbox title code runs in ring 0. Other routines retain
the IRP's requestor-mode route. Therefore the benchmark's direct callback
must not be assumed to exercise the same queue as this title. Existing QD12
throughput results remain measurements of their recorded route; they do not
qualify this in-race title callback cadence.

The synthetic qualification requirements identified from this capture were:

1. Generated data with full byte and canary validation, using an isolated HDD.
2. The exported `NtUserIoApcDispatcher` and its real Win32-style callback ABI,
   including status, byte count, identity and exactly-once checks.
3. An immediate zero-timeout alertable poll followed by controlled
   non-alertable frame intervals, with dependent next reads issued only after
   callback observation. Include the frequent 512-byte reads and larger reads.
4. Separate tight-poll and frame-cadence cases, and paired memory budgets near
   the observed 783 pages and the previous 900-page fixture target.
5. Submission-return, native completion, user callback and next-request timing,
   with no callback fabricated from IOSB polling. Test non-alertable exclusion,
   next-alertable delivery, reentry, lifetime, cancellation and cleanup.
6. Sustained release runs followed by the preserved real-game scene. A change
   must reduce end-to-end title-visible latency while preserving data and APC
   ordering. Delivering callbacks before their permitted wait is not a fix.

The [standalone callback-cadence follow-up](../forza-complex-cadence-20261017/README.md)
now covers the generated-data oracle, title dispatcher route, sustained tight
and frame cadence, paired page targets, and controlled wait semantics. Native
completion timestamps, the full cancellation/lifetime matrix and a verified
real-title performance fix are not established by that follow-up. No firmware
code was changed for either capture or the paired baseline comparison.

## Reproduction and artifacts

`capture-manifest.json` identifies the product commit, xemu base, build options,
run IDs and private source-capture hashes. Exact runner requests, firmware/exe
hashes and `xemu.toml` accompany this report. The HDD is a new private overlay
of the previous SpiritBoot test HDD; it retains its save and cache state.
It is not a cold-HDD measurement, and no Complex EEPROM/profile was substituted.

The emulator was optimized with `-O2` and LTO with symbols retained; Meson's
buildtype label is `debug`, explicitly recorded in the manifest.
`XEMU_DEBUG_BUILD` was not enabled. Fixed-address TCG probes were used without
an instruction profiler. This diagnostic build is used to localize behavior;
ordinary release xemu remains required for a performance acceptance result.

`diagnostic-xemu.patch` includes all modified emulator source files used for
the diagnostic build, including the earlier inactive IDE/texture trace hooks.
Apply it to xemu commit `f3c528eeec86db32c9f96a932267105e83f77375`.
`probe-binding.json` binds PCs to BIOS hash and function/return sites. Do not
apply those addresses to another BIOS. Set `XEMU_SPIRIT_MENU_TRACE=1` and the
runner's `-d guest_errors -D ...` arguments as recorded. Build the existing
Windows cross configuration with the pinned toolchain tag
`ghcr.io/xemu-project/xemu-win64-toolchain-gcc:sha-2881edd`, using
`ninja -j8 qemu-system-i386w.exe` and an isolated writable LTO cache at
`/xemu-cache/lto`. The capture shim source is included; the runner's existing
`native-launch.exe` enters the live PowerShell desktop session.

For scene restore, boot normally until the frontend USB devices exist, issue
QMP `stop`, HMP `loadvm forza-missing-world`, then QMP `stop` again. Verify
`query-status` actually returns `paused`; a completed runner recipe is not
sufficient. CLI `-loadvm` failed because the frontend USB hub did not yet exist.
The original position was restored and verified paused after collection.

Recompute the published replay result from metadata-only events:

```sh
python3 tools/forza_live_latency.py \
  docs/performance/evidence/forza-live-latency-20261017/replay-events.jsonl.gz
python3 -m unittest discover -s tests/host -p test_forza_live_latency.py
```

The normalizer removes unrelated stack dereferences; no game RAM, executable
bytes, disassembly, screenshots, ISO, EEPROM or save data is included. Private
raw captures and the saved scene remain in the lab. Seven host regression
checks cover request-address reuse, duplicate callbacks, skipped-wait signals,
non-alertable exclusion, clock rewind, and the 64-bit interval check. They are
analyzer tests, not native firmware qualification.

The replay reports 131 IOSB reuses without a callback and two repeated native
submissions across all files, outside the selected complete world-read joins.
Boot/synchronous reads and capture boundaries are not fabricated into complete
callback lifetimes. All 803 selected world reads have one native submission,
one observed dispatcher delivery, and an actual successful title callback.

## Failed diagnostic attempts

After the original scene was saved, a GDB callback-breakpoint attempt produced
zero events and lost target/QMP access. The runner terminated the unresponsive
session. That attempt is excluded from timing evidence and is not classified
as a proven BIOS crash. Two CLI snapshot-start attempts exited before normal
execution because of the missing frontend USB hub. The successful callback
replay used runtime snapshot restore and no attached debugger.
