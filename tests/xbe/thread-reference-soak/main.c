#include <windows.h>
#include <xboxkrnl/xboxkrnl.h>
#include <string.h>
#include "regression.h"
#define WIDTH 32
#define LOOPS 32768
#define STATUS_CODE 0x43212345
static KEVENT release;
static volatile ULONG completed;
static ULONG failures;
static VOID NTAPI worker(PVOID context) {
 (void)context;
 LARGE_INTEGER timeout={.QuadPart=-50000000};
 if(KeWaitForSingleObject(&release,Executive,KernelMode,FALSE,&timeout)!=0)InterlockedIncrement((LONG *)&failures);
 InterlockedIncrement((LONG *)&completed);
 PsTerminateSystemThread(STATUS_CODE);
}
static VOID NTAPI startup(PKSTART_ROUTINE start,PVOID context) {start(context);PsTerminateSystemThread(STATUS_CODE);}
static MM_STATISTICS snapshot(const char *phase) {
 MM_STATISTICS s={.Length=sizeof(s)};
 regression_require(MmQueryStatistics(&s)==0,"read public memory statistics");
 tap_comment("memory phase=%s available=%lu pool=%lu stack=%lu image=%lu cache=%lu",phase,s.AvailablePages,s.PoolPagesCommitted,s.StackPagesCommitted,s.ImagePagesCommitted,s.CachePagesCommitted);return s;
}
static void pause_reaper(void){LARGE_INTEGER delay={.QuadPart=-100000};KeDelayExecutionThread(KernelMode,FALSE,&delay);}
static void bench(PVOID object,HANDLE handle,const char *name) {
 for(ULONG round=0;round<3;round++) {
  ULONGLONG start=KeQueryPerformanceCounter();
  for(ULONG i=0;i<LOOPS;i++){ObfReferenceObject(object);ObfDereferenceObject(object);}
  ULONGLONG end=KeQueryPerformanceCounter();
  tap_comment("cost kind=pointer object=%s round=%lu pairs=%u ticks=%llu freq=%llu",name,round,LOOPS,end-start,KeQueryPerformanceFrequency());
  start=KeQueryPerformanceCounter();
  for(ULONG i=0;i<LOOPS;i++){PVOID found=NULL;if(ObReferenceObjectByHandle(handle,NULL,&found)!=0 || found!=object)failures++;if(found)ObfDereferenceObject(found);}
  end=KeQueryPerformanceCounter();
  tap_comment("cost kind=handle object=%s round=%lu pairs=%u ticks=%llu freq=%llu",name,round,LOOPS,end-start,KeQueryPerformanceFrequency());
 }
}
static HANDLE spawn(BOOLEAN suspended,HANDLE *id) {
 HANDLE h=NULL;
 regression_require(PsCreateSystemThreadEx(&h,0,16384,0,id,worker,NULL,suspended,FALSE,startup)==0,"create measured thread");return h;
}
static void retire(HANDLE h,PETHREAD thread) {
 LARGE_INTEGER timeout={.QuadPart=-50000000};
 regression_require(KeWaitForSingleObject(thread,Executive,KernelMode,FALSE,&timeout)==0,"wait for measured thread termination");
 if(!thread->Tcb.HasTerminated || (ULONG)thread->ExitStatus!=STATUS_CODE || thread->UniqueThread!=NULL)failures++;
 NtClose(h);ObfDereferenceObject(thread);
}
int main(void) {
 regression_begin();KeInitializeEvent(&release,NotificationEvent,FALSE);
 PETHREAD self=NULL;PVOID event_object=NULL,file_object=NULL;HANDLE event=NULL;
 regression_require(ObReferenceObjectByHandle((HANDLE)-2,&PsThreadObjectType,(PVOID *)&self)==0,"reference current thread");
 regression_require(NtCreateEvent(&event,NULL,NotificationEvent,FALSE)==0,"create generic event");
 regression_require(ObReferenceObjectByHandle(event,&ExEventObjectType,&event_object)==0,"reference generic event");
 HANDLE file=CreateFileA("D:\\default.xbe",GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
 regression_require(file!=INVALID_HANDLE_VALUE,"open fixture file");
 regression_require(ObReferenceObjectByHandle(file,&IoFileObjectType,&file_object)==0,"reference generic file");
 pause_reaper();MM_STATISTICS before=snapshot("before32");
 HANDLE handles[WIDTH],ids[WIDTH];PETHREAD threads[WIDTH];
 for(ULONG i=0;i<WIDTH;i++) {
  handles[i]=spawn(TRUE,&ids[i]);
  regression_require(ObReferenceObjectByHandle(handles[i],&PsThreadObjectType,(PVOID *)&threads[i])==0,"reference measured thread");
  if(threads[i]->UniqueThread!=ids[i])failures++;
 }
 MM_STATISTICS full=snapshot("suspended32");
 tap_comment("growth width=%u available_delta=%ld pool_delta=%ld stack_delta=%ld",WIDTH,(LONG)before.AvailablePages-(LONG)full.AvailablePages,(LONG)full.PoolPagesCommitted-(LONG)before.PoolPagesCommitted,(LONG)full.StackPagesCommitted-(LONG)before.StackPagesCommitted);
 bench(self,(HANDLE)-2,"current");bench(threads[17],handles[17],"other");bench(event_object,event,"event");bench(file_object,file,"file");
 for(ULONG i=0;i<WIDTH;i++)regression_require(NtResumeThread(handles[i],NULL)==0,"resume measured thread");
 KeSetEvent(&release,0,FALSE);
 for(ULONG i=0;i<WIDTH;i++)retire(handles[i],threads[i]);
 pause_reaper();snapshot("retired32");
 MM_STATISTICS warm={0};ULONG minimum=0,maximum=0,pool_min=0,pool_max=0;
 for(ULONG i=0;i<320;i++) {
  HANDLE id,h=NULL;PETHREAD t=NULL;
  if(PsCreateSystemThreadEx(&h,0,16384,0,&id,worker,NULL,FALSE,FALSE,startup)!=0){failures++;break;}
  if(ObReferenceObjectByHandle(h,&PsThreadObjectType,(PVOID *)&t)!=0){failures++;break;}
  LARGE_INTEGER timeout={.QuadPart=-50000000};
  if(KeWaitForSingleObject(t,Executive,KernelMode,FALSE,&timeout)!=0){failures++;break;}
  if(!t->Tcb.HasTerminated || (ULONG)t->ExitStatus!=STATUS_CODE || t->UniqueThread!=NULL)failures++;
  NtClose(h);ObfDereferenceObject(t);
  if((i+1)%64==0) {
   pause_reaper();MM_STATISTICS s={.Length=sizeof(s)};MmQueryStatistics(&s);
   tap_comment("soak cycles=%lu completed=%lu available=%lu pool=%lu stack=%lu",i+1,completed,s.AvailablePages,s.PoolPagesCommitted,s.StackPagesCommitted);
   if(i==63){warm=s;minimum=maximum=s.AvailablePages;pool_min=pool_max=s.PoolPagesCommitted;}
   else {if(s.AvailablePages<minimum)minimum=s.AvailablePages;if(s.AvailablePages>maximum)maximum=s.AvailablePages;if(s.PoolPagesCommitted<pool_min)pool_min=s.PoolPagesCommitted;if(s.PoolPagesCommitted>pool_max)pool_max=s.PoolPagesCommitted;}
  }
 }
 tap_comment("soak_summary workers=%lu errors=%lu available_min=%lu max=%lu pool_min=%lu max=%lu warm_stack=%lu",completed,failures,minimum,maximum,pool_min,pool_max,warm.StackPagesCommitted);
 regression_check(completed==352,"all measured workers complete");
 regression_check(failures==0,"all public references IDs and terminal fields remain correct");
 regression_check(minimum==maximum && pool_min==pool_max,"quiet post-warmup creation and deletion have flat page and pool use");
 ObfDereferenceObject(file_object);NtClose(file);ObfDereferenceObject(event_object);NtClose(event);ObfDereferenceObject(self);
 regression_finish();
}
