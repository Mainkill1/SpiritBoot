# First-wave kernel conformance plan

This is the dependency-first work order derived from the initial 379-export correlation.

It deliberately overrides the generic numeric `priority_score` in `correlation.csv`. The numeric score is useful for filtering large groups; it does not understand that dispatcher semantics sit underneath much of I/O, timers, APC delivery, and title threading.

None of these rows are claims that Roswell is wrong. They identify APIs where:

1. retail relevance is high;
2. the current kernel test is stubbed or otherwise insufficient;
3. the behavior has broad downstream dependencies; and
4. Roswell already has enough implementation to make a focused hardware-vs-open-kernel comparison useful.

## Wave A — dispatcher, events and waits

Do these first.

| Ord | API | Current test | Roswell implementation | Cxbx reference | Why first |
| ---: | --- | --- | --- | --- | --- |
| 159 | `KeWaitForSingleObject` | stub | `ntoskrnl/ke/wait.c` | `EmuKrnlKe.cpp` | Core wait primitive; alertability and APC delivery affect async I/O. |
| 145 | `KeSetEvent` | stub | `ntoskrnl/ke/eventobj.c` | `EmuKrnlKe.cpp` | Wakes waiters and controls dispatcher ordering/priority effects. |
| 138 | `KeResetEvent` | stub | `ntoskrnl/ke/eventobj.c` | `EmuKrnlKe.cpp` | Event-state semantics used throughout synchronization. |
| 123 | `KePulseEvent` | stub | `ntoskrnl/ke/eventobj.c` | `EmuKrnlKe.cpp` | Timing-sensitive wake semantics; easy place for host/guest behavior to diverge. |
| 99 | `KeDelayExecutionThread` | stub | `ntoskrnl/ke/wait.c` | `EmuKrnlKe.cpp` | Couples waits, timer due-times, alertability and APC delivery. |

### Roswell-specific concern

Roswell's Xbox path in `wait.c` already documents a critical semantic constraint: user-mode alertable waits must retain user-APC delivery because titles use them for overlapped I/O completion. The source notes that removing those paths can starve asynchronous I/O to roughly one completion per clock tick.

That makes wait/APC behavior a better first target than filling low-value missing debug exports.

### Tests to add

For each wait/event primitive, test:

- signaled vs non-signaled initial state;
- synchronization vs notification event behavior;
- previous-state return value;
- zero, relative and absolute timeouts where applicable;
- `Wait=TRUE` chaining semantics;
- one waiter vs multiple waiters;
- alertable vs non-alertable waits;
- user APC pending before wait;
- APC becoming pending during wait;
- priority increment effects where observable;
- ordering/repeatability across at least two retail hardware revisions if possible.

## Wave B — timers, APCs and IRQL

| Ord | API | Current test | Roswell implementation | Cxbx reference | Primary risk |
| ---: | --- | --- | --- | --- | --- |
| 97 | `KeCancelTimer` | stub | `ntoskrnl/ke/timerobj.c` | `EmuKrnlKe.cpp` | Inserted-state return and timer-tree removal. |
| 149 | `KeSetTimer` | stub | `ntoskrnl/ke/timerobj.c` | `EmuKrnlKe.cpp` | Wrapper semantics and immediate-expiry behavior. |
| 150 | `KeSetTimerEx` | stub | `ntoskrnl/ke/timerobj.c` | `EmuKrnlKe.cpp` | Periodic timing, DPC request/order and due-time rounding. |
| 105 | `KeInitializeApc` | stub | `ntoskrnl/ke/apc.c` + Xbox export adapter/shadow | `EmuKrnlKe.cpp` | Xbox KAPC layout differs from generic NT layout. |
| 118 | `KeInsertQueueApc` | stub | `ntoskrnl/ke/apc.c` + Xbox export adapter/shadow | `EmuKrnlKe.cpp` | APC queueing/delivery ordering and wake interaction. |
| 103 | `KeGetCurrentIrql` | stub | x86/HAL IRQL path | `EmuKrnlKe.cpp` / `EmuKrnl.cpp` | Basic state used by assertions and synchronization. |
| 160 | `KfRaiseIrql` | stub | x86/HAL IRQL path | `EmuKrnlKe.cpp` / `EmuKrnlKi.cpp` | Interrupt/dispatcher ordering. |
| 161 | `KfLowerIrql` | stub | x86/HAL IRQL path | `EmuKrnlKe.cpp` / `EmuKrnlKi.cpp` | Deferred APC/DPC delivery points. |

### Tests to add

Focus on observable state transitions rather than only return values:

- timer inserted/cancelled state;
- immediate vs future expiration;
- periodic rescheduling;
- DPC execution count and order;
- APC queue state before/after insertion;
- alertable-wait delivery;
- IRQL round-trip and nested raise/lower;
- whether lowering IRQL triggers deferred work at the same boundary as retail.

## Wave C — memory

| Ord | API | Current test | Roswell implementation | Cxbx reference | Primary risk |
| ---: | --- | --- | --- | --- | --- |
| 166 | `MmAllocateContiguousMemoryEx` | stub | `ntoskrnl/xb/mm/contig.c` | `EmuKrnlMm.cpp` | Physical range/alignment, 64 MiB title window, NV2A instance region, protection/cache attributes. |
| 184 | `NtAllocateVirtualMemory` | stub | `ntoskrnl/mm/ARM3/virtual.c` | `EmuKrnlNt.cpp` / `EmuKrnlMm.cpp` | Generic ReactOS implementation may expose NT behavior not identical to Xbox. |
| 177 | `MmMapIoSpace` | stub | `ntoskrnl/xb/mm/iospace.c` | `EmuKrnlMm.cpp` | Static Xbox alias selection and cacheability semantics. |
| 183 | `MmUnmapIoSpace` | stub | `ntoskrnl/xb/mm/iospace.c` | `EmuKrnlMm.cpp` | Roswell currently treats unmap as a no-op because windows are static. |

### Concrete Roswell questions

`NxMmAllocateContiguousMemoryEx` currently ignores the `Protect` parameter with a TODO for WC/UC PSE alias selection. That is a specific conformance question, not a theoretical concern.

Roswell's Xbox-specific `NxMmUnmapIoSpace` is intentionally a no-op. Hardware testing should establish whether any guest-visible lifetime, alias, protection, or reuse behavior must still be reproduced.

Test memory boundaries aggressively:

- zero-size and page-rounding cases;
- lowest/highest physical bounds;
- alignment values;
- allocation near the NV2A instance-memory boundary;
- 64 MiB vs 128 MiB configurations;
- protection/cacheability requests;
- free/reallocate ordering;
- map/unmap/remap of the same physical range;
- address/protection queries before and after operations.

## Wave D — I/O and object lifetime

| Ord | API | Current test | Roswell implementation | Cxbx reference | Primary risk |
| ---: | --- | --- | --- | --- | --- |
| 66 | `IoCreateFile` | stub | `ntoskrnl/io/iomgr/file.c` | `EmuKrnlIo.cpp` | Xbox parameter-checking rules differ from generic NT. |
| 59 | `IoAllocateIrp` | stub | `ntoskrnl/io/iomgr/irp.c` | `EmuKrnlIo.cpp` | IRP size/stack/flags and allocation behavior. |
| 73 | `IoInitializeIrp` | stub | `ntoskrnl/io/iomgr/irp.c` | `EmuKrnlIo.cpp` | Exact initialized fields and stack location. |
| 86 | `IofCallDriver` | stub | `ntoskrnl/io/iomgr/irp.c` | `EmuKrnlIo.cpp` | Stack decrement, device/driver dispatch and failure behavior. |
| 239 | `ObCreateObject` | stub | `ntoskrnl/xb/obcreate.c` | `EmuKrnlOb.cpp` | Xbox caller-owned object allocation/header semantics. |
| 241 | `ObInsertObject` | stub | `ntoskrnl/xb/obcreate.c` | `EmuKrnlOb.cpp` | Handle insertion, name/namespace and reference lifetime. |

### Concrete Roswell questions

Roswell already has an Xbox-specific `IoCreateFile` branch: Xbox callers are treated as kernel-mode and parameter validation is conditional on `IO_CHECK_CREATE_PARAMETERS`. This should be tested directly instead of assuming generic NT tests are sufficient.

Roswell's `ObCreateObject`/`ObInsertObject` implementation is also explicitly Xbox-specific. It models the console's four-word object header and uses an NT shim to participate in Roswell's handle table/namespace. Focused tests should validate object body location, pointer/handle counts, type callbacks, naming and final-release behavior.

## Parallel quick win — interlocked primitives

All eight registered Interlocked tests are currently explicit stubs:

- 51 `InterlockedCompareExchange`
- 52 `InterlockedDecrement`
- 53 `InterlockedIncrement`
- 54 `InterlockedExchange`
- 55 `InterlockedExchangeAdd`
- 56 `InterlockedFlushSList`
- 57 `InterlockedPopEntrySList`
- 58 `InterlockedPushEntrySList`

These are lower architectural risk than the dispatcher and memory manager, but filling them gives us eight inexpensive hardware-backed checks and validates ABI/atomic semantics used underneath higher-level code.

## Defer by default

Do not prioritize these simply because Roswell currently stubs or omits them:

- debugger-only `Dbg*`;
- `MmDbg*` devkit APIs;
- `XProfp*` / `Irt*` profiling APIs;
- ordinals 367-369 while their retail role remains unknown.

Promote any of them immediately if a retail title, devkit workload, or hardware trace demonstrates actual dependence.

## Completion rule

An API moves from "gap" to "hardware-backed" only when:

1. the test itself is substantive and reviewed;
2. the test is run on a named hardware/reference environment;
3. raw/normalized result provenance is retained;
4. Roswell is run against the same semantic assertions;
5. any discrepancy is reduced to a reproducible case rather than hidden behind a title-level workaround.
