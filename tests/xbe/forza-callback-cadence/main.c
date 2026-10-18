/* SPDX-License-Identifier: GPL-2.0-or-later
 * Owned generated-data fixture. Public kernel ABI only; no title bytes. */
#include <windows.h>
#include <xboxkrnl/xboxkrnl.h>
#include <stdint.h>
#include <string.h>
#include "tap.h"

#define PAGE 4096u
#define MAX_READ 65536u
#define FILE_BYTES (8u*1024u*1024u)
#define SECONDS 10u
#define SAMPLE_COUNT 32u
#define CANARY 0xd3
#define SENTINEL ((NTSTATUS)0x13579bdf)
static const char path[]="\\Device\\Harddisk0\\Partition1\\forza-callback-cadence-generated.tmp";
static HANDLE file, event;
static UCHAR *arena, *buffer;
static PVOID pressure[512];
static ULONG pressure_count, failures;
static volatile ULONG phase, foreign, callback_depth, reentry;
static ULONGLONG frequency;
static PKTHREAD issuer;
/* Published callback storage survives every wait and all timeout exits. */
static struct Request {
    ULONG before;
    IO_STATUS_BLOCK io;
    ULONG after;
    ULONG length, offset;
    volatile ULONG calls, error, bytes, identity, illegal, bad_wait;
    volatile ULONGLONG callback;
} request;
struct Sample {
    ULONGLONG issue, returned, immediate, callback, poll, observed;
    ULONG status, polls, ready_misses, calls, immediate_status;
};
static struct Sample samples[SAMPLE_COUNT];
static ULONGLONG now(void) { return KeQueryPerformanceCounter(); }
static UCHAR pattern(ULONG n) { return (UCHAR)((n*37u)^(n>>8)^(n>>17)^0xa7u); }
static void delay(ULONG ms, BOOLEAN alertable) {
    LARGE_INTEGER interval={.QuadPart=-(LONGLONG)ms*10000};
    KeDelayExecutionThread(UserMode,alertable,&interval);
}
static ULONG pages(void) {
    MM_STATISTICS stats={.Length=sizeof(stats)};
    if(MmQueryStatistics(&stats)!=0)return 0;
    return stats.AvailablePages;
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
static void NTAPI completed(ULONG error, ULONG bytes, PVOID context) {
    ULONGLONG entered=now();
    if(context!=&request.io){foreign++;return;}
    if(callback_depth++)reentry++;
    request.calls++;
    if(request.calls==1) {
        request.callback=entered;request.error=error;request.bytes=bytes;
        request.identity=KeGetCurrentThread()==issuer;
    }
    if(phase!=2)request.illegal++;
    callback_depth--;
}
static void prepare(ULONG length, ULONG index) {
    memset(&request,0,sizeof(request));
    request.before=request.after=0x7183ac95;
    request.length=length;request.offset=((index*197u)%(FILE_BYTES/length))*length;
    request.io.Status=SENTINEL;request.io.Information=0x7183ac95;
    memset(arena,CANARY,MAX_READ+2*PAGE);
    for(ULONG n=0;n<length;n++)buffer[n]=(UCHAR)~pattern(request.offset+n);
    ResetEvent(event);
}
static bool oracle(void) {
    if(request.calls!=1 || request.error || request.bytes!=request.length ||
       !request.identity || request.illegal || request.bad_wait || request.io.Status ||
       request.io.Information!=request.length || request.before!=0x7183ac95 ||
       request.after!=0x7183ac95 || foreign || reentry)return false;
    for(ULONG n=0;n<request.length;n++)if(buffer[n]!=pattern(request.offset+n))return false;
    for(ULONG n=0;n<PAGE;n++)if(arena[n]!=CANARY)return false;
    for(ULONG n=PAGE+request.length;n<MAX_READ+2*PAGE;n++)if(arena[n]!=CANARY)return false;
    return true;
}
static NTSTATUS poll(struct Sample *s, bool immediate) {
    LARGE_INTEGER zero={0};ULONG before=request.calls;
    phase=2;s->poll=now();if(immediate)s->immediate=s->poll;
    NTSTATUS status=KeDelayExecutionThread(UserMode,TRUE,&zero);
    phase=0;s->polls++;
    if(immediate)s->immediate_status=status;
    if(request.calls>before && status!=STATUS_USER_APC)request.bad_wait++;
    return status;
}
static bool issue(struct Sample *s) {
    LARGE_INTEGER at={.QuadPart=request.offset};
    memset(s,0,sizeof(*s));phase=1;s->issue=now();
    NTSTATUS status=NtReadFile(file,event,(PIO_APC_ROUTINE)NtUserIoApcDispatcher,
        (PVOID)completed,&request.io,buffer,request.length,&at);
    s->returned=now();phase=0;s->status=status;
    return status==0 || status==STATUS_PENDING;
}
/* Native-completion time is deliberately not inferred from IOSB publication.
 * Event checks below record an observation upper bound only. */
static bool one_read(ULONG length,ULONG index,ULONG cadence,struct Sample *s) {
    prepare(length,index);
    if(!issue(s))return false;
    poll(s,true);
    while(!request.calls) {
        if(now()-s->issue>frequency*5)return false;
        if(cadence) {phase=3;delay(cadence,FALSE);phase=0;}
        bool ready=WaitForSingleObject(event,0)==WAIT_OBJECT_0;
        if(ready && !s->observed)s->observed=now();
        poll(s,false);
        if(ready && !request.calls)s->ready_misses++;
    }
    s->callback=request.callback;s->calls=request.calls;
    /* Explicit extra delivery opportunity before reusing caller storage. */
    struct Sample drain={0};NTSTATUS drained=poll(&drain,false);
    bool good=oracle() && drained==STATUS_SUCCESS;
    if(!good)tap_comment("FORZA-CADENCE-ORACLE calls=%lu error=%lu bytes=%lu identity=%lu illegal=%lu bad_wait=%lu io=%08lx information=%lu drain=%08lx",request.calls,request.error,request.bytes,request.identity,request.illegal,request.bad_wait,(ULONG)request.io.Status,request.io.Information,(ULONG)drained);
    return good;
}
static bool semantics(void) {
    ULONG bad=0;
    for(ULONG n=0;n<32;n++) {
        struct Sample s;prepare(n&1?MAX_READ:512,n);
        if(!issue(&s))return false;
        /* No alertable entry until completion event plus a full interval. */
        phase=3;
        if(WaitForSingleObject(event,5000)!=WAIT_OBJECT_0)return false;
        delay(20,FALSE);phase=0;
        ULONG before=request.calls;
        NTSTATUS first=poll(&s,true);
        ULONG after=request.calls;
        struct Sample drain={0};NTSTATUS drained=poll(&drain,false);
        if(before || after!=1 || first!=STATUS_USER_APC || drained!=STATUS_SUCCESS || !oracle())bad++;
        tap_comment("FORZA-CADENCE-SEM index=%lu before=%lu after=%lu return=%08lx drain=%08lx errors=%lu",n,before,after,(ULONG)first,(ULONG)drained,bad);
    }
    tap_comment("FORZA-CADENCE-SEM-END cases=32 failures=%lu",bad);
    return bad==0;
}
static bool run_case(ULONG id,ULONG target,ULONG length,ULONG cadence) {
    if(!set_pressure(target))return false;
    ULONG before=pages(), operations=0, pending=0, immediate=0, misses=0, errors=0;
    ULONG histogram[128]={0};
    ULONGLONG submit_sum=0,callback_sum=0,poll_sum=0,max_callback=0,total_bytes=0;
    tap_comment("FORZA-CADENCE-BEGIN id=%lu pages=%lu bytes=%lu frame_ms=%lu seconds=%u",id,before,length,cadence,SECONDS);tap_drain();
    ULONGLONG begin=now(),end=begin;
    do {
        struct Sample sample;
        if(!one_read(length,operations,cadence,&sample)){errors++;break;}
        ULONGLONG latency=sample.callback-sample.issue;
        submit_sum+=sample.returned-sample.issue;callback_sum+=latency;
        if(sample.callback>=sample.poll)poll_sum+=sample.callback-sample.poll;
        if(latency>max_callback)max_callback=latency;
        ULONG bucket=(ULONG)(latency*1000/frequency);if(bucket>127)bucket=127;
        histogram[bucket]++;
        if(operations<SAMPLE_COUNT)samples[operations]=sample;
        pending+=sample.status==STATUS_PENDING;
        immediate+=sample.polls==1;misses+=sample.ready_misses;
        total_bytes+=length;operations++;end=now();
    } while(end-begin<frequency*SECONDS);
    ULONG after=pages();
    tap_comment("FORZA-CADENCE-CASE id=%lu target=%lu before=%lu after=%lu bytes=%lu frame_ms=%lu operations=%lu total_bytes=%llu elapsed=%llu failures=%lu",id,target,before,after,length,cadence,operations,total_bytes,end-begin,errors);
    tap_comment("FORZA-CADENCE-TIMING id=%lu pending=%lu immediate=%lu ready_misses=%lu submit_sum=%llu callback_sum=%llu poll_sum=%llu callback_max=%llu",id,pending,immediate,misses,submit_sum,callback_sum,poll_sum,max_callback);
    for(ULONG n=0;n<operations && n<SAMPLE_COUNT;n++) {
        struct Sample *s=&samples[n];
        tap_comment("FORZA-CADENCE-OP id=%lu index=%lu issue=%llu returned=%llu immediate=%llu callback=%llu last_poll=%llu observed=%llu status=%08lx polls=%lu calls=%lu immediate_status=%08lx",id,n,s->issue,s->returned,s->immediate,s->callback,s->poll,s->observed,s->status,s->polls,s->calls,s->immediate_status);
    }
    for(ULONG n=0;n<128;n++)if(histogram[n])tap_comment("FORZA-CADENCE-HIST id=%lu low_ms=%lu count=%lu",id,n,histogram[n]);
    release_pressure();
    return errors==0 && operations>1 && end-begin>=frequency*SECONDS;
}

/* Controlled public APC enqueue during an immediate-delay scheduler handoff.
 * This is a comparison observation; differing first-return behavior is not
 * classified as fixture failure until the target contract is established. */
static KEVENT producer_gate, producer_ready;
static HANDLE issuer_gate, issuer_handle;
static volatile ULONG handoff_calls, handoff_first_calls, handoff_phase, handoff_errors;
static PKTHREAD handoff_issuer;
static volatile NTSTATUS enqueue_status, handoff_status;
static volatile ULONGLONG handoff_enter,handoff_return,producer_enter,enqueued,apc_enter;
static ULONG handoff_kind;
static void NTAPI owned_apc(PVOID a,PVOID b,PVOID c) {
    (void)a;(void)b;(void)c;apc_enter=now();handoff_calls++;
    if(KeGetCurrentThread()!=handoff_issuer || (handoff_phase!=1 && handoff_phase!=2))handoff_errors++;
}
static DWORD WINAPI producer_thread(PVOID arg) {
    (void)arg;
    if(!SetThreadPriority(GetCurrentThread(),handoff_kind==4?THREAD_PRIORITY_BELOW_NORMAL:THREAD_PRIORITY_NORMAL))return 1;
    KeSetEvent(&producer_ready,0,FALSE);
    LARGE_INTEGER timeout={.QuadPart=-50000000};
    if(KeWaitForSingleObject(&producer_gate,Executive,KernelMode,FALSE,&timeout)!=0)return 1;
    producer_enter=now();
    if(handoff_kind!=3) {
        enqueue_status=NtQueueApcThread(issuer_handle,owned_apc,NULL,NULL,NULL);
        enqueued=now();
    }
    return 0;
}
static DWORD WINAPI issuer_thread(PVOID arg) {
    (void)arg;
    if(WaitForSingleObject(issuer_gate,5000)!=WAIT_OBJECT_0)return 1;
    if(!SetThreadPriority(GetCurrentThread(),THREAD_PRIORITY_NORMAL))return 1;
    handoff_issuer=KeGetCurrentThread();
    KeSetPriorityThread(KeGetCurrentThread(),10);
    if(handoff_kind==3) {
        enqueue_status=NtQueueApcThread(GetCurrentThread(),owned_apc,NULL,NULL,NULL);
        enqueued=now();
    }
    KeSetEvent(&producer_gate,0,FALSE);
    LARGE_INTEGER interval={.QuadPart=handoff_kind==2?1:0};
    handoff_phase=handoff_kind==1?3:1;handoff_enter=now();
    handoff_status=KeDelayExecutionThread(UserMode,handoff_kind!=1,&interval);
    handoff_return=now();handoff_phase=0;handoff_first_calls=handoff_calls;
    /* A blocking non-alertable delay guarantees the producer can run even if
     * this kernel elects not to hand off on a zero/expired delay. */
    handoff_phase=3;delay(20,FALSE);handoff_phase=0;
    for(ULONG n=0;n<100 && !handoff_calls;n++) {handoff_phase=2;delay(1,TRUE);handoff_phase=0;}
    handoff_phase=2;delay(0,TRUE);handoff_phase=0;return 0;
}
static bool handoff(void) {
    ULONG bad=0;
    KeInitializeEvent(&producer_gate,SynchronizationEvent,FALSE);
    KeInitializeEvent(&producer_ready,SynchronizationEvent,FALSE);
    issuer_gate=CreateEvent(NULL,FALSE,FALSE,NULL);
    if(!issuer_gate)return false;
    for(ULONG kind=0;kind<5;kind++)for(ULONG n=0;n<8;n++) {
        handoff_kind=kind;handoff_calls=handoff_first_calls=handoff_phase=handoff_errors=0;
        handoff_enter=handoff_return=producer_enter=enqueued=apc_enter=0;
        enqueue_status=handoff_status=SENTINEL;
        HANDLE producer=CreateThread(NULL,16384,producer_thread,NULL,0,NULL);
        LARGE_INTEGER timeout={.QuadPart=-50000000};
        if(!producer || KeWaitForSingleObject(&producer_ready,Executive,KernelMode,FALSE,&timeout)!=0)return false;
        issuer_handle=CreateThread(NULL,16384,issuer_thread,NULL,0,NULL);
        if(!producer || !issuer_handle)return false;
        if(!SetEvent(issuer_gate))return false;
        if(WaitForSingleObject(issuer_handle,5000)!=WAIT_OBJECT_0 ||
           WaitForSingleObject(producer,5000)!=WAIT_OBJECT_0)return false;
        DWORD issuer_exit=1,producer_exit=1;
        if(!GetExitCodeThread(issuer_handle,&issuer_exit) || !GetExitCodeThread(producer,&producer_exit))return false;
        if(issuer_exit || producer_exit || handoff_errors || enqueue_status || handoff_calls!=1 || (kind==1 && handoff_first_calls) ||
           (kind==3 && (handoff_first_calls!=1 || handoff_status!=STATUS_USER_APC)))bad++;
        tap_comment("FORZA-CADENCE-HANDOFF kind=%lu index=%lu enter=%llu producer=%llu enqueued=%llu returned=%llu callback=%llu status=%08lx enqueue_status=%08lx first_calls=%lu calls=%lu errors=%lu",kind,n,handoff_enter,producer_enter,enqueued,handoff_return,apc_enter,(ULONG)handoff_status,(ULONG)enqueue_status,handoff_first_calls,handoff_calls,handoff_errors);
        CloseHandle(issuer_handle);CloseHandle(producer);
    }
    CloseHandle(issuer_gate);
    tap_comment("FORZA-CADENCE-HANDOFF-END cases=40 failures=%lu",bad);return !bad;
}
static __attribute__((noreturn)) void finish(void) {
    tap_comment("FORZA-CADENCE-END failures=%lu",failures);tap_drain();delay(500,FALSE);
    HalWriteSMBusValue(0x20,0x02,FALSE,0x80);
    for(;;)__asm__ __volatile__("hlt");
}
int main(void) {
    tap_version(13);tap_plan(11);frequency=KeQueryPerformanceFrequency();
    tap_comment("FORZA-CADENCE-META version=1 counter=KeQueryPerformanceCounter frequency=%llu seconds=%u cases=8 route=NtUserIoApcDispatcher oracle=full_bytes_each_request",frequency,SECONDS);
    if(!frequency || !handoff()){failures++;tap_not_ok(1,"controlled immediate-delay handoff");finish();}
    tap_ok(1,"controlled immediate-delay handoff");
    arena=MmAllocateContiguousMemory(MAX_READ+2*PAGE);buffer=arena?arena+PAGE:NULL;
    event=CreateEvent(NULL,TRUE,FALSE,NULL);issuer=KeGetCurrentThread();
    if(!arena || !event || !seed()){failures++;tap_not_ok(2,"seed private generated FATX file");finish();}
    tap_ok(2,"seed private generated FATX file");
    if(!semantics()){failures++;tap_not_ok(3,"nonalertable exclusion and first eligible poll");finish();}
    tap_ok(3,"nonalertable exclusion and first eligible poll");
    ULONG id=0;
    for(ULONG p=0;p<2;p++)for(ULONG size=0;size<2;size++)for(ULONG frame=0;frame<2;frame++) {
        bool ok=run_case(id,p?783:900,size?MAX_READ:512,frame?33:0);
        if(ok)tap_ok(id+4,"sustained title-route callback cadence");
        else {failures++;tap_not_ok(id+4,"sustained title-route callback cadence");finish();}
        id++;
    }
    /* All issued reads have one callback and a subsequent alertable drain.
     * Timeout paths power off while retaining handles and caller buffers. */
    if(NtClose(file)!=0)failures++;
    CloseHandle(event);MmFreeContiguousMemory(arena);
    /* Leave this explicitly named generated file for reproducible reruns. */
    finish();
}
