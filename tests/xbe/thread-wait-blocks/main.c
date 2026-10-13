#include <windows.h>
#include <xboxkrnl/xboxkrnl.h>
#include <string.h>
#include "regression.h"

static void log_blocks(const char *kind,ULONG a,ULONG b,KWAIT_BLOCK *blocks,KWAIT_BLOCK *original,PVOID *objects) {
 ULONG untouched=0,threads=0,objs=0,circle=0,next=0;
 for(ULONG i=0;i<2;i++) {
  if(!memcmp(&blocks[i],&original[i],sizeof(KWAIT_BLOCK)))untouched|=1<<i;
  if(blocks[i].Thread==KeGetCurrentThread())threads|=1<<i;
  if(blocks[i].Object==objects[i])objs|=1<<i;
  if(blocks[i].NextWaitBlock==&blocks[(i+1)%2])circle|=1<<i;
  if(blocks[i].NextWaitBlock==&blocks[i+1])next|=1<<i;
 }
 tap_comment("edge kind=%s a=%lu b=%lu untouched=%lu public_threads=%lu objects=%lu circle=%lu next=%lu raw_threads=%p,%p self=%p raw_objects=%p,%p types=%04x,%04x keys=%04x,%04x",
  kind,a,b,untouched,threads,objs,circle,next,blocks[0].Thread,blocks[1].Thread,KeGetCurrentThread(),blocks[0].Object,blocks[1].Object,
  (USHORT)blocks[0].WaitType,(USHORT)blocks[1].WaitType,(USHORT)blocks[0].WaitKey,(USHORT)blocks[1].WaitKey);
}
static void abandoned_oracle(void) {
 for(ULONG next=0;next<2;next++)for(ULONG type=0;type<2;type++)for(ULONG which=0;which<2;which++) {
  KMUTANT mutant;KEVENT event,kick;PVOID objects[2];
  struct {ULONG pre[4];KWAIT_BLOCK blocks[2];ULONG post[4];} g,original;
  memset(&g,0xa5,sizeof(g));original=g;
  KeInitializeMutant(&mutant,TRUE);KeReleaseMutant(&mutant,0,TRUE,FALSE);
  KeInitializeEvent(&event,NotificationEvent,type==WaitAll);
  KeInitializeEvent(&kick,NotificationEvent,FALSE);
  objects[which]=&mutant;objects[1-which]=&event;
  LARGE_INTEGER zero={.QuadPart=0};
  if(next)KeSetEvent(&kick,0,TRUE);
  NTSTATUS result=KeWaitForMultipleObjects(2,objects,(WAIT_TYPE)type,Executive,KernelMode,FALSE,&zero,g.blocks);
  tap_comment("abandoned n=%lu type=%lu which=%lu ret=%08lx owner=%p self=%p",next,type,which,(ULONG)result,mutant.OwnerThread,KeGetCurrentThread());
  log_blocks("abandoned",type,which,g.blocks,original.blocks,objects);
  regression_check(result==(NTSTATUS)(0x80+(type==WaitAny?which:0)),"abandoned wait returns public result");
  regression_check(!memcmp(g.pre,original.pre,sizeof(g.pre)) && !memcmp(g.post,original.post,sizeof(g.post)),"abandoned wait preserves guards");
  ULONG prefix=type==WaitAny?which:2;int exact=1;
  for(ULONG i=0;i<2;i++) {
   if(i>=prefix){if(memcmp(&g.blocks[i],&original.blocks[i],sizeof(KWAIT_BLOCK)))exact=0;continue;}
   if(g.blocks[i].Thread!=KeGetCurrentThread() || g.blocks[i].Object!=objects[i] || g.blocks[i].WaitType!=(SHORT)type || g.blocks[i].WaitKey!=(SHORT)i ||
      g.blocks[i].NextWaitBlock!=(type==WaitAll?&g.blocks[(i+1)%2]:&g.blocks[i+1]) || memcmp(&g.blocks[i].WaitListEntry,&original.blocks[i].WaitListEntry,sizeof(LIST_ENTRY)))exact=0;
  }
  regression_check(exact,"abandoned wait preserves exact public block prefix and circle");
  KeReleaseMutant(&mutant,0,FALSE,FALSE);
 }
}

#define APC_MAX 64
typedef struct ApcCase {
 KAPC apc;KWAIT_BLOCK *blocks;KWAIT_BLOCK kernel[APC_MAX],normal[APC_MAX];
 ULONG count,kernel_calls,normal_calls,order,kernel_irql,normal_irql,nested_ok,queued;
 PETHREAD target;KEVENT *pending;
} ApcCase;
static VOID NTAPI apc_kernel(PKAPC apc,PKNORMAL_ROUTINE *normal,PVOID *context,PVOID *a,PVOID *b) {
 (void)normal;(void)context;(void)a;(void)b;ApcCase *c=CONTAINING_RECORD(apc,ApcCase,apc);
 if(c->blocks)memcpy(c->kernel,c->blocks,c->count*sizeof(KWAIT_BLOCK));
 c->kernel_calls++;c->kernel_irql=KeGetCurrentIrql();c->order=c->order*10+1;
}
static VOID NTAPI apc_normal(PVOID context,PVOID a,PVOID b) {
 (void)a;(void)b;ApcCase *c=context;
 if(c->blocks)memcpy(c->normal,c->blocks,c->count*sizeof(KWAIT_BLOCK));
 c->normal_calls++;c->normal_irql=KeGetCurrentIrql();c->order=c->order*10+2;
 KEVENT event;PVOID objects[]={&event};KWAIT_BLOCK block;memset(&block,0x5a,sizeof(block));
 KeInitializeEvent(&event,NotificationEvent,TRUE);LARGE_INTEGER zero={.QuadPart=0};
 c->nested_ok=KeWaitForMultipleObjects(1,objects,WaitAll,Executive,KernelMode,FALSE,&zero,&block)==0 &&
  block.Thread==KeGetCurrentThread() && block.Object==&event && block.WaitType==WaitAll;
}
static VOID NTAPI apc_issuer(PVOID context) {
 ApcCase *c=context;LARGE_INTEGER pause={.QuadPart=-10000};
 for(ULONG i=0;i<2000 && IsListEmpty(&c->pending->Header.WaitListHead);i++)KeDelayExecutionThread(KernelMode,FALSE,&pause);
 if(!IsListEmpty(&c->pending->Header.WaitListHead))c->queued=KeInsertQueueApc(&c->apc,NULL,NULL,0);
}
static VOID NTAPI apc_start(PKSTART_ROUTINE start,PVOID context){start(context);PsTerminateSystemThread(0);}
static void apc_oracle(PETHREAD self) {
 for(ULONG variant=0;variant<8;variant++)for(ULONG type=0;type<2;type++) {
  if(variant==2||variant==3)continue; /* Public WaitBlockArray is required. */
  static KEVENT events[APC_MAX];static PVOID objects[APC_MAX];
  static struct {ULONG pre[4];KWAIT_BLOCK blocks[APC_MAX];ULONG post[4];} g,original;
  static ApcCase c;HANDLE helper=NULL;ULONG count=variant>=6?1:variant>=4?APC_MAX:2;int nullblocks=variant==2||variant==3,queued=variant&1;
  memset(&c,0,sizeof(c));memset(&g,0xa5,sizeof(g));original=g;c.blocks=nullblocks?NULL:g.blocks;c.count=count;c.target=self;c.pending=&events[0];
  for(ULONG i=0;i<count;i++){KeInitializeEvent(&events[i],NotificationEvent,FALSE);objects[i]=&events[i];}
  /* Keep event[0] available for the issuer's actual-wait observation. */
  if(count>1 || !queued)objects[count-1]=self;
  KeInitializeApc(&c.apc,&self->Tcb,apc_kernel,NULL,apc_normal,UserMode,&c);
  if(queued)regression_require(PsCreateSystemThreadEx(&helper,0,16384,0,NULL,apc_issuer,&c,FALSE,FALSE,apc_start)==0,"create APC issuer for actual blocked wait");
  else regression_require(KeInsertQueueApc(&c.apc,NULL,NULL,0),"queue own user APC for immediate wait observation");
  LARGE_INTEGER timeout={.QuadPart=queued?-50000000:0};
  KEVENT kick;KeInitializeEvent(&kick,NotificationEvent,FALSE);
  if(variant==0)KeSetEvent(&kick,0,TRUE);
  NTSTATUS result=KeWaitForMultipleObjects(count,objects,(WAIT_TYPE)type,Executive,UserMode,TRUE,&timeout,c.blocks);
  if(helper){LARGE_INTEGER done={.QuadPart=-50000000};regression_require(NtWaitForSingleObject(helper,FALSE,&done)==0,"join APC issuer");NtClose(helper);}
  tap_comment("apc variant=%lu type=%lu count=%lu null=%u ret=%08lx kernel=%lu normal=%lu order=%lu irql=%lu,%lu nested=%lu queued=%lu",
   variant,type,count,nullblocks,(ULONG)result,c.kernel_calls,c.normal_calls,c.order,c.kernel_irql,c.normal_irql,c.nested_ok,c.queued);
  if(c.blocks){log_blocks("apc-kernel",type,variant,c.kernel,original.blocks,objects);log_blocks("apc-normal",type,variant,c.normal,original.blocks,objects);}
  regression_check(result==STATUS_USER_APC && c.kernel_calls==1 && c.normal_calls==1 && (!queued||c.queued),"alertable wait delivers one user APC after immediate or actual queued wait");
  regression_check(c.order==12 && c.kernel_irql==PASSIVE_LEVEL && c.normal_irql==PASSIVE_LEVEL && KeGetCurrentIrql()==PASSIVE_LEVEL,"user APC kernel and normal routines retain exact order and IRQL");
  regression_check(c.nested_ok,"user APC callback can reenter an independent wait");
  int exact=1;
  if(c.blocks)for(ULONG i=0;i<count;i++)if(c.kernel[i].Thread!=KeGetCurrentThread() || c.normal[i].Thread!=KeGetCurrentThread() || c.kernel[i].Object!=objects[i] || c.normal[i].Object!=objects[i] || c.kernel[i].WaitType!=(SHORT)type || c.normal[i].WaitType!=(SHORT)type || c.kernel[i].WaitKey!=(SHORT)i || c.normal[i].WaitKey!=(SHORT)i)exact=0;
  regression_check(exact,"both user APC routines observe public thread object type and index fields");
  regression_check(!memcmp(g.pre,original.pre,sizeof(g.pre)) && !memcmp(g.post,original.post,sizeof(g.post)),"APC wait preserves guards");
 }
}

int main(void) {
 regression_begin();PETHREAD self=NULL;
 regression_require(ObReferenceObjectByHandle((HANDLE)-2,&PsThreadObjectType,(PVOID *)&self)==0,"reference current thread");
 for(ULONG next=0;next<2;next++)for(ULONG alert=0;alert<2;alert++)
 for(ULONG sync=0;sync<2;sync++)for(ULONG type=0;type<2;type++)for(ULONG mask=0;mask<4;mask++) {
  KEVENT events[2],kick;PVOID objects[]={&events[0],&events[1]};
  struct {ULONG pre[4];KWAIT_BLOCK blocks[2];ULONG post[4];} g,original;
  memset(&g,0xa5,sizeof(g));original=g;
  KeInitializeEvent(&events[0],sync?SynchronizationEvent:NotificationEvent,(mask&1)!=0);
  KeInitializeEvent(&events[1],sync?SynchronizationEvent:NotificationEvent,(mask&2)!=0);
  KeInitializeEvent(&kick,NotificationEvent,FALSE);
  KeTestAlertThread(KernelMode);
  if(alert)KeAlertThread(&self->Tcb,KernelMode);
  LARGE_INTEGER zero={.QuadPart=0};
  if(next)KeSetEvent(&kick,0,TRUE);
  NTSTATUS result=KeWaitForMultipleObjects(2,objects,(WAIT_TYPE)type,Executive,KernelMode,alert,&zero,g.blocks);
  ULONG alert_left=KeTestAlertThread(KernelMode);
  ULONG changed=memcmp(g.blocks,original.blocks,sizeof(g.blocks))!=0;
  int guards=memcmp(g.pre,original.pre,sizeof(g.pre))==0 && memcmp(g.post,original.post,sizeof(g.post))==0;
  NTSTATUS expected=type==WaitAny && mask ? ((mask&1)?0:1) : type==WaitAll && mask==3 ? 0 : alert ? (NTSTATUS)0x101:STATUS_TIMEOUT;
  tap_comment("matrix n=%lu a=%lu s=%lu t=%lu mask=%lu ret=%08lx changed=%lu left=%lu signals=%ld,%ld",
    next,alert,sync,type,mask,(ULONG)result,changed,alert_left,events[0].Header.SignalState,events[1].Header.SignalState);
  regression_check(result==expected,"wait matrix returns exact object alert or timeout status");
  regression_check(guards && objects[0]==&events[0] && objects[1]==&events[1],"wait matrix preserves array and block guards");
  ULONG prefix=type==WaitAny && (ULONG)result<2 ? (ULONG)result : 2;
  int bytes=1;
  for(ULONG i=0;i<2;i++) {
   if(i>=prefix){if(memcmp(&g.blocks[i],&original.blocks[i],sizeof(KWAIT_BLOCK)))bytes=0;continue;}
   PKWAIT_BLOCK expected_next=(type==WaitAll && result==0)?&g.blocks[(i+1)%2]:&g.blocks[i+1];
   if(g.blocks[i].Thread!=KeGetCurrentThread() || g.blocks[i].Object!=objects[i] ||
      g.blocks[i].WaitType!=(SHORT)type || g.blocks[i].WaitKey!=(SHORT)i || g.blocks[i].NextWaitBlock!=expected_next ||
      memcmp(&g.blocks[i].WaitListEntry,&original.blocks[i].WaitListEntry,sizeof(LIST_ENTRY)))bytes=0;
  }
  regression_check(bytes,"public wait blocks preserve exact unvisited suffix and initialized prefix fields");
  if(changed)tap_comment("blocks th=%p,%p obj=%p,%p next=%p,%p type=%04x,%04x",
   g.blocks[0].Thread,g.blocks[1].Thread,g.blocks[0].Object,g.blocks[1].Object,g.blocks[0].NextWaitBlock,g.blocks[1].NextWaitBlock,
   (USHORT)g.blocks[0].WaitType,(USHORT)g.blocks[1].WaitType);
 }
 abandoned_oracle();apc_oracle(self);
 ObfDereferenceObject(self);regression_finish();
}
