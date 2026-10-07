/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "../api-regression/harness.h"
#include <string.h>
#include <stdarg.h>
#include <stdio.h>
const char *g_fail_file;
int g_fail_line;
char g_fail_what[160];
void test_record_failure(const char *file, int line, const char *fmt, ...)
{
    va_list ap; g_fail_file = file; g_fail_line = line;
    va_start(ap, fmt); vsnprintf(g_fail_what, sizeof(g_fail_what), fmt, ap); va_end(ap);
}

static bool locks_block_relocation(void)
{
    PVOID va = NULL, pin, chunks[160] = {0};
    SIZE_T bytes;
    ULONG pa = 0, n;
    /* VM pages prefer upper RAM. Fill that class until a movable page is
     * actually inside the contiguous allocator's low-64-MiB aperture. */
    for (n = 0; n < 160; ++n) {
        bytes = 512 * 1024;
        if (NtAllocateVirtualMemory(&chunks[n], 0, &bytes,
            MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE) != STATUS_SUCCESS) break;
        for (ULONG off = 0; off < bytes; off += PAGE_SIZE) {
            PVOID candidate = (PUCHAR)chunks[n] + off;
            pa = MmGetPhysicalAddress(candidate) & ~(PAGE_SIZE - 1);
            if (pa && pa < 0x03FE0000) { va = candidate; break; }
        }
        if (va) { ++n; break; }
    }
    ASSERT_NOT_NULL(va);
    tap_comment("eligible movable page PA=0x%08lx after %lu chunks", pa, n);
    /* Establish the unpinned control before exercising locks. */
    pin = MmAllocateContiguousMemoryEx(PAGE_SIZE, pa, pa + PAGE_SIZE - 1,
                                      PAGE_SIZE, PAGE_READWRITE);
    ASSERT_NOT_NULL(pin);
    MmFreeContiguousMemory(pin);
    pa = MmGetPhysicalAddress(va) & ~(PAGE_SIZE - 1);
    ASSERT_TRUE(pa < 0x03FE0000);
    memset(va, 0x61, PAGE_SIZE);
    pa = MmGetPhysicalAddress(va) & ~(PAGE_SIZE - 1);
    /* Two APIs share one count; PA has deliberately nonzero low bits. */
    MmLockUnlockBufferPages(va, PAGE_SIZE, FALSE);
    MmLockUnlockPhysicalPage(pa + 37, FALSE);
    pin = MmAllocateContiguousMemoryEx(PAGE_SIZE, pa, pa + PAGE_SIZE - 1,
                                       PAGE_SIZE, PAGE_READWRITE);
    ASSERT_EQ_PTR(pin, NULL);
    MmLockUnlockBufferPages(va, PAGE_SIZE, TRUE);
    pin = MmAllocateContiguousMemoryEx(PAGE_SIZE, pa, pa + PAGE_SIZE - 1,
                                       PAGE_SIZE, PAGE_READWRITE);
    ASSERT_EQ_PTR(pin, NULL);
    MmLockUnlockPhysicalPage(pa + 37, TRUE);
    MmLockUnlockPhysicalPage(pa + 37, TRUE); /* no underflow */
    MmLockUnlockPhysicalPage(0xFD000000, FALSE); /* device address */
    pin = MmAllocateContiguousMemoryEx(PAGE_SIZE, pa, pa + PAGE_SIZE - 1,
                                       PAGE_SIZE, PAGE_READWRITE);
    ASSERT_NOT_NULL(pin);
    ASSERT_EQ_U32(MmGetPhysicalAddress(va) == pa, 0);
    ASSERT_EQ_U32(*(UCHAR *)va, 0x61);
    MmFreeContiguousMemory(pin);
    for (ULONG i = 0; i < n; ++i) {
        bytes = 0;
        ASSERT_NTSTATUS(NtFreeVirtualMemory(&chunks[i], &bytes, MEM_RELEASE), STATUS_SUCCESS);
    }
    return true;
}
static bool prompt_detached_is_bounded(void)
{
    char response[3] = { 'x', 'y', 'z' };
    ASSERT_EQ_U32(DbgPrompt("detached", NULL, 0), 0);
    ULONG count = DbgPrompt("detached", response, 1);
    tap_puts("\n"); /* preserve a separate TAP record even on transport failure */
    ASSERT_EQ_U32(count, 0);
    ASSERT_EQ_U32(response[0], 0);
    ASSERT_EQ_U32(response[1], 'y');
    ASSERT_EQ_U32(response[2], 'z');
    return true;
}
static PIDE_START_PACKET_ROUTINE original_start;
static PIDE_FINISHIO_ROUTINE original_finish;
static PIDE_INTERRUPT_ROUTINE original_irq;
static PIDE_START_NEXT_PACKET_ROUTINE original_next;
static ULONG starts, finishes, interrupts, nexts, bad_state;
static VOID NTAPI hooked_start(PDEVICE_OBJECT Device, PIRP Irp)
{
    ++starts;
    if (IdexChannelObject.CurrentIrp != Irp || !IdexChannelObject.StartPacketBusy)
        ++bad_state;
    original_start(Device, Irp);
}
static VOID NTAPI hooked_finish(void)
{ ++finishes; original_finish(); }
static VOID NTAPI hooked_irq(void)
{ ++interrupts; original_irq(); }
static VOID NTAPI hooked_next(void)
{ ++nexts; original_next(); }
static bool ide_callbacks_observe_actual_disc_io(void)
{
    ANSI_STRING name;
    OBJECT_ATTRIBUTES oa;
    IO_STATUS_BLOCK iosb;
    HANDLE file;
    LARGE_INTEGER offset = {.QuadPart = 0};
    PVOID page;
    NTSTATUS status;
    ASSERT_NOT_NULL(IdexChannelObject.StartPacketRoutine);
    ASSERT_NOT_NULL(IdexChannelObject.FinishIoRoutine);
    ASSERT_NOT_NULL(IdexChannelObject.InterruptRoutine);
    name.Buffer = "\\Device\\CdRom0\\default.xbe"; name.Length = strlen(name.Buffer);
    name.MaximumLength = name.Length + 1;
    oa.RootDirectory = NULL; oa.ObjectName = &name; oa.Attributes = OBJ_CASE_INSENSITIVE;
    status = NtCreateFile(&file, GENERIC_READ | SYNCHRONIZE, &oa, &iosb, NULL,
        FILE_ATTRIBUTE_NORMAL, FILE_SHARE_READ, FILE_OPEN,
        FILE_NO_INTERMEDIATE_BUFFERING | FILE_SYNCHRONOUS_IO_NONALERT | FILE_NON_DIRECTORY_FILE);
    ASSERT_NTSTATUS(status, STATUS_SUCCESS);
    page = MmAllocateContiguousMemory(PAGE_SIZE);
    ASSERT_NOT_NULL(page);
    original_start = IdexChannelObject.StartPacketRoutine;
    original_finish = IdexChannelObject.FinishIoRoutine;
    original_irq = IdexChannelObject.InterruptRoutine;
    original_next = IdexChannelObject.StartNextPacketRoutine;
    starts = finishes = interrupts = nexts = bad_state = 0;
    IdexChannelObject.StartPacketRoutine = hooked_start;
    IdexChannelObject.FinishIoRoutine = hooked_finish;
    IdexChannelObject.InterruptRoutine = hooked_irq;
    IdexChannelObject.StartNextPacketRoutine = hooked_next;
    status = NtReadFile(file, NULL, NULL, NULL, &iosb, page, 2048, &offset);
    IdexChannelObject.StartPacketRoutine = original_start;
    IdexChannelObject.FinishIoRoutine = original_finish;
    IdexChannelObject.InterruptRoutine = original_irq;
    IdexChannelObject.StartNextPacketRoutine = original_next;
    MmFreeContiguousMemory(page); NtClose(file);
    tap_comment("IDE lifecycle starts=%lu finishes=%lu irqs=%lu next=%lu bad=%lu",
                starts, finishes, interrupts, nexts, bad_state);
    ASSERT_NTSTATUS(status, STATUS_SUCCESS);
    ASSERT_TRUE(starts > 0 && finishes > 0 && interrupts > 0 && nexts > 0);
    ASSERT_EQ_U32(bad_state, 0);
    return true;
}
DECLARE_GROUP(io_scatter);
static bool ide_channel_is_live(void)
{
    ASSERT_EQ_U32(sizeof(IdexChannelObject), 264);
    ASSERT_NOT_NULL(IdexChannelObject.StartPacketRoutine);
    ASSERT_NOT_NULL(IdexChannelObject.StartNextPacketRoutine);
    ASSERT_NOT_NULL(IdexChannelObject.InterruptRoutine);
    ASSERT_TRUE(IdexChannelObject.InterruptIrql > DISPATCH_LEVEL);
    return true;
}
static bool pin_overflow_stays_pinned(void)
{
    PVOID page = MmAllocateContiguousMemory(PAGE_SIZE);
    ASSERT_NOT_NULL(page);
    ULONG pa = MmGetPhysicalAddress(page);
    /* VOID cannot report overflow: it must retain the page conservatively. */
    for (ULONG n = 0; n < 0x8000; ++n) MmLockUnlockPhysicalPage(pa + 37, FALSE);
    for (ULONG n = 0; n < 0x8000; ++n) MmLockUnlockPhysicalPage(pa + 37, TRUE);
    MmFreeContiguousMemory(page);
    ASSERT_EQ_U32(MmQueryAllocationSize(page), PAGE_SIZE);
    PVOID competing = MmAllocateContiguousMemoryEx(PAGE_SIZE, pa, pa + PAGE_SIZE - 1,
        PAGE_SIZE, PAGE_READWRITE);
    ASSERT_EQ_PTR(competing, NULL);
    tap_comment("overflow latch retains one page until reboot (PA=%08lx)", pa);
    return true;
}
bool inline_error_scatter_sync(void);
bool inline_error_scatter_async(void);
bool pending_error_scatter_sync(void);
bool canceled_pending_scatter_async(void);
bool pending_scatter_reverse_completion(void);
bool pending_gather_reverse_completion(void);
int main(void)
{
    const test_entry_t tests[] = {
        {"pin-relocation", locks_block_relocation, NULL},
        {"detached-prompt", prompt_detached_is_bounded, NULL},
        {"live-ide-channel", ide_channel_is_live, NULL},
        {"ide-real-io", ide_callbacks_observe_actual_disc_io, NULL},
        {"pending-scatter-reverse", pending_scatter_reverse_completion, NULL},
        {"pending-gather-reverse", pending_gather_reverse_completion, NULL},
        {"inline-error-sync", inline_error_scatter_sync, NULL},
        {"inline-error-async", inline_error_scatter_async, NULL},
        {"pending-error-sync", pending_error_scatter_sync, NULL},
        {"cancel-pending-async", canceled_pending_scatter_async, NULL},
        {"pin-overflow-safe", pin_overflow_stays_pinned, NULL}
    };
    tap_puts("== clean-room-contracts begin ==\n");
    tap_version(14); tap_plan(11 + g_group_io_scatter.count);
    unsigned failures = 0;
    for (unsigned i = 0; i < 11; ++i) {
        g_fail_what[0] = 0;
        if (tests[i].fn()) tap_ok(i + 1, tests[i].name);
        else { tap_not_ok(i + 1, tests[i].name); tap_comment("%s", g_fail_what); ++failures; }
    }
    for (unsigned i = 0; i < g_group_io_scatter.count; ++i) {
        const test_entry_t *t = &g_group_io_scatter.entries[i];
        g_fail_what[0] = 0;
        if (t->fn()) tap_ok(i + 12, t->name);
        else { tap_not_ok(i + 12, t->name); tap_comment("%s", g_fail_what); ++failures; }
    }
    tap_puts(failures ? "== clean-room-contracts end FAIL ==\n" :
                        "== clean-room-contracts end PASS ==\n");
    tap_drain(); HalWriteSMBusValue(0x20, 0x02, FALSE, 0x80);
    for (;;) __asm__ __volatile__("hlt");
}
