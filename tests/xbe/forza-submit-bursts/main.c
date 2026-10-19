/* SPDX-License-Identifier: GPL-2.0-or-later
 * Owned generated-data submission-budget experiment. Budgets are synthetic,
 * not constants recovered from a title. Public kernel ABI only. */
#include <windows.h>
#include <xboxkrnl/xboxkrnl.h>
#include <stdint.h>
#include <string.h>
#include "tap.h"
#define PAGE 4096u
#define MAX_READ 65536u
#define STRIDE (MAX_READ+2*PAGE)
#define FILE_BYTES (8u*1024u*1024u)
#define DEPTH 8u
#define SECONDS 10u
#define OP_SAMPLES 64u
#define FRAME_SAMPLES 32u
#define CANARY 0xd3
#define MAGIC 0x7183ac95u
#define SENTINEL ((NTSTATUS)0x13579bdf)
static const char path[]="\\Device\\Harddisk0\\Partition1\\forza-submit-bursts-generated.tmp";
static HANDLE file;
static UCHAR *arena;
static PVOID pressure[512];
static ULONG pressure_count,failures;
static volatile ULONG phase,foreign,reentry,callback_depth,outstanding;
static ULONGLONG frequency;
static PKTHREAD issuer;
enum State { FREE, PREPARED, SUBMITTED, COMPLETE };
struct Slot {
    ULONG before;
    IO_STATUS_BLOCK io;
    ULONG after;
    UCHAR *buffer;
    volatile enum State state;
    ULONG sequence,length,offset,frame;
    volatile ULONG calls,error,bytes,identity,illegal;
    ULONG submit_status;
    ULONGLONG issue,returned,burst;
    volatile ULONGLONG callback;
};
static struct Slot slots[DEPTH];
struct Op {
    ULONG sequence,slot,length,offset,frame,status,calls;
    ULONGLONG issue,returned,callback,burst;
};
static struct Op samples[OP_SAMPLES];
struct Frame {
    ULONG index,issued,before,after,budget_hit;
    ULONGLONG begin,end,submit_ticks,poll_ticks;
};
static struct Frame frames[FRAME_SAMPLES];
struct Metrics {
    ULONG operations,verified,callbacks,pending,high_water,frames,budget_stops;
    ULONG pair_same,pair_split,first_empty_polls,bad_wait,oracle_errors;
    ULONG count[2];
    ULONGLONG bytes,submit_sum[2],submit_max[2],latency_sum[2],latency_max[2];
    ULONGLONG burst_sum,burst_max,poll_sum,pair_gap_sum,pair_gap_max;
} metrics;
static ULONGLONG now(void) {return KeQueryPerformanceCounter();}
static UCHAR pattern(ULONG n) {return (UCHAR)((n*37u)^(n>>8)^(n>>17)^0xa7u);}
static bool nonalertable_frame(void) {
    LARGE_INTEGER interval={.QuadPart=-330000};phase=3;
    NTSTATUS status=KeDelayExecutionThread(UserMode,FALSE,&interval);phase=0;
    if(status!=STATUS_SUCCESS)metrics.bad_wait++;
    return status==STATUS_SUCCESS;
}
static ULONG pages(void) {
    MM_STATISTICS stats={.Length=sizeof(stats)};
    return MmQueryStatistics(&stats)==0?stats.AvailablePages:0;
}
static void release_pressure(void) {
    while(pressure_count)MmFreeContiguousMemory(pressure[--pressure_count]);
}
static bool set_pressure(ULONG target) {
    release_pressure();
    for(ULONG attempt=0;attempt<512;attempt++) {
        ULONG available=pages();
        if(available==target)return true;
        if(available<target)return false;
        ULONG count=available-target;if(count>64)count=64;
        PVOID block=MmAllocateContiguousMemory(count*PAGE);
        if(!block)return false;
        pressure[pressure_count++]=block;
    }
    return false;
}
static bool open_data(bool write) {
    ANSI_STRING name;RtlInitAnsiString(&name,path);
    OBJECT_ATTRIBUTES attrs={NULL,&name,OBJ_CASE_INSENSITIVE};IO_STATUS_BLOCK io;
    NTSTATUS status=NtCreateFile(&file,GENERIC_READ|(write?GENERIC_WRITE:0)|SYNCHRONIZE,
        &attrs,&io,NULL,FILE_ATTRIBUTE_NORMAL,FILE_SHARE_READ,
        write?FILE_OVERWRITE_IF:FILE_OPEN,FILE_NON_DIRECTORY_FILE|
        FILE_NO_INTERMEDIATE_BUFFERING|(write?FILE_SYNCHRONOUS_IO_NONALERT:0));
    return status==0 && io.Status==0;
}
static bool seed(void) {
    UCHAR *buffer=slots[0].buffer;
    if(!open_data(true))return false;
    for(ULONG offset=0;offset<FILE_BYTES;offset+=MAX_READ) {
        for(ULONG n=0;n<MAX_READ;n++)buffer[n]=pattern(offset+n);
        IO_STATUS_BLOCK io;LARGE_INTEGER at={.QuadPart=offset};
        NTSTATUS status=NtWriteFile(file,NULL,NULL,NULL,&io,buffer,MAX_READ,&at);
        if(status || io.Status || io.Information!=MAX_READ)return false;
    }
    IO_STATUS_BLOCK io;
    if(NtFlushBuffersFile(file,&io)!=0 || io.Status!=0)return false;
    if(NtClose(file)!=0)return false;
    file=NULL;return open_data(false);
}
static void NTAPI completed(ULONG error,ULONG bytes,PVOID context) {
    ULONGLONG entered=now();struct Slot *slot=NULL;
    for(ULONG n=0;n<DEPTH;n++)if(context==&slots[n].io)slot=&slots[n];
    if(!slot){foreign++;return;}
    if(callback_depth++)reentry++;
    slot->calls++;
    if(slot->calls==1) {
        slot->callback=entered;slot->error=error;slot->bytes=bytes;
        slot->identity=KeGetCurrentThread()==issuer;
        if(slot->state!=SUBMITTED || !outstanding)slot->illegal++;
        else outstanding--;
        slot->state=COMPLETE;metrics.callbacks++;
    }
    if(phase!=2)slot->illegal++;
    callback_depth--;
}
static bool poll(void) {
    LARGE_INTEGER zero={0};ULONG before=metrics.callbacks;
    phase=2;NTSTATUS status=KeDelayExecutionThread(UserMode,TRUE,&zero);phase=0;
    if(metrics.callbacks>before && status!=STATUS_USER_APC)metrics.bad_wait++;
    if(status!=STATUS_SUCCESS && status!=STATUS_USER_APC)metrics.bad_wait++;
    return metrics.bad_wait==0;
}
static bool oracle(struct Slot *s) {
    if(s->state!=COMPLETE || s->calls!=1 || s->error || s->bytes!=s->length ||
       !s->identity || s->illegal || s->io.Status || s->io.Information!=s->length ||
       s->before!=MAGIC || s->after!=MAGIC || foreign || reentry)return false;
    for(ULONG n=0;n<s->length;n++)if(s->buffer[n]!=pattern(s->offset+n))return false;
    UCHAR *start=s->buffer-PAGE;
    for(ULONG n=0;n<PAGE;n++)if(start[n]!=CANARY)return false;
    for(ULONG n=PAGE+s->length;n<STRIDE;n++)if(start[n]!=CANARY)return false;
    return true;
}
/* Only a successful callback plus a later alertable drain allows retirement.
 * PREPARED slots have never been submitted and may be prepared again safely. */
static bool retire(void) {
    if(!poll())return false;
    ULONG completed_mask=0;
    for(ULONG n=0;n<DEPTH;n++)if(slots[n].state==COMPLETE)completed_mask|=1u<<n;
    if(!poll())return false;
    for(ULONG n=0;n<DEPTH;n++) {
        struct Slot *s=&slots[n];
        if(!(completed_mask&(1u<<n)))continue;
        if(!oracle(s)){metrics.oracle_errors++;return false;}
        ULONG size=s->length==512;
        ULONGLONG submit=s->returned-s->issue,latency=s->callback-s->issue;
        metrics.verified++;metrics.count[size]++;metrics.bytes+=s->length;
        metrics.submit_sum[size]+=submit;metrics.latency_sum[size]+=latency;
        if(submit>metrics.submit_max[size])metrics.submit_max[size]=submit;
        if(latency>metrics.latency_max[size])metrics.latency_max[size]=latency;
        if(s->sequence<OP_SAMPLES)samples[s->sequence]=(struct Op){
            s->sequence,n,s->length,s->offset,s->frame,s->submit_status,s->calls,
            s->issue,s->returned,s->callback,s->burst};
        s->state=FREE;
    }
    return true;
}
static void prepare(struct Slot *s,ULONG sequence,ULONG frame) {
    UCHAR *buffer=s->buffer;memset(s,0,sizeof(*s));s->buffer=buffer;
    s->before=s->after=MAGIC;s->sequence=sequence;s->frame=frame;
    s->length=sequence&1?512:MAX_READ;
    s->offset=(((sequence/2)*197u)%(FILE_BYTES/MAX_READ-1))*MAX_READ;
    if(sequence&1)s->offset+=MAX_READ;
    s->io.Status=SENTINEL;s->io.Information=MAGIC;
    memset(buffer-PAGE,CANARY,STRIDE);
    for(ULONG n=0;n<s->length;n++)buffer[n]=(UCHAR)~pattern(s->offset+n);
    s->state=PREPARED;
}
static bool issue(struct Slot *s,struct Frame *frame) {
    LARGE_INTEGER at={.QuadPart=s->offset};
    s->burst=frame->begin;s->state=SUBMITTED;outstanding++;
    if(outstanding>metrics.high_water)metrics.high_water=outstanding;
    phase=1;s->issue=now();
    NTSTATUS status=NtReadFile(file,NULL,(PIO_APC_ROUTINE)NtUserIoApcDispatcher,
        (PVOID)completed,&s->io,s->buffer,s->length,&at);
    s->returned=now();phase=0;s->submit_status=status;
    metrics.operations++;metrics.pending+=status==STATUS_PENDING;
    frame->issued++;frame->submit_ticks+=s->returned-s->issue;
    if(status!=STATUS_SUCCESS && status!=STATUS_PENDING)return false;
    ULONGLONG started=now();ULONG before=metrics.callbacks;
    bool good=poll();frame->poll_ticks+=now()-started;
    metrics.first_empty_polls+=metrics.callbacks==before;
    return good;
}
static bool run_case(ULONG id,ULONG target,ULONG budget_us) {
    memset(&metrics,0,sizeof(metrics));memset(samples,0,sizeof(samples));
    memset(frames,0,sizeof(frames));outstanding=foreign=reentry=0;
    for(ULONG n=0;n<DEPTH;n++)slots[n].state=FREE;
    if(!set_pressure(target)) {
        tap_comment("FORZA-BURST-ERROR id=%lu stage=pressure target=%lu actual=%lu",id,target,pages());return false;
    }
    ULONG before=pages(),next=0,last_data_frame=0;
    ULONGLONG last_data_issue=0;
    tap_comment("FORZA-BURST-BEGIN id=%lu pages=%lu budget_us=%lu seconds=%u",id,before,budget_us,SECONDS);tap_drain();
    ULONGLONG begin=now(),end=begin;
    bool good=true;
    do {
        if(!retire()){good=false;break;}
        struct Slot *available[DEPTH];ULONG count=0;
        for(ULONG n=0;n<DEPTH;n++)if(slots[n].state==FREE || slots[n].state==PREPARED) {
            prepare(&slots[n],next+count,metrics.frames);available[count++]=&slots[n];
        }
        struct Frame frame={.index=metrics.frames,.before=outstanding};
        frame.begin=now();
        for(ULONG n=0;n<count;n++) {
            struct Slot *s=available[n];
            if(!issue(s,&frame)){good=false;break;}
            next++;
            if(!(s->sequence&1)){last_data_issue=s->issue;last_data_frame=s->frame;}
            else {
                ULONGLONG gap=s->issue-last_data_issue;
                metrics.pair_gap_sum+=gap;
                if(gap>metrics.pair_gap_max)metrics.pair_gap_max=gap;
                if(s->frame==last_data_frame)metrics.pair_same++;else metrics.pair_split++;
            }
            /* First request always proceeds. An expensive call may exceed
             * the synthetic budget; no later request starts in that burst. */
            if(budget_us && (now()-frame.begin)*1000000>=frequency*budget_us) {
                frame.budget_hit=1;metrics.budget_stops++;break;
            }
        }
        frame.end=now();frame.after=outstanding;
        metrics.burst_sum+=frame.end-frame.begin;metrics.poll_sum+=frame.poll_ticks;
        if(frame.end-frame.begin>metrics.burst_max)metrics.burst_max=frame.end-frame.begin;
        if(metrics.frames<FRAME_SAMPLES)frames[metrics.frames]=frame;
        metrics.frames++;
        if(!good)break;
        if(!nonalertable_frame() || !poll()){good=false;break;}
        end=now();
        for(ULONG n=0;n<DEPTH;n++)if(slots[n].state==SUBMITTED && end-slots[n].issue>frequency*5)good=false;
    } while(good && end-begin<frequency*SECONDS);
    /* Drain any final in-flight reads without reusing storage or issuing more. */
    ULONGLONG drain_begin=now();
    while(good && outstanding) {
        if(!nonalertable_frame() || !poll())good=false;
        if(now()-drain_begin>frequency*5)good=false;
    }
    end=now();
    if(good)good=retire();
    for(ULONG n=0;n<DEPTH;n++)if(slots[n].state==SUBMITTED || slots[n].state==COMPLETE)good=false;
    good=good && metrics.operations==metrics.verified && metrics.callbacks==metrics.operations &&
        metrics.operations>1 && metrics.high_water<=DEPTH && !metrics.oracle_errors && !metrics.bad_wait &&
        !foreign && !reentry && end-begin>=frequency*SECONDS;
    tap_comment("FORZA-BURST-CASE id=%lu target=%lu before=%lu after=%lu budget_us=%lu operations=%lu verified=%lu callbacks=%lu bytes=%llu elapsed=%llu frames=%lu high_water=%lu failures=%u",id,target,before,pages(),budget_us,metrics.operations,metrics.verified,metrics.callbacks,metrics.bytes,end-begin,metrics.frames,metrics.high_water,good?0u:1u);
    tap_comment("FORZA-BURST-TIMING id=%lu pending=%lu budget_stops=%lu empty_immediate=%lu pair_same=%lu pair_split=%lu pair_gap_sum=%llu pair_gap_max=%llu burst_sum=%llu burst_max=%llu poll_sum=%llu",id,metrics.pending,metrics.budget_stops,metrics.first_empty_polls,metrics.pair_same,metrics.pair_split,metrics.pair_gap_sum,metrics.pair_gap_max,metrics.burst_sum,metrics.burst_max,metrics.poll_sum);
    for(ULONG n=0;n<2;n++)tap_comment("FORZA-BURST-SIZE id=%lu bytes=%u count=%lu submit_sum=%llu submit_max=%llu callback_sum=%llu callback_max=%llu",id,n?512:MAX_READ,metrics.count[n],metrics.submit_sum[n],metrics.submit_max[n],metrics.latency_sum[n],metrics.latency_max[n]);
    for(ULONG n=0;n<metrics.operations && n<OP_SAMPLES;n++) {
        struct Op *s=&samples[n];
        tap_comment("FORZA-BURST-OP id=%lu seq=%lu slot=%lu bytes=%lu offset=%lu frame=%lu issue=%llu returned=%llu callback=%llu burst=%llu status=%08lx calls=%lu",id,s->sequence,s->slot,s->length,s->offset,s->frame,s->issue,s->returned,s->callback,s->burst,s->status,s->calls);
    }
    for(ULONG n=0;n<metrics.frames && n<FRAME_SAMPLES;n++) {
        struct Frame *f=&frames[n];
        tap_comment("FORZA-BURST-FRAME id=%lu frame=%lu begin=%llu end=%llu issued=%lu before=%lu after=%lu budget_hit=%lu submit_ticks=%llu poll_ticks=%llu",id,f->index,f->begin,f->end,f->issued,f->before,f->after,f->budget_hit,f->submit_ticks,f->poll_ticks);
    }
    if(!good)tap_comment("FORZA-BURST-ERROR id=%lu outstanding=%lu foreign=%lu reentry=%lu bad_wait=%lu oracle_errors=%lu buffers_retained=1",id,outstanding,foreign,reentry,metrics.bad_wait,metrics.oracle_errors);
    release_pressure();return good;
}
/* Invalid Length behavior is an observation, not an assumed status contract.
 * Even unsuccessful calls may write fields; every field is reported. */
static bool statistics_probe(void) {
    static const ULONG lengths[]={0,1,35,36,37,0xc1008c48,0xffffffff};
    struct Guarded {ULONG before[4];MM_STATISTICS stats;ULONG after[4];} guarded;
    _Static_assert(sizeof(MM_STATISTICS)==36,"public statistics ABI");
    bool good=true;
    for(ULONG n=0;n<sizeof(lengths)/sizeof(lengths[0]);n++) {
        memset(&guarded,0xa5,sizeof(guarded));guarded.stats.Length=lengths[n];
        NTSTATUS status=MmQueryStatistics(&guarded.stats);
        for(ULONG j=0;j<4;j++)if(guarded.before[j]!=0xa5a5a5a5 || guarded.after[j]!=0xa5a5a5a5)good=false;
        MM_STATISTICS *s=&guarded.stats;
        tap_comment("FORZA-BURST-MM index=%lu input=%08lx status=%08lx length=%08lx total=%08lx available=%08lx committed=%08lx reserved=%08lx cache=%08lx pool=%08lx stack=%08lx image=%08lx pre0=%08lx pre1=%08lx pre2=%08lx pre3=%08lx post0=%08lx post1=%08lx post2=%08lx post3=%08lx",n,lengths[n],(ULONG)status,s->Length,s->TotalPhysicalPages,s->AvailablePages,s->VirtualMemoryBytesCommitted,s->VirtualMemoryBytesReserved,s->CachePagesCommitted,s->PoolPagesCommitted,s->StackPagesCommitted,s->ImagePagesCommitted,guarded.before[0],guarded.before[1],guarded.before[2],guarded.before[3],guarded.after[0],guarded.after[1],guarded.after[2],guarded.after[3]);
    }
    return good;
}
static __attribute__((noreturn)) void finish(void) {
    tap_comment("FORZA-BURST-END failures=%lu",failures);tap_drain();
    LARGE_INTEGER interval={.QuadPart=-5000000};KeDelayExecutionThread(UserMode,FALSE,&interval);
    HalWriteSMBusValue(0x20,0x02,FALSE,0x80);
    for(;;)__asm__ __volatile__("hlt");
}
int main(void) {
    tap_version(13);tap_plan(10);frequency=KeQueryPerformanceFrequency();issuer=KeGetCurrentThread();
    tap_comment("FORZA-BURST-META version=1 frequency=%llu seconds=%u cases=8 depth=%u frame_ms=33 route=NtUserIoApcDispatcher budgets=synthetic_hypothesis oracle=full_bytes_before_reuse",frequency,SECONDS,DEPTH);
    if(!statistics_probe()){failures++;tap_not_ok(1,"statistics queries preserve surrounding canaries");finish();}
    tap_ok(1,"statistics queries preserve surrounding canaries; statuses are observations");
    arena=MmAllocateContiguousMemory(DEPTH*STRIDE);
    if(arena)for(ULONG n=0;n<DEPTH;n++)slots[n].buffer=arena+n*STRIDE+PAGE;
    if(!frequency || !arena || !seed()){failures++;tap_not_ok(2,"private generated file setup");finish();}
    tap_ok(2,"private generated file setup");
    static const ULONG budgets[]={250,500,1000,0};
    for(ULONG p=0;p<2;p++)for(ULONG b=0;b<4;b++) {
        ULONG id=p*4+b;
        if(run_case(id,p?900:783,budgets[b]))tap_ok(id+3,"bounded submission bursts preserve callback and byte contracts");
        else {failures++;tap_not_ok(id+3,"bounded submission bursts preserve callback and byte contracts");finish();}
    }
    if(NtClose(file)!=0)failures++;
    MmFreeContiguousMemory(arena);finish();
}
