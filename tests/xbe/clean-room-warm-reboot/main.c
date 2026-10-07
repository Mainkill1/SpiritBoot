/* SPDX-License-Identifier: GPL-2.0-or-later
 * A two-boot guest: retain only the middle page of a three-page allocation,
 * record actual shutdown callbacks in that page, then validate restored RAM.
 * Deliberately uses the former loader XZ scratch window (PA 32 MiB).
 */
#include <xboxkrnl/xboxkrnl.h>
#include "../api-regression/tap.h"
#include <string.h>
#define DATA_PA 0x02000000UL
#define PROBE_MAGIC 0x43524D50UL /* independent test sentinel */
typedef struct { ULONG Magic, Pa, Count, NestedReturned, Order[6]; UCHAR Fill[64]; } PROBE;
static PROBE *record;
static HAL_SHUTDOWN_REGISTRATION regs[5];
static VOID NTAPI notify(PHAL_SHUTDOWN_REGISTRATION Registration)
{
    ULONG id = (ULONG)(Registration - regs) + 1;
    if (record->Count < 6) record->Order[record->Count++] = id;
    if (id == 1) {
        HalRegisterShutdownNotification(&regs[4], FALSE);
        /* A real public return-to-firmware call must unwind to the outer
         * drain (never resume its noreturn callsite); otherwise stage 2 observes only this first callback. */
        HalReturnToFirmware(HalQuickRebootRoutine);
        record->NestedReturned = 1;
    }
}
static VOID stop(void)
{
    tap_drain(); HalWriteSMBusValue(0x20, 0x02, FALSE, 0x80);
    for (;;) __asm__ __volatile__("hlt");
}
int main(void)
{
    ULONG magic = 0, pa = 0;
    if (LaunchDataPage) {
        memcpy(&magic, LaunchDataPage->LaunchData, sizeof(magic));
        memcpy(&pa, LaunchDataPage->LaunchData + sizeof(magic), sizeof(pa));
    }
    if (magic == PROBE_MAGIC) {
        BOOLEAN pass = TRUE;
        tap_puts("== clean-room-warm-reboot stage 2 ==\n");
        tap_version(14); tap_plan(5);
        record = (PROBE *)(0x80000000UL | pa);
        pass = record->Magic == PROBE_MAGIC && MmGetPhysicalAddress(record) == pa;
        if (pass) tap_ok(1, "same physical address and contents");
        else tap_not_ok(1, "same physical address and contents");
        BOOLEAN order = record->Count == 3 && record->Order[0] == 1 &&
                        record->Order[1] == 2 && record->Order[2] == 3;
        if (order) tap_ok(2, "shutdown stable priority, duplicate and pending removal");
        else tap_not_ok(2, "shutdown stable priority, duplicate and pending removal");
        pass &= order;
        BOOLEAN ownership = MmQueryAllocationSize(record) == PAGE_SIZE;
        if (ownership) tap_ok(3, "restored selected range owns one page");
        else tap_not_ok(3, "restored selected range owns one page");
        pass &= ownership;
        BOOLEAN data = TRUE;
        for (ULONG i = 0; i < sizeof(record->Fill); ++i) if (record->Fill[i] != 0xA6) data = FALSE;
        PVOID competing = MmAllocateContiguousMemoryEx(PAGE_SIZE, pa, pa + PAGE_SIZE - 1,
                                                       PAGE_SIZE, PAGE_READWRITE);
        data &= competing == NULL;
        if (competing) MmFreeContiguousMemory(competing);
        if (data) tap_ok(4, "persistent content survives and competing allocation is refused");
        else tap_not_ok(4, "persistent content survives and competing allocation is refused");
        pass &= data;
        BOOLEAN nested = record->NestedReturned == 0 && order;
        if (nested) tap_ok(5, "nested noreturn reset unwinds and remaining callbacks run before outer reset");
        else tap_not_ok(5, "nested noreturn reset unwinds and remaining callbacks run before outer reset");
        pass &= nested;
        MmPersistContiguousMemory(record, PAGE_SIZE, FALSE);
        MmFreeContiguousMemory(record);
        tap_puts(pass ? "== clean-room-warm-reboot end PASS ==\n" :
                        "== clean-room-warm-reboot end FAIL ==\n");
        stop();
    }
    tap_puts("== clean-room-warm-reboot stage 1 ==\n");
    PVOID allocation = MmAllocateContiguousMemoryEx(3 * PAGE_SIZE, DATA_PA,
        DATA_PA + 3 * PAGE_SIZE - 1, PAGE_SIZE, PAGE_READWRITE);
    if (!allocation) { tap_puts("== clean-room-warm-reboot setup FAIL ==\n"); stop(); }
    memset(allocation, 0x37, 3 * PAGE_SIZE);
    record = (PROBE *)((PUCHAR)allocation + PAGE_SIZE);
    memset(record, 0, sizeof(*record)); record->Magic = PROBE_MAGIC;
    record->Pa = DATA_PA + PAGE_SIZE; memset(record->Fill, 0xA6, sizeof(record->Fill));
    MmPersistContiguousMemory(allocation, 3 * PAGE_SIZE, TRUE);
    MmPersistContiguousMemory(allocation, PAGE_SIZE, FALSE);
    MmPersistContiguousMemory((PUCHAR)allocation + 2 * PAGE_SIZE, PAGE_SIZE, FALSE);
    MmPersistContiguousMemory((PUCHAR)record + 17, 20, TRUE); /* valid partial range */
    MmPersistContiguousMemory((PVOID)0xFFFFFFF0, 128, TRUE); /* overflow, inert */
    for (ULONG i = 0; i < 5; ++i) {
        regs[i].NotificationRoutine = notify;
        regs[i].Priority = i < 2 ? 100 : 10 - (LONG)i;
        HalRegisterShutdownNotification(&regs[i], TRUE);
    }
    HalRegisterShutdownNotification(&regs[0], TRUE); /* stable duplicate */
    HalRegisterShutdownNotification(&regs[3], FALSE); /* removed before shutdown */
    LaunchDataPage = MmAllocateContiguousMemory(PAGE_SIZE);
    if (!LaunchDataPage) { tap_puts("== clean-room-warm-reboot launch FAIL ==\n"); stop(); }
    memset(LaunchDataPage, 0, PAGE_SIZE);
    LaunchDataPage->Header.dwLaunchDataType = 0;
    strcpy(LaunchDataPage->Header.szLaunchPath, "\\Device\\CdRom0\\default.xbe");
    magic = PROBE_MAGIC; pa = record->Pa;
    memcpy(LaunchDataPage->LaunchData, &magic, sizeof(magic));
    memcpy(LaunchDataPage->LaunchData + sizeof(magic), &pa, sizeof(pa));
    MmPersistContiguousMemory(LaunchDataPage, PAGE_SIZE, TRUE);
    tap_puts("== clean-room-warm-reboot resetting ==\n"); tap_drain();
    HalReturnToFirmware(HalQuickRebootRoutine);
    tap_puts("== clean-room-warm-reboot reset returned FAIL ==\n"); stop();
    return 1;
}
