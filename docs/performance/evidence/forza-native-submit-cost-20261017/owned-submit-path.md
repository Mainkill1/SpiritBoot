# Owned submission, completion and lock audit

This audit explains owned control flow, not a proven explanation of the entire
missing-world symptom. It uses the preserved baseline source at
`artifacts/halo-final-queued-release64/work-3y5us6t0/source` and its own linked
symbols/disassembly. Source line numbers below refer to that baseline unless
otherwise stated. No proprietary implementation is an input to the changes.

## Why completion can run before an asynchronous read returns

`native_adapter.c:256` acquires the adapter spinlock through `KfAcquireSpinLock`;
`:262` releases it through `KfReleaseSpinLock`. The owned HAL implementation
(`hal/halx86/generic/spinlock.c:66,81`) raises to dispatch level on entry and
lowers to the saved IRQL on release. `KfLowerIrql`, in
`hal/halx86/pic/pic.c:417`, tests pending software interrupts against the restored
IRQL and invokes the eligible software interrupt handler synchronously at
`:453`. Returning to passive level can therefore run pending DPC work before
the lock-release call itself returns. An entry already at dispatch level does
not gain that same DPC admission window on release.

`HalpDispatchInterruptHandler` (`pic.c:1204`) calls `KiDispatchInterrupt`.
That function (`ntoskrnl/ke/i386/thrdini.c:480`) drains pending DPC work on the
DPC stack. This retains the interrupted thread identity; it need not mean a
worker thread ran. `KiRetireDpcList` (`ntoskrnl/ke/dpc.c:567`) loops over queued
routines and invokes them at `:642`. A DPC queued by another DPC can run in the
same drain pass. Scheduling can also occur on this path, so the trace alone
cannot attribute all elapsed time to storage instructions.

The hardware completion route is `PataProcessRequest` → `PataCompleteCommand`
→ `AtaPortNotification(AtaRequestComplete)` → `AtaPortOnRequestComplete`
(`drivers/storage/ide/atapi/portstate.c:232`). The last function queues the
channel completion DPC. `AtaReqCompletionDpc` (`scsi.c:806`) removes completed
requests and reaches `AtaReqCompleteRequest` (`scsi.c:262`), which releases
lower resources, advances lower queued work, and calls `IoCompleteRequest` at
`:426`. The Xbox bridge is in `ntoskrnl/xb/ide.c:151,186`.

There are two guarded adapter routes:

1. While `port_submit` is inside `IofCallDriver`, `submit_active` remains set.
   `NxNativeAdapterChildComplete` saves the result and returns
   `STATUS_MORE_PROCESSING_REQUIRED`. After the lower call returns,
   `port_submit` clears that flag and reports the saved result.
2. If lower completion arrives after that flag clears, the child completion
   queues `NxNativeCompletionDpc`. The current DPC drain may execute this new
   DPC immediately in the same pass. It reports the result after the child
   completion routine has unwound.

`report_result` calls `nx_lower_done`. If the original synchronous `run_pump`
still owns pumping, the completion only marks its slot done. That original
pump then retires the packet and completes the parent before `nx_start` can
return. Otherwise, the completion route starts the pump itself. The existing
gates protect child reuse, cancellation and callback reentry; they do not
promise completion will occur after the public API returns.

`finish_parent` writes the parent result and calls `IofCompleteRequest`.
`ntoskrnl/io/iomgr/irp.c:1570–1611` unlocks pages and either takes the deferred
completion path or queues `IopCompleteRequest`. `IopCompleteRequest` publishes
the user's IOSB and queues the user APC (`:369,474,491`). Thus an asynchronous
read may return `STATUS_PENDING` with a completed IOSB before its user callback
runs. Callback delivery still requires the appropriate alertable user wait.
An untouched zero IOSB status alone is not proof of completion; the public
trace must also match the IOSB pointer and expected transferred byte count.

## What the measured extra time establishes

The v6 aggregate profile used owned entry/return addresses. Its DPC interval
is `KiRetireDpcList`, not a title callback. World-read profile partitions were:

| Request partition | Count | Median total µs | Adapter µs | PATA µs | DPC µs |
| --- | ---: | ---: | ---: | ---: | ---: |
| 512 bytes, no DPC interval | 27 | 244.7 | 137.1 | 32.5 | 0 |
| 512 bytes, with DPC interval | 106 | 398.7 | 283.05 | 32.5 | 103.65 |
| Larger, no DPC interval | 137 | 261.1 | 139.5 | 32.6 | 0 |
| Larger, with DPC interval | 32 | 325.9 | 193.7 | 32.5 | 29.6 |

These are inclusive scopes with diagnostic overhead and no IRQ-time exclusion;
the columns must not be added or interpreted as exclusive CPU costs. Some
reads contain multiple DPC intervals, and unrelated timer work can be included.
Every observed submission had the required one-microsecond settle stall;
repeated ten-microsecond busy polling was not observed. Ordinary release
fixtures separately establish submission overhead without these probes.

The supported inference is a feedback mechanism: extra precompletion work
gives the device time to finish, and a later IRQL lowering can then charge
completion/retirement work to the still-running API. Shortening that work may
reduce such overlap. The no-DPC rows show that overlap is not the whole cost.
Holding dispatch level across the entire lower call, or forcing completion
after API return, is not justified by this evidence.

The actual baseline nxstorage compiler rule uses `-Os -flto -march=pentium`,
with `-fno-optimize-sibling-calls -fno-omit-frame-pointer -mstackrealign`.
The generic release cache's `-O3` value is not the effective per-file setting.
The retained data-read path does not clear an entire envelope/control buffer;
packet resets were already narrowed by patch 0150.

## Sixteen adapter lock entries in an ordinary pending retained read

The deterministic host trace counts the same shared adapter lock used by core
callbacks. A pending retained read with no cancellation or completion during
submission takes these entries:

| Entry | Site and reason |
| ---: | --- |
| 1 | Submit: reserve retained envelope |
| 2 | Submit: publish active envelope and dispatch lease |
| 3 | Submit: enqueue request after cancel-routine installation |
| 4 | Admission: acquire admission ownership and dequeue |
| 5 | `nx_start`: reserve core slot |
| 6 | Pump: select first work |
| 7 | Prepare: publish handle |
| 8 | Pump: recheck cancellation/quarantine and commit prepared packet |
| 9 | Lower submission: set `submit_active` |
| 10 | Lower submission: clear `submit_active`, collect deferred result |
| 11 | Pump: record pending return |
| 12 | Pump: scan and release pumping ownership if idle |
| 13 | `nx_start`: finish start bookkeeping |
| 14 | Admission: publish returned handle and inspect cancel latch |
| 15 | Admission: release start lease and select next request |
| 16 | Submit: record public return and release dispatch lease |

The intermediate cancellation/prepare commit validation, lower-call gates,
pump ownership and final dispatch lease remain necessary. The prior rejected
core pump-lock experiment is not reintroduced. Two windows contain no external
operation on their ordinary branches: 1→2 for an already retained envelope,
and 14→15 when no cancellation must be performed.

## 0168 behavioral specification and proof obligations

[0168](../../../../patches/roswell/0168-coalesce-native-adapter-bookkeeping.patch)
combines only those two windows. A normal retained pending request now takes
14 lock entries, measured against 16 in the unchanged 0167 implementation.
This proves a structural work reduction, not native latency improvement.

* Reserving a retained envelope and publishing its active/dispatch lease are
  one locked operation. Sealing either precedes reservation (reject) or follows
  publication (rundown must wait). Dynamic allocation stays unlocked and keeps
  the subsequent sealed/quarantined recheck and failed-allocation cleanup.
* Publishing the core handle and releasing the start lease share the lock only
  when no cancellation is needed. A latched cancellation still releases the
  lock, calls `nx_cancel`, reacquires it, and then releases the start lease.
  A cancellation arriving later sees the published handle, and the existing
  dispatch or active-request lifetime still protects the envelope.
* Lower submission, parent completion and packet preparation callbacks remain
  outside the adapter lock. Transport ordering, cancellation ownership,
  completion unwind, admission fairness and generation rules are unchanged.

Four added adapter groups check the counted pending path, removal immediately
after retained reservation, sealing during dynamic allocation, and cancellation
at the late submit unlock. The removal test starts a real host removal thread
and waits until it either reaches its rundown wait or has returned. Acceptance
is valid only if removal waits for completion; a completed removal requires
rejection without lower I/O. Host doubles assert that `IoReuseIrp`,
`IofCallDriver` and `IofCompleteRequest` run outside the adapter lock, including
all existing synchronous completion and reentry scenarios.

The count regression fails on the unchanged implementation (16 entries) and
passes on the candidate (14). All 42 adapter groups pass plain and ASan/UBSan;
the exact locked reconstruction additionally passes core, differential scan,
pthread ownership, packet, sense, geometry, cache and owner checks. These host
results do not model the real IRQL dispatcher or prove a native speedup.
Release firmware and ordinary fixture qualification are separate gates.
