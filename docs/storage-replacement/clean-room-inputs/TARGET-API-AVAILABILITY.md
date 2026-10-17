# Target API availability packet

Declaration-only, 2026-10-14. `target-api-declarations.h` states source-available linked API signatures in original interface prose/declarations; it has no inline helper bodies or private SDK structures. It requires already approved definitions for public kernel types and calling conventions. It is not a replacement for reviewing the actual target ABI/header dependency closure.

| API | Target availability | Important contract |
| --- | --- | --- |
| IoAllocateIrp / IoFreeIrp | linked GPL implementation | nonpaged driver ownership; no automatic MDL disposal |
| IoInitializeIrp / IoReuseIrp | GPL source implementation | reuse clears packet state; allocation bookkeeping preserved by IoReuseIrp |
| IofCallDriver | linked GPL implementation, FASTCALL | ordinary IoCallDriver macro targets this; no IRP access after dispatch return |
| IofCompleteRequest | linked GPL implementation, FASTCALL | ordinary IoCompleteRequest macro targets this; MORE_PROCESSING_REQUIRED stops all further packet processing |
| IoAllocateMdl / IoBuildPartialMdl / IoFreeMdl | GPL source implementation | caller owns partial descriptor; parent pages remain borrowed |
| IoCancelIrp | linked GPL implementation | sets cancel bit; return value does not establish terminal completion |
| IoAcquireCancelSpinLock / IoReleaseCancelSpinLock | GPL source implementation | cancellation synchronization at DISPATCH_LEVEL |
| IoSetCancelRoutine | current target header inline helper, no standalone source function | atomic callback replacement returning previous pointer; body is excluded from this packet |
| IoSetCompletionRoutine | current target header inline helper, no standalone source function | registers next-stack callback/context plus success/error/cancel invocation choices; body excluded |
| IoMarkIrpPending | current target header inline helper | marks the current stack pending; body excluded |
| IoGetCurrentIrpStackLocation / IoGetNextIrpStackLocation / IoSkipCurrentIrpStackLocation | current target header helpers | public stack-position operation; bodies excluded |
| MmGetMdlVirtualAddress / MmGetSystemAddressForMdlSafe / MmPrepareMdlForReuse | current target header helpers plus retained MM services | use public MDL semantics; no unchecked inline body import authorized |

The ordinary public signatures of the header-only operations are documented in Microsoft Learn; they do not authorize linking to nonexistent standalone symbols. Independently authored local helpers may express those public contracts using approved kernel field/atomic interfaces. Do not copy uncertain SDK helper bodies or globally shadow kernel APIs as an incidental shortcut. Newly introduced helpers need their own provenance record and meaningful target/host checks.

The existing release's LTO can localize, clone or inline a source-available function (IoReuseIrp and IoAllocateMdl are examples); absence of an exact baseline symbol does not mean the retained source API is unavailable to a new static kernel caller. Conversely, a declaration alone does not prove runtime callback residency or device lifetime. Check the exact candidate build, calling convention, source inputs and final link.

Public references: [allocation](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/nf-wdm-ioallocateirp), [reuse](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/nf-wdm-ioreuseirp), [cancellation](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/nf-wdm-iosetcancelroutine), [completion registration](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/nf-wdm-iosetcompletionroutine), [next stack](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/nf-wdm-iogetnextirpstacklocation), [partial MDL](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/nf-wdm-iobuildpartialmdl).
