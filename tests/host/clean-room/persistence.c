/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
#include "ntoskrnl.h"
UCHAR __ImageBase[1];
static bool pinned;
static unsigned returned;
void NxkPageSupplyReturn(PFN_NUMBER page) { (void)page; ++returned; }
BOOLEAN NxkPageSupplyIsPinned(PFN_NUMBER page) { (void)page; return pinned; }
#include "../../../ntoskrnl/xb/mm/persistence.c"
static unsigned tests, failed;
#define CHECK(c) do { ++tests; if (!(c)) { ++failed; printf("not ok %u - %s:%d %s\n", tests, __FILE__, __LINE__, #c); } else printf("ok %u - %s\n", tests, #c); } while(0)
static void reset(void)
{
    memset((void *)PM_VA, 0, PAGE_SIZE); memset((void *)PM_LAUNCH_VA, 0, PAGE_SIZE);
    memset(PmSelected, 0, sizeof(PmSelected)); memset(PmRestored, 0, sizeof(PmRestored));
    pinned = false; returned = 0;
}
static void reboot_read(LOADER_PARAMETER_BLOCK *lb)
{
    memset(PmSelected, 0, sizeof(PmSelected)); memset(PmRestored, 0, sizeof(PmRestored));
    NxkMmReadPersistence(lb);
}
int main(void)
{
    void *ram = mmap((void *)NXK_KSEG0_BASE, NXK_KSEG0_RAM_SIZE,
        PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED_NOREPLACE, -1, 0);
    if (ram == MAP_FAILED) { perror("mmap"); return 2; }
    LOADER_PARAMETER_BLOCK lb;
    MEMORY_ALLOCATION_DESCRIPTOR d;
    lb.MemoryDescriptorListHead.Flink = lb.MemoryDescriptorListHead.Blink = &d.ListEntry;
    d.ListEntry.Flink = d.ListEntry.Blink = &lb.MemoryDescriptorListHead;
    d.MemoryType = LoaderFree; d.BasePage = 0x200; d.PageCount = 0x3C00 - 0x200;
    PM_HANDOFF *slot = (PM_HANDOFF *)PM_VA;
    PVOID alias = (void *)(NXK_KSEG0_BASE | 0x2001000);
    reset(); reboot_read(&lb); CHECK(!NxkMmPersistentPage(0x2001));
    NxkMmSetPersistentPages(0x2001011, 20, TRUE);
    CHECK(PmBit(PmSelected, 0x2001) && !PmBit(PmSelected, 0x2000));
    NxkMmPublishPersistence(TRUE); CHECK(slot->Magic == PM_MAGIC);
    reboot_read(&lb); CHECK(slot->Magic == 0 && NxkMmPersistentPage(0x2001));
    CHECK(NxkMmQueryRestored(alias) == PAGE_SIZE);
    NxkMmSetPersistentPages(0x2001000, PAGE_SIZE, FALSE);
    CHECK(NxkMmPersistentPage(0x2001) && !PmBit(PmSelected, 0x2001));
    pinned = true; CHECK(NxkMmFreeRestored(alias) && returned == 0);
    CHECK(NxkMmQueryRestored(alias) == PAGE_SIZE);
    pinned = false; CHECK(NxkMmFreeRestored(alias) && returned == 1);
    CHECK(NxkMmQueryRestored(alias) == 0 && !PmBit(PmSelected, 0x2001));
    reset(); PmSet(PmSelected, 0x2001, TRUE); NxkMmPublishPersistence(TRUE);
    slot->Pages[0x2001 >> 3] ^= 1; reboot_read(&lb); CHECK(!NxkMmPersistentPage(0x2001));
    reset(); PmSet(PmSelected, 0x2001, TRUE); NxkMmPublishPersistence(TRUE);
    slot->Version++; reboot_read(&lb); CHECK(!NxkMmPersistentPage(0x2001));
    reset(); PmSet(PmSelected, 0x2001, TRUE); NxkMmPublishPersistence(TRUE);
    slot->ImageBase++; reboot_read(&lb); CHECK(!NxkMmPersistentPage(0x2001));
    reset(); PmSet(PmSelected, 0x2001, TRUE); NxkMmPublishPersistence(TRUE);
    *(ULONG *)PM_LAUNCH_VA = PM_LAUNCH_MAGIC; reboot_read(&lb); CHECK(!NxkMmPersistentPage(0x2001));
    reset(); PmSet(PmSelected, 0x2001, TRUE); PmSet(PmSelected, 0x30, TRUE);
    NxkMmPublishPersistence(TRUE); reboot_read(&lb); CHECK(!NxkMmPersistentPage(0x2001));
    reset(); PmSet(PmSelected, 0x2001, TRUE); NxkMmPublishPersistence(TRUE);
    reboot_read(&lb); reboot_read(&lb); CHECK(!NxkMmPersistentPage(0x2001));
    reset(); PmSet(PmSelected, 0x2001, TRUE); NxkMmPublishPersistence(FALSE);
    CHECK(slot->Magic == 0);
    reset(); NxkMmSetPersistentPages(0x30000, PAGE_SIZE, TRUE);
    CHECK(!PmBit(PmSelected, 0x30));
    printf("persistence host checks: %u/%u passed\n", tests - failed, tests);
    return failed ? 1 : 0;
}
