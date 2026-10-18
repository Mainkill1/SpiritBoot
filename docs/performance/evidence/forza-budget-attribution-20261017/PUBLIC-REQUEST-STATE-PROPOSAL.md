# Separate public request-state and ordinal experiment

**Specification only; no fixture, firmware or native run is authorized by this
document.** Preserve the frozen initial-poll fixture and its evidence.

## Existing evidence already answers part of the question

The initial-poll fixture retains its first 64 operations and first 32 frames per
case. Joining operations to fully sampled frames gives the submission ordinal
and native duration. At the 450 µs setting:

| Pages | Firmware | First-call median (n) | Later-call median (n) |
|---:|---|---:|---:|
| 783 | baseline Spirit | 170.40 µs (14) | 45.93 µs (50) |
| 783 | candidate0168 | 156.76 µs (11) | 21.34 µs (53) |
| 783 | Complex | 33.48 µs (8) | 2.963 µs (56) |
| 900 | baseline Spirit | 150.54 µs (12) | 42.08 µs (49) |
| 900 | candidate0168 | 131.87 µs (9) | 24.74 µs (48) |
| 900 | Complex | 42.07 µs (8) | 2.963 µs (56) |

All these sampled frames have zero callback-unacknowledged requests immediately
after the initial poll. Complex's later 64 KiB requests also have a 2.963 µs
median (24 samples at each page target); cheap later calls are not merely an
artifact of the alternating 512-byte size. This is consistent with a cheap
queued-admission path once a burst is underway. It does **not** prove that
Complex defers lower-transport entry or that Spirit enters transport on every
request. Spirit also has cheaper later calls, so an unconditional eager-start
claim for every Spirit read is unsupported.

These are early prefix samples, not distributions over each complete ten-second
case. Partial final sampled frames are excluded. Request sizes, callback timing
and deadline censoring differ between ordinal populations. The raw samples have
no IOSB-at-return state. Their public outstanding count means callbacks not yet
acknowledged, not requests necessarily active on hardware. In particular, there
are no sampled frames with a positive `after_initial` count at 450 µs, so this
prefix cannot answer the sustained-outstanding comparison.

Reproduce these exploratory tables without a new run:

```sh
python analyze_initial_ordinals.py
```

The analyzer reads the existing owned serial logs in the neighboring
`forza-complex-cadence-20261017/initial-poll` archive and writes
`initial-poll-ordinals.json`. Its reconstructed outstanding counts use callback
timestamp ordering and are diagnostic estimates; a new fixture should record
its live counters directly.

## Smallest actionable new release fixture

Keep the generated file, public `NtReadFile` plus exported APC dispatcher route,
minimal callbacks, byte/canary oracle, page targets, and persistent-buffer
lifetime rules. Use 450 µs as the primary synthetic deadline and uncapped as a
control. Start the clock before the initial alertable poll and check before
every issue. Retain the cap of eight outstanding requests and eight issues,
with at least sixteen prepared storage slots. These are experimental controls,
not a new claim about the game's exact workload.

Add a per-request generation identifier, frame and ordinal, requested size,
entry/return timestamps, native return status, and the following scalar state:

1. Before each issue, initialize a never-active IOSB to a pending status and a
   recognizable Information sentinel, with surrounding canaries. Record the
   exact initial pair. A kernel reset to zero is a distinct observation, not
   completion. Do not change a live request's IOSB.
2. At the earliest practical point after native return, snapshot IOSB Status and
   Information, callback count and live callback-unacknowledged count. Retain the
   before/after sample timestamps so the finite observation window is explicit.
   Use single, ordered scalar observations, not a busy-wait completion loop.
3. Sample the same state before and after the first subsequent alertable poll.
   The callback records its timestamp, count, status, byte count and generation;
   it performs no I/O, validation, allocation or formatting.
4. Validate full bytes and canaries outside the measured interval. Reuse requires
   the exactly-once callback plus a later completed alertable fence, as in the
   frozen fixture. Callback completion during the initial poll cannot permit
   same-pump slot reuse. Retain storage on timeout.

Record all-call aggregate distributions, partitioned jointly by size, ordinal
and observed request state, rather than only the first 64 calls. A bounded
representative sample can supplement aggregates. Buffer telemetry in memory and
format only outside measured pumps. Report sampling and counter-read overhead.

Compare two explicitly labeled conditions:

- **Drained start:** the preceding requests have delivered callbacks, passed the
  later fence and full oracle before preparing the next burst.
- **Carryover start:** earlier requests remain callback-unacknowledged. Record
  their actual IOSB states after the initial poll; separate unpublished/pending
  state from completed-but-unacknowledged state. Do not call this hardware queue
  depth. If the initial poll drains everything, classify the trial as drained;
  do not manufacture a sustained-outstanding result.

For size control, include uniform-size bursts (512 bytes and 64 KiB), or rotate
the first request's size in a balanced schedule. Alternation alone confounds
ordinal and size when deadline stops change the next frame's starting parity.
Use the same prepared offsets across firmwares and repeated balanced run order.
Generated-file reseeding does not imply a cold cache; preserve that limitation.

## Discriminating outcomes and limits

A large Spirit gap even on drained, one-request, still-unpublished-at-return
calls supports excess immediate submission work independent of that request's
visible completion. A large first-versus-later contrast restricted to genuinely
unpublished queued requests supports separate idle-start and admission costs.
If the gap is concentrated in calls whose IOSB is newly terminal with the
expected byte count at the first sample, completion/publishing work is a likely
contributor. None of those observations alone identifies a private transport
routine or proves the device was not started before return.

A sentinel prevents mistaking stale successful IOSB data for new publication.
It does not make the two-field snapshot atomic and does not timestamp the exact
write. Completion may occur in the interval between API return and the first
sample. Report **visible at first post-return sample**, not “completed before
return.” Record inconsistent/transient pairs separately rather than coercing
them into completed or pending categories. Eventual correct bytes/callbacks do
not eliminate this boundary race.

If that boundary distinction remains actionable, the smallest follow-up is a
value-only, buffered observation of the public native return and matching parent
`IoCompleteRequest` boundary, using fixture-owned request IDs/IOSBs and the same
frozen release workload. This separates parent completion entry from later
callback delivery. Even that public boundary does not expose exact hardware
start or final IOSB publication timing. Directly claiming a lower-transport
queue-policy difference would require an additional independently justified
hardware-command observation, not inference from pending return status.

The first experiment can determine which public request-state population should
be optimized and whether a candidate improves pending-only admission without
merely shifting completion past the measurement boundary. It cannot by itself
qualify missing scenery or explain the game's unestablished storage medium.
