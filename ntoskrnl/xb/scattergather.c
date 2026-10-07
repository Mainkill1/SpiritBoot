/* SPDX-License-Identifier: GPL-2.0-or-later
 * Xbox FILE_SEGMENT_ELEMENT is a four-byte page pointer (public nxdk ABI).
 * One bounce-backed IRP owns its segments and buffer through completion.
 * Native I/O manager handles pending, event/APC, cancellation and file locking.
 */
#include <ntoskrnl.h>
#include <mm/ARM3/miarm.h>
#include "mm/mm.h"
#include <reactos/xb-io.h>

typedef union _XB_FILE_SEGMENT_ELEMENT {
    PVOID Buffer;
    ULONG Alignment;
} XB_FILE_SEGMENT_ELEMENT, *PXB_FILE_SEGMENT_ELEMENT;
C_ASSERT(sizeof(XB_FILE_SEGMENT_ELEMENT) == 4);
#define SG_TAG 'gSbX'
typedef struct _XB_SG_PAGE { PVOID Buffer; PFN_NUMBER Pfn; } XB_SG_PAGE;
typedef struct _XB_SG_REQUEST {
    PVOID Allocation;
    PUCHAR Bounce;
    ULONG Count, Length;
    BOOLEAN Write;
    XB_SG_PAGE Pages[1];
} XB_SG_REQUEST;
extern NTSTATUS NTAPI IopPerformSynchronousRequest(PDEVICE_OBJECT, PIRP,
    PFILE_OBJECT, BOOLEAN, KPROCESSOR_MODE, BOOLEAN, IOP_TRANSFER_TYPE);

static VOID XbSgRelease(XB_SG_REQUEST *Request)
{
#ifdef NXK_MM_PHYS
    KIRQL irql = MiAcquirePfnLock();
    ULONG i;
    for (i = 0; i < Request->Count; ++i)
        NxkPageSupplyPin(Request->Pages[i].Pfn, TRUE);
    MiReleasePfnLock(irql);
#endif
    if (Request->Allocation) ExFreePoolWithTag(Request->Allocation, SG_TAG);
    ExFreePoolWithTag(Request, SG_TAG);
}
static NTSTATUS NTAPI XbSgCompletion(PDEVICE_OBJECT Device, PIRP Irp, PVOID Context)
{
    XB_SG_REQUEST *r = Context;
    ULONG i, copied = 0, bytes = (ULONG)Irp->IoStatus.Information;
    UNREFERENCED_PARAMETER(Device);
    if (bytes > r->Length) {
        Irp->IoStatus.Status = STATUS_IO_DEVICE_ERROR;
        Irp->IoStatus.Information = bytes = 0;
    }
    if (!r->Write && !NT_ERROR(Irp->IoStatus.Status))
        for (i = 0; copied < bytes; ++i) {
            ULONG chunk = min(PAGE_SIZE, bytes - copied);
            RtlCopyMemory(r->Pages[i].Buffer, r->Bounce + copied, chunk);
            copied += chunk;
        }
    /* Native completion no longer needs the bounce MDL after this callback. */
    if (Irp->MdlAddress) { IoFreeMdl(Irp->MdlAddress); Irp->MdlAddress = NULL; }
    Irp->UserBuffer = NULL;
    XbSgRelease(r);
    if (Irp->PendingReturned) IoMarkIrpPending(Irp);
    return STATUS_SUCCESS;
}
static NTSTATUS XbScatterGather(BOOLEAN Write, HANDLE FileHandle, HANDLE Event,
    PIO_APC_ROUTINE ApcRoutine, PVOID ApcContext, PIO_STATUS_BLOCK Iosb,
    PXB_FILE_SEGMENT_ELEMENT Segments, ULONG Length, PLARGE_INTEGER ByteOffset)
{
    PFILE_OBJECT file = NULL;
    PKEVENT event = NULL;
    PDEVICE_OBJECT device;
    PIRP irp = NULL;
    PIO_STACK_LOCATION stack;
    XB_SG_REQUEST *r = NULL;
    LARGE_INTEGER offset;
    NTSTATUS status;
    BOOLEAN synchronous, locked = FALSE;
    ULONG count, i, copied;
    if (Iosb == NULL || (Length && Segments == NULL)) return STATUS_INVALID_PARAMETER;
    status = ObReferenceObjectByHandle(FileHandle,
        Write ? FILE_WRITE_DATA : FILE_READ_DATA, IoFileObjectType, KernelMode,
        (PVOID *)&file, NULL);
    if (!NT_SUCCESS(status)) goto fail;
    synchronous = BooleanFlagOn(file->Flags, FO_SYNCHRONOUS_IO);
    if (!(file->Flags & FO_NO_INTERMEDIATE_BUFFERING) ||
        (!synchronous && ByteOffset == NULL) || Length > MAXULONG - PAGE_SIZE) {
        status = STATUS_INVALID_PARAMETER; goto fail;
    }
    if (Event) {
        status = ObReferenceObjectByHandle(Event, EVENT_MODIFY_STATE,
            ExEventObjectType, KernelMode, (PVOID *)&event, NULL);
        if (!NT_SUCCESS(status)) goto fail;
    }
    if (synchronous) {
        status = IopLockFileObject(file, KernelMode);
        if (!NT_SUCCESS(status)) goto fail;
        locked = TRUE;
    }
    offset = ByteOffset ? *ByteOffset : file->CurrentByteOffset;
    if (offset.QuadPart == -2 && synchronous) offset = file->CurrentByteOffset;
    if (offset.QuadPart < 0 && !(Write && offset.QuadPart == -1)) {
        status = STATUS_INVALID_PARAMETER; goto fail;
    }
    if (offset.QuadPart >= 0 && offset.QuadPart > MAXLONGLONG - Length) {
        status = STATUS_INVALID_PARAMETER; goto fail;
    }
    count = (Length + PAGE_SIZE - 1) >> PAGE_SHIFT;
    r = ExAllocatePoolWithTag(NonPagedPool,
        FIELD_OFFSET(XB_SG_REQUEST, Pages) + count * sizeof(XB_SG_PAGE), SG_TAG);
    if (!r) { status = STATUS_INSUFFICIENT_RESOURCES; goto fail; }
    RtlZeroMemory(r, FIELD_OFFSET(XB_SG_REQUEST, Pages));
    r->Write = Write; r->Length = Length;
    for (i = 0; i < count; ++i) {
        PVOID page;
        if (!NxMmIsAddressValid(&Segments[i]) ||
            !NxMmIsAddressValid((PUCHAR)&Segments[i] + sizeof(Segments[i]) - 1)) {
            status = STATUS_ACCESS_VIOLATION; goto fail;
        }
        page = (PVOID)((ULONG_PTR)Segments[i].Buffer & ~(PAGE_SIZE - 1));
        KIRQL pfnIrql;
        PFN_NUMBER pfn;
        if (page == NULL || !NxMmIsAddressValid(page) ||
            !NxMmIsAddressValid((PUCHAR)page + PAGE_SIZE - 1)) {
            status = STATUS_ACCESS_VIOLATION; goto fail;
        }
        pfnIrql = MiAcquirePfnLock();
        pfn = NxMmGetPhysicalAddress(page) >> PAGE_SHIFT;
#ifdef NXK_MM_PHYS
        if (!NxkPageSupplyCanPin(pfn, FALSE)) {
            MiReleasePfnLock(pfnIrql); status = STATUS_INVALID_PARAMETER; goto fail;
        }
        NxkPageSupplyPin(pfn, FALSE);
#endif
        r->Pages[i].Buffer = page; r->Pages[i].Pfn = pfn; ++r->Count;
        MiReleasePfnLock(pfnIrql);
    }
    r->Allocation = ExAllocatePoolWithTag(NonPagedPool, Length + PAGE_SIZE, SG_TAG);
    if (!r->Allocation) { status = STATUS_INSUFFICIENT_RESOURCES; goto fail; }
    r->Bounce = (PUCHAR)(((ULONG_PTR)r->Allocation + PAGE_SIZE - 1) & ~(PAGE_SIZE - 1));
    if (Write)
        for (i = 0, copied = 0; copied < Length; ++i) {
            ULONG chunk = min(PAGE_SIZE, Length - copied);
            RtlCopyMemory(r->Bounce + copied, r->Pages[i].Buffer, chunk); copied += chunk;
        }
    device = IoGetRelatedDeviceObject(file);
    irp = IoAllocateIrp(device->StackSize, FALSE);
    if (!irp) { status = STATUS_INSUFFICIENT_RESOURCES; goto fail; }
    irp->Tail.Overlay.OriginalFileObject = file;
    irp->Tail.Overlay.Thread = PsGetCurrentThread();
    irp->RequestorMode = KernelMode;
    irp->UserIosb = Iosb; irp->UserEvent = event;
    irp->UserBuffer = r->Bounce;
    irp->Overlay.AsynchronousParameters.UserApcRoutine = ApcRoutine;
    irp->Overlay.AsynchronousParameters.UserApcContext = ApcContext;
    irp->Flags = IRP_NOCACHE | IRP_DEFER_IO_COMPLETION | IRP_XB_SG_COMPLETION |
                 (Write ? IRP_WRITE_OPERATION : IRP_READ_OPERATION);
    if (Length) {
        irp->MdlAddress = IoAllocateMdl(r->Bounce, Length, FALSE, FALSE, NULL);
        if (!irp->MdlAddress) { status = STATUS_INSUFFICIENT_RESOURCES; goto fail; }
        MmBuildMdlForNonPagedPool(irp->MdlAddress);
    }
    stack = IoGetNextIrpStackLocation(irp);
    stack->MajorFunction = Write ? IRP_MJ_WRITE : IRP_MJ_READ;
    stack->FileObject = file;
    stack->Parameters.Read.Length = Length;
    stack->Parameters.Read.ByteOffset = offset;
    IoSetCompletionRoutine(irp, XbSgCompletion, r, TRUE, TRUE, TRUE);
    if (event) KeClearEvent(event);
    KeClearEvent(&file->Event);
    /* Ownership transfers to the IRP/completion, including FO/event refs.
     * Async returns dispatch status, never waits on the shared FO event. */
    return IopPerformSynchronousRequest(device, irp, file, TRUE, KernelMode,
        synchronous, Write ? IopWriteTransfer : IopReadTransfer);
fail:
    if (irp) { if (irp->MdlAddress) IoFreeMdl(irp->MdlAddress); IoFreeIrp(irp); }
    if (r) XbSgRelease(r);
    if (locked) IopUnlockFileObject(file);
    if (event) ObDereferenceObject(event);
    if (file) ObDereferenceObject(file);
    Iosb->Status = status; Iosb->Information = 0;
    return status;
}
NTSTATUS NTAPI XeNtReadFileScatter(HANDLE f, HANDLE e, PIO_APC_ROUTINE a,
    PVOID c, PIO_STATUS_BLOCK s, PXB_FILE_SEGMENT_ELEMENT p, ULONG n, PLARGE_INTEGER o)
{ return XbScatterGather(FALSE, f, e, a, c, s, p, n, o); }
NTSTATUS NTAPI XeNtWriteFileGather(HANDLE f, HANDLE e, PIO_APC_ROUTINE a,
    PVOID c, PIO_STATUS_BLOCK s, PXB_FILE_SEGMENT_ELEMENT p, ULONG n, PLARGE_INTEGER o)
{ return XbScatterGather(TRUE, f, e, a, c, s, p, n, o); }
