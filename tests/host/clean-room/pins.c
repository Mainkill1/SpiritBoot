/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <ntoskrnl.h>
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
typedef USHORT *PUSHORT;
#define ASSERT assert
#define UNREFERENCED_PARAMETER(x) (void)(x)
#define MI_ASSERT_PFN_LOCK_HELD() ((void)0)
#define MAXUSHORT 0xffff
#define MAXULONG_PTR UINTPTR_MAX
#define NXK_MM_PHYS
static ULONG MmAvailablePages;
static BOOLEAN NxkMmRetailShapedMap(void) { return FALSE; }
static VOID MiZeroPhysicalPage(PFN_NUMBER p) { (void)p; }
static BOOLEAN NxkMmPersistentPage(PFN_NUMBER p) { (void)p;return FALSE; }
static BOOLEAN NxMmIsAddressValid(PVOID p) { return (ULONG_PTR)p>=0x1000&&(ULONG_PTR)p<0x5000; }
/* VAs 0x1000 and 0x2000 alias the same PFN; 0x3000 and 0x4000 another. */
static ULONG_PTR NxMmGetPhysicalAddress(PVOID p) { return (ULONG_PTR)p<0x3000?0x10000:0x11000; }
#include "pins-actual.inc"
static unsigned checks;
#define CHECK(c) do{++checks;if(!(c)){fprintf(stderr,"FAIL %u: %s\n",checks,#c);return 1;}}while(0)
int main(void)
{
    UCHAR metadata[32*(sizeof(ULONG)+2*sizeof(USHORT))];
    NxkPageSupplyInitialize(31,metadata);
    MmLockUnlockPhysicalPage(0x10025,FALSE);
    CHECK(NxpPins[16]==1&&NxpPins[1]==0);
    MmLockUnlockPhysicalPage(0xFD000000,FALSE);CHECK(NxpPins[16]==1);
    /* Two aliases but only one pin: unlock preflight must change nothing. */
    MmLockUnlockBufferPages((PVOID)0x1000,2*PAGE_SIZE,TRUE);
    CHECK(NxpPins[16]==1);
    MmLockUnlockBufferPages((PVOID)0x1000,2*PAGE_SIZE,FALSE);
    CHECK(NxpPins[16]==3);
    MmLockUnlockBufferPages((PVOID)0x1000,2*PAGE_SIZE,TRUE);
    CHECK(NxpPins[16]==1);
    MmLockUnlockPhysicalPage(0x10000,TRUE);MmLockUnlockPhysicalPage(0x10000,TRUE);
    CHECK(NxpPins[16]==0);
    /* All mappings must validate before any count changes. */
    MmLockUnlockBufferPages((PVOID)0x3000,3*PAGE_SIZE,FALSE);
    CHECK(NxpPins[17]==0);
    MmLockUnlockBufferPages((PVOID)(UINTPTR_MAX-1),PAGE_SIZE,FALSE);
    CHECK(NxpPins[17]==0);
    /* The exact count limit still balances. Crossing it via repeated aliases
     * latches retention for the whole buffer instead of partial acquisition. */
    for(unsigned i=0;i<NXP_PIN_LIMIT-1;++i) MmLockUnlockPhysicalPage(0x10000,FALSE);
    MmLockUnlockBufferPages((PVOID)0x1000,4*PAGE_SIZE,FALSE);
    CHECK((NxpPins[16]&NXP_PIN_OVERFLOW)!=0&&NxpPins[17]==2);
    for(unsigned i=0;i<0x8000;++i) MmLockUnlockPhysicalPage(0x10000,TRUE);
    CHECK(NxkPageSupplyIsPinned(16));
    NxkPageSupplyReturn(16);
    CHECK(!NxkPageSupplyIsFree(16)&&NxkPageSupplyIsPinned(16));
    MmLockUnlockBufferPages((PVOID)0x3000,2*PAGE_SIZE,TRUE);
    CHECK(!NxkPageSupplyIsPinned(17));
    NxkPageSupplyReturn(17);CHECK(NxkPageSupplyIsFree(17));
    printf("physical pin host checks: %u/%u passed\n",checks,checks);
    return 0;
}
