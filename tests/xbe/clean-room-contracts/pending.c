/* SPDX-License-Identifier: GPL-2.0-or-later */
/* A deterministic public title driver holds two requests on one async handle.
 * No scheduling or filesystem speed assumption can turn these into inline IO. */
#include "../api-regression/harness.h"
#include <string.h>

static DRIVER_OBJECT driver;
static PDEVICE_OBJECT device;
static PIRP held[2];
static ULONG lengths[2], calls, bad;
static bool writing;
static ULONG error_mode, error_completions;
static KDPC error_dpc;
static NTSTATUS expected_status[2];
static ULONG expected_bytes[2];
static VOID NTAPI error_complete_dpc(PKDPC dpc, PVOID context, PVOID arg1, PVOID arg2)
{
    PIRP irp = arg1;
    (void)dpc; (void)context; (void)arg2;
    ++error_completions;
    irp->IoStatus.Status = STATUS_END_OF_FILE; irp->IoStatus.Information = 0;
    IofCompleteRequest(irp, 0);
}
static PVOID pages;
static FILE_SEGMENT_ELEMENT segments[2][3];
static IO_STATUS_BLOCK results[2];
static HANDLE events[2], apc_gate;
static ULONG apcs[2], apc_order[2], apc_count;
static PIO_STATUS_BLOCK apc_iosb[2];
static const char path[] = "\\Device\\cleanroompending";

static NTSTATUS NTAPI dispatch(PDEVICE_OBJECT dev, PIRP irp)
{
    UCHAR *stack = (UCHAR *)irp->Tail.Overlay.CurrentStackLocation;
    ULONG *raw = (ULONG *)stack;
    (void)dev;
    if (stack[0] == 2 && error_mode) {
        ++calls;
        if (error_mode == 1) {
            ++error_completions;
            irp->IoStatus.Status = STATUS_END_OF_FILE; irp->IoStatus.Information = 0;
            IofCompleteRequest(irp, 0);
            return STATUS_END_OF_FILE;
        }
        stack[3] |= 1;
        if (error_mode == 2) KeInsertQueueDpc(&error_dpc, irp, NULL);
        else held[0] = irp;
        return STATUS_PENDING;
    }
    if (stack[0] == 2 || stack[0] == 3) {
        ULONG id = raw[3]; /* public read/write byte offset low word */
        if (id > 1 || held[id] || calls >= 2) {
            ++bad;
            irp->IoStatus.Status = STATUS_INVALID_PARAMETER;
            irp->IoStatus.Information = 0;
            IofCompleteRequest(irp, 0);
            return STATUS_INVALID_PARAMETER;
        }
        held[id] = irp; lengths[id] = raw[1]; ++calls;
        if ((stack[0] == 3) != writing || lengths[id] != (id + 1) * PAGE_SIZE)
            ++bad;
        stack[3] |= 1; /* SL_PENDING_RETURNED; nxdk omits stack accessor macros */
        return STATUS_PENDING;
    }
    irp->IoStatus.Status = STATUS_SUCCESS;
    irp->IoStatus.Information = stack[0] == 0 ? FILE_OPENED : 0;
    IofCompleteRequest(irp, 0);
    return STATUS_SUCCESS;
}

static VOID NTAPI completion_apc(PVOID context, PIO_STATUS_BLOCK iosb, ULONG reserved)
{
    ULONG id = (ULONG_PTR)context - 1;
    (void)reserved;
    if (id > 1 || apc_count >= 2) { ++bad; return; }
    ++apcs[id]; apc_order[apc_count++] = id; apc_iosb[id] = iosb;
    if (iosb != &results[id] || iosb->Status != expected_status[id] ||
        iosb->Information != expected_bytes[id]) ++bad;
}

static bool setup(void)
{
    OBJECT_STRING name = {sizeof(path) - 1, sizeof(path), (PCHAR)path};
    if (device) return true;
    for (unsigned i = 0; i < 14; ++i) driver.MajorFunction[i] = dispatch;
    if (IoCreateDevice(&driver, 0, &name, 0x22, FALSE, &device) != STATUS_SUCCESS)
        return false;
    device->Flags &= ~0x10u; /* DO_DEVICE_INITIALIZING */
    pages = MmAllocateContiguousMemory(6 * PAGE_SIZE);
    if (!pages) return false;
    for (unsigned i = 0; i < 2; ++i)
        if (NtCreateEvent(&events[i], NULL, NotificationEvent, FALSE) != STATUS_SUCCESS)
            return false;
    return NtCreateEvent(&apc_gate, NULL, NotificationEvent, FALSE) == STATUS_SUCCESS;
}

static bool pending_pair(bool write)
{
    OBJECT_ATTRIBUTES oa;
    ANSI_STRING name = {sizeof(path) - 1, sizeof(path), (PCHAR)path};
    IO_STATUS_BLOCK opened;
    HANDLE file;
    LARGE_INTEGER offsets[2], poll = {.QuadPart = 0}, timeout = {.QuadPart = -1000000};
    NTSTATUS status[2];
    typedef NTSTATUS (NTAPI *gather_fn)(HANDLE, HANDLE, PIO_APC_ROUTINE, PVOID,
        PIO_STATUS_BLOCK, PFILE_SEGMENT_ELEMENT, ULONG, PLARGE_INTEGER);
    ASSERT_TRUE(setup());
    writing = write; error_mode = 0; calls = bad = apc_count = 0;
    memset(held, 0, sizeof(held)); memset(apcs, 0, sizeof(apcs));
    memset(pages, 0xEE, 6 * PAGE_SIZE);
    oa.RootDirectory = NULL; oa.ObjectName = &name; oa.Attributes = OBJ_CASE_INSENSITIVE;
    ASSERT_NTSTATUS(NtCreateFile(&file, GENERIC_READ | GENERIC_WRITE | SYNCHRONIZE,
        &oa, &opened, NULL, FILE_ATTRIBUTE_NORMAL, 0, FILE_OPEN,
        FILE_NO_INTERMEDIATE_BUFFERING | FILE_NON_DIRECTORY_FILE), STATUS_SUCCESS);
    for (unsigned i = 0; i < 2; ++i) {
        NtClearEvent(events[i]);
        expected_status[i] = STATUS_SUCCESS; expected_bytes[i] = (i + 1) * PAGE_SIZE;
        results[i].Status = STATUS_PENDING; results[i].Information = 0xABCD;
        segments[i][0].Buffer = (PUCHAR)pages + (i * 3) * PAGE_SIZE;
        segments[i][1].Buffer = (PUCHAR)pages + (i * 3 + 2) * PAGE_SIZE;
        segments[i][2].Buffer = NULL;
        offsets[i].QuadPart = i;
        if (write)
            for (unsigned p = 0; p <= i; ++p)
                memset(segments[i][p].Buffer, 0x40 + i * 4 + p, PAGE_SIZE);
        status[i] = write ? ((gather_fn)NtWriteFileGather)(file, events[i], completion_apc,
            (PVOID)(i + 1), &results[i], segments[i], (i + 1) * PAGE_SIZE, &offsets[i]) :
            NtReadFileScatter(file, events[i], completion_apc, (PVOID)(i + 1),
            &results[i], segments[i], (i + 1) * PAGE_SIZE, &offsets[i]);
        ASSERT_NTSTATUS(status[i], STATUS_PENDING);
        ASSERT_NOT_NULL(held[i]);
        ASSERT_NTSTATUS(NtWaitForSingleObject(events[i], FALSE, &poll), STATUS_TIMEOUT);
        ASSERT_NTSTATUS(results[i].Status, STATUS_PENDING);
        ASSERT_EQ_U32(results[i].Information, 0xABCD);
        /* The request must own a capture after dispatch returns. */
        memset(segments[i], 0, sizeof(segments[i])); offsets[i].QuadPart = 0x7FFFFFFF;
    }
    ASSERT_EQ_U32(calls, 2);
    ASSERT_TRUE(held[0] != held[1] && held[0]->UserBuffer != held[1]->UserBuffer);
    if (write) memset(pages, 0xEE, 6 * PAGE_SIZE); /* gather already captured input */
    for (unsigned n = 2; n-- > 0;) {
        PIRP irp = held[n];
        for (unsigned p = 0; p <= n; ++p) {
            PUCHAR buffer = (PUCHAR)irp->UserBuffer + p * PAGE_SIZE;
            if (write) {
                for (unsigned b = 0; b < PAGE_SIZE; ++b)
                    if (buffer[b] != 0x40 + n * 4 + p) ++bad;
            } else memset(buffer, 0x70 + n * 4 + p, PAGE_SIZE);
        }
        /* Complete out of line at DPC level, then allow native completion APCs. */
        KIRQL old = KeRaiseIrqlToDpcLevel();
        irp->IoStatus.Status = STATUS_SUCCESS; irp->IoStatus.Information = lengths[n];
        held[n] = NULL; IofCompleteRequest(irp, 0); KfLowerIrql(old);
        ASSERT_NTSTATUS(NtWaitForSingleObject(events[n], FALSE, &timeout), STATUS_SUCCESS);
        /* APC delivery is alertable, independently of the completion event. */
        NtWaitForSingleObjectEx(apc_gate, UserMode, TRUE, &timeout);
        ASSERT_NTSTATUS(results[n].Status, STATUS_SUCCESS);
        ASSERT_EQ_U32(results[n].Information, (n + 1) * PAGE_SIZE);
        ASSERT_EQ_U32(apcs[n], 1); ASSERT_EQ_PTR(apc_iosb[n], &results[n]);
        if (n == 1) {
            ASSERT_NTSTATUS(results[0].Status, STATUS_PENDING);
            ASSERT_EQ_U32(results[0].Information, 0xABCD);
            ASSERT_NTSTATUS(NtWaitForSingleObject(events[0], FALSE, &poll), STATUS_TIMEOUT);
            ASSERT_EQ_U32(apcs[0], 0);
        }
        if (!write) {
            for (unsigned p = 0; p <= n; ++p)
                for (unsigned b = 0; b < PAGE_SIZE; ++b)
                    if (((PUCHAR)pages)[(n * 3 + p * 2) * PAGE_SIZE + b] != 0x70 + n * 4 + p)
                        ++bad;
            for (unsigned b = 0; b < PAGE_SIZE; ++b)
                if (((PUCHAR)pages)[(n * 3 + 1) * PAGE_SIZE + b] != 0xEE) ++bad;
        }
    }
    NtClose(file);
    tap_comment("pending %s returns=%08lx,%08lx completion order=%lu,%lu APCs=%lu,%lu bad=%lu",
        write ? "gather" : "scatter", status[0], status[1], apc_order[0], apc_order[1],
        apcs[0], apcs[1], bad);
    ASSERT_EQ_U32(apc_count, 2); ASSERT_EQ_U32(apc_order[0], 1);
    ASSERT_EQ_U32(apc_order[1], 0); ASSERT_EQ_U32(bad, 0);
    return true;
}
bool pending_scatter_reverse_completion(void) { return pending_pair(false); }
bool pending_gather_reverse_completion(void) { return pending_pair(true); }

/* Inline error and native pending synchronous-file error used to skip the
 * IOSB/event/APC branch. This seeds visible sentinels instead of zeroing them. */
static bool error_transfer(bool synchronous, ULONG mode)
{
    ANSI_STRING name = {sizeof(path) - 1, sizeof(path), (PCHAR)path};
    OBJECT_ATTRIBUTES oa;
    IO_STATUS_BLOCK opened;
    HANDLE file;
    LARGE_INTEGER offset = {.QuadPart = 0}, poll = {.QuadPart = 0};
    LARGE_INTEGER timeout = {.QuadPart = -1000000};
    NTSTATUS status;
    ASSERT_TRUE(setup());
    calls = bad = apc_count = error_completions = 0; error_mode = mode;
    memset(held, 0, sizeof(held)); memset(apcs, 0, sizeof(apcs));
    expected_status[0] = mode == 3 ? STATUS_CANCELLED : STATUS_END_OF_FILE;
    expected_bytes[0] = 0;
    NtClearEvent(events[0]);
    results[0].Status = STATUS_PENDING; results[0].Information = 0xABCD;
    memset(pages, 0xEE, PAGE_SIZE);
    segments[0][0].Buffer = pages; segments[0][1].Buffer = NULL;
    KeInitializeDpc(&error_dpc, error_complete_dpc, NULL);
    oa.RootDirectory = NULL; oa.ObjectName = &name; oa.Attributes = OBJ_CASE_INSENSITIVE;
    ASSERT_NTSTATUS(NtCreateFile(&file, GENERIC_READ | SYNCHRONIZE, &oa, &opened,
        NULL, FILE_ATTRIBUTE_NORMAL, 0, FILE_OPEN, FILE_NO_INTERMEDIATE_BUFFERING |
        FILE_NON_DIRECTORY_FILE | (synchronous ? FILE_SYNCHRONOUS_IO_NONALERT : 0)), STATUS_SUCCESS);
    status = NtReadFileScatter(file, events[0], completion_apc, (PVOID)1,
        &results[0], segments[0], PAGE_SIZE, &offset);
    if (mode == 3) {
        ASSERT_NTSTATUS(status, STATUS_PENDING); ASSERT_NOT_NULL(held[0]);
        ASSERT_NTSTATUS(NtWaitForSingleObject(events[0], FALSE, &poll), STATUS_TIMEOUT);
        ASSERT_NTSTATUS(results[0].Status, STATUS_PENDING);
        ASSERT_EQ_U32(results[0].Information, 0xABCD);
        /* nxdk exposes the driver's Cancel acknowledgement flag but no
         * cancellation syscall. Exercise native canceled-IRP completion. */
        KIRQL old = KeRaiseIrqlToDpcLevel();
        PIRP irp = held[0]; held[0] = NULL; irp->Cancel = TRUE;
        irp->IoStatus.Status = STATUS_CANCELLED; irp->IoStatus.Information = 0;
        ++error_completions; IofCompleteRequest(irp, 0); KfLowerIrql(old);
    } else ASSERT_NTSTATUS(status, STATUS_END_OF_FILE);
    ASSERT_NTSTATUS(NtWaitForSingleObject(events[0], FALSE, &timeout), STATUS_SUCCESS);
    NtWaitForSingleObjectEx(apc_gate, UserMode, TRUE, &timeout);
    ASSERT_NTSTATUS(results[0].Status, expected_status[0]);
    ASSERT_EQ_U32(results[0].Information, 0);
    ASSERT_EQ_U32(apcs[0], 1); ASSERT_EQ_PTR(apc_iosb[0], &results[0]);
    ASSERT_EQ_U32(calls, 1); ASSERT_EQ_U32(error_completions, 1);
    ASSERT_EQ_U32(bad, 0);
    for (unsigned b = 0; b < PAGE_SIZE; ++b) ASSERT_EQ_U32(((PUCHAR)pages)[b], 0xEE);
    NtClose(file); error_mode = 0;
    tap_comment("error scatter synchronous=%u mode=%lu status=%08lx IOSB=%08lx bytes=%lu APCs=%lu",
        synchronous, mode, status, results[0].Status, results[0].Information, apcs[0]);
    return true;
}
bool inline_error_scatter_sync(void) { return error_transfer(true, 1); }
bool inline_error_scatter_async(void) { return error_transfer(false, 1); }
bool pending_error_scatter_sync(void) { return error_transfer(true, 2); }
bool canceled_pending_scatter_async(void) { return error_transfer(false, 3); }
