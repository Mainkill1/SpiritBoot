/* SPDX-License-Identifier: GPL-2.0-or-later
 * Independently authored public Xbox API timing recorder. Firmware unchanged. */
#include <xboxkrnl/xboxkrnl.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include "tap.h"
#include "suite-select.h"
#define OPS 1024u
#define BLOCK 4096u
#define EXTENT (OPS*BLOCK)
static UCHAR *seed, *buffer;
static ULONGLONG samples[OPS];
static ULONG statuses[OPS], io_statuses[OPS], information[OPS];
static const char path[]="\\Device\\Harddisk0\\Partition1\\pr248-owned-storage-perf.tmp";
static ULONGLONG clock_ticks(void) {
    ULONG low,high;
    __asm__ __volatile__("rdtsc" : "=a"(low),"=d"(high) : : "memory");
    return ((ULONGLONG)high<<32)|low;
}
static NTSTATUS open_file(HANDLE *handle, ULONG disposition) {
    ANSI_STRING name={(USHORT)(sizeof(path)-1),(USHORT)sizeof(path),(PCHAR)path};
    OBJECT_ATTRIBUTES oa={0};IO_STATUS_BLOCK io;memset(&io,0x5a,sizeof(io));
    oa.ObjectName=&name;oa.Attributes=OBJ_CASE_INSENSITIVE;
    return NtCreateFile(handle,GENERIC_READ|GENERIC_WRITE|SYNCHRONIZE,&oa,&io,NULL,
        FILE_ATTRIBUTE_NORMAL,FILE_SHARE_READ,disposition,
        FILE_SYNCHRONOUS_IO_NONALERT|FILE_NON_DIRECTORY_FILE|FILE_NO_INTERMEDIATE_BUFFERING);
}
static ULONG available_pages(void) {
    MM_STATISTICS stats={0};stats.Length=sizeof(stats);
    return NT_SUCCESS(MmQueryStatistics(&stats))?stats.AvailablePages:0;
}
static ULONGLONG frequency(void) {
    ULONGLONG values[5],qfreq=KeQueryPerformanceFrequency();
    LARGE_INTEGER delay={.QuadPart=-1000000};
    for(ULONG i=0;i<5;i++) {
        ULONGLONG qstart=KeQueryPerformanceCounter(),start=clock_ticks();
        KeDelayExecutionThread(KernelMode,FALSE,&delay);
        ULONGLONG end=clock_ticks(),qend=KeQueryPerformanceCounter();
        values[i]=(end-start)*qfreq/(qend-qstart);
    }
    for(ULONG i=0;i<5;i++)for(ULONG j=i+1;j<5;j++)if(values[j]<values[i]){ULONGLONG t=values[i];values[i]=values[j];values[j]=t;}
    tap_comment("STORAGE-PERF-CLOCK min=%llu median=%llu max=%llu",values[0],values[2],values[4]);
    return values[2];
}
static __attribute__((noreturn)) void finish(void) {
    tap_drain();LARGE_INTEGER delay={.QuadPart=-5000000};
    KeDelayExecutionThread(KernelMode,FALSE,&delay);
    HalWriteSMBusValue(0x20,0x02,FALSE,0x80);
    for(;;)__asm__ __volatile__("hlt");
}
static ULONG measure(HANDLE handle,const char *id,const char *cache) {
    ULONG failures=0;IO_STATUS_BLOCK io;LARGE_INTEGER offset={0};
    ULONGLONG first=0,last=0;
    for(ULONG i=0;i<OPS;i++) {
        offset.QuadPart=i*BLOCK;
        for(ULONG j=0;j<BLOCK;j++)buffer[j]=(UCHAR)~seed[i*BLOCK+j];
        memset(&io,0x5a,sizeof(io));
        ULONGLONG issued=clock_ticks();if(i==0)first=issued;
        NTSTATUS status=NtReadFile(handle,NULL,NULL,NULL,&io,buffer,BLOCK,&offset);
        ULONG bad=(status!=STATUS_SUCCESS)|((io.Status!=STATUS_SUCCESS)<<1)|((io.Information!=BLOCK)<<2)|((memcmp(buffer,seed+i*BLOCK,BLOCK)!=0)<<3);
        bool good=bad==0;
        last=clock_ticks();samples[i]=last-issued;
        statuses[i]=status;io_statuses[i]=io.Status;information[i]=io.Information;
        if(!good)++failures;
    }
    ULONGLONG elapsed=last-first;
    for(ULONG i=0;i<OPS;i++)tap_comment("STORAGE-PERF-OP id=%s index=%lu ticks=%llu status=%08lx io_status=%08lx information=%lu apcs=0",id,i,samples[i],statuses[i],io_statuses[i],information[i]);
    tap_comment("STORAGE-PERF-CASE id=%s operations=%u bytes=%u ticks=%llu assertions=%u failures=%lu flush_calls=0 persistence=0 qd_actual=1 available_pages=%lu cache=%s",id,OPS,EXTENT,elapsed,OPS*4,failures,available_pages(),cache);
    return failures;
}
#ifdef STORAGE_SUITE
int storage_pilot_main(void)
#else
int main(void)
#endif
 {
    tap_version(13);tap_plan(3);HANDLE handle=NULL;IO_STATUS_BLOCK io;ULONG failed=0;
    seed=MmAllocateContiguousMemory(EXTENT);buffer=MmAllocateContiguousMemory(BLOCK);
    bool ready=seed&&buffer&&open_file(&handle,FILE_SUPERSEDE)==STATUS_SUCCESS;
    if(!ready){tap_not_ok(1,"private disposable extent setup");tap_comment("STORAGE-PERF-ERROR stage=setup");finish();}
    for(ULONG i=0;i<EXTENT;i++)seed[i]=(UCHAR)((i*37u)^(i>>8)^(i>>17)^0xa7u);
    LARGE_INTEGER zero={0};
    memset(&io,0x5a,sizeof(io));
    NTSTATUS status=NtWriteFile(handle,NULL,NULL,NULL,&io,seed,EXTENT,&zero);
    ready=status==0&&io.Status==0&&io.Information==EXTENT;
    if(ready){memset(&io,0x5a,sizeof(io));ready=NtFlushBuffersFile(handle,&io)==0&&io.Status==0;}
    tap_ok(1,"allocate and seed owned extent outside timing");
    if(!ready){tap_comment("STORAGE-PERF-ERROR stage=seed");finish();}
    ULONGLONG overhead=~(ULONGLONG)0;
    for(ULONG i=0;i<1000;i++){ULONGLONG t=clock_ticks(),delta=clock_ticks()-t;if(delta<overhead)overhead=delta;}
    ULONGLONG freq=frequency();
    tap_comment("STORAGE-PERF-META version=1 fixture_generation=2 counter=rdtsc frequency=%llu overhead_ticks=%llu",freq,overhead);
#ifdef STORAGE_SUITE
    if(!strcmp(storage_selected_cache,"warm")) {
        for(ULONG i=0;i<OPS;i++){LARGE_INTEGER at={.QuadPart=i*BLOCK};
            for(ULONG j=0;j<BLOCK;j++)buffer[j]=(UCHAR)~seed[i*BLOCK+j];memset(&io,0x5a,sizeof(io));
            if(NtReadFile(handle,NULL,NULL,NULL,&io,buffer,BLOCK,&at)!=0||io.Status!=0||io.Information!=BLOCK||memcmp(buffer,seed+i*BLOCK,BLOCK)) {
                tap_comment("STORAGE-PERF-ERROR stage=small-warmup");finish();
            }
        }
    }
    failed+=measure(handle,storage_selected_id,storage_selected_cache);
    tap_ok(2,"selected single-case timing capture complete");
#else
    failed+=measure(handle,"small-first","cold-ish");
    tap_ok(2,"first-use timing capture complete");
    for(ULONG i=0;i<OPS;i++){LARGE_INTEGER at={.QuadPart=i*BLOCK};
        for(ULONG j=0;j<BLOCK;j++)buffer[j]=(UCHAR)~seed[i*BLOCK+j];memset(&io,0x5a,sizeof(io));
        if(NtReadFile(handle,NULL,NULL,NULL,&io,buffer,BLOCK,&at)!=0||io.Status!=0||io.Information!=BLOCK||memcmp(buffer,seed+i*BLOCK,BLOCK)) {tap_comment("STORAGE-PERF-ERROR stage=small-warmup");finish();}
    }
    failed+=measure(handle,"small-warm","warm");
#endif
    if(failed)tap_not_ok(3,"exact byte/status/IOSB verification");else tap_ok(3,"exact byte/status/IOSB verification");
    NtClose(handle);MmFreeContiguousMemory(seed);MmFreeContiguousMemory(buffer);
    #ifdef STORAGE_SUITE
    tap_comment("STORAGE-PERF-END cases=1 failures=%lu",failed);
#else
    tap_comment("STORAGE-PERF-END cases=2 failures=%lu",failed);
#endif
    finish();
}
