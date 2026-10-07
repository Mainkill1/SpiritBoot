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
static unsigned translations, cleared, clears, valid_pages, invalid_at, aliases;
static unsigned checks, optimized;
static BOOLEAN NxkMmRetailShapedMap(void) { return FALSE; }
static VOID MiZeroPhysicalPage(PFN_NUMBER p) { (void)p; }
static BOOLEAN NxkMmPersistentPage(PFN_NUMBER p) { (void)p;return FALSE; }
static BOOLEAN NxMmIsAddressValid(PVOID p) {
    ULONG_PTR i=((ULONG_PTR)p-0x1000)/PAGE_SIZE;
    return i<valid_pages && i!=invalid_at;
}
static ULONG_PTR NxMmGetPhysicalAddress(PVOID p) {
    ULONG_PTR i=((ULONG_PTR)p-0x1000)/PAGE_SIZE;
    ++translations;
    return (aliases?16:16+i)*PAGE_SIZE;
}
static void counted_zero(void *p,size_t n) { cleared+=(unsigned)n;++clears;memset(p,0,n); }
#undef RtlZeroMemory
#define RtlZeroMemory counted_zero
#include "pins-actual.inc"
#define CHECK(c) do{++checks;if(!(c)){fprintf(stderr,"FAIL %u: %s\n",checks,#c);exit(1);}}while(0)
static UCHAR metadata[32768*(sizeof(ULONG)+2*sizeof(USHORT))];
static void init(unsigned n,unsigned alias) {
    NxkPageSupplyInitialize(32767,metadata);
    valid_pages=n;invalid_at=~0U;aliases=alias;
    translations=cleared=clears=0;
}
static void clean(void) {
    if(optimized) for(unsigned i=0;i<=NxpHighestPfn;++i) CHECK(NxpPinBatch[i]==0);
}
int main(int argc,char **argv) {
    optimized=argc>1 && atoi(argv[1]);
    unsigned sizes[]={0,1,2,16,32,64,65,128,256,4096};
    for(unsigned s=0;s<sizeof(sizes)/sizeof(*sizes);++s) {
        unsigned n=sizes[s];
        for(unsigned alias=0;alias<2;++alias) {
            init(n,alias);
            MmLockUnlockBufferPages((PVOID)0x1000,n*PAGE_SIZE,FALSE);
            CHECK(NxpPins[16]==(alias?n:!!n));clean();
            printf("pin-work success n=%u alias=%u translations=%u cleared=%u bulk=%u\n",n,alias,translations,cleared,clears);
            if(optimized) CHECK(cleared==(n>64?65536:2*n));
            MmLockUnlockBufferPages((PVOID)0x1000,n*PAGE_SIZE,FALSE);clean();
            CHECK(NxpPins[16]==2*(alias?n:!!n));
            MmLockUnlockBufferPages((PVOID)0x1000,n*PAGE_SIZE,TRUE);clean();
            MmLockUnlockBufferPages((PVOID)0x1000,n*PAGE_SIZE,TRUE);clean();
            CHECK(NxpPins[16]==0);
            /* Underflow after RecordPin increments then rejects is inert. */
            MmLockUnlockBufferPages((PVOID)0x1000,n*PAGE_SIZE,TRUE);clean();
            CHECK(NxpPins[16]==0);
            if(!n) continue;
            unsigned positions[]={0,n/2,n-1};
            for(unsigned p=0;p<3;++p) {
                init(n,alias);invalid_at=positions[p];
                MmLockUnlockBufferPages((PVOID)0x1000,n*PAGE_SIZE,FALSE);clean();
                CHECK(NxpPins[16]==0);
                unsigned prefix=positions[p];
                printf("pin-work rejected n=%u prefix=%u alias=%u translations=%u cleared=%u bulk=%u\n",n,prefix,alias,translations,cleared,clears);
                if(optimized) {
                    CHECK(cleared==(prefix>64?65536:2*prefix));
                    CHECK(translations==prefix*(prefix<=64?2:1));
                }
                invalid_at=~0U;
                MmLockUnlockBufferPages((PVOID)0x1000,n*PAGE_SIZE,FALSE);clean();
                CHECK(NxpPins[16]==(alias?n:1));
            }
        }
    }
    init(2,1);MmLockUnlockPhysicalPage(16*PAGE_SIZE,FALSE);
    MmLockUnlockBufferPages((PVOID)0x1000,2*PAGE_SIZE,TRUE);
    CHECK(NxpPins[16]==1);clean();
    MmLockUnlockBufferPages((PVOID)(UINTPTR_MAX-1),PAGE_SIZE,FALSE);clean();
    CHECK(NxpPins[16]==1);
    /* A translated invalid PFN must never index scratch. */
    init(4096,0);NxpHighestPfn=16;
    MmLockUnlockBufferPages((PVOID)0x1000,2*PAGE_SIZE,FALSE);clean();
    CHECK(NxpPins[16]==0);NxpHighestPfn=32767;
    init(2,1);NxpPins[16]=NXP_PIN_LIMIT-1;
    MmLockUnlockBufferPages((PVOID)0x1000,2*PAGE_SIZE,FALSE);clean();
    CHECK((NxpPins[16]&NXP_PIN_OVERFLOW)!=0);
    NxkPageSupplyReturn(16);
    MmLockUnlockBufferPages((PVOID)0x1000,2*PAGE_SIZE,TRUE);clean();
    CHECK(NxkPageSupplyIsPinned(16)&&!NxkPageSupplyIsFree(16));
    init(2,1);MmLockUnlockBufferPages((PVOID)0x1000,2*PAGE_SIZE,FALSE);
    NxkPageSupplyReturn(16);
    MmLockUnlockBufferPages((PVOID)0x1000,2*PAGE_SIZE,TRUE);clean();
    CHECK(NxkPageSupplyIsFree(16));
    printf("pin optimization checks: %u/%u passed\n",checks,checks);
}
