/* SPDX-License-Identifier: GPL-2.0-or-later
 * Public thread identity/lifetime contract. All dereferences use nxdk's
 * published structures. Thread-pointer operations use handle references,
 * which are safe on both current native-backed and public-backed kernels.
 */
#include <windows.h>
#include <xboxkrnl/xboxkrnl.h>
#include <stddef.h>
#include "regression.h"
#define CASES 4
#define TIMEOUT (-50000000LL)
typedef struct Case {
    KEVENT entered, release;
    HANDLE id;
    PKTHREAD current;
    PETHREAD self_reference;
    NTSTATUS self_status;
    ULONG exit_code, explicit_exit;
    volatile ULONG create_count, exit_count;
    PETHREAD create_pointer, exit_pointer;
    ULONG create_uid, exit_uid, notify_exit_status, notify_terminated;
    ULONG create_status, create_terminated, create_header, create_signal;
    ULONGLONG create_time;
    LONG create_quantum;
    ULONG create_priority, create_base, create_suspend, create_state;
    PVOID create_start, create_tls, create_stack_base, create_stack_limit;
    KAPC kernel_apc, user_apc;
    volatile ULONG kernel_calls, rundown_calls, user_calls;
    PKTHREAD kernel_identity, rundown_identity;
} Case;
static Case cases[CASES];
static volatile LONG creating=-1;
static VOID NTAPI notify(PETHREAD thread,HANDLE id,BOOLEAN create) {
    Case *c=NULL;
    if(create && creating>=0 && creating<CASES)c=&cases[creating];
    else for(ULONG n=0;n<CASES;n++)if(cases[n].id==id)c=&cases[n];
    if(!c)return;
    if(create) {
        c->create_pointer=thread;c->create_uid=(ULONG)thread->UniqueThread;c->create_count++;
        c->create_status=thread->ExitStatus;c->create_terminated=thread->Tcb.HasTerminated;
        c->create_header=thread->Tcb.Header.Type|(thread->Tcb.Header.Size<<8);
        c->create_signal=thread->Tcb.Header.SignalState;
        c->create_time=thread->CreateTime.QuadPart;c->create_quantum=thread->Tcb.Quantum;
        c->create_priority=thread->Tcb.Priority;c->create_base=thread->Tcb.BasePriority;
        c->create_suspend=thread->Tcb.SuspendCount;c->create_state=thread->Tcb.State;
        c->create_start=thread->StartAddress;c->create_tls=thread->Tcb.TlsData;
        c->create_stack_base=thread->Tcb.StackBase;c->create_stack_limit=thread->Tcb.StackLimit;
    } else {
        c->exit_pointer=thread;c->exit_uid=(ULONG)thread->UniqueThread;
        c->notify_exit_status=thread->ExitStatus;c->notify_terminated=thread->Tcb.HasTerminated;c->exit_count++;
    }
}
static VOID NTAPI kernel_apc(PKAPC apc,PKNORMAL_ROUTINE *normal,PVOID *context,PVOID *arg1,PVOID *arg2) {
    (void)normal;(void)context;(void)arg1;(void)arg2;
    Case *c=CONTAINING_RECORD(apc,Case,kernel_apc);
    c->kernel_identity=KeGetCurrentThread();c->kernel_calls++;
}
static VOID NTAPI user_kernel(PKAPC apc,PKNORMAL_ROUTINE *normal,PVOID *context,PVOID *arg1,PVOID *arg2) {
    (void)apc;(void)normal;(void)context;(void)arg1;(void)arg2;
}
static VOID NTAPI user_normal(PVOID context,PVOID arg1,PVOID arg2) {
    (void)arg1;(void)arg2;((Case *)context)->user_calls++;
}
static VOID NTAPI user_rundown(PKAPC apc) {
    Case *c=CONTAINING_RECORD(apc,Case,user_apc);
    c->rundown_identity=KeGetCurrentThread();c->rundown_calls++;
}
static VOID NTAPI worker(PVOID context) {
    Case *c=context;
    c->current=KeGetCurrentThread();
    c->self_status=ObReferenceObjectByHandle((HANDLE)-2,&PsThreadObjectType,(PVOID *)&c->self_reference);
    KeSetEvent(&c->entered,0,FALSE);
    LARGE_INTEGER wait={.QuadPart=TIMEOUT};
    KeWaitForSingleObject(&c->release,Executive,KernelMode,FALSE,&wait);
    if(c->self_reference)ObfDereferenceObject(c->self_reference);
    if(c->explicit_exit)PsTerminateSystemThread(c->exit_code);
}
static VOID NTAPI system_start(PKSTART_ROUTINE entry,PVOID context) {
    entry(context);PsTerminateSystemThread(((Case *)context)->exit_code);
}
static void observe(ULONG n,const char *phase,PETHREAD object) {
    tap_comment("thread n=%lu phase=%s ptr=%p uid=%08lx ended=%u exit=%08lx header=%u/%u signal=%ld",
        n,phase,object,(ULONG)object->UniqueThread,object->Tcb.HasTerminated,
        (ULONG)object->ExitStatus,object->Tcb.Header.Type,object->Tcb.Header.Size,
        object->Tcb.Header.SignalState);
}
static void run(ULONG n) {
    Case *c=&cases[n];HANDLE file=NULL,reopened=NULL;PETHREAD typed=NULL,untyped=NULL;
    c->exit_code=0x10203040+n;c->explicit_exit=n&1;
    KeInitializeEvent(&c->entered,NotificationEvent,FALSE);
    KeInitializeEvent(&c->release,SynchronizationEvent,FALSE);
    creating=(LONG)n;
    NTSTATUS status=PsCreateSystemThreadEx(&file,0,16384,0,&c->id,worker,c,TRUE,FALSE,system_start);
    creating=-1;
    regression_require(status==0 && file!=NULL,"create suspended public thread without TLS allocation");
    regression_require(ObReferenceObjectByHandle(file,&PsThreadObjectType,(PVOID *)&typed)==0,
        "obtain typed public thread reference");
    regression_require(ObReferenceObjectByHandle(file,NULL,(PVOID *)&untyped)==0,
        "obtain untyped public thread reference");
    observe(n,"suspended",typed);
    tap_comment("create_metadata n=%lu time=%llu returned_time=%llu quantum=%ld returned_quantum=%ld priority=%lu base=%lu suspend=%lu state=%lu",
        n,c->create_time,typed->CreateTime.QuadPart,c->create_quantum,typed->Tcb.Quantum,c->create_priority,c->create_base,c->create_suspend,c->create_state);
    tap_comment("create_addresses n=%lu start=%p expected_start=%p tls=%p stack=%p limit=%p returned_suspend=%u returned_state=%u",
        n,c->create_start,worker,c->create_tls,c->create_stack_base,c->create_stack_limit,typed->Tcb.SuspendCount,typed->Tcb.State);
    regression_check(typed==untyped,"typed and untyped handles expose one thread identity");
    regression_check(typed->UniqueThread==c->id,"suspended public thread exposes assigned ID before startup");
    regression_check(!typed->Tcb.HasTerminated,"suspended thread is not terminated");
    regression_check(c->create_count==1 && c->create_pointer==typed && c->create_uid==(ULONG)c->id,
        "creation notification exposes same public identity and ID");
    regression_check(c->create_status==0 && !c->create_terminated && !c->create_signal && c->create_header==0x4406,
        "creation callback sees initialized public header and live exit state");
    regression_require(ObReferenceObjectByPointer(typed,&PsThreadObjectType)==0,
        "reference public thread by pointer and type");
    ObfDereferenceObject(typed);
    ObfReferenceObject(typed);ObfDereferenceObject(typed);
    regression_require(ObOpenObjectByPointer(typed,&PsThreadObjectType,&reopened)==0 && reopened!=NULL,
        "open a thread handle from its public pointer");
    PVOID wrong=(PVOID)0x55;
    status=ObReferenceObjectByHandle(reopened,&ExEventObjectType,&wrong);
    regression_check(status==(NTSTATUS)0xc0000024,"thread reference rejects an event type");
    if(NT_SUCCESS(status))ObfDereferenceObject(wrong);
    LONG base=KeQueryBasePriorityThread(&typed->Tcb);
    regression_check(KeSetBasePriorityThread(&typed->Tcb,base)==base,"base-priority setter accepts public pointer");
    KPRIORITY priority=KeSetPriorityThread(&typed->Tcb,8);
    regression_check(priority>=1 && priority<=31,"priority setter accepts public pointer");
    KeSetPriorityThread(&typed->Tcb,priority);
    KeBoostPriorityThread(&typed->Tcb,0);
    regression_check(KeAlertThread(&typed->Tcb,KernelMode)==FALSE,"alert setter accepts public pointer");
    KeInitializeApc(&c->kernel_apc,&typed->Tcb,kernel_apc,NULL,NULL,KernelMode,NULL);
    regression_check(KeInsertQueueApc(&c->kernel_apc,NULL,NULL,0),"queue kernel APC through suspended public pointer");
    KeInitializeApc(&c->user_apc,&typed->Tcb,user_kernel,user_rundown,user_normal,UserMode,c);
    regression_check(KeInsertQueueApc(&c->user_apc,NULL,NULL,0),"queue user APC for thread-exit rundown");
    ULONG prior=KeSuspendThread(&typed->Tcb);
    regression_check(prior==1,"pointer suspend sees initial suspended count");
    regression_check(KeResumeThread(&typed->Tcb)==2,"pointer resume preserves remaining suspension");
    LOGICAL boost=KeSetDisableBoostThread(&typed->Tcb,TRUE);
    regression_check(KeSetDisableBoostThread(&typed->Tcb,boost)==TRUE,"disable-boost setter round trips pointer");
    if(n&1)regression_check(KeAlertResumeThread(&typed->Tcb)==1,"pointer alert-resume starts suspended target");
    else {
        ULONG count=0;regression_require(NtResumeThread(reopened,&count)==0,"handle resume starts suspended target");
        regression_check(count==1,"handle resume reports previous count");
    }
    LARGE_INTEGER wait={.QuadPart=TIMEOUT};
    regression_require(KeWaitForSingleObject(&c->entered,Executive,KernelMode,FALSE,&wait)==0,"worker reaches live identity checkpoint");
    observe(n,"live",typed);
    tap_comment("identity n=%lu create_id=%08lx current=%p self=%p handle=%p self_status=%08lx",
        n,(ULONG)c->id,c->current,c->self_reference,typed,(ULONG)c->self_status);
    regression_check(c->self_status==0 && c->current==(PKTHREAD)typed && c->self_reference==typed,
        "current export pseudo handle and real handle have identical public pointer");
    regression_check(((PETHREAD)c->current)->UniqueThread==c->id,"current-thread public view exposes assigned ID");
    DWORD code=0;BOOL query=GetExitCodeThread(reopened,&code);
    regression_check(query && code==STILL_ACTIVE,"live public wrapper reports STILL_ACTIVE");
    LARGE_INTEGER zero={.QuadPart=0};
    regression_check(KeWaitForSingleObject(typed,Executive,KernelMode,FALSE,&zero)==STATUS_TIMEOUT,
        "pointer wait on live target times out without signaling");
    regression_require(NtClose(file)==0,"close first handle while references retain target");
    LARGE_INTEGER pause={.QuadPart=-10000};
    for(ULONG spins=0;spins<1000 && IsListEmpty(&c->release.Header.WaitListHead);spins++)
        KeDelayExecutionThread(KernelMode,FALSE,&pause);
    regression_require(!IsListEmpty(&c->release.Header.WaitListHead),"target is pending on synchronization event");
    PKTHREAD awakened=NULL;
    KeSetEventBoostPriority(&c->release,&awakened);
    regression_check(awakened==&typed->Tcb,"boost-event output uses the same public thread identity");
    wait.QuadPart=TIMEOUT;
    regression_require(KeWaitForSingleObject(typed,Executive,KernelMode,FALSE,&wait)==0,
        "retained public pointer wait observes termination");
    observe(n,"exited",typed);
    query=GetExitCodeThread(reopened,&code);
    tap_comment("exit n=%lu expected=%08lx wrapper=%08lx query=%u notify=%lu ptr=%p uid=%08lx status=%08lx ended=%lu",
        n,c->exit_code,code,query,c->exit_count,c->exit_pointer,c->exit_uid,c->notify_exit_status,c->notify_terminated);
    regression_check(typed->Tcb.HasTerminated && (ULONG)typed->ExitStatus==c->exit_code,
        "termination state and exact exit status publish before wait succeeds");
    regression_check(query && code==c->exit_code,"public wrapper reads exact completed exit code");
    regression_check(typed->UniqueThread==NULL,"completed thread clears its public unique ID");
    regression_check(c->exit_count==1 && c->exit_pointer==typed && c->exit_uid==(ULONG)c->id,
        "exit notification retains same public pointer and unique ID");
    regression_check(c->notify_terminated==1 && c->notify_exit_status==0,
        "exit notification publishes termination before final status");
    regression_check(c->kernel_calls==1 && c->kernel_identity==&typed->Tcb && !c->kernel_apc.Inserted,
        "kernel APC executes exactly once with target public identity");
    regression_check(c->rundown_calls==1 && c->rundown_identity==&typed->Tcb && !c->user_calls && !c->user_apc.Inserted,
        "undelivered user APC runs down exactly once before thread signal");
    PVOID objects[]={typed,&c->entered};KWAIT_BLOCK blocks[2];wait.QuadPart=TIMEOUT;
    regression_check(KeWaitForMultipleObjects(2,objects,WaitAll,Executive,KernelMode,FALSE,&wait,blocks)==0,
        "multiple-object wait translates a thread beside an ordinary event");
    regression_require(NtClose(reopened)==0,"close final handle before final references");
    wait.QuadPart=0;
    regression_check(KeWaitForSingleObject(typed,Executive,KernelMode,FALSE,&wait)==0,
        "public pointer and terminal state survive closing every handle");
    ObfDereferenceObject(untyped);ObfDereferenceObject(typed);
}
static void wait_blocks_probe(void) {
    KEVENT ready,pending;PETHREAD self=NULL;
    KeInitializeEvent(&ready,NotificationEvent,TRUE);
    KeInitializeEvent(&pending,NotificationEvent,FALSE);
    PVOID objects[]={&ready,&pending};
    regression_require(ObReferenceObjectByHandle((HANDLE)-2,&PsThreadObjectType,(PVOID *)&self)==0,"reference current thread for alert wait oracle");
    for(ULONG n=0;n<3;n++) {
        struct {ULONG before[4];KWAIT_BLOCK blocks[2];ULONG after[4];} guarded;
        memset(&guarded,0xa5,sizeof(guarded));
        if(n==2)KeAlertThread(&self->Tcb,KernelMode);
        LARGE_INTEGER zero={.QuadPart=0};
        NTSTATUS result=KeWaitForMultipleObjects(2,objects,n?WaitAll:WaitAny,Executive,KernelMode,n==2,&zero,guarded.blocks);
        tap_comment("waitblocks mode=%lu result=%08lx current=%p thread0=%p thread1=%p object0=%p object1=%p next0=%p next1=%p keys=%u,%u types=%u,%u",
            n,(ULONG)result,KeGetCurrentThread(),guarded.blocks[0].Thread,guarded.blocks[1].Thread,
            guarded.blocks[0].Object,guarded.blocks[1].Object,guarded.blocks[0].NextWaitBlock,guarded.blocks[1].NextWaitBlock,
            guarded.blocks[0].WaitKey,guarded.blocks[1].WaitKey,guarded.blocks[0].WaitType,guarded.blocks[1].WaitType);
        regression_check(result==(n==0?0:n==1?STATUS_TIMEOUT:(NTSTATUS)0x101),"immediate timeout and alerted multiple waits return exact status");
        int guards=1;for(ULONG i=0;i<4;i++)if(guarded.before[i]!=0xa5a5a5a5 || guarded.after[i]!=0xa5a5a5a5)guards=0;
        regression_check(guards && objects[0]==&ready && objects[1]==&pending,"multiple wait preserves block guards and caller object array");
    }
    ULONGLONG start,end;
    start=KeQueryPerformanceCounter();
    for(ULONG n=0;n<65536;n++){ObfReferenceObject(self);ObfDereferenceObject(self);}
    end=KeQueryPerformanceCounter();
    tap_comment("reference_bench pairs=65536 ticks=%llu frequency=%llu",end-start,KeQueryPerformanceFrequency());
    ObfDereferenceObject(self);
}
int main(void) {
    regression_begin();
    wait_blocks_probe();
    tap_comment("public layout KTHREAD=%u ETHREAD=%u HasTerminated=%u ExitStatus=%u UniqueThread=%u",
        sizeof(KTHREAD),sizeof(ETHREAD),offsetof(KTHREAD,HasTerminated),offsetof(ETHREAD,ExitStatus),offsetof(ETHREAD,UniqueThread));
    regression_require(PsSetCreateThreadNotifyRoutine(notify)==0,"register public thread creation and exit observer");
    for(ULONG n=0;n<CASES;n++)run(n);
    regression_finish();
}
