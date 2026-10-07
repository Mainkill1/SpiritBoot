# Kernel correlation status

Generated from:
- Roswell `1569e2e89fb47cc72b9c704a8884f98200432bd4`
- Cxbx-Reloaded `585c49a50af1255ab155099e06f24505f9c5a800`
- xbox_kernel_test_suite `da80f1f50f14bce19a836facc13d5cd40b3c9227`

## What changed

The original export inventory answered whether Roswell had an export mapping. This pass adds test coverage, subsystem ownership, source-location hints, dependency/risk heuristics, and a place for real hardware results.

The important correction is that **a registered kernel test is not the same as a substantive test**.

| Test-suite state | Slots |
| --- | ---: |
| Registered API slots | 378 |
| Substantive test implementation | **257** |
| Explicit FIXME stub | **120** |
| Explicitly disabled/fatal test | **1** |
| Reserved slot 0 | 1 |

No hardware log has been imported into SpiritBoot yet. Accordingly, `hardware_status` is deliberately `not-ingested` for every API.

## Roswell x test coverage

| Roswell state | Test state | Count |
| --- | --- | ---: |
| mapped | substantive | 245 |
| mapped | stub | 114 |
| mapped | disabled | 1 |
| Roswell generated stub | substantive | 5 |
| Roswell generated stub | test stub | 3 |
| missing export | substantive | 5 |
| missing export | test stub | 2 |
| data scaffold | substantive | 2 |
| data scaffold | test stub | 1 |

The **114 mapped + test-stub** rows are the dangerous category: Roswell has code, but the current test suite cannot yet give us a focused behavioral oracle for that API.

## Coverage by subsystem

| Subsystem | Slots | Roswell mapped | Roswell stub/missing | Substantive tests | Test gaps |
| --- | ---: | ---: | ---: | ---: | ---: |
| Av | 4 | 4 | 0 | 3 | 1 |
| Dbg | 6 | 3 | 3 | 3 | 3 |
| Hal | 19 | 18 | 0 | 19 | 0 |
| Ex | 23 | 23 | 0 | 19 | 4 |
| Fsc | 3 | 3 | 0 | 1 | 2 |
| Interlocked | 8 | 8 | 0 | 0 | 8 |
| Io | 30 | 30 | 0 | 19 | 11 |
| Iof | 2 | 2 | 0 | 1 | 1 |
| Kd | 2 | 0 | 0 | 1 | 1 |
| Ke | 67 | 67 | 0 | 36 | 31 |
| Mm | 25 | 20 | 5 | 18 | 7 |
| Kf | 2 | 2 | 0 | 0 | 2 |
| Ki | 2 | 2 | 0 | 1 | 1 |
| Misc | 2 | 2 | 0 | 1 | 1 |
| Nt | 55 | 55 | 0 | 33 | 22 |
| Ob | 10 | 10 | 0 | 8 | 2 |
| Obp | 1 | 1 | 0 | 1 | 0 |
| Obf | 2 | 2 | 0 | 2 | 0 |
| Phy | 2 | 2 | 0 | 0 | 2 |
| Ps | 6 | 6 | 0 | 6 | 0 |
| Rtl | 66 | 66 | 0 | 57 | 9 |
| Xbox | 7 | 7 | 0 | 4 | 3 |
| Xe | 4 | 4 | 0 | 3 | 1 |
| PortIO | 6 | 6 | 0 | 6 | 0 |
| Xc | 17 | 17 | 0 | 10 | 7 |
| Unknown | 3 | 0 | 3 | 3 | 0 |
| XProfp | 2 | 0 | 2 | 1 | 1 |
| Irt | 2 | 0 | 2 | 1 | 1 |

Key findings:
- **Hal: 19/19 substantive tests.**
- **Ps: 6/6 substantive tests.**
- **Port-I/O: 6/6 substantive tests.**
- **Interlocked: 0/8 substantive tests; all eight are explicit stubs.**
- Largest core test gaps: **Ke 31, Nt 22, Io 11, Mm 7**.
- High-impact mapped APIs with stub tests include `KeWaitForSingleObject`, `KeSetEvent`, `KeSetTimerEx`, `MmAllocateContiguousMemoryEx`, `NtAllocateVirtualMemory`, and `IoCreateFile`.
- Roswell's absent/stubbed exports skew toward debugger/devkit/profiling/unknown APIs, so completing the export count should not outrank dispatcher, memory, I/O and object semantics.

## First attack set

This ranking is a heuristic, not a claim that a Roswell implementation is broken.

| Ord | API | Subsystem | Roswell | Test | Score | Dependencies |
| ---: | --- | --- | --- | --- | ---: | --- |
| 35 | `FscGetCacheSize` | Fsc | mapped | stub | 11 | filesystem cache;storage |
| 37 | `FscSetCacheSize` | Fsc | mapped | stub | 11 | filesystem cache;storage |
| 59 | `IoAllocateIrp` | Io | mapped | stub | 11 | I/O manager;IRP;device objects |
| 65 | `IoCreateDevice` | Io | mapped | stub | 11 | I/O manager;IRP;device objects |
| 66 | `IoCreateFile` | Io | mapped | stub | 11 | I/O manager;IRP;device objects |
| 68 | `IoDeleteDevice` | Io | mapped | stub | 11 | I/O manager;IRP;device objects |
| 72 | `IoFreeIrp` | Io | mapped | stub | 11 | I/O manager;IRP;device objects |
| 73 | `IoInitializeIrp` | Io | mapped | stub | 11 | I/O manager;IRP;device objects |
| 77 | `IoQueueThreadIrp` | Io | mapped | stub | 11 | I/O manager;IRP;device objects |
| 79 | `IoSetIoCompletion` | Io | mapped | stub | 11 | I/O manager;IRP;device objects |
| 80 | `IoSetShareAccess` | Io | mapped | stub | 11 | I/O manager;IRP;device objects |
| 83 | `IoStartPacket` | Io | mapped | stub | 11 | I/O manager;IRP;device objects |
| 86 | `IofCallDriver` | Iof | mapped | stub | 11 | I/O manager;IRP;drivers |
| 90 | `IoDismountVolume` | Io | mapped | stub | 11 | I/O manager;IRP;device objects |
| 92 | `KeAlertResumeThread` | Ke | mapped | stub | 11 | dispatcher;thread-state;object-layout |
| 93 | `KeAlertThread` | Ke | mapped | stub | 11 | dispatcher;thread-state;object-layout |
| 94 | `KeBoostPriorityThread` | Ke | mapped | stub | 11 | dispatcher;thread-state;object-layout |
| 97 | `KeCancelTimer` | Ke | mapped | stub | 11 | dispatcher;clock;timers |
| 99 | `KeDelayExecutionThread` | Ke | mapped | stub | 11 | dispatcher;clock;timers |
| 102 | `MmGlobalData` | Mm | mapped | stub | 11 | PTE/PFN;physical allocator;TLB;GPU-visible memory |
| 103 | `KeGetCurrentIrql` | Ke | mapped | stub | 11 | IRQL;interrupt-controller;dispatcher |
| 104 | `KeGetCurrentThread` | Ke | mapped | stub | 11 | dispatcher;thread-state;object-layout |
| 105 | `KeInitializeApc` | Ke | mapped | stub | 11 | dispatcher;thread-state;APC |
| 116 | `KeInsertHeadQueue` | Ke | mapped | stub | 11 | dispatcher;thread-state;object-layout |

Recommended family order:
1. Dispatcher/event/wait semantics.
2. Timers/APC/DPC/IRQL.
3. Memory allocation/mapping/protection.
4. I/O/IRP lifetime.
5. Object-manager create/insert/reference semantics.
6. Interlocked primitives as a low-complexity coverage win.
7. Debug/devkit/profiling only when a real title or hardware requirement justifies it.

## Hardware evidence

Use `scripts/import-kernel-test-log.ps1` to normalize a real xbox_kernel_test_suite log. Then run `scripts/correlate-kernel.ps1`. Hardware PASS/FAIL is intentionally not inferred from source code alone.
