/* SPDX-License-Identifier: GPL-2.0-only
 * Independently authored public export contracts. No private kernel layout.
 * Objects remain static through shutdown even if a cancellation check fails. */
#include <xboxkrnl/xboxkrnl.h>
#include <limits.h>
#include <string.h>
#include "regression.h"

_Static_assert(sizeof(LONG) == 4 && LONG_MAX == 2147483647L,
               "semaphore boundary probe requires the 32-bit native LONG maximum");

static KTIMER notification_timer, synchronization_timer;
static LARGE_INTEGER poll_time = {.QuadPart = 0};

#ifndef STATUS_INVALID_DEVICE_REQUEST
#define STATUS_INVALID_DEVICE_REQUEST ((NTSTATUS)0xC0000010L)
#endif
#ifndef STATUS_MORE_PROCESSING_REQUIRED
#define STATUS_MORE_PROCESSING_REQUIRED ((NTSTATUS)0xC0000016L)
#endif

#define XBOX_SYNCH_LEVEL 28

static void init_ansi(ANSI_STRING *name, const char *text)
{
    name->Buffer = (PCHAR)text;
    name->Length = (USHORT)strlen(text);
    name->MaximumLength = name->Length + 1;
}

static NTSTATUS timer_wait(PKTIMER timer, LONGLONG timeout)
{
    LARGE_INTEGER bound = {.QuadPart = timeout};
    return KeWaitForSingleObject(timer, Executive, KernelMode, FALSE, &bound);
}

static void timer_contracts(void)
{
    const LARGE_INTEGER far = {.QuadPart = -100000000}; /* ten seconds */
    const LARGE_INTEGER soon = {.QuadPart = -50000}; /* five milliseconds */
    const LONGLONG wait_bound = -20000000; /* two seconds, never infinite */
    KeInitializeTimerEx(&notification_timer, NotificationTimer);
    regression_check(timer_wait(&notification_timer, 0) == STATUS_TIMEOUT, "notification timer initializes unsignaled");
    regression_check(!KeCancelTimer(&notification_timer), "cancel unarmed timer reports false");
    regression_check(!KeSetTimer(&notification_timer, far, NULL), "first KeSetTimer reports not previously queued");
    regression_check(KeSetTimerEx(&notification_timer, far, 0, NULL), "KeSetTimerEx replaces pending timer");
    regression_check(KeCancelTimer(&notification_timer), "cancel removes pending timer");
    regression_check(!KeCancelTimer(&notification_timer), "second cancel reports no pending timer");
    regression_check(timer_wait(&notification_timer, 0) == STATUS_TIMEOUT, "cancelled unexpired timer stays unsignaled");
    regression_check(!KeSetTimerEx(&notification_timer, soon, 0, NULL), "cancelled timer can be rearmed with KeSetTimerEx");
    regression_check(timer_wait(&notification_timer, wait_bound) == STATUS_SUCCESS, "notification timer expires within finite wait");
    regression_check(timer_wait(&notification_timer, 0) == STATUS_SUCCESS, "notification signal survives a wait");
    regression_check(!KeCancelTimer(&notification_timer), "expired one-shot timer is not queued");
    regression_check(!KeSetTimer(&notification_timer, far, NULL), "expired notification timer can be rearmed");
    regression_check(timer_wait(&notification_timer, 0) == STATUS_TIMEOUT, "rearm clears the old notification signal");
    regression_check(KeCancelTimer(&notification_timer), "rearmed notification timer can be cancelled");

    KeInitializeTimerEx(&synchronization_timer, SynchronizationTimer);
    regression_check(timer_wait(&synchronization_timer, 0) == STATUS_TIMEOUT, "synchronization timer initializes unsignaled");
    regression_check(!KeSetTimer(&synchronization_timer, soon, NULL), "first synchronization timer arm reports false");
    regression_check(timer_wait(&synchronization_timer, wait_bound) == STATUS_SUCCESS, "synchronization timer expires within finite wait");
    regression_check(timer_wait(&synchronization_timer, 0) == STATUS_TIMEOUT, "synchronization signal is consumed once");
    regression_check(!KeSetTimerEx(&synchronization_timer, soon, 0, NULL), "synchronization timer rearms with KeSetTimerEx");
    regression_check(timer_wait(&synchronization_timer, wait_bound) == STATUS_SUCCESS, "rearmed synchronization timer expires");
    regression_check(timer_wait(&synchronization_timer, 0) == STATUS_TIMEOUT, "rearmed synchronization signal is consumed once");
    regression_check(!KeCancelTimer(&synchronization_timer), "expired synchronization timer is not queued");
    /* No callback/DPC references stack storage; cancel both even after failure. */
    KeCancelTimer(&notification_timer);
    KeCancelTimer(&synchronization_timer);
}

static struct {
    ULONG before[4];
    SLIST_HEADER head __attribute__((aligned(16)));
    ULONG after[4];
} list_storage;
static struct { SINGLE_LIST_ENTRY entry; ULONG canary; } first, second, third;

static void slist_contracts(void)
{
    memset(&list_storage, 0, sizeof(list_storage));
    for (unsigned i = 0; i < 4; ++i) {
        list_storage.before[i] = 0x3172a8d5;
        list_storage.after[i] = 0x61b9c4e2;
    }
    first.canary = 0x11223344; second.canary = 0x55667788; third.canary = 0x99aabbcc;
    PSLIST_HEADER head = &list_storage.head;
    regression_check(InterlockedPopEntrySList(head) == NULL, "pop empty SLIST returns null");
    regression_check(InterlockedFlushSList(head) == NULL, "flush empty SLIST returns null");
    regression_check(InterlockedPushEntrySList(head, &first.entry) == NULL, "first push returns old empty head");
    regression_check(InterlockedPushEntrySList(head, &second.entry) == &first.entry, "second push returns previous head");
    regression_check(InterlockedPopEntrySList(head) == &second.entry, "pop follows last-in first-out ordering");
    regression_check(InterlockedPushEntrySList(head, &third.entry) == &first.entry, "push after pop preserves remaining head");
    regression_check(InterlockedFlushSList(head) == &third.entry, "flush returns the detached chain head");
    regression_check(third.entry.Next == &first.entry, "flush preserves known successor link");
    regression_check(first.entry.Next == NULL, "detached chain has the original null tail");
    regression_check(InterlockedPopEntrySList(head) == NULL, "flush leaves live head empty");
    regression_check(InterlockedPushEntrySList(head, &second.entry) == NULL, "popped node may be reused in empty list");
    regression_check(InterlockedPopEntrySList(head) == &second.entry, "reused node is returned exactly once");
    regression_check(InterlockedPopEntrySList(head) == NULL, "pop after reuse is empty");
    regression_check(InterlockedFlushSList(head) == NULL, "flush after reuse is empty");
    int fences = 1;
    for (unsigned i = 0; i < 4; ++i)
        fences &= list_storage.before[i] == 0x3172a8d5 && list_storage.after[i] == 0x61b9c4e2;
    regression_check(fences, "SLIST operations preserve header fences");
    regression_check(first.canary == 0x11223344 && second.canary == 0x55667788 && third.canary == 0x99aabbcc,
                     "SLIST operations preserve node payload canaries");
    /* No guessed SLIST_HEADER offsets or Depth/Sequence interpretation. */
}

static void semaphore_contracts(void)
{
    HANDLE semaphore = NULL;
    NTSTATUS status = NtCreateSemaphore(&semaphore, NULL, 0, 3);
    regression_require(status == STATUS_SUCCESS && semaphore != NULL, "create semaphore with zero count and limit three");
    SEMAPHORE_BASIC_INFORMATION state = {0};
    regression_check(NtQuerySemaphore(semaphore, &state) == STATUS_SUCCESS, "query created semaphore");
    regression_check(state.CurrentCount == 0 && state.MaximumCount == 3, "initial semaphore count and limit match creation");
    LONG previous = -1;
    regression_check(NtReleaseSemaphore(semaphore, 2, &previous) == STATUS_SUCCESS, "release two semaphore units");
    regression_check(previous == 0, "first release reports previous count zero");
    regression_check(NtQuerySemaphore(semaphore, &state) == STATUS_SUCCESS && state.CurrentCount == 2, "release adds exactly two units");
    previous = -1;
    regression_check(NtReleaseSemaphore(semaphore, 1, &previous) == STATUS_SUCCESS, "release reaches semaphore limit");
    regression_check(previous == 2, "second release reports previous count two");
    regression_check(NtQuerySemaphore(semaphore, &state) == STATUS_SUCCESS && state.CurrentCount == 3, "semaphore reaches declared limit");
    regression_check(NtReleaseSemaphore(semaphore, 1, &previous) == (NTSTATUS)STATUS_SEMAPHORE_LIMIT_EXCEEDED, "release past limit reports overflow");
    regression_check(NtQuerySemaphore(semaphore, &state) == STATUS_SUCCESS && state.CurrentCount == 3, "overflow does not alter semaphore count");

    /* Each error starts from the queried nonzero count above. The caller's
     * output must remain untouched; no failed release may change the object. */
    previous = 0x13579bdf;
    regression_check(NtReleaseSemaphore(semaphore, 0, &previous) == (NTSTATUS)STATUS_INVALID_PARAMETER,
                     "zero semaphore release reports invalid parameter");
    regression_check(previous == 0x13579bdf, "zero release preserves previous-count output");
    regression_check(NtQuerySemaphore(semaphore, &state) == STATUS_SUCCESS && state.CurrentCount == 3 && state.MaximumCount == 3,
                     "zero release preserves semaphore count and limit");

    previous = 0x2468ace;
    regression_check(NtReleaseSemaphore(semaphore, -1, &previous) == (NTSTATUS)STATUS_INVALID_PARAMETER,
                     "negative semaphore release reports invalid parameter");
    regression_check(previous == 0x2468ace, "negative release preserves previous-count output");
    regression_check(NtQuerySemaphore(semaphore, &state) == STATUS_SUCCESS && state.CurrentCount == 3 && state.MaximumCount == 3,
                     "negative release preserves semaphore count and limit");

    previous = 0x31415926;
    regression_check(NtReleaseSemaphore(semaphore, LONG_MAX, &previous) == (NTSTATUS)STATUS_SEMAPHORE_LIMIT_EXCEEDED,
                     "LONG_MAX release from nonzero count reports overflow");
    regression_check(previous == 0x31415926, "LONG_MAX overflow preserves previous-count output");
    regression_check(NtQuerySemaphore(semaphore, &state) == STATUS_SUCCESS && state.CurrentCount == 3 && state.MaximumCount == 3,
                     "LONG_MAX overflow preserves semaphore count and limit");

    regression_check(NtWaitForSingleObject(semaphore, FALSE, &poll_time) == STATUS_SUCCESS, "one semaphore wait consumes one unit");
    regression_check(NtQuerySemaphore(semaphore, &state) == STATUS_SUCCESS && state.CurrentCount == 2, "wait decrements count exactly once");
    regression_check(NtReleaseSemaphore(semaphore, 1, NULL) == STATUS_SUCCESS, "previous-count output is optional");
    regression_check(NtQuerySemaphore(semaphore, &state) == STATUS_SUCCESS && state.CurrentCount == 3, "optional-output release restores limit");
    for (unsigned i = 0; i < 3; ++i)
        regression_check(NtWaitForSingleObject(semaphore, FALSE, &poll_time) == STATUS_SUCCESS, "drain one available semaphore unit");
    regression_check(NtWaitForSingleObject(semaphore, FALSE, &poll_time) == STATUS_TIMEOUT, "empty semaphore poll returns timeout");
    regression_check(NtQuerySemaphore(semaphore, &state) == STATUS_SUCCESS && state.CurrentCount == 0, "drained semaphore remains zero");
    regression_check(NtClose(semaphore) == STATUS_SUCCESS, "close the owned semaphore handle");
}

static KDPC context_dpc;
static KEVENT context_dpc_done;
static volatile ULONG context_dpc_calls;
static volatile BOOLEAN context_dpc_active;
static volatile KIRQL context_dpc_irql;
static volatile PVOID context_dpc_context;
static volatile PVOID context_dpc_arg1;
static volatile PVOID context_dpc_arg2;

static VOID NTAPI context_dpc_probe(PKDPC dpc, PVOID context, PVOID arg1, PVOID arg2)
{
    (void)dpc;
    ++context_dpc_calls;
    context_dpc_active = KeIsExecutingDpc();
    context_dpc_irql = KeGetCurrentIrql();
    context_dpc_context = context;
    context_dpc_arg1 = arg1;
    context_dpc_arg2 = arg2;
    KeSetEvent(&context_dpc_done, 0, FALSE);
}

static void irql_and_dpc_contracts(void)
{
    static ULONG context_marker, arg1_marker, arg2_marker;
    LARGE_INTEGER wait_bound = {.QuadPart = -20000000};
    KIRQL old;

    KeInitializeEvent(&context_dpc_done, SynchronizationEvent, FALSE);
    KeInitializeDpc(&context_dpc, context_dpc_probe, &context_marker);
    regression_check(KeInsertQueueDpc(&context_dpc, &arg1_marker, &arg2_marker),
                     "fresh DPC is inserted exactly once");
    regression_check(KeWaitForSingleObject(&context_dpc_done, Executive, KernelMode, FALSE,
                                           &wait_bound) == STATUS_SUCCESS,
                     "queued DPC completes within a finite wait");
    regression_check(context_dpc_calls == 1, "queued DPC callback runs exactly once");
    regression_check(context_dpc_active, "KeIsExecutingDpc reports true inside a DPC callback");
    regression_check(context_dpc_irql == DISPATCH_LEVEL, "DPC callback runs at dispatch level");
    regression_check(context_dpc_context == &context_marker &&
                     context_dpc_arg1 == &arg1_marker && context_dpc_arg2 == &arg2_marker,
                     "DPC callback receives its exact context and system arguments");

    old = KfRaiseIrql(DISPATCH_LEVEL);
    regression_check(old == PASSIVE_LEVEL, "KfRaiseIrql returns the previous passive level");
    regression_check(KeGetCurrentIrql() == DISPATCH_LEVEL, "KfRaiseIrql raises to dispatch level");
    KfLowerIrql(old);
    regression_check(KeGetCurrentIrql() == PASSIVE_LEVEL, "KfLowerIrql restores the previous level");

    old = KeRaiseIrqlToSynchLevel();
    regression_check(old == PASSIVE_LEVEL, "KeRaiseIrqlToSynchLevel returns the previous level");
    regression_check(KeGetCurrentIrql() == XBOX_SYNCH_LEVEL,
                     "Xbox synchronization level is the public clock level");
    KfLowerIrql(old);
    regression_check(KeGetCurrentIrql() == PASSIVE_LEVEL,
                     "synchronization-level probe restores passive level");
}

static KINTERRUPT synchronize_interrupt;
static ULONG synchronize_calls;
static PVOID synchronize_context;
static KIRQL synchronize_irql;

static BOOLEAN NTAPI inert_interrupt(PKINTERRUPT interrupt, PVOID context)
{
    (void)interrupt;
    (void)context;
    return FALSE;
}

static BOOLEAN NTAPI synchronize_probe(PVOID context)
{
    ++synchronize_calls;
    synchronize_context = context;
    synchronize_irql = KeGetCurrentIrql();
    return *(BOOLEAN *)context;
}

static void synchronize_contracts(void)
{
    BOOLEAN callback_result = FALSE;

    KeInitializeInterrupt(&synchronize_interrupt, inert_interrupt, NULL, 0x24,
                          DISPATCH_LEVEL, LevelSensitive, FALSE);
    regression_check(!KeSynchronizeExecution(&synchronize_interrupt, synchronize_probe,
                                              &callback_result),
                     "KeSynchronizeExecution returns a false callback result");
    regression_check(synchronize_calls == 1 && synchronize_context == &callback_result,
                     "synchronize callback runs once with the exact context");
    regression_check(synchronize_irql == DISPATCH_LEVEL,
                     "synchronize callback runs at the interrupt synchronization level");
    regression_check(KeGetCurrentIrql() == PASSIVE_LEVEL,
                     "synchronize callback restores the caller IRQL");
    callback_result = TRUE;
    regression_check(KeSynchronizeExecution(&synchronize_interrupt, synchronize_probe,
                                             &callback_result),
                     "KeSynchronizeExecution returns a true callback result");
    regression_check(synchronize_calls == 2,
                     "second synchronize operation invokes the callback exactly once");
}

static DRIVER_OBJECT invalid_driver;
static PDEVICE_OBJECT invalid_device;
static PETHREAD invalid_self_thread;
static KEVENT invalid_completion_event;
static volatile ULONG invalid_completion_calls;
static PIRP invalid_completion_irp;
static PVOID invalid_completion_context;
static ULONG invalid_completion_marker;

static void unlink_thread_irp(PIRP irp)
{
    PLIST_ENTRY entry = &irp->ThreadListEntry;
    entry->Blink->Flink = entry->Flink;
    entry->Flink->Blink = entry->Blink;
    entry->Flink = entry->Blink = entry;
}

static NTSTATUS NTAPI invalid_completion(PDEVICE_OBJECT device, PIRP irp,
                                         PVOID context)
{
    (void)device;
    ++invalid_completion_calls;
    invalid_completion_irp = irp;
    invalid_completion_context = context;
    KeSetEvent(&invalid_completion_event, 0, FALSE);
    return STATUS_MORE_PROCESSING_REQUIRED;
}

static void io_invalid_contracts(void)
{
    static char device_name[] = "\\Device\\kernelcontractinvalid";
    OBJECT_STRING name = {
        .Length = sizeof(device_name) - 1,
        .MaximumLength = sizeof(device_name),
        .Buffer = device_name,
    };
    LARGE_INTEGER wait_bound = {.QuadPart = -20000000};
    PIRP irp;
    NTSTATUS status, wait_status;

    status = ObReferenceObjectByHandle((HANDLE)-2, &PsThreadObjectType,
                                       (PVOID *)&invalid_self_thread);
    regression_check(status == STATUS_SUCCESS && invalid_self_thread != NULL,
                     "hold the current thread for an owned invalid-request IRP");
    if (!NT_SUCCESS(status) || invalid_self_thread == NULL) return;

    memset(&invalid_driver, 0, sizeof(invalid_driver));
    for (unsigned i = 0; i < sizeof(invalid_driver.MajorFunction) /
                              sizeof(invalid_driver.MajorFunction[0]); ++i)
        invalid_driver.MajorFunction[i] = IoInvalidDeviceRequest;
    status = IoCreateDevice(&invalid_driver, 0, &name, 0x22,
                            FALSE, &invalid_device);
    regression_check(status == STATUS_SUCCESS && invalid_device != NULL,
                     "create an isolated device with invalid-request dispatch");
    if (!NT_SUCCESS(status) || invalid_device == NULL) {
        ObfDereferenceObject(invalid_self_thread);
        return;
    }

    KeInitializeEvent(&invalid_completion_event, NotificationEvent, FALSE);
    invalid_completion_calls = 0;
    invalid_completion_irp = NULL;
    invalid_completion_context = NULL;
    irp = IoAllocateIrp(1);
    regression_check(irp != NULL, "allocate a real one-stack invalid-request IRP");
    if (irp == NULL) {
        IoDeleteDevice(invalid_device);
        ObfDereferenceObject(invalid_self_thread);
        return;
    }

    irp->Tail.Overlay.Thread = invalid_self_thread;
    irp->IoStatus.Status = (NTSTATUS)0xa5a5a5a5;
    irp->IoStatus.Information = 0xa5a5a5a5;
    IoQueueThreadIrp(irp);
    /* nxdk exposes this public nine-word stack entry but no setter macro. */
    ULONG *next = (ULONG *)irp->Tail.Overlay.CurrentStackLocation - 9;
    memset(next, 0, 9 * sizeof(*next));
    next[0] = 2 | (0xe0u << 24);
    next[7] = (ULONG)invalid_completion;
    next[8] = (ULONG)&invalid_completion_marker;

    status = IofCallDriver(invalid_device, irp);
    wait_status = KeWaitForSingleObject(&invalid_completion_event, Executive,
                                        KernelMode, FALSE,
                                        &wait_bound);
    regression_check(status == (NTSTATUS)STATUS_INVALID_DEVICE_REQUEST,
                     "invalid-device dispatch returns STATUS_INVALID_DEVICE_REQUEST");
    regression_check(wait_status == STATUS_SUCCESS && invalid_completion_calls == 1,
                     "invalid-device dispatch invokes completion exactly once");
    regression_check(invalid_completion_irp == irp &&
                     invalid_completion_context == &invalid_completion_marker,
                     "invalid-device completion receives the exact IRP and context");
    regression_check(irp->IoStatus.Status == (NTSTATUS)STATUS_INVALID_DEVICE_REQUEST,
                     "invalid-device completion publishes its final status in the IRP");
    unlink_thread_irp(irp);
    IoFreeIrp(irp);
    IoDeleteDevice(invalid_device);
    ObfDereferenceObject(invalid_self_thread);
}

static void object_directory_contracts(void)
{
    HANDLE parent = NULL, child = NULL, opened = NULL;
    ANSI_STRING child_name;
    OBJECT_ATTRIBUTES anonymous = {0};
    OBJECT_ATTRIBUTES named;
    NTSTATUS status;

    status = NtCreateDirectoryObject(&parent, &anonymous);
    regression_check(status == STATUS_SUCCESS && parent != NULL,
                     "create an anonymous parent directory");
    if (!NT_SUCCESS(status)) return;

    init_ansi(&child_name, "kernel_export_contract_child");
    named.RootDirectory = parent;
    named.ObjectName = &child_name;
    named.Attributes = OBJ_CASE_INSENSITIVE;
    status = NtCreateDirectoryObject(&child, &named);
    regression_check(status == STATUS_SUCCESS && child != NULL,
                     "create a named child directory");
    if (NT_SUCCESS(status)) {
        status = NtOpenDirectoryObject(&opened, &named);
        regression_check(status == STATUS_SUCCESS && opened != NULL,
                         "open the child directory by its relative name");
        regression_check(opened != child, "opening the directory returns a distinct handle");
    }
    if (opened != NULL)
        regression_check(NtClose(opened) == STATUS_SUCCESS, "close the opened directory handle");
    if (child != NULL)
        regression_check(NtClose(child) == STATUS_SUCCESS, "close the created child handle");
    regression_check(NtClose(parent) == STATUS_SUCCESS, "close the anonymous parent handle");
}

static NTSTATUS open_dvd_root(HANDLE *handle)
{
    static const char path[] = "\\Device\\CdRom0";
    ANSI_STRING name;
    OBJECT_ATTRIBUTES attributes;
    IO_STATUS_BLOCK io;

    init_ansi(&name, path);
    attributes.RootDirectory = NULL;
    attributes.ObjectName = &name;
    attributes.Attributes = OBJ_CASE_INSENSITIVE;
    return NtOpenFile(handle, GENERIC_READ | SYNCHRONIZE, &attributes, &io,
                      FILE_SHARE_READ, FILE_SYNCHRONOUS_IO_NONALERT);
}

static void filesystem_contracts(void)
{
    static const char self_path[] = "\\Device\\CdRom0\\default.xbe";
    static const ULONG unknown_fsctl = CTL_CODE(FILE_DEVICE_FILE_SYSTEM, 0x3ff,
                                                 METHOD_BUFFERED, FILE_ANY_ACCESS);
    FILE_NETWORK_OPEN_INFORMATION information;
    ANSI_STRING self_name;
    OBJECT_ATTRIBUTES self_attributes;
    IO_STATUS_BLOCK io;
    HANDLE volume = NULL;
    NTSTATUS status;

    init_ansi(&self_name, self_path);
    self_attributes.RootDirectory = NULL;
    self_attributes.ObjectName = &self_name;
    self_attributes.Attributes = OBJ_CASE_INSENSITIVE;
    memset(&information, 0, sizeof(information));
    status = NtQueryFullAttributesFile(&self_attributes, &information);
    regression_check(status == STATUS_SUCCESS, "query full attributes of the running DVD image");
    regression_check(information.EndOfFile.QuadPart > 0,
                     "running DVD image has a nonzero end-of-file");
    regression_check(information.AllocationSize.QuadPart >= information.EndOfFile.QuadPart,
                     "DVD image allocation covers its end-of-file");
    regression_check(!(information.FileAttributes & FILE_ATTRIBUTE_DIRECTORY),
                     "running DVD image is reported as a file");

    status = open_dvd_root(&volume);
    regression_check(status == STATUS_SUCCESS && volume != NULL,
                     "open the read-only DVD volume for a filesystem control");
    if (!NT_SUCCESS(status)) return;
    memset(&io, 0xa5, sizeof(io));
    status = NtFsControlFile(volume, NULL, NULL, NULL, &io, unknown_fsctl,
                             NULL, 0, NULL, 0);
    regression_check(status == (NTSTATUS)STATUS_INVALID_DEVICE_REQUEST,
                     "unknown DVD filesystem control is rejected");
    regression_check(NtClose(volume) == STATUS_SUCCESS, "close the DVD volume handle");
}

static void floating_point_contracts(void)
{
    KFLOATING_SAVE saved;
    unsigned short original, changed, observed;
    NTSTATUS status;

    __asm__ volatile("fnstcw %0" : "=m"(original));
    status = KeSaveFloatingPointState(&saved);
    regression_check(status == STATUS_SUCCESS, "save the current floating-point state");
    if (!NT_SUCCESS(status)) return;

    changed = original ^ 0x0c00;
    __asm__ volatile("fldcw %1\n\tfnstcw %0" : "=m"(observed) : "m"(changed));
    regression_check(observed == changed, "test changes the x87 rounding-control field");
    status = KeRestoreFloatingPointState(&saved);
    regression_check(status == STATUS_SUCCESS, "restore the saved floating-point state");
    __asm__ volatile("fnstcw %0" : "=m"(observed));
    regression_check(observed == original, "floating-point restore recovers the original control word");
    if (observed != original) __asm__ volatile("fldcw %0" :: "m"(original));
}

__asm__(
    ".text\n"
    "_contract_capture_with_frame:\n\t"
    "pushl %ebp\n\t"
    "movl %esp, %ebp\n\t"
    "pushl 8(%ebp)\n\t"
    "call _RtlCaptureContext@4\n\t"
    "popl %ebp\n\t"
    "ret\n");
extern void __cdecl contract_capture_with_frame(CONTEXT *context);

static void capture_context_contracts(void)
{
    volatile char *pad = __builtin_alloca(16);
    CONTEXT context;
    ULONG function, frame;

    pad[0] = 0;
    memset(&context, 0xee, sizeof(context));
    contract_capture_with_frame(&context);
    regression_check(context.ContextFlags == 0xeeeeeeee,
                     "capture leaves the caller's ContextFlags sentinel unchanged");
    function = (ULONG)(ULONG_PTR)capture_context_contracts;
    regression_check(context.Eip >= function && context.Eip < function + 0x300,
                     "captured instruction pointer returns into the calling test");
    frame = (ULONG)(ULONG_PTR)__builtin_frame_address(0);
    regression_check(context.Ebp == frame, "captured base pointer identifies the caller frame");
    regression_check(context.Esp > frame - 0x1000 && context.Esp < frame + 0x100,
                     "captured stack pointer lies within the caller frame bounds");
    regression_check(context.SegCs != 0 && context.SegSs != 0 &&
                     !(context.SegCs & 3) && !(context.SegSs & 3),
                     "captured code and stack segments are ring zero selectors");
    regression_check(context.EFlags & 0x200, "captured flags record enabled interrupts");
}

static void pci_read_contracts(void)
{
    ULONG identity = 0xffffffff;

    HalReadWritePCISpace(0, 0, 0, &identity, sizeof(identity), FALSE);
    regression_check((identity & 0xffff) == 0x10de,
                     "read-only host bridge query reports the Xbox NVIDIA vendor");
    regression_check((identity >> 16) != 0 && (identity >> 16) != 0xffff,
                     "read-only host bridge query reports a present device");
}

int main(void)
{
    regression_begin();
    tap_puts("== kernel-export-contracts begin schema=1 ==\n");
    timer_contracts();
    slist_contracts();
    semaphore_contracts();
    irql_and_dpc_contracts();
    synchronize_contracts();
    io_invalid_contracts();
    object_directory_contracts();
    filesystem_contracts();
    floating_point_contracts();
    capture_context_contracts();
    pci_read_contracts();
    regression_finish();
}
