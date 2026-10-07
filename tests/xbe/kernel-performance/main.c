/* SPDX-License-Identifier: GPL-2.0-or-later
 * One immutable public-ABI guest for paired baseline/candidate measurements.
 */
#include <xboxkrnl/xboxkrnl.h>
#include "../api-regression/tap.h"
#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#define SAMPLES 3
#define PIN_BYTES (4096 * PAGE_SIZE)
static PUCHAR pin_buffer;
static SIZE_T pin_size;
static PUCHAR reject_buffer;
static SIZE_T reject_size;
static UCHAR data[1048576], table[384], out[4096];
static OBJECT_TYPE types[128];
static ULONG allocations, frees, deletes;
static volatile ULONG empty_sink;
static ULONG checksum;
static bool correct;
static PVOID fragments[4096];

static void mix(ULONG value) { checksum=(checksum^value)*16777619U; }
static void require(bool value) { if(!value) correct=false; }
static PVOID NTAPI object_allocate(SIZE_T size,ULONG tag) {
    ++allocations;return ExAllocatePoolWithTag(size,tag);
}
static VOID NTAPI object_free(PVOID value) { ++frees;ExFreePool(value); }
static VOID NTAPI object_delete(PVOID value) { (void)value;++deletes; }
static bool create(ULONG type) {
    PVOID obj=NULL;
    NTSTATUS status=ObCreateObject(&types[type],NULL,4,&obj);
    if(status!=STATUS_SUCCESS || !obj) return false;
    *(PULONG)obj=0x12345678;
    mix(*(PULONG)obj);
    ObfDereferenceObject(obj);
    return true;
}

typedef enum { EMPTY,PIN,PIN_REJECT,POOL,SYSVA,OBJECT,MODEXP,SHA,DES } KIND;
typedef struct { const char *name;KIND kind;ULONG size,arg,iterations; } WORK;
static const WORK workloads[]={
    {"empty",EMPTY,0,0,1000},
    {"pin-1",PIN,1,0,1000}, {"pin-16",PIN,16,0,500},
    {"pin-64",PIN,64,0,100}, {"pin-65",PIN,65,0,100},
    {"pin-256",PIN,256,0,32}, {"pin-4096",PIN,4096,0,4},
    {"pin-reject-0",PIN_REJECT,0,0,500},
    {"pin-reject-32",PIN_REJECT,32,0,100},
    {"pin-reject-64",PIN_REJECT,64,0,100},
    {"pin-reject-65",PIN_REJECT,65,0,100},
    {"pool-1",POOL,1,0,64}, {"pool-16",POOL,16,0,16},
    {"pool-256",POOL,256,0,4}, {"pool-1024",POOL,1024,0,1},
    {"pool-fragmented-fail-4",POOL,4,1,16},
    {"sysva-1",SYSVA,1,0,32}, {"sysva-16",SYSVA,16,0,8},
    {"sysva-1024",SYSVA,1024,0,1}, {"sysva-1025",SYSVA,1025,0,1},
    {"sysva-4096",SYSVA,4096,0,1},
    {"object-cold-64",OBJECT,64,64,1},
    {"object-warm-1",OBJECT,1,0,1000},
    {"object-warm-8",OBJECT,8,0,128},
    {"object-warm-64",OBJECT,64,0,16},
    {"modexp-1-e1-odd",MODEXP,1,1,64},
    {"modexp-1-e65537-odd",MODEXP,1,65537,32},
    {"modexp-2-e3-even",MODEXP,2,3,8},
    {"modexp-32-e3-odd",MODEXP,32,3,2},
    {"modexp-64-e65537-odd",MODEXP,64,65537,1},
    {"modexp-512-e1-odd",MODEXP,512,1,1},
    {"sha-0",SHA,0,0,512}, {"sha-1",SHA,1,0,512},
    {"sha-63",SHA,63,0,256}, {"sha-65",SHA,65,0,256},
    {"sha-4096",SHA,4096,0,8}, {"sha-1MiB",SHA,1048576,0,1},
    {"des-block",DES,8,0,128}, {"des3-block",DES,8,1,64},
    {"des-cbc-4096",DES,4096,0,2}, {"des3-cbc-4096",DES,4096,1,1}
};

static void one(const WORK *w) {
    ULONG bytes=w->size*PAGE_SIZE;
    switch(w->kind) {
    case EMPTY: ++empty_sink;break;
    case PIN:
        MmLockUnlockBufferPages(pin_buffer,bytes,FALSE);
        MmLockUnlockBufferPages(pin_buffer,bytes,TRUE);
        require(pin_buffer[0]==0x61 && pin_buffer[bytes-1]==0x61);
        mix(bytes);break;
    case PIN_REJECT: {
        PUCHAR first=reject_buffer+(65-w->size)*PAGE_SIZE;
        MmLockUnlockBufferPages(first,(w->size+1)*PAGE_SIZE,FALSE);
        require(reject_buffer[0]==0x53 && reject_buffer[65*PAGE_SIZE-1]==0x53);
        mix(w->size);break;
    }
    case POOL: {
        PUCHAR p=ExAllocatePool(bytes);
        if(w->arg) {
            require(p==NULL);mix(p==NULL);
            if(p) ExFreePool(p);
            break;
        }
        require(p!=NULL);
        if(p) {
            require(ExQueryPoolBlockSize(p)==bytes);
            p[0]=0x37;p[bytes-1]=0x62;
            mix(p[0]+p[bytes-1]);ExFreePool(p);
        }
        break;
    }
    case SYSVA: {
        PUCHAR p=MmAllocateSystemMemory(bytes,PAGE_READWRITE);
        require(p!=NULL);
        if(p) {
            /* Inspect each freshly zeroed page before writing. */
            for(ULONG i=0;i<bytes;i+=PAGE_SIZE) require(p[i]==0);
            require(p[bytes-1]==0);p[0]=0x39;p[bytes-1]=0x6B;
            mix(p[0]+p[bytes-1]);
            require(MmFreeSystemMemory(p,bytes)==w->size);
        }
        break;
    }
    case OBJECT: {
        ULONG before_alloc=allocations,before_free=frees,before_delete=deletes;
        for(ULONG i=0;i<w->size;++i) require(create(w->arg+i));
        require(allocations-before_alloc==w->size);
        require(frees-before_free==w->size && deletes-before_delete==w->size);
        break;
    }
    case MODEXP: {
        ULONG base[512]={0},exp[512]={0},mod[512]={0},result[512];
        base[0]=5;exp[0]=w->arg;
        mod[0]=(w->size==2)?18:17;
        memset(result,0xCC,w->size*sizeof(ULONG));
        require(XcModExp(result,base,exp,mod,w->size)==1);
        ULONG expected=(w->arg==1 || w->arg==65537)?5:6;
        if(w->size==2) expected=17; /* 5^3 mod18 */
        require(result[0]==expected);
        for(ULONG i=1;i<w->size;++i) require(result[i]==0);
        mix(result[0]);break;
    }
    case SHA: {
        UCHAR context[116],digest[20],again[20];
        memset(context,0xCC,sizeof(context));
        XcSHAInit(context);XcSHAUpdate(context,data,w->size);XcSHAFinal(context,digest);
        /* Reset semantics and fixed-data second computation are checked;
         * public independent known answers are checked once before timing. */
        XcSHAUpdate(context,data,w->size);XcSHAFinal(context,again);
        require(memcmp(digest,again,20)==0);
        for(ULONG i=0;i<24;++i) require(context[i]==0xCC);
        for(ULONG i=52;i<116;++i) require(context[i]==0);
        for(ULONG i=0;i<20;++i) mix(digest[i]);
        break;
    }
    case DES: {
        UCHAR feedback[8]={0},plain[4096];
        if(w->size==8) {
            XcBlockCrypt(w->arg,out,data,table,1);
            XcBlockCrypt(w->arg,plain,out,table,0);
        } else {
            XcBlockCryptCBC(w->arg,w->size,out,data,table,1,feedback);
            memset(feedback,0,8);
            XcBlockCryptCBC(w->arg,w->size,plain,out,table,0,feedback);
        }
        require(memcmp(plain,data,w->size)==0);
        for(ULONG i=0;i<8;++i) mix(out[i]);
        break;
    }
    }
}

static bool known_answers(void) {
    static const UCHAR sha[20]={0xa9,0x99,0x3e,0x36,0x47,0x06,0x81,0x6a,0xba,0x3e,
        0x25,0x71,0x78,0x50,0xc2,0x6c,0x9c,0xd0,0xd8,0x9d};
    static const UCHAR key[8]={0x13,0x34,0x57,0x79,0x9b,0xbc,0xdf,0xf1};
    static const UCHAR input[8]={0x01,0x23,0x45,0x67,0x89,0xab,0xcd,0xef};
    static const UCHAR des[8]={0x85,0xe8,0x13,0x54,0x0f,0x0a,0xb4,0x05};
    UCHAR ctx[116],digest[20],schedule[128],cipher[8];
    XcSHAInit(ctx);XcSHAUpdate(ctx,(PUCHAR)"abc",3);XcSHAFinal(ctx,digest);
    XcKeyTable(0,schedule,(PUCHAR)key);
    XcBlockCrypt(0,cipher,(PUCHAR)input,schedule,1);
    return memcmp(digest,sha,20)==0 && memcmp(cipher,des,8)==0;
}

int main(void) {
    const ULONG count=sizeof(workloads)/sizeof(workloads[0]);
    ULONG failures=0;
    tap_puts("== kernel-performance begin ==\n");tap_version(14);tap_plan(count+1);
    ULONGLONG frequency=KeQueryPerformanceFrequency();
    tap_comment("PERF-META version=1 clock=KeQueryPerformanceCounter frequency=%llu samples=%u",frequency,SAMPLES);
    bool kats=known_answers();
    if(kats) tap_ok(1,"public-known-answers"); else {tap_not_ok(1,"public-known-answers");++failures;}
    for(ULONG i=0;i<sizeof(data);++i) data[i]=(UCHAR)((i*29+7)&255);
    for(ULONG i=0;i<128;++i) {
        types[i].AllocateProcedure=object_allocate;types[i].FreeProcedure=object_free;
        types[i].DeleteProcedure=object_delete;types[i].PoolTag='fPeK';
    }
    pin_size=PIN_BYTES;
    NTSTATUS status=NtAllocateVirtualMemory((PVOID *)&pin_buffer,0,&pin_size,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
    bool ready=status==STATUS_SUCCESS && pin_buffer;
    if(ready) memset(pin_buffer,0x61,pin_size);
    reject_size=66*PAGE_SIZE;
    status=NtAllocateVirtualMemory((PVOID *)&reject_buffer,0,&reject_size,MEM_RESERVE,PAGE_READWRITE);
    if(status==STATUS_SUCCESS && reject_buffer) {
        SIZE_T commit_size=65*PAGE_SIZE;
        PVOID commit_base=reject_buffer;
        status=NtAllocateVirtualMemory(&commit_base,0,&commit_size,MEM_COMMIT,PAGE_READWRITE);
        if(status==STATUS_SUCCESS) memset(reject_buffer,0x53,commit_size);
        else ready=false;
        if(MmIsAddressValid(reject_buffer+65*PAGE_SIZE)) ready=false;
    } else ready=false;
    /* Establish the warm registry before any measured warm workload. */
    checksum=2166136261U;
    for(ULONG i=0;i<64;++i) if(!create(i)) ready=false;
    for(ULONG j=0;j<count;++j) {
        const WORK *w=&workloads[j];bool all=ready;
        ULONG fragment_count=0;
        if(w->kind==POOL && w->arg) {
            /* Fill the bounded 16-MiB window before releasing groups of two.
             * Classification uses public VA alignment only; no window base,
             * PFN or returned address contributes to the semantic checksum. */
            for(;fragment_count<4096;++fragment_count) {
                fragments[fragment_count]=ExAllocatePool(PAGE_SIZE);
                if(!fragments[fragment_count]) break;
            }
            for(ULONG i=0;i<fragment_count;++i) {
                if((((ULONG_PTR)fragments[i]/PAGE_SIZE)&3)<2) {
                    ExFreePool(fragments[i]);fragments[i]=NULL;
                }
            }
            PVOID probe=ExAllocatePool(4*PAGE_SIZE);
            if(probe) {ExFreePool(probe);all=false;}
        }
        if(w->kind==DES) XcKeyTable(w->arg,table,data);
        ULONG samples=(w->kind==OBJECT && w->arg==64)?1:SAMPLES;
        for(ULONG sample=0;sample<samples;++sample) {
            correct=all;checksum=2166136261U;
            ULONGLONG start=KeQueryPerformanceCounter();
            if(all) for(ULONG i=0;i<w->iterations;++i) one(w);
            ULONGLONG end=KeQueryPerformanceCounter();
            require(end>=start);all=all && correct;
            tap_comment("PERF workload=%s sample=%lu iterations=%lu ticks=%llu correct=%u checksum=%08lx",
                w->name,sample,w->iterations,end-start,correct?1:0,checksum);
        }
        for(ULONG i=0;i<fragment_count;++i) if(fragments[i]) {ExFreePool(fragments[i]);fragments[i]=NULL;}
        if(all) tap_ok(j+2,w->name);else {tap_not_ok(j+2,w->name);++failures;}
    }
    if(pin_buffer) {SIZE_T bytes=0;NtFreeVirtualMemory((PVOID *)&pin_buffer,&bytes,MEM_RELEASE);}
    if(reject_buffer) {SIZE_T bytes=0;NtFreeVirtualMemory((PVOID *)&reject_buffer,&bytes,MEM_RELEASE);}
    tap_comment("PERF-SUMMARY workloads=%lu failures=%lu",count,failures);
    tap_puts(failures?"== kernel-performance end FAIL ==\n":"== kernel-performance end PASS ==\n");
    tap_drain();HalWriteSMBusValue(0x20,0x02,FALSE,0x80);
    for(;;) __asm__ __volatile__("hlt");
}
