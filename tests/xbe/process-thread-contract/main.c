/* SPDX-License-Identifier: GPL-2.0-or-later
 * Public nxdk ABI only. Observes creation, priority, membership and retirement.
 */
#include <windows.h>
#include <xboxkrnl/xboxkrnl.h>
#include <stddef.h>
#include "regression.h"
#define TIMEOUT -50000000LL
#define CASES 3
static PKPROCESS process;
typedef struct Case {
 KEVENT entered,release;
 PKTHREAD current;
 PETHREAD created;
 HANDLE id;
 LONG create_base,create_priority,entry_base,entry_priority;
 ULONG create_member,exit_member,created_count,exit_count;
} Case;
static Case cases[CASES];
static volatile LONG creating=-1;
static ULONG membership(PKTHREAD target,ULONG *total) {
 PLIST_ENTRY head=&process->ThreadListHead,entry;
 ULONG count=0,found=0;
 KIRQL old=KeRaiseIrqlToDpcLevel();entry=head->Flink;
 while(entry!=head && count<4096) {
  if(!entry || !entry->Flink || !entry->Blink || entry->Flink->Blink!=entry || entry->Blink->Flink!=entry){found=0xffffffff;break;}
  if(entry==&target->ThreadListEntry)found++;
  count++;entry=entry->Flink;
 }
 if(count==4096)found=0xffffffff;
 KfLowerIrql(old);if(total)*total=count;return found;
}
static VOID NTAPI notify(PETHREAD thread,HANDLE id,BOOLEAN create) {
 Case *c=NULL;
 if(create && creating>=0 && creating<CASES)c=&cases[creating];
 else for(ULONG i=0;i<CASES;i++)if(cases[i].id==id){c=&cases[i];break;}
 if(!c)return;
 if(create) {
  c->created=thread;c->create_base=thread->Tcb.BasePriority;c->create_priority=thread->Tcb.Priority;
  c->create_member=membership(&thread->Tcb,NULL);c->created_count++;
 } else {c->exit_member=membership(&thread->Tcb,NULL);c->exit_count++;}
}
static VOID NTAPI worker(PVOID context) {
 Case *c=context;c->current=KeGetCurrentThread();
 c->entry_base=c->current->BasePriority;c->entry_priority=c->current->Priority;
 KeSetEvent(&c->entered,0,FALSE);
 LARGE_INTEGER timeout={.QuadPart=TIMEOUT};
 KeWaitForSingleObject(&c->release,Executive,KernelMode,FALSE,&timeout);
}
static VOID NTAPI startup(PKSTART_ROUTINE start,PVOID context){start(context);PsTerminateSystemThread(0x4321);}
static HANDLE spawn(ULONG i,BOOLEAN suspended,BOOLEAN simple) {
 Case *c=&cases[i];HANDLE h=NULL;
 KeInitializeEvent(&c->entered,NotificationEvent,FALSE);KeInitializeEvent(&c->release,NotificationEvent,FALSE);
 creating=i;
 NTSTATUS status=simple?PsCreateSystemThread(&h,&c->id,worker,c,FALSE):PsCreateSystemThreadEx(&h,0,16384,0,&c->id,worker,c,suspended,FALSE,startup);
 creating=-1;
 regression_require(status==0&&h!=NULL,"create zero-TLS title thread");
 tap_comment("create case=%lu suspended=%u simple=%u base=%ld priority=%ld member=%lu",i,suspended,simple,c->create_base,c->create_priority,c->create_member);
 regression_check(c->created_count==1,"creation callback runs once");
 regression_check(c->create_base==process->BasePriority&&c->create_priority==process->BasePriority,"creation callback observes inherited process priority");
 regression_check(c->create_member==1,"creation callback observes public process membership");return h;
}
static void entered(ULONG i) {
 LARGE_INTEGER timeout={.QuadPart=TIMEOUT};Case *c=&cases[i];
 regression_require(KeWaitForSingleObject(&c->entered,Executive,KernelMode,FALSE,&timeout)==0,"worker reaches its first title instruction");
 tap_comment("entry case=%lu base=%ld priority=%ld member=%lu",i,c->entry_base,c->entry_priority,membership(c->current,NULL));
 regression_check(c->entry_base==process->BasePriority&&c->entry_priority==process->BasePriority,"new title thread inherits current process priority");
 regression_check(c->current==&c->created->Tcb,"create and current pointers share public identity");
 regression_check(c->current->ApcState.Process==process,"worker names the same process");
}
static void retire(ULONG i,HANDLE h) {
 PETHREAD t=NULL;Case *c=&cases[i];
 regression_require(ObReferenceObjectByHandle(h,&PsThreadObjectType,(PVOID *)&t)==0,"reference retiring public thread");
 KeSetEvent(&c->release,0,FALSE);LARGE_INTEGER timeout={.QuadPart=TIMEOUT};
 regression_require(KeWaitForSingleObject(t,Executive,KernelMode,FALSE,&timeout)==0,"wait for worker retirement");
 tap_comment("retire case=%lu member=%lu exit_notify_member=%lu exit_count=%lu links_self=%u",i,membership(&t->Tcb,NULL),c->exit_member,c->exit_count,t->Tcb.ThreadListEntry.Flink==&t->Tcb.ThreadListEntry&&t->Tcb.ThreadListEntry.Blink==&t->Tcb.ThreadListEntry);
 regression_check(membership(&t->Tcb,NULL)==0,"terminated referenced thread leaves process list");
 regression_check(c->exit_count==1,"termination callback runs once");
 regression_check(c->exit_member==1,"termination callback precedes process list removal");
 LONG terminal_increment=KeQueryBasePriorityThread(&t->Tcb);
 tap_comment("terminal_priority case=%lu process_base=%d thread_base=%d query_increment=%ld",i,process->BasePriority,t->Tcb.BasePriority,terminal_increment);
 regression_check(terminal_increment==0&&t->Tcb.BasePriority==process->BasePriority,"referenced terminated thread keeps its process-relative base query");
 NtClose(h);ObfDereferenceObject(t);c->id=NULL;
}
static void saturation_matrix(LONG original) {
 const LONG priorities[]={original+2,16,20,31,15,2,original+1};
 KeSetPriorityProcess(process,original+1);
 regression_check(KeSetBasePriorityThread(cases[0].current,16)==0,"positive saturation setter reports previous increment");
 regression_check(KeSetBasePriorityThread(cases[1].current,-16)==0,"negative saturation setter reports previous increment");
 regression_check(KeQueryBasePriorityThread(cases[0].current)==16,"positive saturation query before process move");
 regression_check(KeQueryBasePriorityThread(cases[1].current)==-16,"negative saturation query before process move");
 for(ULONG i=0;i<sizeof(priorities)/sizeof(priorities[0]);i++) {
  LONG before=process->BasePriority,p=priorities[i],positive=p>=16?31:15,negative=p>=16?16:1;
  LONG returned=KeSetPriorityProcess(process,p);
  LONG positive_query=KeQueryBasePriorityThread(cases[0].current),negative_query=KeQueryBasePriorityThread(cases[1].current);
  tap_comment("saturation process=%ld->%ld positive_base=%d query=%ld negative_base=%d query=%ld",before,p,cases[0].current->BasePriority,positive_query,cases[1].current->BasePriority,negative_query);
  regression_check(returned==before&&process->BasePriority==p,"saturation process setter publishes new base and returns old base");
  regression_check(cases[0].current->BasePriority==positive,"positive saturated thread stays at class maximum");
  regression_check(cases[1].current->BasePriority==negative,"negative saturated thread stays at class minimum");
  regression_check(positive_query==16,"process move preserves positive saturation increment");
  regression_check(negative_query==-16,"process move preserves negative saturation increment");
 }
 KeSetBasePriorityThread(cases[0].current,0);KeSetBasePriorityThread(cases[1].current,0);
}
static void inheritance_matrix(void) {
 const LONG priorities[]={16,31,1};
 for(ULONG i=0;i<sizeof(priorities)/sizeof(priorities[0]);i++) {
  LONG old=process->BasePriority;
  regression_check(KeSetPriorityProcess(process,priorities[i])==old&&process->BasePriority==priorities[i],"inheritance matrix process setter publishes chosen base");
  for(ULONG suspended=0;suspended<2;suspended++) {
   memset(&cases[0],0,sizeof(cases[0]));
   tap_comment("inheritance process=%ld suspended=%lu",priorities[i],suspended);
   HANDLE h=spawn(0,suspended,FALSE);
   if(suspended) {
    PETHREAD thread=NULL;
    regression_require(ObReferenceObjectByHandle(h,&PsThreadObjectType,(PVOID *)&thread)==0,"reference inheritance matrix suspended thread");
    regression_check(membership(&thread->Tcb,NULL)==1,"inheritance matrix suspended thread belongs to public process");
    regression_check(thread->Tcb.BasePriority==priorities[i]&&thread->Tcb.Priority==priorities[i],"inheritance matrix suspended thread inherits selected process base");
    ObfDereferenceObject(thread);
    regression_require(NtResumeThread(h,NULL)==0,"resume inheritance matrix suspended thread");
   }
   entered(0);retire(0,h);
  }
 }
}
int main(void) {
 regression_begin();PKTHREAD self=KeGetCurrentThread();process=self->ApcState.Process;
 regression_require(process!=NULL,"current thread names public process");
 regression_check(sizeof(KPROCESS)==0x1c&&offsetof(KPROCESS,ThreadListHead)==8&&offsetof(KTHREAD,ThreadListEntry)==0x104,"process and thread links use public nxdk ABI");
 ULONG initial_count=0;
 regression_check(membership(self,&initial_count)==1,"running title thread belongs to its process");
 tap_comment("initial process_base=%d current_base=%d current_priority=%d thread_count=%lu stack_count=%lu",process->BasePriority,self->BasePriority,self->Priority,initial_count,process->StackCount);
 regression_require(PsSetCreateThreadNotifyRoutine(notify)==0,"register creation and exit observer");
 LONG original=process->BasePriority;regression_require(original>=2&&original<=12,"process base permits in-range priority probes");
 regression_check(KeSetPriorityProcess(process,original+1)==original,"process setter reports previous base");
 HANDLE first=spawn(0,TRUE,FALSE);PETHREAD suspended=NULL;
 regression_require(ObReferenceObjectByHandle(first,&PsThreadObjectType,(PVOID *)&suspended)==0,"reference suspended zero-TLS thread");
 regression_check(membership(&suspended->Tcb,NULL)==1,"suspended zero-TLS thread is already a process member");
 regression_check(suspended->Tcb.BasePriority==original+1,"suspended thread inherits before it runs");
 regression_require(NtResumeThread(first,NULL)==0,"resume first title thread");entered(0);
 LONG offset=KeSetBasePriorityThread(cases[0].current,2);
 LONG worker_before=cases[0].current->BasePriority;
 regression_check(offset==0&&worker_before==original+3,"thread base increment is relative to public process");
 regression_check(KeQueryBasePriorityThread(cases[0].current)==2,"thread base query reports its public process increment");
 KeSetPriorityProcess(process,original+2);
 tap_comment("priority_offset old_increment=%ld worker_before=%ld process_before=%ld process_after=%d worker_after=%d current_after=%d",offset,worker_before,original+1,process->BasePriority,cases[0].current->BasePriority,self->BasePriority);
 regression_check(cases[0].current->BasePriority==original+4&&self->BasePriority==original+2,"process change preserves individual thread base increment");
 KeSetPriorityProcess(process,original+1);
 KeSetBasePriorityThread(cases[0].current,0);
 HANDLE second=spawn(1,FALSE,FALSE);entered(1);
 HANDLE third=spawn(2,FALSE,TRUE);entered(2);
 ULONG active_count=0;membership(self,&active_count);
 tap_comment("active process_threads=%lu initial=%lu stack_count=%lu",active_count,initial_count,process->StackCount);
 regression_check(active_count==initial_count+CASES,"public list adds only created title threads");
 KeSetPriorityProcess(process,original+2);
 regression_check(cases[1].current->BasePriority==original+2&&cases[2].current->BasePriority==original+2,"process priority follows already running title threads");
 KeSetPriorityProcess(process,original);
 regression_check(self->BasePriority==original,"caller native base restores with process");
 KeSetPriorityProcess(process,original+1);
 saturation_matrix(original);
 ObfDereferenceObject(suspended);retire(0,first);retire(1,second);retire(2,third);
 inheritance_matrix();
 KeSetPriorityProcess(process,original);
 ULONG final_count=0;membership(self,&final_count);
 regression_check(final_count==initial_count,"retirement restores original public list count");
 tap_comment("final process_threads=%lu stack_count=%lu",final_count,process->StackCount);
 regression_finish();
}
