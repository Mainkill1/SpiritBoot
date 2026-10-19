# Owned queue-only and hardware-start paths

The lower IDE driver already has a cheap queue-only submission route. The
native class adapter eagerly prepares a child request before discovering that
the lower device is busy. This locates specific avoidable-work candidates; it
does not establish a contract defect or a complete Forza fix.

Source references below are relative to the preserved baseline
`artifacts/halo-final-queued-release64/work-3y5us6t0/source`, tree
`84e1d572b5a3a4ae81c78c28a0855908a909acf1`, release BIOS
`add882b6f50e9c9ae49705bb8374be5646e44ed1b72f0e2eb4b77bdedeeaf296`.
Only owned source and numeric probe observations were used.

## Admission and actual hardware work

- `drivers/storage/class/nxstorage/native_adapter.c:782–805`: initialization
  gives the core four times the retained-envelope count and sets `data_limit`
  to that capacity: 64 for this build. `admit_waiting_requests`, line 885,
  admits FIFO parents until that limit, then calls `nx_start` unlocked. An
  ordinary eight-request burst therefore does not stop at the class FIFO.
  Each admitted request runs core command construction and child preparation
  before lower submission.
- `drivers/storage/ide/pciidex/fdo.c:473` sets PATA queue depth to one.
  `ide/atapi/pdo.c:797` initializes the device request bitmap from that depth;
  `ide/atapi/fdo.c:309–316` initializes the channel slot bitmap. The single
  device request tag and single channel slot are distinct admission gates.
- In `drivers/storage/ide/atapi/scsi.c:1392`, `AtaReqStartSrb` raises IRQL and
  locks the device queue. `AtaReqGetTagForRequest` (1244) checks frozen flags
  and free tags. If unavailable, `AtaReqDeviceQueueAddSrb` queues the SRB with
  cancellation handling and returns pending. It does not translate an ATA
  request, build DMA scatter/gather state or start hardware on this branch.
- A free tag selects a retained `ATA_REQUEST` (1276), then
  `AtaReqStartRequest` (1052) translates the SRB (999). Dispatch (940) must
  also obtain a channel slot; failure queues on the port and freezes the
  device for that slot. Success reaches `AtaReqSendRequest` (678), DMA/PIO
  preparation, and `AtaReqStartIo` (510). A port-busy condition can still
  defer the start. Otherwise the owned bridge calls `PataStartIo`
  (`ide/pciidex/chipset/pata_io.c:909`) to select/program the hardware command.
- `AtaReqCompleteRequest` (262) releases resources, the device tag (318), and
  channel slot (322), dispatches queued port work (356) and queued device work
  (404), **before** completing the old child IRP (426). Consequently the next
  queued command can incur translation and hardware-start work in a completion
  path rather than in its own original `NtReadFile` call.

Every actual command needs the appropriate translation, DMA/PIO setup and
hardware programming. Every API submission need not perform those stages
synchronously. An idle device normally starts immediately; an already occupied
device can retain the SRB and return cheaply. Longer public submissions may
allow the device to become idle before the caller issues its next read, causing
more immediate starts. That feedback is a hypothesis requiring identities,
not a conclusion from the aggregate phase counts.

## Reproduce the v12b distinction

```sh
python3 docs/performance/evidence/forza-native-submit-cost-20261017/analyze_queue_path.py
```

The script revalidates the archived observer/sites/log/receipt result, restricts
completed scopes to the saved replay window and world handle `0x42c`, and emits
[queue-path-analysis.json](queue-path-analysis.json). All 373 selected scopes
have one parent allocation, page pin, adapter submit, packet preparation, port
preparation and port submission. PATA start counts are 24 zero / 349 one.
DPC-retirement counts are 191 zero / 145 one / 37 two; pump counts are 253 one /
111 two / 9 three. Selected scopes have no bad, reentrant or open phase records.

| API-scope partition | Count | API median µs | Adapter | Pump | Port prepare | Packet prepare | Port submit | PATA |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| No observed PATA start, no DPC retirement | 22 | 117.25 | 67.4 | 50.1 | 19.3 | 7.4 | 8.5 | 0 |
| Observed PATA start, no DPC retirement | 169 | 259.7 | 160.2 | 125.6 | 25.4 | 10.9 | 69.2 | 27.6 |

These are instrumented inclusive elapsed scopes. Nested columns are not
additive and are not isolated CPU costs. The no-PATA group also has two scopes
with DPC retirement. Counts do not connect a `PataStartIo` to a particular child
IRP: a completion inside an API may start an earlier queued request. Conversely,
no observed start does not distinguish the device queue, port queue, or another
defer gate. All no-DPC rows above have IOSB information zero at return;
IOSB status zero alone does not prove completed I/O. This population is neither
all started calls nor a matched release-timing comparison with another BIOS.

The useful target is the remaining class work on the queue-only path, plus the
frequency of immediate hardware starts. Blindly changing class admission to one
is not justified: lower completion currently starts queued work before upper
completion, and an upper-only queue could introduce a hardware idle bubble.

## Smallest discriminating next capture

Record buffered numeric identities from parent/IOSB through envelope, child IRP
and SRB. At `AtaReqStartSrb`, record free tags, queue flags and the explicit
queue-versus-tag decision. At dispatch, record channel-slot success or deferral.
At PATA start and completion record child IRP and generation, separating the
current API's command from an older queued command. Join these with native
return IOSB information. Partition class-queued, device-queued, port-queued,
own-start, other-start and own-completion scopes, with DPC presence separately.
Use the generated burst fixture and retain idle-first versus later-call order.
Do not infer causality by subtracting overlapping scopes, hold high IRQL over
lower calls, or arbitrarily defer completion to manufacture a shorter API.

## Earlier core-lock coalescing experiment

The [rejected 2026-10-15 patch](../forza-map-pump-lock-rejected-20261015/rejected-pump-lock-candidate.patch)
carried the core lock across internal bookkeeping. For the ordinary first
pending submission, seven lock acquisitions became five by removing:

1. the unlock/relock between claiming pump ownership and the first slot scan;
2. the unlock/relock between post-submit pending bookkeeping and the next scan.

It also retained the lock from retirement result recording, prepare failure,
terminal-command construction failure, and post-retire cancellation/quarantine
bookkeeping into the next scan. Prepare, submit, retire, cancel and complete
transport callbacks remained unlocked. `mark_pending` was already called under
the core lock and remained there; the old README's “all port callbacks unlocked”
is too broad. Locked state updates and the final lock-held idle handoff remained.
Cancellation after prepare was checked before submit commitment; cancellation
after commitment still had to drain lower ownership. No callback-return value
was substituted for the lower terminal report.

The archived report says core/adapter, sanitizer, cancellation, recovery and
reentry gates passed; its included test asserts the pending lock count of five.
Those are empirical gates, not a proof that removing a PASSIVE-level handoff
preserves interrupt/DPC opportunity timing. A modern re-evaluation must explicitly
check reentry, inline completion, cancellation at prepare/commit, removal,
terminal failures, split/recovery commands, lost wakeups and unlocked callbacks.

Native evidence was **two candidate runs versus two queue-depth controls**,
each 16 passes × 1,024 reads, QD12, 900 pressure pages, release64 without debugger
or firmware tracing. This was the older public map-stream replay fixture ISO
`d095682b8691b0c43deae66530a7ccd553d8bc828b4fe4537469b86c463b4b6b`,
not the current initial-poll budget fixture. Candidate BIOS was
`0762122d7632fc9f6cf7e1f2a0f54f077318fd9e61a3621d64b8dd52cac722bf`.
All 32,768 candidate reads passed the fixture oracle.

The [summary](../forza-map-pump-lock-rejected-20261015/summary.json) computes
submit-sum **+1.9867%** from the mean of the two candidate run medians
(45,255,086.25 ticks) divided by the mean of the two control run medians
(44,373,524.5 ticks). APC batch changes **−0.9613%**. These are neither per-read
estimates nor confidence intervals; two trials per arm did not establish a
useful improvement. The host's reported stable million-cycle QD12 result
(about −10.2%) did not predict this native outcome. Raw logs are not in that
archive; their hashes/lengths and derived analyses are retained. Re-evaluating
the boundary change on the selected modern stack requires fresh qualification.
