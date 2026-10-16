/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "native_adapter_host_platform.h"
#include "native_adapter.h"
#include "native_driver.h"
#include "cache_property.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <sched.h>
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"%s:%d %s\n",__func__,__LINE__,#x); return 0; } } while(0)
#define MUST(x) do { if (!(x)) abort(); } while(0)

static PDEVICE_OBJECT created_device;
static PIRP active_child;
static PIRP pending_children[16];
static unsigned pending_child_count;
static unsigned lower_calls, cancel_calls, forward_calls;
static unsigned property_calls,free_irps,free_mdls,detaches,deletes;
static int fail_pool,fail_symbolic_link;
static int pool_fail_call=-1,irp_fail_call=-1,mdl_fail_call=-1;
static unsigned pool_calls,irp_calls,mdl_calls,pool_live;
static unsigned invalid_irp_frees,invalid_mdl_frees;
static int poison_pool,cancel_during_prepare,cancel_during_submit;
static PIRP cancel_parent;
static void *live_irps[128],*live_mdls[128];
static uint8_t opcodes[64],functions[64];
static int lower_pending;
static NTSTATUS sync_command_status;
static uint32_t read_capacity_last=15,read_capacity_sector=2048;
static int freeze_next,release_failure,next_sense_key,next_sense_asc,next_sense_descriptor;
static uint8_t cache_query_descriptor[28];
static nx_lcq_state host_lower_cache;
const nx_lcq_state *NxNativeHostCacheState(PDEVICE_OBJECT lower)
{ (void)lower; return &host_lower_cache; }
static int lower_started=1;
static unsigned pool_allocations,irp_allocations,mdl_allocations;
static int revoke_cache_during_submit;
static PDEVICE_OBJECT completion_reentry_device;
static PIRP completion_reentry_parent;
static NTSTATUS completion_reentry_status;
static void publish_host_cache_from_descriptor(void);

static void remember(void **live,void *pointer){for(unsigned i=0;i<128;++i)if(!live[i]){live[i]=pointer;return;}abort();}
static int forget(void **live,void *pointer){for(unsigned i=0;i<128;++i)if(live[i]==pointer){live[i]=NULL;return 1;}return 0;}
static unsigned live_count(void **live){unsigned count=0;for(unsigned i=0;i<128;++i)count+=live[i]!=NULL;return count;}
static void cancel_now(void)
{
    PDRIVER_CANCEL routine;
    MUST(cancel_parent&&cancel_parent->CancelRoutine);
    routine=cancel_parent->CancelRoutine;cancel_parent->CancelRoutine=NULL;
    cancel_parent->Cancel=TRUE;cancel_parent->CancelIrql=0;
    routine(created_device,cancel_parent);
}
VOID IoReuseIrp(PIRP i,NTSTATUS s){if(cancel_during_prepare){cancel_during_prepare=0;cancel_now();}int8_t n=i->StackCount;PIO_STACK_LOCATION base=i->Tail.Overlay.CurrentStackLocation-n;memset(i,0,sizeof(*i));i->StackCount=n;i->CurrentLocation=n+1;i->Tail.Overlay.CurrentStackLocation=base+n;i->IoStatus.Status=s;}
PIRP IoAllocateIrp(CCHAR n,BOOLEAN q){(void)q;++irp_allocations;unsigned call=irp_calls++;if((int)call==irp_fail_call)return NULL;size_t z=sizeof(IRP)+(size_t)n*sizeof(IO_STACK_LOCATION);PIRP i=calloc(1,z);if(i){remember(live_irps,i);i->StackCount=n;i->CurrentLocation=n+1;i->Tail.Overlay.CurrentStackLocation=(PIO_STACK_LOCATION)(i+1)+n;}return i;}
VOID IoFreeIrp(PIRP i){if(!forget(live_irps,i)){++invalid_irp_frees;return;}++free_irps;free(i);}

VOID FASTCALL IofCompleteRequest(PIRP i,CCHAR b){(void)b;MUST(!i->host_completed);i->host_completed=1;
    if(completion_reentry_parent&&i!=completion_reentry_parent){PIRP parent=completion_reentry_parent;
        completion_reentry_parent=NULL;
        completion_reentry_status=NxNativeDispatchReadWrite(completion_reentry_device,parent);}}
VOID IoMarkIrpPending(PIRP i){i->host_pending=1;}
VOID KeInitializeEvent(PKEVENT event,int type,BOOLEAN state){(void)type;__atomic_store_n(&event->signaled,state,__ATOMIC_RELEASE);}
LONG KeSetEvent(PKEVENT event,LONG increment,BOOLEAN wait){(void)increment;(void)wait;return (LONG)__atomic_exchange_n(&event->signaled,1,__ATOMIC_ACQ_REL);}
NTSTATUS KeWaitForSingleObject(PVOID object,int reason,int mode,BOOLEAN alert,PVOID timeout)
{(void)reason;(void)mode;(void)alert;(void)timeout;while(!__atomic_load_n(&((PKEVENT)object)->signaled,__ATOMIC_ACQUIRE))sched_yield();return STATUS_SUCCESS;}
VOID IoAcquireCancelSpinLock(KIRQL *q){*q=0;}
VOID IoReleaseCancelSpinLock(KIRQL q){(void)q;}
VOID KeInitializeSpinLock(PKSPIN_LOCK l){*l=0;}
KIRQL FASTCALL KfAcquireSpinLock(PKSPIN_LOCK l){while(__atomic_exchange_n(l,1,__ATOMIC_ACQUIRE))sched_yield();return 0;}
VOID FASTCALL KfReleaseSpinLock(PKSPIN_LOCK l,KIRQL q){(void)q;MUST(__atomic_load_n(l,__ATOMIC_RELAXED));__atomic_store_n(l,0,__ATOMIC_RELEASE);}
PVOID ExAllocatePool(int t,size_t n){(void)t;++pool_allocations;unsigned call=pool_calls++;if(fail_pool){--fail_pool;return NULL;}if((int)call==pool_fail_call)return NULL;PVOID p=malloc(n);if(p){memset(p,poison_pool?0xa5:0,n);++pool_live;}return p;}
VOID ExFreePool(PVOID p){if(p){MUST(pool_live);--pool_live;}free(p);}
PMDL IoAllocateMdl(PVOID p,ULONG n,BOOLEAN s,BOOLEAN q,PIRP i){(void)s;(void)q;(void)i;++mdl_allocations;unsigned call=mdl_calls++;if((int)call==mdl_fail_call)return NULL;PMDL m=calloc(1,sizeof(*m)+2*sizeof(ULONG));if(m){remember(live_mdls,m);uintptr_t a=(uintptr_t)p;m->StartVa=(PVOID)(a&~(uintptr_t)4095);m->ByteOffset=(ULONG)(a&4095);m->ByteCount=n;m->Size=sizeof(*m)+2*sizeof(ULONG);}return m;}

VOID MmBuildMdlForNonPagedPool(PMDL m){(void)m;}
VOID IoFreeMdl(PMDL m){if(!forget(live_mdls,m)){++invalid_mdl_frees;return;}++free_mdls;free(m);}
NTSTATUS IoCreateDevice(PDRIVER_OBJECT d,ULONG n,PUNICODE_STRING u,DEVICE_TYPE t,ULONG c,BOOLEAN x,PDEVICE_OBJECT *o){(void)u;(void)x;PDEVICE_OBJECT v=calloc(1,sizeof(*v)+n);if(!v)return STATUS_INSUFFICIENT_RESOURCES;v->DriverObject=d;v->DeviceExtension=(uint8_t *)v+sizeof(*v);v->DeviceType=(UCHAR)t;v->Characteristics=c;*o=created_device=v;return 0;}
PDEVICE_OBJECT IoAttachDeviceToDeviceStack(PDEVICE_OBJECT a,PDEVICE_OBJECT b){a->AttachedDevice=b;a->StackSize=b->StackSize+1;return b;}
VOID IoDetachDevice(PDEVICE_OBJECT d){(void)d;++detaches;}
VOID IoDeleteDevice(PDEVICE_OBJECT d){++deletes;free(d);}
NTSTATUS IoCreateSymbolicLink(PUNICODE_STRING a,PUNICODE_STRING b){(void)a;(void)b;return fail_symbolic_link?STATUS_IO_DEVICE_ERROR:0;}
NTSTATUS IoDeleteSymbolicLink(PUNICODE_STRING a){(void)a;return 0;}
NTSTATUS ZwCreateDirectoryObject(HANDLE *h,ULONG a,POBJECT_ATTRIBUTES o){(void)a;(void)o;*h=(HANDLE)(uintptr_t)1;return STATUS_SUCCESS;}
NTSTATUS ZwMakeTemporaryObject(HANDLE h){(void)h;return STATUS_SUCCESS;}
NTSTATUS ZwClose(HANDLE h){(void)h;return STATUS_SUCCESS;}

static NTSTATUS complete_specific_child(PIRP child,NTSTATUS status,ULONG bytes,UCHAR srb_status)
{
    MUST(child);PIO_STACK_LOCATION s=child->Tail.Overlay.CurrentStackLocation-1;
    child->IoStatus.Status=status;child->IoStatus.Information=bytes;s->Parameters.Scsi.Srb->SrbStatus=srb_status;
    if(active_child==child)active_child=NULL;
    for(unsigned index=0;index<pending_child_count;++index) if(pending_children[index]==child) {
        for(unsigned tail=index+1;tail<pending_child_count;++tail)
            pending_children[tail-1]=pending_children[tail];
        pending_children[--pending_child_count]=NULL;break;
    }
    return s->CompletionRoutine(created_device,child,s->Context);
}
static NTSTATUS complete_child(NTSTATUS status,ULONG bytes,UCHAR srb_status)
{
    return complete_specific_child(active_child,status,bytes,srb_status);
}
NTSTATUS FASTCALL IofCallDriver(PDEVICE_OBJECT lower,PIRP child)
{
    PIO_STACK_LOCATION s=child->Tail.Overlay.CurrentStackLocation-1;
    if(s->MajorFunction==IRP_MJ_PNP) {
        (void)lower;++forward_calls;
        if(s->MinorFunction==IRP_MN_START_DEVICE) {
            lower_started=1;
            publish_host_cache_from_descriptor();
        }
        else if(s->MinorFunction==IRP_MN_STOP_DEVICE ||
                s->MinorFunction==IRP_MN_SURPRISE_REMOVAL ||
                s->MinorFunction==IRP_MN_REMOVE_DEVICE) {
            lower_started=0;
            nx_lcq_revoke(&host_lower_cache);
        }
        child->IoStatus.Status=STATUS_SUCCESS;
        if(s->CompletionRoutine) {
            MUST(s->CompletionRoutine(created_device,child,s->Context)==STATUS_MORE_PROCESSING_REQUIRED);
        } else IofCompleteRequest(child,IO_NO_INCREMENT);
        return STATUS_SUCCESS;
    }
    if(child->StackCount<=1){(void)lower;
        if(s->Parameters.DeviceIoControl.IoControlCode==IOCTL_STORAGE_QUERY_PROPERTY)
            ++property_calls;
        else ++forward_calls;
        child->IoStatus.Status=STATUS_SUCCESS;
        IofCompleteRequest(child,IO_NO_INCREMENT);return STATUS_SUCCESS;}
    (void)lower;
    MUST(lower_calls<64 && s->Parameters.Scsi.Srb);PSCSI_REQUEST_BLOCK srb=s->Parameters.Scsi.Srb;
    opcodes[lower_calls]=srb->Cdb[0];functions[lower_calls]=srb->Function;++lower_calls;
    if(revoke_cache_during_submit) {
        revoke_cache_during_submit=0;
        nx_lcq_revoke(&host_lower_cache);
    }
    active_child=child;
    if(cancel_during_submit){cancel_during_submit=0;cancel_now();}

    if(s->Parameters.Scsi.Srb->Cdb[0]==0x25){uint8_t *b=s->Parameters.Scsi.Srb->DataBuffer;memset(b,0,8);
        b[0]=(uint8_t)(read_capacity_last>>24);b[1]=(uint8_t)(read_capacity_last>>16);
        b[2]=(uint8_t)(read_capacity_last>>8);b[3]=(uint8_t)read_capacity_last;
        b[4]=(uint8_t)(read_capacity_sector>>24);b[5]=(uint8_t)(read_capacity_sector>>16);
        b[6]=(uint8_t)(read_capacity_sector>>8);b[7]=(uint8_t)read_capacity_sector;}
    if(s->Parameters.Scsi.Srb->Cdb[0]==0x43){uint8_t *b=s->Parameters.Scsi.Srb->DataBuffer;memset(b,0,804);b[1]=10;b[2]=1;b[3]=1;b[5]=0x14;}
    if(lower_pending){active_child=child;MUST(pending_child_count<16);
        pending_children[pending_child_count++]=child;return STATUS_PENDING;}
    ULONG bytes=srb->Cdb[0]==0x43 ? 12:srb->DataTransferLength;
    NTSTATUS status=srb->Cdb[0]==0x35 ? sync_command_status:STATUS_SUCCESS;
    UCHAR srb_status=NT_SUCCESS(status)?1:2;
    if(next_sense_key){uint8_t *sense=srb->SenseInfoBuffer;memset(sense,0,18);
        if(next_sense_descriptor){sense[0]=0x72;sense[1]=(uint8_t)next_sense_key;
            sense[2]=(uint8_t)next_sense_asc;srb->SenseInfoBufferLength=8;}
        else {sense[0]=0x70;sense[2]=(uint8_t)next_sense_key;sense[7]=10;
            sense[12]=(uint8_t)next_sense_asc;srb->SenseInfoBufferLength=18;}
        next_sense_key=next_sense_asc=next_sense_descriptor=0;
        status=STATUS_IO_DEVICE_ERROR;srb_status=0x84;bytes=0;}
    else if(srb->Function==4&&release_failure){status=STATUS_IO_DEVICE_ERROR;srb_status=4;bytes=0;}
    else if(srb->Function==0&&freeze_next){freeze_next=0;status=STATUS_IO_DEVICE_ERROR;srb_status=0x44;bytes=0;}
    MUST(complete_specific_child(child,status,bytes,srb_status)==STATUS_MORE_PROCESSING_REQUIRED);

    return STATUS_SUCCESS;
}
BOOLEAN IoCancelIrp(PIRP child){++cancel_calls;MUST(complete_specific_child(child,STATUS_CANCELLED,0,2)==STATUS_MORE_PROCESSING_REQUIRED);return TRUE;}

typedef struct parent_fixture { IRP irp; IO_STACK_LOCATION stack; MDL mdl; uint32_t pfns[34]; } parent_fixture;
typedef struct control_fixture { IRP irp; IO_STACK_LOCATION stack; uint8_t output[804]; } control_fixture;
static void init_parent(parent_fixture *p,UCHAR major,ULONG bytes)
{
    memset(p,0,sizeof(*p));p->irp.StackCount=1;p->irp.CurrentLocation=1;p->irp.Tail.Overlay.CurrentStackLocation=&p->stack;
    p->stack.MajorFunction=major;p->stack.Parameters.Read.Length=bytes;p->stack.Parameters.Read.ByteOffset=0;
    p->mdl.Size=(int16_t)(sizeof(MDL)+sizeof(p->pfns));p->mdl.StartVa=0;p->mdl.ByteCount=bytes;p->irp.MdlAddress=&p->mdl;
}
static void init_control(control_fixture *p,ULONG code,ULONG bytes)
{
    memset(p,0,sizeof(*p));memset(p->output,0xa5,sizeof(p->output));
    p->irp.StackCount=1;p->irp.CurrentLocation=1;p->irp.Tail.Overlay.CurrentStackLocation=&p->stack;
    p->irp.AssociatedIrp.SystemBuffer=p->output;p->stack.MajorFunction=IRP_MJ_DEVICE_CONTROL;
    p->stack.Parameters.DeviceIoControl.IoControlCode=code;
    p->stack.Parameters.DeviceIoControl.OutputBufferLength=bytes;
}
typedef struct pnp_thread {
    PDRIVER_DISPATCH dispatch;
    PDEVICE_OBJECT device;
    IRP irp;
    IO_STACK_LOCATION stack[3];
    NTSTATUS status;
    unsigned entered,returned;
} pnp_thread;
static void init_pnp(pnp_thread *thread,PDRIVER_DISPATCH dispatch,
                     PDEVICE_OBJECT device,UCHAR minor)
{
    memset(thread,0,sizeof(*thread));thread->dispatch=dispatch;thread->device=device;
    thread->irp.StackCount=1;thread->irp.CurrentLocation=1;
    thread->irp.Tail.Overlay.CurrentStackLocation=&thread->stack[1];
    thread->stack[1].MajorFunction=IRP_MJ_PNP;thread->stack[1].MinorFunction=minor;
}
static void *run_pnp(void *context)
{
    pnp_thread *thread=context;
    __atomic_store_n(&thread->entered,1,__ATOMIC_RELEASE);
    thread->status=thread->dispatch(thread->device,&thread->irp);
    __atomic_store_n(&thread->returned,1,__ATOMIC_RELEASE);
    return NULL;
}
static NTSTATUS dispatch_pnp(PDRIVER_DISPATCH dispatch,PDEVICE_OBJECT device,UCHAR minor)
{
    pnp_thread thread;init_pnp(&thread,dispatch,device,minor);run_pnp(&thread);
    MUST(thread.irp.host_completed);return thread.status;

}
static PDEVICE_OBJECT make_device(ULONG slots)
{
    static DRIVER_OBJECT driver;static DEVICE_OBJECT lower;memset(&driver,0,sizeof(driver));memset(&lower,0,sizeof(lower));lower.StackSize=2;
    nx_config c={512,4096,4096,2,0,256,1u<<20,0,NX_CACHE_ENABLED};
    NX_NATIVE_DEVICE_INIT init={0};init.DeviceType=7;init.Config=c;init.SlotCount=slots;
    PDEVICE_OBJECT out=NULL;MUST(NxNativeCreateClassDevice(&driver,&lower,&init,&out)==STATUS_SUCCESS);return out;
}
static PDEVICE_OBJECT make_optical(void)
{
    static DRIVER_OBJECT driver;static DEVICE_OBJECT lower;memset(&driver,0,sizeof(driver));memset(&lower,0,sizeof(lower));lower.StackSize=2;
    nx_config c={2048,4096,0x20000,33,0,0xffff,0,1,NX_CACHE_DISABLED};NX_NATIVE_DEVICE_INIT init={0};init.DeviceType=2;init.Config=c;init.SlotCount=2;
    PDEVICE_OBJECT out=NULL;MUST(NxNativeCreateClassDevice(&driver,&lower,&init,&out)==0);return out;
}
static PDEVICE_OBJECT make_unknown_disk(void)
{
    static DRIVER_OBJECT driver;static DEVICE_OBJECT lower;memset(&driver,0,sizeof(driver));memset(&lower,0,sizeof(lower));lower.StackSize=2;
    nx_config c={512,4096,0x20000,33,0,256,0,0,NX_CACHE_UNQUALIFIED};NX_NATIVE_DEVICE_INIT init={0};init.DeviceType=7;init.Config=c;init.SlotCount=2;
    PDEVICE_OBJECT out=NULL;MUST(NxNativeCreateClassDevice(&driver,&lower,&init,&out)==0);return out;
}
static void reset_allocation_faults(void)
{
    MUST(!pool_live&&!live_count(live_irps)&&!live_count(live_mdls));
    fail_pool=0;pool_fail_call=irp_fail_call=mdl_fail_call=-1;
    pool_calls=irp_calls=mdl_calls=0;free_irps=free_mdls=0;
    invalid_irp_frees=invalid_mdl_frees=0;poison_pool=1;
}
static NTSTATUS initialize_for_failure(ULONG slots)
{
    static DEVICE_OBJECT lower;
    _Alignas(max_align_t) unsigned char storage[4096];
    nx_config config={512,4096,4096,2,0,256,1u<<20,0,NX_CACHE_ENABLED};
    memset(&lower,0,sizeof(lower));lower.StackSize=2;memset(storage,0xa5,sizeof(storage));
    return NxNativeAdapterInitialize((NX_NATIVE_ADAPTER *)(void *)storage,&lower,slots,&config);
}
/* Break: partial initialization frees poisoned pointers from envelope slots it never initialized. */
static int initialization_cleans_only_constructed_envelopes(void)
{
    enum { SLOTS=4 };
    for(int failure=0;failure<2;++failure) {
        NTSTATUS status;unsigned invalid_irps,invalid_mdls;
        reset_allocation_faults();pool_fail_call=failure;
        status=initialize_for_failure(SLOTS);invalid_irps=invalid_irp_frees;invalid_mdls=invalid_mdl_frees;
        pool_fail_call=-1;poison_pool=0;
        CHECK(status==STATUS_INSUFFICIENT_RESOURCES);
        CHECK(!pool_live&&!live_count(live_irps)&&!live_count(live_mdls));
        CHECK(!invalid_irps&&!invalid_mdls);
    }
    for(int failure=0;failure<SLOTS;++failure) {
        reset_allocation_faults();irp_fail_call=failure;
        CHECK(initialize_for_failure(SLOTS)==STATUS_INSUFFICIENT_RESOURCES);
        CHECK(free_irps==(unsigned)failure&&free_mdls==(unsigned)failure+1u);
        CHECK(!pool_live&&!live_count(live_irps)&&!live_count(live_mdls));
        CHECK(!invalid_irp_frees&&!invalid_mdl_frees);
    }
    for(int failure=0;failure<SLOTS;++failure) {
        reset_allocation_faults();mdl_fail_call=failure;
        CHECK(initialize_for_failure(SLOTS)==STATUS_INSUFFICIENT_RESOURCES);
        CHECK(free_irps==(unsigned)failure+1u&&free_mdls==(unsigned)failure);
        CHECK(!pool_live&&!live_count(live_irps)&&!live_count(live_mdls));
        CHECK(!invalid_irp_frees&&!invalid_mdl_frees);
    }
    poison_pool=0;return 1;
}
static int sync_read_and_write_through(void)
{
    PDEVICE_OBJECT d=make_device(2);parent_fixture p;lower_calls=0;lower_pending=0;init_parent(&p,IRP_MJ_READ,4096);
    CHECK(NxNativeDispatchReadWrite(d,&p.irp)==STATUS_SUCCESS);CHECK(p.irp.host_completed==1&&p.irp.IoStatus.Status==0&&p.irp.IoStatus.Information==4096);
    CHECK(lower_calls==1&&opcodes[0]==0x28);
    parent_fixture w;init_parent(&w,IRP_MJ_WRITE,4096);w.stack.Flags=SL_WRITE_THROUGH;
    CHECK(NxNativeDispatchReadWrite(d,&w.irp)==STATUS_SUCCESS);CHECK(w.irp.host_completed==1&&lower_calls==3&&opcodes[1]==0x2a&&opcodes[2]==0x35);
    return 1;
}
static int pending_cancel_and_pool_bound(void)
{
    PDEVICE_OBJECT d=make_device(1);parent_fixture a,b;lower_calls=cancel_calls=0;lower_pending=1;init_parent(&a,IRP_MJ_READ,4096);
    CHECK(NxNativeDispatchReadWrite(d,&a.irp)==STATUS_PENDING);CHECK(a.irp.host_pending&&!a.irp.host_completed&&a.irp.CancelRoutine);
    init_parent(&b,IRP_MJ_READ,4096);CHECK(NxNativeDispatchReadWrite(d,&b.irp)==STATUS_INSUFFICIENT_RESOURCES);CHECK(b.irp.host_completed&&b.irp.IoStatus.Status==STATUS_INSUFFICIENT_RESOURCES);
    NxNativeSealClassDevice(d);
    CHECK(cancel_calls==0);a.irp.Cancel=1;a.irp.CancelIrql=0;a.irp.CancelRoutine(d,&a.irp);
    CHECK(cancel_calls==1&&a.irp.host_completed==1&&a.irp.IoStatus.Status==STATUS_CANCELLED);
    return 1;
}
/* Completing A may synchronously dispatch B after A's core slot is free while
 * A's adapter envelope is still owned by its outer dispatch.  The command
 * lease must keep B's reused core slot paired with B's distinct envelope. */
static int completion_reentry_keeps_envelope_lease(void)
{
    PDEVICE_OBJECT d=make_device(2);parent_fixture a,b;
    lower_calls=0;lower_pending=0;init_parent(&a,IRP_MJ_READ,512);init_parent(&b,IRP_MJ_READ,512);
    completion_reentry_device=d;completion_reentry_parent=&b.irp;
    completion_reentry_status=STATUS_IO_DEVICE_ERROR;
    CHECK(NxNativeDispatchReadWrite(d,&a.irp)==STATUS_SUCCESS);
    CHECK(!completion_reentry_parent&&completion_reentry_status==STATUS_PENDING);
    CHECK(a.irp.host_completed&&b.irp.host_completed&&lower_calls==2);
    CHECK(a.irp.IoStatus.Status==STATUS_SUCCESS&&b.irp.IoStatus.Status==STATUS_SUCCESS);
    completion_reentry_device=NULL;return 1;
}
/* Break: a cancelled parent reaches lower transport before commit, or committed transport is not drained once. */
static int cancellation_respects_transport_commit(void)
{
    static const struct { UCHAR major; int delayed; } precancel[] = {
        {IRP_MJ_READ,0},{IRP_MJ_WRITE,0},{IRP_MJ_READ,1},{IRP_MJ_WRITE,1}
    };
    PDEVICE_OBJECT d=make_device(1);parent_fixture parent,before,after;size_t index;
    for(index=0;index<sizeof(precancel)/sizeof(precancel[0]);++index) {
        lower_pending=precancel[index].delayed;lower_calls=cancel_calls=0;
        init_parent(&parent,precancel[index].major,4096);parent.irp.Cancel=TRUE;
        CHECK(!parent.stack.Flags);
        CHECK(NxNativeDispatchReadWrite(d,&parent.irp)==STATUS_CANCELLED);
        CHECK(parent.irp.host_completed==1&&parent.irp.IoStatus.Status==STATUS_CANCELLED);
        CHECK(parent.irp.IoStatus.Information==0&&!lower_calls&&!cancel_calls);
    }

    init_parent(&before,IRP_MJ_READ,4096);cancel_parent=&before.irp;cancel_during_prepare=1;
    CHECK(NxNativeDispatchReadWrite(d,&before.irp)==STATUS_CANCELLED);
    CHECK(before.irp.host_completed&&before.irp.IoStatus.Status==STATUS_CANCELLED);
    CHECK(!lower_calls&&!cancel_calls&&!cancel_during_prepare);

    init_parent(&after,IRP_MJ_READ,4096);cancel_parent=&after.irp;cancel_during_submit=1;
    CHECK(NxNativeDispatchReadWrite(d,&after.irp)==STATUS_PENDING);
    CHECK(after.irp.host_completed&&after.irp.IoStatus.Status==STATUS_CANCELLED);
    CHECK(lower_calls==1&&cancel_calls==1&&!cancel_during_submit);
    cancel_parent=NULL;lower_pending=0;return 1;
}
static uint32_t word(const uint8_t *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static uint64_t dword(const uint8_t *p){return word(p)|((uint64_t)word(p+4)<<32);}
static int frozen_control_recovery(ULONG code,ULONG output,UCHAR opcode)
{
    PDEVICE_OBJECT d=make_optical();control_fixture c;parent_fixture read;
    init_control(&c,code,output);lower_calls=0;lower_pending=0;release_failure=0;freeze_next=1;
    CHECK(NxNativeDispatchControl(d,&c.irp)==STATUS_PENDING);
    CHECK(c.irp.host_pending&&c.irp.host_completed==1&&c.irp.IoStatus.Status==STATUS_IO_DEVICE_ERROR);
    CHECK(lower_calls==2&&functions[0]==0&&opcodes[0]==opcode&&functions[1]==4);
    init_parent(&read,IRP_MJ_READ,2048);
    CHECK(NxNativeDispatchReadWrite(d,&read.irp)==STATUS_SUCCESS);
    CHECK(read.irp.host_completed==1&&read.irp.IoStatus.Status==STATUS_SUCCESS&&lower_calls==3);
    return 1;
}
static int read_capacity_releases_frozen_queue(void)
{ return frozen_control_recovery(IOCTL_CDROM_GET_DRIVE_GEOMETRY,24,0x25); }
static int read_toc_releases_frozen_queue(void)
{ return frozen_control_recovery(IOCTL_CDROM_READ_TOC,804,0x43); }
static int check_verify_releases_frozen_queue(void)
{ return frozen_control_recovery(IOCTL_CDROM_CHECK_VERIFY,4,0); }
static int failed_control_recovery_quarantines_adapter(void)
{
    PDEVICE_OBJECT d=make_optical();control_fixture c;parent_fixture read;
    init_control(&c,IOCTL_CDROM_GET_DRIVE_GEOMETRY,24);lower_calls=0;lower_pending=0;
    release_failure=1;freeze_next=1;CHECK(NxNativeDispatchControl(d,&c.irp)==STATUS_PENDING);
    release_failure=0;CHECK(c.irp.host_completed==1&&c.irp.IoStatus.Status==STATUS_IO_DEVICE_ERROR);
    CHECK(lower_calls==2&&functions[1]==4);
    init_parent(&read,IRP_MJ_READ,2048);CHECK(NxNativeDispatchReadWrite(d,&read.irp)==STATUS_IO_DEVICE_ERROR);
    CHECK(read.irp.host_completed==1&&read.irp.IoStatus.Status==STATUS_IO_DEVICE_ERROR&&lower_calls==2);
    return 1;
}
/* Break: a failed control release quarantines admission but an already-active
 * multi-chunk request retires its first chunk and submits the next one. */
static int failed_control_recovery_drains_active_core(void)
{
    PDEVICE_OBJECT d=make_optical();parent_fixture read;control_fixture verify;
    PIRP data_child,control_child;
    lower_pending=1;lower_calls=cancel_calls=0;
    init_parent(&read,IRP_MJ_READ,0x21000);
    CHECK(NxNativeDispatchReadWrite(d,&read.irp)==STATUS_PENDING);
    data_child=active_child;CHECK(data_child&&lower_calls==1&&opcodes[0]==0x28);

    init_control(&verify,IOCTL_CDROM_CHECK_VERIFY,4);
    CHECK(NxNativeDispatchControl(d,&verify.irp)==STATUS_PENDING);
    control_child=active_child;CHECK(control_child&&control_child!=data_child&&lower_calls==2);
    CHECK(complete_specific_child(control_child,STATUS_IO_DEVICE_ERROR,0,0x44)==STATUS_MORE_PROCESSING_REQUIRED);
    CHECK(lower_calls==3&&functions[2]==4);
    CHECK(complete_specific_child(control_child,STATUS_IO_DEVICE_ERROR,0,4)==STATUS_MORE_PROCESSING_REQUIRED);
    CHECK(verify.irp.host_completed&&verify.irp.IoStatus.Status==STATUS_IO_DEVICE_ERROR);

    if(!read.irp.host_completed)
        CHECK(complete_specific_child(data_child,STATUS_SUCCESS,0x20000,1)==STATUS_MORE_PROCESSING_REQUIRED);
    CHECK(lower_calls==3);
    CHECK(cancel_calls==1&&read.irp.host_completed&&read.irp.IoStatus.Status==STATUS_IO_DEVICE_ERROR);
    lower_pending=0;return 1;
}
static int control_recovery_uses_preallocated_state(void)
{
    PDEVICE_OBJECT d=make_optical();control_fixture c;NTSTATUS status;
    init_control(&c,IOCTL_CDROM_READ_TOC,804);lower_calls=0;lower_pending=0;freeze_next=1;
    fail_pool=100;status=NxNativeDispatchControl(d,&c.irp);fail_pool=0;
    CHECK(status==STATUS_PENDING&&c.irp.host_completed==1&&c.irp.IoStatus.Status==STATUS_IO_DEVICE_ERROR);
    CHECK(lower_calls==2&&functions[1]==4);return 1;
}
static int query_geometry(PDEVICE_OBJECT d,control_fixture *c)
{
    init_control(c,IOCTL_CDROM_GET_DRIVE_GEOMETRY,24);
    return NxNativeDispatchControl(d,&c->irp)==STATUS_PENDING&&c->irp.host_completed&&
        c->irp.IoStatus.Status==STATUS_SUCCESS&&c->irp.IoStatus.Information==24;
}
static int query_verify(PDEVICE_OBJECT d,uint32_t *generation)
{
    control_fixture c;init_control(&c,IOCTL_CDROM_CHECK_VERIFY,4);
    if(NxNativeDispatchControl(d,&c.irp)!=STATUS_PENDING||!c.irp.host_completed||
       c.irp.IoStatus.Status!=STATUS_SUCCESS||c.irp.IoStatus.Information!=4)return 0;
    *generation=word(c.output);return 1;
}
static int verify_preserves_unchanged_generation(void)
{
    PDEVICE_OBJECT d=make_optical();control_fixture geometry;uint32_t first,second;
    lower_pending=0;lower_calls=0;read_capacity_last=15;read_capacity_sector=2048;
    CHECK(query_geometry(d,&geometry));CHECK(query_verify(d,&first));CHECK(query_verify(d,&second));
    CHECK(first==1&&second==first);return 1;
}
static int removal_invalidates_cached_capacity(void)
{
    PDEVICE_OBJECT d=make_optical();control_fixture geometry,remove,length;NTSTATUS dispatch;
    lower_pending=0;lower_calls=0;read_capacity_last=15;read_capacity_sector=2048;
    CHECK(query_geometry(d,&geometry));
    init_control(&remove,IOCTL_CDROM_CHECK_VERIFY,4);next_sense_key=2;next_sense_asc=0x3a;
    CHECK(NxNativeDispatchControl(d,&remove.irp)==STATUS_PENDING&&remove.irp.host_completed&&
          remove.irp.IoStatus.Status==STATUS_IO_DEVICE_ERROR);
    init_control(&length,IOCTL_DISK_GET_LENGTH_INFO,8);lower_pending=1;
    dispatch=NxNativeDispatchControl(d,&length.irp);
    {
        int queried=dispatch==STATUS_PENDING&&!length.irp.host_completed&&active_child!=NULL;
        lower_pending=0;if(active_child)CHECK(complete_child(STATUS_IO_DEVICE_ERROR,0,4)==STATUS_MORE_PROCESSING_REQUIRED);
        CHECK(queried&&length.irp.host_completed&&length.irp.IoStatus.Status==STATUS_IO_DEVICE_ERROR);
    }
    return 1;
}
static int new_media_advances_once_and_refreshes_capacity(void)
{
    PDEVICE_OBJECT d=make_optical();control_fixture a,remove,b,length;uint32_t generation_a,generation_b;
    lower_pending=0;lower_calls=0;read_capacity_last=15;read_capacity_sector=2048;
    CHECK(query_geometry(d,&a));CHECK(query_verify(d,&generation_a));
    init_control(&remove,IOCTL_CDROM_CHECK_VERIFY,4);next_sense_key=2;next_sense_asc=0x3a;
    CHECK(NxNativeDispatchControl(d,&remove.irp)==STATUS_PENDING&&remove.irp.host_completed);
    read_capacity_last=31;CHECK(query_geometry(d,&b));CHECK(query_verify(d,&generation_b));
    init_control(&length,IOCTL_DISK_GET_LENGTH_INFO,8);
    CHECK(NxNativeDispatchControl(d,&length.irp)==STATUS_SUCCESS&&dword(length.output)==65536);
    CHECK(generation_a==1&&generation_b==3);read_capacity_last=15;return 1;
}
static int repeated_unit_attention_counts_one_transition(void)
{
    PDEVICE_OBJECT d=make_optical();control_fixture geometry,change;uint32_t generation;
    lower_pending=0;read_capacity_last=15;read_capacity_sector=2048;
    CHECK(query_geometry(d,&geometry));
    for(unsigned attempt=0;attempt<2;++attempt) {
        init_control(&change,IOCTL_CDROM_CHECK_VERIFY,4);next_sense_key=6;next_sense_asc=0x28;
        CHECK(NxNativeDispatchControl(d,&change.irp)==STATUS_PENDING&&change.irp.host_completed&&
              change.irp.IoStatus.Status==STATUS_IO_DEVICE_ERROR);
    }
    CHECK(query_verify(d,&generation)&&generation==2);return 1;
}
static int repeated_no_media_counts_state_transitions_only(void)
{
    PDEVICE_OBJECT d=make_optical();control_fixture geometry,remove;uint32_t generation;
    lower_pending=0;read_capacity_last=15;read_capacity_sector=2048;
    CHECK(query_geometry(d,&geometry));
    for(unsigned attempt=0;attempt<2;++attempt) {
        init_control(&remove,IOCTL_CDROM_CHECK_VERIFY,4);next_sense_key=2;next_sense_asc=0x3a;
        next_sense_descriptor=attempt==1;
        CHECK(NxNativeDispatchControl(d,&remove.irp)==STATUS_PENDING&&remove.irp.host_completed&&
              remove.irp.IoStatus.Status==STATUS_IO_DEVICE_ERROR);
    }
    CHECK(query_verify(d,&generation)&&generation==3);return 1;
}
static int descriptor_no_media_invalidates_cached_capacity(void)
{
    PDEVICE_OBJECT d=make_optical();control_fixture geometry,remove,length;NTSTATUS dispatch;
    lower_pending=0;read_capacity_last=15;read_capacity_sector=2048;
    CHECK(query_geometry(d,&geometry));init_control(&remove,IOCTL_CDROM_CHECK_VERIFY,4);
    next_sense_key=2;next_sense_asc=0x3a;next_sense_descriptor=1;
    CHECK(NxNativeDispatchControl(d,&remove.irp)==STATUS_PENDING&&remove.irp.host_completed&&
          remove.irp.IoStatus.Status==STATUS_IO_DEVICE_ERROR);
    init_control(&length,IOCTL_DISK_GET_LENGTH_INFO,8);lower_pending=1;
    dispatch=NxNativeDispatchControl(d,&length.irp);
    {
        int queried=dispatch==STATUS_PENDING&&!length.irp.host_completed&&active_child!=NULL;
        lower_pending=0;if(active_child)CHECK(complete_child(STATUS_IO_DEVICE_ERROR,0,4)==STATUS_MORE_PROCESSING_REQUIRED);
        CHECK(queried&&length.irp.host_completed&&length.irp.IoStatus.Status==STATUS_IO_DEVICE_ERROR);
    }
    return 1;
}
static int reset_toc_invalidates_cached_capacity(void)
{
    PDEVICE_OBJECT d=make_optical();control_fixture geometry,toc,length;NTSTATUS dispatch;
    lower_pending=0;lower_calls=0;read_capacity_last=15;read_capacity_sector=2048;
    CHECK(query_geometry(d,&geometry));init_control(&toc,IOCTL_CDROM_READ_TOC,804);
    next_sense_key=6;next_sense_asc=0x29;
    CHECK(NxNativeDispatchControl(d,&toc.irp)==STATUS_PENDING&&toc.irp.host_completed&&
          toc.irp.IoStatus.Status==STATUS_IO_DEVICE_ERROR);
    init_control(&length,IOCTL_DISK_GET_LENGTH_INFO,8);lower_pending=1;
    dispatch=NxNativeDispatchControl(d,&length.irp);
    {
        int queried=dispatch==STATUS_PENDING&&!length.irp.host_completed&&active_child!=NULL;
        lower_pending=0;if(active_child)CHECK(complete_child(STATUS_IO_DEVICE_ERROR,0,4)==STATUS_MORE_PROCESSING_REQUIRED);
        CHECK(queried&&length.irp.host_completed&&length.irp.IoStatus.Status==STATUS_IO_DEVICE_ERROR);
    }
    return 1;
}
static int stale_capacity_cannot_overwrite_new_media(void)
{
    PDEVICE_OBJECT d=make_optical();control_fixture old_capacity,change,new_capacity,length;
    PIRP old_child;NTSTATUS old_completion;
    lower_calls=0;lower_pending=1;read_capacity_last=15;read_capacity_sector=2048;
    init_control(&old_capacity,IOCTL_CDROM_GET_DRIVE_GEOMETRY,24);
    CHECK(NxNativeDispatchControl(d,&old_capacity.irp)==STATUS_PENDING&&!old_capacity.irp.host_completed);
    old_child=active_child;lower_pending=0;init_control(&change,IOCTL_CDROM_CHECK_VERIFY,4);
    next_sense_key=6;next_sense_asc=0x28;
    CHECK(NxNativeDispatchControl(d,&change.irp)==STATUS_PENDING&&change.irp.host_completed&&
          change.irp.IoStatus.Status==STATUS_IO_DEVICE_ERROR);
    read_capacity_last=31;CHECK(query_geometry(d,&new_capacity));
    old_completion=complete_specific_child(old_child,STATUS_SUCCESS,8,1);
    CHECK(old_completion==STATUS_MORE_PROCESSING_REQUIRED&&old_capacity.irp.host_completed&&
          old_capacity.irp.IoStatus.Status==STATUS_DEVICE_NOT_READY);
    init_control(&length,IOCTL_DISK_GET_LENGTH_INFO,8);
    CHECK(NxNativeDispatchControl(d,&length.irp)==STATUS_SUCCESS&&dword(length.output)==65536);
    read_capacity_last=15;return 1;
}
static int geometry_reports_device_media_type(void)
{
    PDEVICE_OBJECT optical=make_optical();control_fixture cd,disk_geometry;
    PDEVICE_OBJECT disk;lower_pending=0;read_capacity_last=15;read_capacity_sector=2048;
    CHECK(query_geometry(optical,&cd));CHECK(word(cd.output+8)==RemovableMedia);
    disk=make_unknown_disk();read_capacity_last=31;read_capacity_sector=512;
    init_control(&disk_geometry,IOCTL_DISK_GET_DRIVE_GEOMETRY,24);
    CHECK(NxNativeDispatchControl(disk,&disk_geometry.irp)==STATUS_PENDING&&disk_geometry.irp.host_completed);
    CHECK(word(disk_geometry.output+8)==FixedMedia);
    read_capacity_last=15;read_capacity_sector=2048;return 1;
}
static void cache_property(uint32_t enabled,uint8_t flush)
{
    memset(cache_query_descriptor,0,sizeof(cache_query_descriptor));
    cache_query_descriptor[0]=cache_query_descriptor[4]=28;
    cache_query_descriptor[12]=(uint8_t)enabled;cache_query_descriptor[24]=flush;
    publish_host_cache_from_descriptor();
}
static void publish_host_cache_from_descriptor(void)
{
    uint32_t enabled=cache_query_descriptor[12];
    uint8_t flush=cache_query_descriptor[24];
    nx_lcq_init(&host_lower_cache,NX_CACHE_PROFILE_ATA);
    if(!lower_started) {
        nx_lcq_revoke(&host_lower_cache);
        return;
    }
    if(enabled) {
        nx_lcq_raw raw={0x20,(uint16_t)(0x4000u|(flush?0x1000u:0)),
                        0x4000,(uint16_t)(enabled==2?0x20u:0),0,0};
        nx_lcq_writer writer;
        nx_lcq_define(&writer,NX_LCQ_CACHED,0xec,512);
        (void)nx_lcq_start(&host_lower_cache,&writer,0xec,512,NX_LCQ_PIO_COUNTED);
        (void)nx_lcq_publish(&host_lower_cache,
            nx_lcq_result_copy(&writer,1,512),raw);
    }
}
static int capacity_control_publishes_geometry(void)
{
    PDEVICE_OBJECT d=make_optical();IRP irp;IO_STACK_LOCATION stack;uint8_t output[32];memset(&irp,0,sizeof(irp));memset(&stack,0,sizeof(stack));memset(output,0xa5,sizeof(output));
    irp.StackCount=1;irp.CurrentLocation=1;irp.Tail.Overlay.CurrentStackLocation=&stack;irp.AssociatedIrp.SystemBuffer=output;
    stack.MajorFunction=IRP_MJ_DEVICE_CONTROL;stack.Parameters.DeviceIoControl.IoControlCode=IOCTL_CDROM_GET_DRIVE_GEOMETRY;stack.Parameters.DeviceIoControl.OutputBufferLength=24;
    lower_pending=0;lower_calls=0;CHECK(NxNativeDispatchControl(d,&irp)==STATUS_PENDING);CHECK(irp.host_pending&&irp.host_completed&&irp.IoStatus.Status==0&&irp.IoStatus.Information==24);
    CHECK(lower_calls==1&&opcodes[0]==0x25);CHECK(word(output+20)==2048);CHECK(word(output+12)>0&&word(output+16)>0);
    IRP len;IO_STACK_LOCATION ls;uint8_t length[8];memset(&len,0,sizeof(len));memset(&ls,0,sizeof(ls));len.Tail.Overlay.CurrentStackLocation=&ls;len.AssociatedIrp.SystemBuffer=length;ls.MajorFunction=IRP_MJ_DEVICE_CONTROL;ls.Parameters.DeviceIoControl.IoControlCode=IOCTL_DISK_GET_LENGTH_INFO;ls.Parameters.DeviceIoControl.OutputBufferLength=8;
    CHECK(NxNativeDispatchControl(d,&len)==STATUS_SUCCESS);CHECK(len.IoStatus.Information==8&&word(length)==32768&&word(length+4)==0);CHECK(lower_calls==1);
    IRP ex;IO_STACK_LOCATION xs;uint8_t extended[32];memset(&ex,0,sizeof(ex));memset(&xs,0,sizeof(xs));memset(extended,0xa5,sizeof(extended));
    ex.Tail.Overlay.CurrentStackLocation=&xs;ex.AssociatedIrp.SystemBuffer=extended;xs.Parameters.DeviceIoControl.IoControlCode=IOCTL_DISK_GET_DRIVE_GEOMETRY_EX;xs.Parameters.DeviceIoControl.OutputBufferLength=32;
    CHECK(NxNativeDispatchControl(d,&ex)==STATUS_SUCCESS);CHECK(ex.host_completed&&ex.IoStatus.Information==32);CHECK(dword(extended+24)==32768);CHECK(lower_calls==1);
    return 1;
}
static int optical_toc_verify_and_pending_capacity(void)
{
    PDEVICE_OBJECT d=make_optical();IRP toc;IO_STACK_LOCATION ts;uint8_t data[804];memset(&toc,0,sizeof(toc));memset(&ts,0,sizeof(ts));memset(data,0xa5,sizeof(data));toc.Tail.Overlay.CurrentStackLocation=&ts;toc.AssociatedIrp.SystemBuffer=data;ts.Parameters.DeviceIoControl.IoControlCode=IOCTL_CDROM_READ_TOC;ts.Parameters.DeviceIoControl.OutputBufferLength=804;
    lower_pending=0;lower_calls=0;CHECK(NxNativeDispatchControl(d,&toc)==STATUS_PENDING);CHECK(toc.host_pending&&toc.host_completed&&toc.IoStatus.Information==12&&data[1]==10&&data[5]==0x14);CHECK(opcodes[0]==0x43);
    IRP tur;IO_STACK_LOCATION vs;uint8_t count[4];memset(&tur,0,sizeof(tur));memset(&vs,0,sizeof(vs));tur.Tail.Overlay.CurrentStackLocation=&vs;tur.AssociatedIrp.SystemBuffer=count;vs.Parameters.DeviceIoControl.IoControlCode=IOCTL_CDROM_CHECK_VERIFY;vs.Parameters.DeviceIoControl.OutputBufferLength=4;
    CHECK(NxNativeDispatchControl(d,&tur)==STATUS_PENDING);CHECK(tur.host_pending&&tur.host_completed&&tur.IoStatus.Information==4&&word(count)==1);CHECK(opcodes[1]==0);
    PDEVICE_OBJECT p=make_optical();IRP geo;IO_STACK_LOCATION gs;uint8_t geometry[24];memset(&geo,0,sizeof(geo));memset(&gs,0,sizeof(gs));geo.Tail.Overlay.CurrentStackLocation=&gs;geo.AssociatedIrp.SystemBuffer=geometry;gs.Parameters.DeviceIoControl.IoControlCode=IOCTL_DISK_GET_DRIVE_GEOMETRY;gs.Parameters.DeviceIoControl.OutputBufferLength=24;
    lower_pending=1;CHECK(NxNativeDispatchControl(p,&geo)==STATUS_PENDING);CHECK(geo.host_pending&&!geo.host_completed);lower_pending=0;CHECK(complete_child(0,8,1)==STATUS_MORE_PROCESSING_REQUIRED);CHECK(geo.host_completed&&geo.IoStatus.Status==0&&geo.IoStatus.Information==24);
    return 1;
}
static int closes_control_races_and_forwards_property(void)
{
    PDEVICE_OBJECT d=make_optical();IRP irp;IO_STACK_LOCATION stack[2];uint8_t out[24];
    memset(&irp,0,sizeof(irp));memset(stack,0,sizeof(stack));
    irp.StackCount=1;irp.CurrentLocation=1;irp.Tail.Overlay.CurrentStackLocation=&stack[0];
    irp.AssociatedIrp.SystemBuffer=out;stack[0].Parameters.DeviceIoControl.IoControlCode=IOCTL_STORAGE_GET_DEVICE_NUMBER;
    stack[0].Parameters.DeviceIoControl.OutputBufferLength=12;
    CHECK(NxNativeDispatchControl(d,&irp)==STATUS_SUCCESS&&irp.host_completed);
    CHECK(word(out)==FILE_DEVICE_CD_ROM);
    memset(&irp,0,sizeof(irp));memset(stack,0,sizeof(stack));irp.StackCount=1;irp.CurrentLocation=1;
    irp.Tail.Overlay.CurrentStackLocation=&stack[0];stack[0].Parameters.DeviceIoControl.IoControlCode=IOCTL_STORAGE_QUERY_PROPERTY;
    property_calls=0;CHECK(NxNativeDispatchControl(d,&irp)==STATUS_SUCCESS);
    CHECK(property_calls==1&&irp.host_completed);
    memset(&irp,0,sizeof(irp));memset(stack,0,sizeof(stack));irp.Tail.Overlay.CurrentStackLocation=&stack[0];
    stack[0].Parameters.DeviceIoControl.IoControlCode=IOCTL_CDROM_CHECK_VERIFY;
    stack[0].Parameters.DeviceIoControl.OutputBufferLength=4;
    CHECK(NxNativeDispatchControl(d,&irp)==STATUS_BUFFER_TOO_SMALL&&irp.host_completed);
    memset(&irp,0,sizeof(irp));memset(stack,0,sizeof(stack));irp.Tail.Overlay.CurrentStackLocation=&stack[0];
    irp.Cancel=1;stack[0].Parameters.DeviceIoControl.IoControlCode=IOCTL_CDROM_READ_TOC;
    stack[0].Parameters.DeviceIoControl.OutputBufferLength=804;irp.AssociatedIrp.SystemBuffer=out;
    lower_calls=0;CHECK(NxNativeDispatchControl(d,&irp)==STATUS_CANCELLED);
    CHECK(irp.host_completed&&irp.IoStatus.Status==STATUS_CANCELLED&&!lower_calls);
    return 1;
}
static int publishes_authoritative_disk_capacity(void)
{
    static const uint64_t sizes[]={UINT64_C(8)<<30,UINT64_C(10)<<30};
    for(unsigned test=0;test<2;++test) {
        PDEVICE_OBJECT d=make_unknown_disk();parent_fixture read;IRP geometry;IO_STACK_LOCATION stack;uint8_t out[24];
        init_parent(&read,IRP_MJ_READ,512);lower_calls=0;
        CHECK(NxNativeDispatchReadWrite(d,&read.irp)==STATUS_DEVICE_NOT_READY);
        CHECK(read.irp.host_completed&&read.irp.IoStatus.Status==STATUS_DEVICE_NOT_READY&&!lower_calls);
        read_capacity_sector=512;read_capacity_last=(uint32_t)(sizes[test]/512-1);
        memset(&geometry,0,sizeof(geometry));memset(&stack,0,sizeof(stack));memset(out,0,sizeof(out));
        geometry.Tail.Overlay.CurrentStackLocation=&stack;geometry.AssociatedIrp.SystemBuffer=out;
        stack.Parameters.DeviceIoControl.IoControlCode=IOCTL_DISK_GET_DRIVE_GEOMETRY;
        stack.Parameters.DeviceIoControl.OutputBufferLength=24;lower_pending=0;
        CHECK(NxNativeDispatchControl(d,&geometry)==STATUS_PENDING);
        CHECK(geometry.host_completed&&word(out+20)==512);
        CHECK(dword(out)==sizes[test]/(512u*255u*63u));
        init_parent(&read,IRP_MJ_READ,512);CHECK(NxNativeDispatchReadWrite(d,&read.irp)==STATUS_SUCCESS);
        CHECK(read.irp.host_completed&&read.irp.IoStatus.Information==512);
    }
    read_capacity_last=15;read_capacity_sector=2048;
    return 1;
}
static int unwinds_unpublished_creation(void)
{
    DRIVER_OBJECT driver={0};DEVICE_OBJECT lower={0};NX_NATIVE_DEVICE_INIT init={0};
    WCHAR name_buffer[2]={0},link_buffer[2]={0};UNICODE_STRING name={0,2,name_buffer},link={0,2,link_buffer};
    PDEVICE_OBJECT out=NULL;lower.StackSize=2;init.DeviceName=&name;init.SymbolicLinkName=&link;
    init.DeviceType=FILE_DEVICE_CD_ROM;init.Config=(nx_config){2048,4096,0x20000,33,0,0xffff,0,1,NX_CACHE_DISABLED};init.SlotCount=2;
    detaches=deletes=free_irps=free_mdls=0;fail_pool=1;
    CHECK(NxNativeCreateClassDevice(&driver,&lower,&init,&out)==STATUS_INSUFFICIENT_RESOURCES);
    CHECK(!out&&detaches==1&&deletes==1);
    detaches=deletes=free_irps=free_mdls=0;fail_symbolic_link=1;
    CHECK(NxNativeCreateClassDevice(&driver,&lower,&init,&out)==STATUS_IO_DEVICE_ERROR);
    fail_symbolic_link=0;CHECK(!out&&detaches==1&&deletes==1&&free_irps==2&&free_mdls==2);
    return 1;
}
static int production_cache_qualification_and_durability(void)
{
    DRIVER_EXTENSION disk_extension={0},cdrom_extension={0};
    DRIVER_OBJECT disk={0},cdrom={0};DEVICE_OBJECT disk_lower={0},cdrom_lower={0};
    PDEVICE_OBJECT disk_device;IRP geometry;IO_STACK_LOCATION geometry_stack;uint8_t geometry_data[24];
    disk.DriverExtension=&disk_extension;cdrom.DriverExtension=&cdrom_extension;
    disk_lower.StackSize=2;cdrom_lower.StackSize=2;
    property_calls=0;lower_started=0;cache_property(2,1);
    CHECK(DiskDriverEntry(&disk,NULL)==STATUS_SUCCESS);
    CHECK(CdromDriverEntry(&cdrom,NULL)==STATUS_SUCCESS);
    CHECK(disk.DriverExtension->AddDevice&&cdrom.DriverExtension->AddDevice);
    CHECK(disk.MajorFunction[IRP_MJ_READ]==NxNativeDispatchReadWrite);
    CHECK(cdrom.MajorFunction[IRP_MJ_DEVICE_CONTROL]==NxNativeDispatchControl);
    CHECK(disk.MajorFunction[IRP_MJ_PNP]==NxNativeDispatchPnp);
    CHECK(disk.DriverExtension->AddDevice(&disk,&disk_lower)==STATUS_SUCCESS);
    CHECK(created_device&&created_device->DeviceType==FILE_DEVICE_DISK);
    disk_device=created_device;CHECK(property_calls==0);

    parent_fixture before_start;init_parent(&before_start,IRP_MJ_FLUSH_BUFFERS,0);
    CHECK(disk.MajorFunction[IRP_MJ_FLUSH_BUFFERS](disk_device,&before_start.irp)==STATUS_NOT_SUPPORTED);
    CHECK(before_start.irp.host_completed&&before_start.irp.IoStatus.Status==STATUS_NOT_SUPPORTED);
    CHECK(before_start.irp.IoStatus.Information==0&&!lower_started);
    CHECK(dispatch_pnp(disk.MajorFunction[IRP_MJ_PNP],disk_device,IRP_MN_START_DEVICE)==STATUS_SUCCESS);
    CHECK(property_calls==0&&lower_started);

    memset(&geometry,0,sizeof(geometry));memset(&geometry_stack,0,sizeof(geometry_stack));
    geometry.Tail.Overlay.CurrentStackLocation=&geometry_stack;geometry.AssociatedIrp.SystemBuffer=geometry_data;
    geometry_stack.Parameters.DeviceIoControl.IoControlCode=IOCTL_DISK_GET_DRIVE_GEOMETRY;
    geometry_stack.Parameters.DeviceIoControl.OutputBufferLength=sizeof(geometry_data);
    read_capacity_sector=512;read_capacity_last=2047;lower_calls=0;lower_pending=0;
    CHECK(disk.MajorFunction[IRP_MJ_DEVICE_CONTROL](disk_device,&geometry)==STATUS_PENDING);
    CHECK(geometry.host_completed&&geometry.IoStatus.Status==STATUS_SUCCESS&&lower_calls==1&&opcodes[0]==0x25);

    /* Forza issues twelve concurrent async map reads through this production
     * disk path.  Its fixed envelope pool must admit the whole burst. */
    parent_fixture map_reads[12];lower_pending=1;lower_calls=0;pending_child_count=0;
    for(unsigned index=0;index<12;++index) {
        init_parent(&map_reads[index],IRP_MJ_READ,4096);
        CHECK(disk.MajorFunction[IRP_MJ_READ](disk_device,&map_reads[index].irp)==STATUS_PENDING);
        CHECK(!map_reads[index].irp.host_completed);
    }
    CHECK(lower_calls==12&&pending_child_count==12);
    while(pending_child_count)
        CHECK(complete_specific_child(pending_children[0],STATUS_SUCCESS,4096,1)==STATUS_MORE_PROCESSING_REQUIRED);
    for(unsigned index=0;index<12;++index)
        CHECK(map_reads[index].irp.host_completed&&map_reads[index].irp.IoStatus.Status==STATUS_SUCCESS);
    lower_pending=0;
    unsigned pools_before=pool_allocations,irps_before=irp_allocations,mdls_before=mdl_allocations;

    parent_fixture enabled;init_parent(&enabled,IRP_MJ_WRITE,512);enabled.stack.Flags=SL_WRITE_THROUGH;
    lower_calls=0;CHECK(disk.MajorFunction[IRP_MJ_WRITE](disk_device,&enabled.irp)==STATUS_SUCCESS);
    CHECK(enabled.irp.host_completed&&enabled.irp.IoStatus.Status==STATUS_SUCCESS);
    CHECK(lower_calls==2&&opcodes[0]==0x2a&&opcodes[1]==0x35&&property_calls==0);

    /* Inline completion observes the exact admission token. */
    cache_property(2,1);
    parent_fixture raced;init_parent(&raced,IRP_MJ_WRITE,512);
    raced.stack.Flags=SL_WRITE_THROUGH;revoke_cache_during_submit=1;lower_calls=0;
    CHECK(disk.MajorFunction[IRP_MJ_WRITE](disk_device,&raced.irp)==STATUS_NOT_SUPPORTED);
    CHECK(raced.irp.host_completed&&raced.irp.IoStatus.Status==STATUS_NOT_SUPPORTED);
    CHECK(raced.irp.IoStatus.Information==0&&lower_calls==2);

    /* Pending completion uses the same token and clears bytes on revocation. */
    cache_property(2,1);lower_pending=1;lower_calls=0;
    parent_fixture pending_race;init_parent(&pending_race,IRP_MJ_WRITE,512);
    pending_race.stack.Flags=SL_WRITE_THROUGH;
    CHECK(disk.MajorFunction[IRP_MJ_WRITE](disk_device,&pending_race.irp)==STATUS_PENDING);
    CHECK(lower_calls==1&&!pending_race.irp.host_completed);
    nx_lcq_revoke(&host_lower_cache);
    CHECK(complete_child(STATUS_SUCCESS,512,1)==STATUS_MORE_PROCESSING_REQUIRED);
    CHECK(lower_calls==2&&!pending_race.irp.host_completed);
    CHECK(complete_child(STATUS_SUCCESS,0,1)==STATUS_MORE_PROCESSING_REQUIRED);
    CHECK(pending_race.irp.host_completed&&pending_race.irp.IoStatus.Status==STATUS_NOT_SUPPORTED);
    CHECK(pending_race.irp.IoStatus.Information==0);lower_pending=0;

    /* Known, supported and inactive needs no synchronization command. */
    cache_property(1,1);parent_fixture disabled;init_parent(&disabled,IRP_MJ_WRITE,512);
    disabled.stack.Flags=SL_WRITE_THROUGH;lower_calls=0;
    CHECK(disk.MajorFunction[IRP_MJ_WRITE](disk_device,&disabled.irp)==STATUS_SUCCESS);
    CHECK(disabled.irp.host_completed&&lower_calls==1&&opcodes[0]==0x2a);

    /* Every unknown, unsupported, malformed or failed publication fails closed. */
    nx_lcq_revoke(&host_lower_cache);
    parent_fixture unknown;init_parent(&unknown,IRP_MJ_WRITE,512);unknown.stack.Flags=SL_WRITE_THROUGH;
    lower_calls=0;CHECK(disk.MajorFunction[IRP_MJ_WRITE](disk_device,&unknown.irp)==STATUS_NOT_SUPPORTED);
    CHECK(unknown.irp.host_completed&&unknown.irp.IoStatus.Information==0&&!lower_calls);
    cache_property(2,0);
    parent_fixture unsupported;init_parent(&unsupported,IRP_MJ_WRITE,512);unsupported.stack.Flags=SL_WRITE_THROUGH;
    CHECK(disk.MajorFunction[IRP_MJ_WRITE](disk_device,&unsupported.irp)==STATUS_NOT_SUPPORTED&&!lower_calls);
    cache_property(2,1);
    __atomic_fetch_and(&host_lower_cache.published,~(3u<<7),__ATOMIC_ACQ_REL);
    parent_fixture unproved;init_parent(&unproved,IRP_MJ_WRITE,512);unproved.stack.Flags=SL_WRITE_THROUGH;
    CHECK(disk.MajorFunction[IRP_MJ_WRITE](disk_device,&unproved.irp)==STATUS_NOT_SUPPORTED&&!lower_calls);
    nx_lcq_revoke(&host_lower_cache);
    parent_fixture malformed;init_parent(&malformed,IRP_MJ_WRITE,512);malformed.stack.Flags=SL_WRITE_THROUGH;
    CHECK(disk.MajorFunction[IRP_MJ_WRITE](disk_device,&malformed.irp)==STATUS_NOT_SUPPORTED&&!lower_calls);
    nx_lcq_revoke(&host_lower_cache);
    parent_fixture failed;init_parent(&failed,IRP_MJ_WRITE,512);failed.stack.Flags=SL_WRITE_THROUGH;
    CHECK(disk.MajorFunction[IRP_MJ_WRITE](disk_device,&failed.irp)==STATUS_NOT_SUPPORTED&&!lower_calls);

    /* Lower reset/stop revokes, then successful START republishes. */
    CHECK(dispatch_pnp(disk.MajorFunction[IRP_MJ_PNP],disk_device,IRP_MN_STOP_DEVICE)==STATUS_SUCCESS);
    parent_fixture revoked;init_parent(&revoked,IRP_MJ_FLUSH_BUFFERS,0);lower_calls=0;
    CHECK(disk.MajorFunction[IRP_MJ_FLUSH_BUFFERS](disk_device,&revoked.irp)==STATUS_NOT_SUPPORTED&&!lower_calls);
    cache_property(2,1);
    CHECK(dispatch_pnp(disk.MajorFunction[IRP_MJ_PNP],disk_device,IRP_MN_START_DEVICE)==STATUS_SUCCESS);

    parent_fixture write,flush;init_parent(&write,IRP_MJ_WRITE,512);init_parent(&flush,IRP_MJ_FLUSH_BUFFERS,0);
    lower_pending=1;lower_calls=0;
    CHECK(disk.MajorFunction[IRP_MJ_WRITE](disk_device,&write.irp)==STATUS_PENDING);
    CHECK(disk.MajorFunction[IRP_MJ_FLUSH_BUFFERS](disk_device,&flush.irp)==STATUS_PENDING);
    CHECK(lower_calls==1&&opcodes[0]==0x2a&&!write.irp.host_completed&&!flush.irp.host_completed);
    CHECK(complete_child(STATUS_SUCCESS,512,1)==STATUS_MORE_PROCESSING_REQUIRED);
    CHECK(write.irp.host_completed&&write.irp.IoStatus.Status==STATUS_SUCCESS);
    CHECK(!flush.irp.host_completed&&lower_calls==2&&opcodes[1]==0x35);
    CHECK(complete_child(STATUS_IO_DEVICE_ERROR,0,2)==STATUS_MORE_PROCESSING_REQUIRED);
    CHECK(flush.irp.host_completed&&flush.irp.IoStatus.Status==STATUS_IO_DEVICE_ERROR);
    lower_pending=0;sync_command_status=STATUS_IO_DEVICE_ERROR;
    parent_fixture sync_error;init_parent(&sync_error,IRP_MJ_WRITE,512);
    sync_error.stack.Flags=SL_WRITE_THROUGH;lower_calls=0;
    CHECK(disk.MajorFunction[IRP_MJ_WRITE](disk_device,&sync_error.irp)==STATUS_IO_DEVICE_ERROR);
    CHECK(sync_error.irp.host_completed&&sync_error.irp.IoStatus.Status==STATUS_IO_DEVICE_ERROR);
    CHECK(sync_error.irp.IoStatus.Information==512&&lower_calls==2);
    parent_fixture shutdown;init_parent(&shutdown,IRP_MJ_SHUTDOWN,0);lower_calls=0;
    CHECK(disk.MajorFunction[IRP_MJ_SHUTDOWN](disk_device,&shutdown.irp)==STATUS_IO_DEVICE_ERROR);
    CHECK(shutdown.irp.host_completed&&shutdown.irp.IoStatus.Status==STATUS_IO_DEVICE_ERROR&&lower_calls==1&&opcodes[0]==0x35);
    sync_command_status=STATUS_SUCCESS;

    /* START forwarding has no hidden query allocation, wait or shared barrier. */
    pnp_thread parallel[2];pthread_t parallel_ids[2];
    init_pnp(&parallel[0],disk.MajorFunction[IRP_MJ_PNP],disk_device,IRP_MN_START_DEVICE);
    init_pnp(&parallel[1],disk.MajorFunction[IRP_MJ_PNP],disk_device,IRP_MN_START_DEVICE);
    CHECK(!pthread_create(&parallel_ids[0],NULL,run_pnp,&parallel[0]));
    CHECK(!pthread_create(&parallel_ids[1],NULL,run_pnp,&parallel[1]));
    CHECK(!pthread_join(parallel_ids[0],NULL)&&!pthread_join(parallel_ids[1],NULL));
    CHECK(parallel[0].returned&&parallel[1].returned&&property_calls==0);
    CHECK(pool_allocations==pools_before&&irp_allocations==irps_before&&mdl_allocations==mdls_before);

    lower_started=1;
    CHECK(cdrom.DriverExtension->AddDevice(&cdrom,&cdrom_lower)==STATUS_SUCCESS);
    CHECK(created_device&&created_device->DeviceType==FILE_DEVICE_CD_ROM);
    return 1;
}
static int removal_drains_bound_cache_readers(void)
{
    cache_property(2,1);
    PDEVICE_OBJECT device=make_device(2);
    CHECK(dispatch_pnp(NxNativeDispatchPnp,device,IRP_MN_START_DEVICE)==STATUS_SUCCESS);
    parent_fixture write;init_parent(&write,IRP_MJ_WRITE,512);
    write.stack.Flags=SL_WRITE_THROUGH;lower_pending=1;lower_calls=0;
    CHECK(NxNativeDispatchReadWrite(device,&write.irp)==STATUS_PENDING);
    pnp_thread removal;init_pnp(&removal,NxNativeDispatchPnp,device,IRP_MN_REMOVE_DEVICE);
    pthread_t removal_id;CHECK(!pthread_create(&removal_id,NULL,run_pnp,&removal));
    while(!__atomic_load_n(&removal.entered,__ATOMIC_ACQUIRE)) sched_yield();
    for(unsigned i=0;i<1000;++i) sched_yield();
    CHECK(!__atomic_load_n(&removal.returned,__ATOMIC_ACQUIRE));
    CHECK(complete_child(STATUS_SUCCESS,512,1)==STATUS_MORE_PROCESSING_REQUIRED);
    CHECK(!write.irp.host_completed&&active_child);
    CHECK(complete_child(STATUS_SUCCESS,0,1)==STATUS_MORE_PROCESSING_REQUIRED);
    CHECK(write.irp.host_completed&&write.irp.IoStatus.Status==STATUS_SUCCESS);
    CHECK(!pthread_join(removal_id,NULL)&&removal.returned&&removal.status==STATUS_SUCCESS);
    lower_pending=0;
    return 1;
}

#include <time.h>
static uint64_t now_ns(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC_RAW,&t);return (uint64_t)t.tv_sec*1000000000u+(uint64_t)t.tv_nsec;}
int main(void)
{
    enum { QD=12, BATCHES=1000000, SAMPLES=5 };
    PDEVICE_OBJECT d=make_device(16);
    parent_fixture reads[QD];
    uint64_t samples[SAMPLES];
    lower_pending=1;
    for(unsigned sample=0;sample<SAMPLES;++sample) {
        uint64_t start=now_ns();
        for(unsigned batch=0;batch<BATCHES;++batch) {
            lower_calls=0;pending_child_count=0;
            for(unsigned i=0;i<QD;++i) {
                init_parent(&reads[i],IRP_MJ_READ,4096);
                if(NxNativeDispatchReadWrite(d,&reads[i].irp)!=STATUS_PENDING) abort();
            }
            while(pending_child_count)
                if(complete_specific_child(pending_children[0],STATUS_SUCCESS,4096,1)!=STATUS_MORE_PROCESSING_REQUIRED)abort();
        }
        samples[sample]=now_ns()-start;
    }
    for(unsigned i=0;i<SAMPLES;++i)for(unsigned j=i+1;j<SAMPLES;++j)if(samples[j]<samples[i]){uint64_t t=samples[i];samples[i]=samples[j];samples[j]=t;}
    printf("median_ns=%llu ns_per_io=%.2f batches=%u qd=%u\n",(unsigned long long)samples[SAMPLES/2],(double)samples[SAMPLES/2]/(BATCHES*QD),BATCHES,QD);
    return 0;
}
