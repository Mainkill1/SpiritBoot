/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <windows.h>
#include <xboxkrnl/xboxkrnl.h>
#include <string.h>
#include "regression.h"

static void system_case(ULONG pages, ULONG protect)
{
    SIZE_T size = pages * 4096;
    PUCHAR p = MmAllocateSystemMemory(size, protect);
    regression_require(p != NULL, "system allocation succeeds");
    BOOLEAN zero = TRUE;
    for (SIZE_T i = 0; i < size; ++i) if (p[i]) { zero = FALSE; break; }
    regression_check(zero, "entire system allocation is zero");
    if (protect == PAGE_READWRITE) {
        memset(p, 0x5a, size);
        regression_check(p[0] == 0x5a && p[size - 1] == 0x5a,
                         "system allocation is writable through both ends");
    }
    tap_comment("system pages=%lu protect=%lu VA=%p PA=%08lx", pages, protect,
                p, (ULONG)MmGetPhysicalAddress(p));
    regression_check(MmFreeSystemMemory(p, size) == pages, "system free returns exact page count");
}

static BOOLEAN verify_bytes(const UCHAR *p, ULONG size, UCHAR salt)
{
    for (ULONG i = 0; i < size; ++i) if (p[i] != (UCHAR)(i ^ salt)) return FALSE;
    return TRUE;
}

/* A 1 MiB window surrounding a live page can include unrelated immovable
 * kernel frames. Pin only the observed page: success now proves relocation
 * admission and byte preservation rather than a layout-dependent diagnostic. */
static void relocate_case(BOOLEAN pool)
{
    PVOID memory = NULL;
    SIZE_T size = 4096;
    if (pool) memory = ExAllocatePoolWithTag(size, 'rSyN');
    else regression_require(NT_SUCCESS(NtAllocateVirtualMemory(&memory, 0, &size,
                                      MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE)),
                            "reserve and commit relocation page");
    regression_require(memory != NULL, "live relocation allocation succeeds");
    PUCHAR p = memory;
    for (ULONG i = 0; i < 4096; ++i) p[i] = (UCHAR)(i ^ 0x79);
    ULONG before = (ULONG)MmGetPhysicalAddress(p) & ~4095UL;
    regression_require(before && before < 0x04000000, "relocation page is inside retail physical window");
    PVOID pin = MmAllocateContiguousMemoryEx(4096, before, before + 4095, 0, PAGE_READWRITE);
    regression_check(pin != NULL, "exact live-page contiguous request succeeds");
    ULONG after = (ULONG)MmGetPhysicalAddress(p) & ~4095UL;
    regression_check(after != before, "live page moves outside requested exact frame");
    regression_check(verify_bytes(p, 4096, 0x79), "all live-page bytes survive relocation");
    if (pin) {
        regression_check(((ULONG)MmGetPhysicalAddress(pin) & ~4095UL) == before,
                         "contiguous allocation owns the requested old frame");
        memset(pin, 0xaa, 4096);
        regression_check(verify_bytes(p, 4096, 0x79), "old-frame writes cannot alter relocated live bytes");
        MmFreeContiguousMemory(pin);
    }
    tap_comment("relocation kind=%s old=%08lx new=%08lx pin=%p", pool ? "pool" : "VM", before, after, pin);
    if (pool) ExFreePool(memory);
    else { size = 0; regression_check(NT_SUCCESS(NtFreeVirtualMemory(&memory, &size, MEM_RELEASE)),
                                     "release relocated VM allocation"); }
}

static void pinned_case(void)
{
    PVOID memory = NULL; SIZE_T size = 4096;
    regression_require(NT_SUCCESS(NtAllocateVirtualMemory(&memory, 0, &size,
                            MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE)), "commit pinned VM page");
    memset(memory, 0x6b, 4096);
    ULONG before = (ULONG)MmGetPhysicalAddress(memory) & ~4095UL;
    MmLockUnlockBufferPages(memory, 4096, FALSE);
    PVOID pin = MmAllocateContiguousMemoryEx(4096, before, before + 4095, 0, PAGE_READWRITE);
    regression_check(pin == NULL, "physical pin blocks live-page relocation");
    regression_check(((ULONG)MmGetPhysicalAddress(memory) & ~4095UL) == before &&
                     ((PUCHAR)memory)[4095] == 0x6b, "pinned page stays at same physical frame with intact bytes");
    if (pin) MmFreeContiguousMemory(pin);
    MmLockUnlockBufferPages(memory, 4096, TRUE);
    size = 0; NtFreeVirtualMemory(&memory, &size, MEM_RELEASE);
}

static void pressure_case(void)
{
    /* Force supply failure after earlier batches, while retaining existing
     * live data. The public fallback may also return NULL; do not infer its
     * internal failure stage from the public status alone. */
    PUCHAR witness = MmAllocateSystemMemory(17 * 4096, PAGE_READWRITE);
    regression_require(witness != NULL, "pressure witness allocation succeeds");
    memset(witness, 0xc7, 17 * 4096);
    MM_STATISTICS stats = { .Length = sizeof(MM_STATISTICS) };
    regression_require(NT_SUCCESS(MmQueryStatistics(&stats)), "query supply before exhaustion");
    SIZE_T request = ((SIZE_T)stats.AvailablePages + 32) * 4096;
    regression_require(request < 64 * 1024 * 1024, "exhaustion request fits system aperture");
    PVOID huge = MmAllocateSystemMemory(request, PAGE_READWRITE);
    regression_check(huge == NULL, "oversized system request fails cleanly on 64 MiB setup");
    if (huge) MmFreeSystemMemory(huge, request);
    BOOLEAN intact = TRUE;
    for (ULONG i = 0; i < 17 * 4096; ++i) if (witness[i] != 0xc7) { intact = FALSE; break; }
    regression_check(intact, "failed request preserves neighboring live allocation");
    regression_check(MmFreeSystemMemory(witness, 17 * 4096) == 17, "witness free returns exact page count");
    system_case(17, PAGE_READWRITE);
}

int main(void)
{
    regression_begin();
    MM_STATISTICS stats = { .Length = sizeof(MM_STATISTICS) };
    regression_require(NT_SUCCESS(MmQueryStatistics(&stats)), "query memory profile");
    regression_require(stats.TotalPhysicalPages <= 16384, "fixture runs on pinned 64 MiB profile");
    ULONG counts[] = {1, 2, 8, 9, 16, 17, 1024, 1025, 4096};
    for (unsigned i = 0; i < sizeof(counts) / sizeof(counts[0]); ++i) system_case(counts[i], PAGE_READWRITE);
    system_case(17, PAGE_READONLY);
    relocate_case(FALSE); relocate_case(TRUE); pinned_case(); pressure_case();
    regression_finish();
}
