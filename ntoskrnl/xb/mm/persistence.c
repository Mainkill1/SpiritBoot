/* SPDX-License-Identifier: GPL-2.0-or-later
 * Independently designed one-shot warm RAM handoff. No firmware-derived data.
 * Only the low 64 MiB contiguous aperture can persist. A selected partial page
 * is retained whole. Restored allocations are maximal selected page runs;
 * their alias bases can be queried/freed by the next title. Original holes and
 * unselected pages are ordinary free memory on reboot.
 */
#include <ntoskrnl.h>
#include <mm/ARM3/miarm.h>
#include "mm.h"
#define PM_PAGES (NXK_KSEG0_RAM_SIZE / PAGE_SIZE)
#define PM_BYTES (PM_PAGES / 8)
#define PM_VA (NXK_KSEG0_BASE | 0xD000)
#define PM_MAGIC 0x4D50584EUL /* independently chosen format tag: NXPM */
#define PM_VERSION 1
#define PM_LAUNCH_VA (NXK_KSEG0_BASE | 0xE000)
#define PM_LAUNCH_MAGIC 0x6E78436CUL /* existing kernel launch protocol */
#define PM_LAUNCH_BYTES 3616

typedef struct _PM_HANDOFF {
    ULONG Magic, Version, BitmapBytes, ImageBase, LaunchHash, Checksum;
    UCHAR Pages[PM_BYTES];
} PM_HANDOFF;
C_ASSERT(sizeof(PM_HANDOFF) <= PAGE_SIZE);
static UCHAR PmSelected[PM_BYTES];
static UCHAR PmRestored[PM_BYTES];

static BOOLEAN PmBit(const UCHAR *Map, PFN_NUMBER Page)
{ return Page < PM_PAGES && (Map[Page >> 3] & (1 << (Page & 7))) != 0; }
static VOID PmSet(UCHAR *Map, PFN_NUMBER Page, BOOLEAN Set)
{
    if (Set) Map[Page >> 3] |= (UCHAR)(1 << (Page & 7));
    else Map[Page >> 3] &= (UCHAR)~(1 << (Page & 7));
}
static ULONG PmHash(const UCHAR *Bytes, ULONG Length)
{
    /* FNV-1a: integrity detection, not authentication or proprietary keys. */
    ULONG hash = 2166136261UL, i;
    for (i = 0; i < Length; ++i) hash = (hash ^ Bytes[i]) * 16777619UL;
    return hash;
}
static ULONG PmLaunchHash(VOID)
{
    if (*(volatile ULONG *)PM_LAUNCH_VA != PM_LAUNCH_MAGIC) return 0;
    return PmHash((const UCHAR *)PM_LAUNCH_VA, PM_LAUNCH_BYTES);
}
static ULONG PmChecksum(const PM_HANDOFF *H)
{
    ULONG h = PmHash((const UCHAR *)&H->Version,
                    FIELD_OFFSET(PM_HANDOFF, Checksum) - sizeof(ULONG));
    return h ^ PmHash(H->Pages, PM_BYTES);
}
BOOLEAN NxkMmPersistentPage(PFN_NUMBER Page)
{ return PmBit(PmRestored, Page); }

/* Called while boot descriptors are complete, before MM scans/carves them.
 * Validate every selected page against actual reservations, not just RAM size.
 * Any invalid page rejects the whole handoff. Magic is consumed even on error.
 */
VOID NxkMmReadPersistence(PLOADER_PARAMETER_BLOCK Lb)
{
    PM_HANDOFF *slot = (PM_HANDOFF *)PM_VA;
    PFN_NUMBER p;
    BOOLEAN valid;
    valid = slot->Magic == PM_MAGIC && slot->Version == PM_VERSION &&
        slot->BitmapBytes == PM_BYTES && slot->ImageBase == (ULONG)__ImageBase &&
        slot->Checksum == PmChecksum(slot) && slot->LaunchHash == PmLaunchHash();
    slot->Magic = 0; /* stale handoffs cannot be consumed twice */
    if (!valid) return;
    for (p = 0; p < PM_PAGES; ++p) {
        PLIST_ENTRY e;
        BOOLEAN allowed = FALSE;
        if (!PmBit(slot->Pages, p)) continue;
        for (e = Lb->MemoryDescriptorListHead.Flink;
             e != &Lb->MemoryDescriptorListHead; e = e->Flink) {
            PMEMORY_ALLOCATION_DESCRIPTOR d = CONTAINING_RECORD(e,
                MEMORY_ALLOCATION_DESCRIPTOR, ListEntry);
            if (p < d->BasePage || p - d->BasePage >= d->PageCount) continue;
            allowed = d->MemoryType == LoaderFree ||
                (d->MemoryType == LoaderFirmwarePermanent && p >= 0x3C00 &&
                 p < (NXK_NV2A_INSTANCE_BASE >> PAGE_SHIFT));
            break;
        }
        if (!allowed || p == 0) return;
    }
    RtlCopyMemory(PmSelected, slot->Pages, PM_BYTES);
    RtlCopyMemory(PmRestored, slot->Pages, PM_BYTES);
}

/* The HAL calls this after shutdown callbacks, immediately before reset.
 * Clear first, copy/checksum, publish last; no allocator state pointers cross.
 * Power-off/cycle invalidates the slot. Cold xemu RAM has no valid slot.
 */
VOID NTAPI NxkMmPublishPersistence(BOOLEAN WarmReset)
{
    PM_HANDOFF *slot = (PM_HANDOFF *)PM_VA;
    KIRQL irql;
    slot->Magic = 0;
    if (!WarmReset) return;
    irql = MiAcquirePfnLock();
    slot->Version = PM_VERSION; slot->BitmapBytes = PM_BYTES;
    slot->ImageBase = (ULONG)__ImageBase; slot->LaunchHash = PmLaunchHash();
    RtlCopyMemory(slot->Pages, PmSelected, PM_BYTES);
    slot->Checksum = PmChecksum(slot);
    KeMemoryBarrier(); slot->Magic = PM_MAGIC;
    MiReleasePfnLock(irql);
}
VOID NxkMmSetPersistentPages(ULONG_PTR Pa, SIZE_T Size, BOOLEAN Persist)
{
    PFN_NUMBER first = Pa >> PAGE_SHIFT, last = (Pa + Size - 1) >> PAGE_SHIFT, p;
    KIRQL irql;
    /* Reclaimed boot objects may be live title allocations, but their PAs
     * must be reused by the next loader. Reject these collisions as a whole. */
    if (first == 0 || last >= PM_PAGES ||
        (first < 0x11 && last >= 0xD) ||
        (first < 0x42 && last >= 0x30) ||
        last >= (NXK_NV2A_INSTANCE_BASE >> PAGE_SHIFT)) return;
    irql = MiAcquirePfnLock();
    for (p = first; p <= last; ++p) PmSet(PmSelected, p, Persist);
    MiReleasePfnLock(irql);
}
VOID NxkMmClearPersistence(ULONG_PTR Pa, ULONG_PTR End)
{
    PFN_NUMBER p;
    /* Caller holds PFN lock and owns the allocation. */
    for (p = Pa >> PAGE_SHIFT; p < (End >> PAGE_SHIFT); ++p) {
        PmSet(PmSelected, p, FALSE); PmSet(PmRestored, p, FALSE);
    }
}
SIZE_T NxkMmQueryRestored(PVOID Alias)
{
    ULONG_PTR va = (ULONG_PTR)Alias;
    PFN_NUMBER p, end;
    if (va < NXK_KSEG0_BASE || va >= NXK_KSEG0_BASE + NXK_KSEG0_RAM_SIZE ||
        (va & (PAGE_SIZE - 1))) return 0;
    p = (va - NXK_KSEG0_BASE) >> PAGE_SHIFT;
    if (!PmBit(PmRestored, p) || (p && PmBit(PmRestored, p - 1))) return 0;
    for (end = p + 1; PmBit(PmRestored, end); ++end) ;
    return (end - p) << PAGE_SHIFT;
}
VOID NxkMmDetachRestored(ULONG_PTR Pa, SIZE_T Size)
{
    PFN_NUMBER p;
    for (p = Pa >> PAGE_SHIFT; p < ((Pa + Size) >> PAGE_SHIFT); ++p)
        PmSet(PmRestored, p, FALSE);
}
BOOLEAN NxkMmFreeRestored(PVOID Alias)
{
    SIZE_T size;
    ULONG_PTR pa = (ULONG_PTR)Alias - NXK_KSEG0_BASE, end, check;
    KIRQL irql = MiAcquirePfnLock();
    size = NxkMmQueryRestored(Alias);
    if (!size) { MiReleasePfnLock(irql); return FALSE; }
    end = pa + size;
    for (check = pa; check < end; check += PAGE_SIZE)
        if (NxkPageSupplyIsPinned(check >> PAGE_SHIFT)) {
            MiReleasePfnLock(irql); return TRUE; /* unlock and retry */
        }
    NxkMmClearPersistence(pa, end);
    for (; pa < end; pa += PAGE_SIZE) NxkPageSupplyReturn(pa >> PAGE_SHIFT);
    MiReleasePfnLock(irql);
    return TRUE;
}
