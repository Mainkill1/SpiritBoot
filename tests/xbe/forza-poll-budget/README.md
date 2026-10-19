# Initial-alertable-poll budget fixture

This separate owned release fixture starts a synthetic caller deadline
**before** its first zero-time alertable wait. It preserves the frozen
`forza-submit-bursts` fixture and artifacts. It is a generated-data timing
experiment; neither its budgets nor its caller loop are claimed to reproduce
Forza's implementation. The fixture has now passed repeated native release runs;
see the [fresh-boot validation protocol](VALIDATION.md) and its archived results.

Each pump executes the following contract:

1. Outside the clock, validate all eligible completed requests byte for byte,
   check buffer/IOSB canaries and callback status/count/identity, then prepare
   up to eight fresh requests with complemented expected bytes.
2. Start the clock and make one `KeDelayExecutionThread(UserMode, TRUE, zero)`
   call. Record its return timestamp, elapsed ticks and callback count.
3. In the caller, check the same deadline before every issue, including the
   first. If the initial poll exhausted it, issue zero reads. Otherwise issue
   one prepared `NtReadFile` request through `NtUserIoApcDispatcher`, record
   entry/return timestamps, and immediately perform another alertable poll.
   Continue until the deadline, eight issues or eight outstanding requests.
4. End the clock. Wait 33 ms non-alertably, checking `STATUS_SUCCESS`. There
   is no end-of-frame alertable poll: ready callbacks remain for the next
   timed initial poll. Repeat for at least ten seconds per case.

Callbacks only record completion metadata and mark their slot complete. They
perform no file I/O, byte validation or formatting. All serial formatting is
outside pumps. Native read-call durations and initial-wait duration are
separate, nonoverlapping components within the whole pump span; per-read polls
are a third component. Deadline-check timestamps are retained in OP samples,
so checks at or after the budget are rejected rather than confusing a later
issue timestamp with when the boundary was actually checked.

Sixteen persistent buffer/IOSB slots support at most eight outstanding reads
and eight issues per pump. This permits the initial poll to finish the previous
batch while eight different buffers are already prepared. Completed storage
cannot be retired until a later complete alertable call after its callback,
then every byte and canary must pass outside the pump before reuse. Initial
poll completion never permits immediate same-pump buffer reuse. This buffer
arrangement is an experimental control, not established title behavior.

The eight cases cross available-page targets 783 and 900 with synthetic budgets
250 µs, **450 µs**, 1 ms and uncapped. The 450 µs value is a parameter choice,
not a recovered title constant. Each read alternates 64 KiB data with an adjacent
512-byte request, using a generated private 8 MiB FATX file at
`E:\forza-poll-budget-generated.tmp`. No raw disk writes are made. Successful
requests receive exactly one callback on the issuer in an alertable phase.
On a stuck request, storage is retained until shutdown rather than reused.

The same seven public `MmQueryStatistics` Length observations are printed as
in the frozen burst fixture. Surrounding canaries are required; failure-status
field writes are observations. Available-page pressure is set after allocating
the buffer arena. This does not recreate title allocator decisions.

Build using configured nxdk (tested commit
`29638d0b001f179b73c3513489af10ddc2986216`) and clang 19.1.7:

```sh
NXDK_DIR=/home/codex/src/nxdk \
PATH=/home/codex/src/nxdk/bin:/usr/lib/llvm-19/bin:$PATH \
make -C tests/xbe/forza-poll-budget -j4
python3 -m unittest discover -s tests/xbe/forza-poll-budget -p test_analyze.py
python3 tests/xbe/forza-poll-budget/analyze.py SERIAL.log
```

Release flags are `-O2 -mno-sse -mno-sse2`; disabling both SIMD targets avoids
the documented clang 19 SSE1/SSE2 optimizer hazard. `-Werror` applies only to
owned `main.c`, not SDK sources. The existing linker merge warning is unchanged.
Launch the XISO with 64 MiB, writable E:, and COM1 serial capture at 115200 baud.
Allow 240 seconds for boot, generated-file setup and eight >=10-second cases.
The fixture powers off after completion and produces ten TAP checks. Expected
markers are `FORZA-PUMP-META`, seven `MM` rows, eight each of `CASE`/`TIMING`,
per-size and OP/FRAME samples, and `FORZA-PUMP-END failures=0`.

The analyzer requires all eight case records, seven query observations and
unique complete sample sets. It checks the initial-poll accounting, shared
budget, QD cap, byte totals, exactly-once callback counts, generated offsets,
slot-reuse timing and all firmware-reported oracle outcomes. The fixture
validates every payload; serial retains timing/count evidence, not payloads.
The tests include exhausted initial waits, invalid deadline-check timestamps,
missing records, invalid QD, early buffer reuse and canary failures.

The 33 ms interval blocks rather than doing CPU/GPU frame work. This controls
poll cadence but does not simulate rendering. Whole-case throughput includes
outside-pump preparation and the full oracle. Native storage completion is
not timestamped. A run passing this fixture does not establish a Forza world
streaming fix or performance acceptance result.

Frozen after independent review: ISO SHA256
`8d94b0c6fa4699de29959e0bdc5ddd63b6b518ea7c65fcf22cf4da9e1f9b4630`; XBE SHA256
`510c0706f2ad01ee76aede12e1fd5bc1999c346d0c7c35b98dafd9ddeae80e12`. The [release identity](release-identity.json) binds
source/analyzer hashes and the 24 passing analyzer regressions.
