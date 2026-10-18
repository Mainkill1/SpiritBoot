# Forza-shaped callback cadence fixture

A standalone release XBE for an A/B comparison of SpiritBoot and Complex. It
uses owned generated data and public APIs. It contains no title executable,
data, disassembly, or private kernel layout. The application opens only its
named private FATX file; it never opens the raw disk.

## Launch

Boot `forza-callback-cadence.iso` on a private writable Xbox HDD with a formatted
Partition1 (E:) and at least 8 MiB free. No selector file, optical data, title,
network access, or preparatory upload is needed. The fixture creates/overwrites
`E:\forza-callback-cadence-generated.tmp`, fills all 8 MiB with a deterministic
pattern, flushes and closes its synchronous writer, then reopens asynchronously
with `FILE_NO_INTERMEDIATE_BUFFERING`. The generated file is retained for reruns.

Capture COM1 at 115200 8N1. There is no graphical progress display. Allow at least
120 seconds; eight cases each run for at least ten guest performance-counter
seconds, plus setup and serial output. Host elapsed time may be longer. On
completion or failure, the XBE prints its final marker and requests SMC poweroff.
Use the same release xemu, HDD/EEPROM configuration and memory size for both
BIOSes. No QMP disk throttle or instrumentation is needed.

Successful output contains TAP `1..11`, eleven `ok` results, and:

- `FORZA-CADENCE-HANDOFF-END cases=40 failures=0`
- `FORZA-CADENCE-SEM-END cases=32 failures=0`
- Eight `FORZA-CADENCE-CASE` and matching `TIMING` records, IDs 0 through 7
- `FORZA-CADENCE-END failures=0`

An early final marker, timeout, nonzero failure count or absent final marker is
not a complete qualification. On timeout, caller buffers and handles remain
alive until poweroff; they are never recycled as though an IOSB poll were a
callback. Failure paths can leave the TAP plan incomplete intentionally.

## What runs

The handoff probe uses a separate issuer thread and a producer with a real
issuer handle. The issuer establishes base priority 8 and actual priority 10,
signals an owned public `KEVENT` with priority increment zero, and enters `KeDelayExecutionThread`. The equal-priority
producer queues a public user APC when it runs. A producer-ready handshake
confirms its priority setup before the issuer is created. Both thread exit
codes and all setup calls are checked. Timestamps identify whether
enqueue happened inside the first delay call or after it returned. No serial
output occurs in this interval. Eight repetitions run for each kind:

| Kind | Delay/control |
| --- | --- |
| 0 | UserMode, alertable, zero interval; equal-priority producer |
| 1 | UserMode, non-alertable, zero interval |
| 2 | UserMode, alertable, expired absolute interval 1 |
| 3 | User APC queued on issuer before zero alertable delay |
| 4 | Zero alertable delay; producer base priority 7 |

The first-return status/count/timestamps are observations for kinds 0, 2 and 4,
not an assumed compatibility rule. All cases require successful enqueue and
exactly one eventual APC on the issuer during a permitted alertable phase. Kind 1 forbids first-call delivery; kind 3 requires
first-call delivery and `STATUS_USER_APC`. Enqueue-return timestamps can follow
issuer preemption, so absence of an enqueue inside the first-call timestamps
is reported as not established rather than proof of no enqueue. A later blocking non-alertable delay
lets the producer run even if the first call does not hand off. Subsequent
alertable delays drain the APC before either thread handle is closed.

The 32 I/O semantic checks alternate 512-byte and 64 KiB requests. They submit
without an alertable poll, wait non-alertably for the completion event, spend
another 20 ms non-alertable, require zero callbacks, and then require exactly
one callback and `STATUS_USER_APC` at the first zero alertable poll. A further
alertable drain checks for a duplicate and must return success. The completion event is an observation of publication; the
extra interval gives completion/APC queuing time before this semantic check.

All I/O calls pass exported `NtUserIoApcDispatcher` as `NtReadFile`'s APC routine
and a `NTAPI (ULONG error, ULONG bytes, PVOID iosb)` completion as its context.
Each request checks the exact IOSB identity, issuer thread, callback count,
Win32 error, byte count, IOSB success/count, non-reentry and permitted callback
phase. Every byte is verified against its absolute generated-file offset;
full buffer prefix/tail and adjacent IOSB canaries must survive. Callback
observation, never IOSB polling, allows the next dependent request.

The sustained case order is:

| ID | Target free pages | Read bytes | Non-alertable cadence after an empty immediate poll |
| --- | ---: | ---: | ---: |
| 0 | 900 | 512 | tight polling |
| 1 | 900 | 512 | 33 ms |
| 2 | 900 | 65536 | tight polling |
| 3 | 900 | 65536 | 33 ms |
| 4 | 783 | 512 | tight polling |
| 5 | 783 | 512 | 33 ms |
| 6 | 783 | 65536 | tight polling |
| 7 | 783 | 65536 | 33 ms |

Each accepted read gets an immediate zero-timeout alertable poll. If incomplete,
frame cases use `KeDelayExecutionThread(UserMode,FALSE,-330000)` between further
zero alertable polls. Pressure is allocated only after all fixture storage and
file/event handles exist; the public page count must equal its requested target
at case entry. The final count is reported rather than silently rebalanced
inside the measured interval. This consumes available physical pages, not a
reproduction of a title allocator or streaming pool.

`CASE` reports all successful operations/bytes and elapsed counter ticks;
`TIMING` reports aggregate submit-return, submit-callback and last-poll-callback
ticks. `OP` logs the first 32 requests per case after timing ends. `HIST` bins
all callback latencies at one-millisecond resolution, with 127 ms as the
unbounded overflow bin. The counter frequency comes from
`KeQueryPerformanceFrequency`, not a guessed CPU speed.

## Analysis and limitations

```sh
python3 tests/xbe/forza-callback-cadence/analyze.py serial.log > summary.json
python3 -m unittest discover -s tests/xbe/forza-callback-cadence -p test_analyze.py
```

The analyzer rejects absent final markers, failed checks, incomplete case
matrices, cases shorter than ten seconds, duplicate cases/timings, byte-count
mismatches and incomplete histograms. All 40 unique handoff rows, 32 semantic rows and expected request
samples must be present with valid counts, statuses and timestamp ordering. It reports callback mean/max and p50/p95
bucket bounds, plus the handoff's observed ordering.

Native storage completion is not timestamped. `observed` is the first sampled
signaled-event time, and `ready_misses` counts polls after that observation that
still found no callback. The event can become signaled before APC queuing, so
this counter alone does not prove a missed eligible APC. The semantic test and
controlled peer enqueue provide separate ordering evidence.

The full oracle and buffer preparation happen between each request's callback
and the next submission. They affect end-to-end throughput; submit-to-callback
timings exclude them. Thus this is a dependent-request cadence and semantics
fixture, not a replica of title decompression, publication, pool management or
frame rendering. The cadence interval is a blocking non-alertable delay, not
CPU-bound frame work. Buffers are reused only after a callback and an additional
alertable drain. Cancellation and issuer-exit rundown are not exercised here;
the existing `fatx-async-lifetime` fixture covers those separately. No firmware
performance or compatibility claim follows from a successful compile alone.

## Release build

```sh
export NXDK_DIR=/home/codex/src/nxdk
export PATH="$NXDK_DIR/bin:/usr/lib/llvm-19/bin:$PATH"
make -B -C tests/xbe/forza-callback-cadence -j8
```

The Makefile uses `-O2 -mno-sse -mno-sse2`, with `-Werror` scoped to fixture
`main.c`. Rebuild dependencies (`-B`) when changing compiler safety flags.
The installed clang 19.1.7 falls in nxdk's warning range for
[LLVM issue 134607](https://github.com/llvm/llvm-project/issues/134607): an SSE1
target can receive SSE2 instructions during vector constant optimization.
Disabling SSE generation avoids that path for this integer-only fixture and
its rebuilt SDK dependencies. The final build still emits the SDK linker's
existing `.edata=.rdata` merge warning. No third-party code was copied into the
fixture or disassembled.

Artifact hashes (2026-10-17; native execution still required):

- XISO: `55698144b2efbc230356ee33decaa89b5e3c9db8c672ad2b5abc62c330f1da49`
- XBE: `aa106cef5733d15f75492bad31751446fde8c44b7ac67532963e3033edb81bb7`
