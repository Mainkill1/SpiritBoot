# Forza streaming submission budget attribution — 2026-10-17

The observed title stops its streaming submission pump when its elapsed-time
budget expires. Spirit spends more of that budget inside native asynchronous
read submissions in these replays, leaving room for fewer requests per productive
pump. The outstanding-request cap is not the limiting gate in either capture.
This identifies the caller's stopping condition and an inclusive API-cost
contribution; it does **not** identify an internal firmware routine or establish
that the measured API duration is disk waiting, CPU execution, or host scheduling.

## Measured behavior

The title's budget is **335,000 RDTSC ticks**, approximately **456.818 µs** at the
clock progression measured in the earlier value trace. The timer starts before
an initial zero-duration alertable delay. Setup, that delay, callbacks delivered
inside it, and subsequent submission work all consume the same elapsed budget.
Successful submissions increase the title's outstanding count; execution of the
title completion callback releases that count. The count limit is **512**.
The pump can also stop after finding no available work. A final alertable delay
occurs after the measured submission interval.

Only completed pumps whose recorded host-end falls between the resume receipt's
`EndedUtc` and pause receipt's `StartedUtc` are included below. Warmup and
pre-restore records are excluded. Exact nanosecond boundaries are in the analysis
JSON files. Both replay windows are about 12 seconds.

| Saved-scene replay observation | Complex | Spirit |
|---|---:|---:|
| Complete pumps | 291 | 315 |
| Budget exhausted at first check | 16 | 20 |
| Budget exhausted later | 167 | 295 |
| Empty-work exits | 108 | 0 |
| Outstanding-limit exits | 0 | 0 |
| Productive pumps | 117 | 294 |
| Native reads within pumps | 236 | 366 |
| Reads per productive pump, mean | 2.017 | 1.245 |
| Maximum observed start/end outstanding | 4 | 2 |
| Initial interval, productive-pump median | 103.7 µs | 140.5 µs |
| Inclusive read API time, weighted mean per read | 70.253 µs | 163.671 µs |
| Median of productive-pump mean read API time | 46.867 µs | 162.000 µs |

Every productive pump ended on elapsed budget in both captures. Higher inclusive
submission cost consumes more of the fixed budget; the title then exits instead
of filling its outstanding-request allowance. The initial interval also consumes
more time in the Spirit productive population, though its median difference is
smaller than the measured submission-cost difference.

The two restored scenes have different queued work and progress. Complex has
many empty-work exits; Spirit has none. Total reads across the windows therefore
must not be presented as a firmware throughput ranking. The probe counts every
native read at the observed title return callsite while a pump is active; it does
not record callback or file identity. Earlier callback-filtered observations
identified the world-streaming path, but that does not make every v11 request an
identical resource or cache state.

A request-length check supports, but does not remove those limitations: among
pumps containing exactly one read, 512-byte calls had median inclusive API times
of **68.35 µs (Complex, 16 samples)** and **163.3 µs (Spirit, 105 samples)**.
Conditioning on one-read pumps selects different populations, and file offset,
cache state, preparation work, and host scheduling remain uncontrolled.

## Timing and capture boundaries

The observer uses fixed buffers and flushes after emulator exit. It performs no
per-event formatting or host writes during gameplay. Observation hooks still add
work, so these are lower-interference measurements, not uninstrumented timings.

- `total_ns` spans pump entry through the exit decision, before the final delay.
- `initial_ns` includes setup and the complete initial alertable wrapper. It is
  not just kernel-delay time.
- `read_ns` sums inclusive native read-entry-to-return intervals.
- `wait_ns` sums inclusive kernel-delay-entry-to-title-return intervals.
- `callback_ns` measures completion callback bodies and overlaps the delay scope.
  It must not be added to `wait_ns` or `initial_ns`.
- Aggregate records do not preserve every read/wait/callback intersection.
  No exclusive stacked breakdown or CPU-only residual is inferred. The time
  outside observed APIs can include title processing, other kernel work,
  interrupts, emulation overhead, and host scheduling.

Both capture headers match their row counts and report zero overflow and pump
reentry. All spans are closed. Within the selected rows, the initial interval
never exceeds total, delay duration never exceeds initial duration, and callback
duration never exceeds delay duration. These checks establish consistency, not
proof of every nested intersection. The observer uses a single open flag per
scope and cannot detect all possible nested same-kind API calls.

Only host-end is captured. The analyzer reports possible start-boundary overlap
using `host_end - total_ns` as an estimate; there are no such candidates in these
replays. That estimate assumes virtual and host clocks progress together during
a pump. Replay control timestamps are receipts, not exact guest instruction
boundaries. No timer reset or snapshot operation occurs inside the selected
measurement window.

The earlier v9 probe printed many events during gameplay. All phase-filtered v9
pumps hit the budget (217 Complex and 276 Spirit), and productive batches usually
contained one native read. Its timings are materially perturbed and are not a
natural performance baseline. Earlier full-run Spirit v9 counts included 1,016
warmup pumps and were explicitly withdrawn as replay comparisons. The buffered
v11 results supersede those performance interpretations.

## Reproduce and verify the evidence

From this directory, using Python 3:

```sh
python -m unittest -v test_analyze.py
python analyze.py complex-v11-budget.log complex-v11-receipts.jsonl --output complex-analysis.json
python analyze.py spirit-v11-budget.log spirit-v11-receipts.jsonl --output spirit-analysis.json
python verify_manifest.py
```

The tests cover precise fractional UTC parsing, inclusive phase endpoints,
possible start-boundary overlap, equality at the deadline, distinct exit causes,
overlapping timing scopes, missing/duplicate fields, malformed/truncated input,
capture loss, and unfinished spans. No game implementation is used as a test
oracle. The analyzer is offline and does not operate the runner.

`buffer-budget-probe.py` freezes the independently authored v11 observer and its
translation-hook insertion. `observer-source.c.txt` exposes the exact C observer
literal for review. The script was applied to an already instrumented local xemu
checkout, not a pristine tree: it depends on `spirit_read32`, the diagnostic
helper entry point, and the insertion context. It is preserved source, **not a
standalone clean-tree build recipe**. `probe-provenance.json` records the xemu
base revision and exact frozen source hashes. Reproducing a capture additionally
requires the private title, preserved snapshots, compatible emulator build, and
its existing diagnostic harness; none is embedded here.

## Provenance and package contents

This is a spec/verification evidence package under the repository's
[storage provenance protocol](../../../storage-replacement/PROVENANCE.md).
An isolated investigator privately examined the user-supplied title's runtime
caller to establish observable conditions and measurement boundaries. Only
original behavioral conclusions, runtime scalar values, independently authored
observer/analyzer source, and synthetic log-parser tests are archived. No
proprietary BIOS implementation was inspected for this work. This does not
certify that any participant is unexposed or that firmware provenance is cleared.

The value logs are retained unchanged. Receipt files remove runner directory
paths and detail fields; `receipt-lineage.json` preserves original receipt hashes.
Snapshot identities and supplied preservation hashes are in
`snapshot-metadata.json`; disk images, RAM, title bytes, disassembly, screenshots,
private assets, and credentials are excluded. Complex's preservation hash was
not locally available when this package was assembled and is explicitly unset.
`manifest.json` binds all archived artifacts by SHA-256.

No firmware code, firmware tests, configuration locks, or commits were changed
as part of this evidence archive.

## Additional discriminators

[Completion ordering](COMPLETION-ORDER.md) partitions matched v5 requests by
their parent-completion boundary relative to API return, with per-size controls.
[Existing ordinal evidence and a proposed public state experiment](PUBLIC-REQUEST-STATE-PROPOSAL.md)
separate early first-call and later-call costs without claiming hardware queue
identity. [Storage metadata](STORAGE-MEDIUM.md) establishes Spirit's HDD/FATX
medium while retaining the unknown Complex medium. The proposed fixture was
not implemented or run.

Run all archived parser and bounded-reader checks with
`python -m unittest discover -p 'test_*.py'`.
