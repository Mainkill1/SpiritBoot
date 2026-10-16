# nxstorage QD12 transition specification (v7)

This document is derived only from SpiritBoot's independently authored
`nxstorage` implementation, its tests, public NT I/O contracts, and the
measured Forza fixture. No legacy class-driver implementation body was used.

Evidence labels:

- **[contract]** public API/driver behavior or an existing SpiritBoot invariant.
- **[measured]** observed in the dedicated fixture or benchmark.
- **[inferred]** implementation reasoning that must remain backed by a test.

## Workload and failure

**[measured]** Forza sustains up to 12 asynchronous, noncached 4 KiB FATX reads
while streaming world data. A 16-slot disk pool admits that burst. **[measured]**
v1 reached fixture timeout with six reads outstanding; v2 timed out with five.
Both contained the read-completion early exit described below.

The v2 core represented all pump reentry with one Boolean `wake` and one
`cursor`. While submit C owned the pump, lower completion A set `wake=1` and
`cursor=A`; lower completion B then left `wake=1` and replaced `cursor=B`.
Submit C consumed the Boolean and selected B. After completing B, the read-only
early exit saw no new wake and ended the pump. A remained `active + done +
inflight` with no future event guaranteed to restart it. **[measured]**
`coalesced_completions_drain_every_runnable_slot` reproduces this exact
transition and fails on v2. Removing only that early exit makes it pass.

The error was therefore a missing transition:

`COMPLETE(read B) -> scan remaining active slots before PUMP_IDLE`.

A wake bit can say that work arrived; it cannot prove that all work published
under that bit was consumed. v7 retains bounded round-robin selection and
reaches idle only through a complete lock-held scan that finds no action.
Persistent slot state carries every runnable transition, so v7 has no
notification counter. An event does not change the cursor while another caller
owns the pump; only an idle-to-owned transition chooses a new starting slot.

## Objects and ownership

### Parent IRP

1. **[contract]** The caller owns the parent before dispatch.
2. Under the adapter lock, dispatch claims one inactive envelope and sets
   `active`, `dispatch_active`, and `parent`. **[inferred]**
3. Under the cancel spin lock, dispatch installs the cancel routine or latches
   preexisting cancellation. **[contract]**
4. The envelope pointer is published in `DriverContext[0]`. **[inferred]**
5. The parent remains borrowed until `port_complete` removes the cancel routine,
   publishes status/bytes, and invokes `IofCompleteRequest`. **[contract]**
6. The envelope is not reusable until completion returned and both
   `dispatch_active` and `cancel_active` are clear. **[inferred]** Tested by
   `completion_reentry_waits_for_lower_return_and_keeps_envelope_lease` and
   pthread completion reentry.

### Child IRP/SRB/MDL

1. One child IRP, SRB, sense buffer, and control MDL are preallocated per
   envelope. **[inferred]**
2. `port_prepare` fully rebuilds reusable packet state and publishes
   `packet_live` only after validation succeeds. **[contract]**
3. `port_submit` sets `submit_active` under the adapter lock before calling
   `IofCallDriver`. **[inferred]**
4. A completion inside that lower call captures the result but sets
   `result_deferred`; it does not drive core retirement. **[inferred]**
5. After `IofCallDriver` returns, submit clears `submit_active`, consumes at
   most one deferred terminal result, and reports it to the core. **[contract]**
6. `port_retire` clears `packet_live` only after the core consumes the terminal
   result. **[inferred]**
7. The same child cannot be reused until the enclosing lower call returned.
   **[contract]** Explicitly tested by the lower-call child reuse guard.

### Core slot and tokens

1. Admission pops one slot from an O(1) free list under the core lock.
   **[inferred]**
2. Recycled mutable state from `command` through the state flags is cleared;
   the request prefix is overwritten from the validated request and `free_next`
   is overwritten on the next release. **[inferred]** Layout/initialization tests and
   the sanitizer suites cover this reduced-clear boundary.
3. Generation increments on each reuse and never wraps. A slot at
   `UINT64_MAX` is retired permanently. **[contract]** Tested by
   `exhausted_generation_is_retired_from_free_list`.
4. Every lower command adds a monotonically increasing command sequence to
   `(slot,generation)`. **[contract]**
5. A callback is accepted only when slot, generation, command, active,
   inflight, prepared, and not-done all match. **[contract]** Duplicate/stale
   callback tests cover rejection.
6. Completion marks the slot inactive before calling the external parent
   completion, then returns the slot to the free list. **[inferred]** The
   generation and envelope lease prevent a stale callback from affecting the
   replacement request.

## Pump ownership and lock transitions

Only one logical pump mutates commands. **[contract]** All transport calls and
parent completions occur outside the core state lock. **[contract]**

### Admission

1. Validate without holding the core lock.
2. Acquire the core lock.
3. Reject quarantine, exhausted order, or empty free list.
4. Pop a slot, clear its recycled mutable state, then publish generation,
   order, the complete request value, active, and stack-local dispatch-result
   pointer.
5. If no pump exists, set `pumping=1`, set `cursor` to the admitted slot, and
   transfer ownership directly to this caller. **[inferred]**
6. If another caller owns the pump, preserve its cursor and mark the parent
   pending. Preserving the cursor prevents completion reentry into a just-freed
   slot from starving older eligible work.
7. Release the core lock.
8. The owner enters `run_pump`; a nonowner waits for its dispatch-result
   handshake. **[inferred]** Covered by inline, pthread, and reentry tests.

### Queue selection

1. Acquire the core lock.
2. Scan at most `count` slots beginning at `cursor`.
3. Advance cursor after every inspected slot.
4. Select exactly one action: `RETIRE`, `CANCEL`, `COMPLETE`, or `SEND`.
5. If command construction creates terminal state, release and rescan.
6. If a complete bounded scan finds no action, clear
   `pumping`, release the lock, and return. This is the only transition to
   `PUMP_IDLE`. **[inferred]**
7. Release the lock before executing the selected external action.

The targeted cursor reduces the common search distance. It is only a hint;
every idle decision still performs the bounded scan. **[inferred]**

### SEND

1. Call `prepare` without the core lock.
2. Reacquire the core lock and publish preparation failure if any.
3. If quarantine/cancel won during preparation, release the lock, retire the
   prepared packet, reacquire, and make the slot terminal.
4. Otherwise set `inflight=1`, `prepared=1`; release the lock. This is the lower
   ownership commit. **[contract]**
5. Call `submit` outside the lock. Adapter callback deferral remains active.
6. Reacquire the core lock. Mark pending when lower returned pending or no
   terminal report exists.
7. Release and continue scanning regardless of the lower return value. A SEND
   return never proves the whole device idle.
8. Admission and completion need no side-channel notification: their persistent
   slot state is visible to the next bounded scan. Only that scan may release
   pump ownership.

### Lower completion

1. Acquire the core lock.
2. Validate the full token/lifetime tuple.
3. Publish lower status, bytes, flags, and `done=1`.
4. If no pump exists, claim it and point cursor to the completed slot.
5. If another caller owns the pump, preserve its cursor. The published `done`
   state remains visible to the owner's next scan.
6. Release the lock.
7. The new owner runs the pump. A nonowner returns immediately.

**[measured]** The randomized native-shaped adapter test publishes bursts of
one to three older completions while another QD12 submit owns the pump, for
1,024 reads. The core fairness fixture also holds four asynchronous mixed reads
and writes, randomly completes lower commands, and replenishes the queue from a
1,024-operation stream. All operations submit and finish on v7.

### RETIRE and result interpretation

1. Call adapter retire outside the lock; lower ownership is now ended.
2. Acquire the core lock and interpret the captured result.
3. Add only verified bytes, reject overreport/short transfer, and apply cancel
   or quarantine precedence. **[contract]**
4. A frozen queue transitions to recovery instead of parent completion.
5. Successful write-through data transitions to sync; ordinary completed data
   transitions to terminal.
6. Set cursor back to this slot so its next phase is selected promptly.
7. Release and continue the bounded scan.

### COMPLETE

1. Under the core lock, snapshot parent/status/bytes and update a live
   stack-local dispatch result if present.
2. Clear active ownership and push a non-exhausted slot onto the free list.
3. Release the core lock.
4. Complete the parent through the adapter outside the lock.
5. Always continue the pump scan. v7 has neither a read-completion fast exit
   nor a pending-SEND idle exit.

Parent completion may synchronously dispatch a new request. It sees
`pumping=1`, preserves the owner cursor, marks its parent pending, and returns
to the owner. The admitted slot remains visible to the owner's round-robin scan.
**[inferred]** Covered by completion reentry, eligible-write fairness, and pthread
slot-reuse tests.

## Cancellation

1. Cancel routine latches cancellation under the adapter lock, snapshots a
   valid core handle if published, then releases the cancel spin lock.
2. `nx_cancel` validates `(slot,generation)` under the core lock.
3. It sets `cancelled`. If the pump is idle it claims ownership and points the
   cursor to the slot; otherwise it preserves the owner cursor. The `cancelled`
   state remains visible to the owner's next scan.
4. Before lower commit, the pump retires prepared state without submission.
5. After lower commit, exactly one `port.cancel` is sent; pages and parent stay
   live until lower terminal callback and retire.
6. Cancellation status wins, while verified bytes already transferred remain
   accounted. **[contract]** Covered by initial, preparation, committed,
   synchronous, and write-through cancellation tests.

## Barriers and durability

1. Reads do not wait behind flush/write-through barriers. **[contract]**
2. Later writes wait behind earlier flush/write-through requests.
3. A sync phase also waits for prior writes.
4. Data success for write-through transitions to a real sync command when cache
   capability is qualified.
5. Disabled cache keeps ordering but emits no unnecessary sync.
6. Unqualified cache fails before false durability is reported.
7. Completing a write/barrier always continues the bounded scan so newly
   unblocked work is selected. **[contract]** Covered by all durability tests.

## Queue freeze, recovery, and quarantine

1. A frozen lower result sets `recovery=1` after the original packet retires.
2. The next command for that slot is queue release with no data payload.
3. Parent completion waits for recovery terminal state.
4. Failed recovery sets device quarantine and converts otherwise successful
   requests to I/O error.
5. Quarantine claims an idle pump, cancels committed transports once, and terminally
   drains every nonrecovery slot.
6. Only a full no-action scan may end quarantine draining. **[contract]**
   Covered by bounded release, failed recovery, and quarantine waiter tests.

## Optical separation

Disk QD12 sizing and these hot-path changes do not change optical slot count or
control packet sequencing. Optical media epoch/capacity, TOC, verify, sense,
and recovery use their existing adapter control path and callback deferral.
**[contract]** Covered by optical control/media tests.

## Completion and APC boundary

`IofCompleteRequest` is the kernel completion boundary. User APC delivery is
outside nxstorage. **[contract]** nxstorage guarantees that status and byte
count are final, cancel routine is removed, child transport ownership ended,
and the parent is completed once. The Forza fixture measures caller issue to
APC entry, so missing core completion appears as outstanding work at warmup
rather than merely higher latency. **[measured]**

## Coalesced admission and fairness transitions

The v6 counter was removed after an independent state-machine audit established
that it did not authorize an action or an idle transition. Removing it produced
no new RED case: the unchanged core, pthread, and native-shaped adapter suites
all remained green. **[measured]** This is expected because every external
action returns to a bounded persistent-state scan and only a full no-action scan
can release pump ownership.

While submit A owns the pump, nested admissions B and C publish persistent active
state and preserve A's round-robin cursor. After A returns, the pump continues
until a full no-action scan. **[inferred]**
`coalesced_admissions_submit_every_runnable_slot` fails if SEND returns without
scanning all persistent runnable state.

A parent completion can re-admit a read into the slot just released while an
older write is already eligible elsewhere. v5 retargeted the cursor on every
reentry, so a bounded but continuously replenished hot-slot stream delayed the
write until replenishment stopped. **[measured]**
`completion_reentry_cannot_starve_eligible_write` fails on v5 and passes on v7:
the write reaches submit while unread replenishment remains.
`randomized_mixed_reentry_is_fair` then runs 1,024 read/write operations at QD4
with randomized lower completion order and verifies every admitted operation
reaches transport within the bounded queue window.

## Test map

- QD12 capacity: production adapter 12-pending-read test.
- 1024 randomized completion bursts: `randomized_qd12_bursts_complete_1024_reads`.
- Exact missing v2 completion transition: `coalesced_completions_drain_every_runnable_slot`.
- Coalesced nested admission transition: `coalesced_admissions_submit_every_runnable_slot`.
- Completion reentry versus older eligible write: `completion_reentry_cannot_starve_eligible_write`.
- Randomized QD4 mixed fairness: `randomized_mixed_reentry_is_fair` (1,024 operations).
- Child lower-call reuse fence: completion reentry adapter test.
- Slot generation retirement: exhausted-generation test.
- Stale/duplicate callback: duplicate-generation/segment tests.
- Pump/lifetime races: eight pthread ownership scenarios.
- Cancellation phases: core and adapter cancel groups.
- Freeze/recovery/quarantine: release and failed-recovery groups.
- Durability/barriers: write-through and flush groups.
- Optical separation: TOC/verify/capacity/media-generation groups.
- Resource bounds: production pool and initialization-unwind groups.

Native release qualification remains mandatory because host scheduling cannot
fully reproduce xemu's interrupt/DPC timing. **[inferred]**
