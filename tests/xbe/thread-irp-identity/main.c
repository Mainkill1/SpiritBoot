/* Public IRP thread identity: queue ownership and delayed cross-thread completion. */
#include <windows.h>
#include <xboxkrnl/xboxkrnl.h>
#include <string.h>
#include <stddef.h>
#include "regression.h"

static DRIVER_OBJECT driver;
static PDEVICE_OBJECT device;
static PETHREAD self;
static PIRP pending;
static KEVENT submitted, finish;
static PETHREAD dispatched_thread;
static ULONG dispatches, delayed;
static volatile ULONG completion_returned;
static ULONG starts, start_bad_identity, retained;
static ULONG native_request;
static SHARE_ACCESS share_access;

static void unlink_packet(PIRP irp)
{
    PLIST_ENTRY e=&irp->ThreadListEntry;
    e->Blink->Flink=e->Flink;e->Flink->Blink=e->Blink;
    e->Flink=e->Blink=e;
}

static NTSTATUS NTAPI dispatch(PDEVICE_OBJECT dev,PIRP irp)
{
    (void)dev;
    dispatches++;dispatched_thread=irp->Tail.Overlay.Thread;
    if(delayed) {
        /* Public IO_STACK_LOCATION Control is byte 3. */
        ((UCHAR *)irp->Tail.Overlay.CurrentStackLocation)[3]|=1;
        pending=irp;KeSetEvent(&submitted,0,FALSE);return STATUS_PENDING;
    }
    UCHAR major=*(UCHAR *)irp->Tail.Overlay.CurrentStackLocation;
    if(native_request&&major==0) {
        PFILE_OBJECT file=(PFILE_OBJECT)((ULONG *)irp->Tail.Overlay.CurrentStackLocation)[6];
        IoSetShareAccess(FILE_READ_DATA,FILE_SHARE_READ,file,&share_access);
    }
    if(native_request&&major==12) {
        PFILE_OBJECT file=(PFILE_OBJECT)((ULONG *)irp->Tail.Overlay.CurrentStackLocation)[6];
        IoRemoveShareAccess(file,&share_access);
    }
    irp->IoStatus.Status=STATUS_SUCCESS;
    irp->IoStatus.Information=major==0?1:(native_request?0:0x1234);
    if(native_request&&major==2) {
        ULONG length=((ULONG *)irp->Tail.Overlay.CurrentStackLocation)[1];
        memset(irp->UserBuffer,0x6a,length);irp->IoStatus.Information=length;
    }
    IofCompleteRequest(irp,0);return STATUS_SUCCESS;
}

static VOID NTAPI start_io(PDEVICE_OBJECT dev,PIRP irp)
{
    if(irp->Tail.Overlay.Thread!=self||dev->CurrentIrp!=irp)start_bad_identity++;
    starts++;
}

static NTSTATUS NTAPI retain(PDEVICE_OBJECT dev,PIRP irp,PVOID context)
{
    (void)dev;(void)context;
    if(irp->Tail.Overlay.Thread!=self)start_bad_identity++;
    retained++;return (NTSTATUS)0xc0000016;
}

static void start_and_retain_cases(void)
{
    PIRP packets[3];driver.DriverStartIo=start_io;
    for(unsigned n=0;n<3;n++) {
        packets[n]=IoAllocateIrp(1);regression_require(packets[n]!=NULL,"allocate StartIo packet");
        packets[n]->Tail.Overlay.Thread=self;ULONG key=n;
        IoStartPacket(device,packets[n],n?&key:NULL);
    }
    regression_check(starts==1,"StartIo starts first packet and queues following packets");
    IoStartNextPacket(device);IoStartNextPacketByKey(device,2);IoStartNextPacket(device);
    regression_check(starts==3&&!start_bad_identity,"all StartIo entry paths preserve public thread identity");
    for(unsigned n=0;n<3;n++)IoFreeIrp(packets[n]);
    for(unsigned round=0;round<2;round++) {
        PIRP irp=IoAllocateIrp(1);regression_require(irp!=NULL,"allocate completion-owner packet");
        irp->Tail.Overlay.Thread=self;IoQueueThreadIrp(irp);
        ULONG *next=(ULONG *)irp->Tail.Overlay.CurrentStackLocation-9;
        memset(next,0,36);next[0]=2|(0x40u<<24);next[7]=(ULONG)retain;
        delayed=0;ULONG prior=retained;
        regression_check(IofCallDriver(device,irp)==0,"driver completion returns after retaining packet");
        regression_check(retained==prior+1&&irp->Tail.Overlay.Thread==self&&!start_bad_identity,
                         "MORE_PROCESSING_REQUIRED retains packet and public thread field");
        unlink_packet(irp);
        USHORT size=irp->Size;IoInitializeIrp(irp,size,1);
        regression_check(irp->Tail.Overlay.Thread==NULL&&irp->ThreadListEntry.Flink==&irp->ThreadListEntry,
                         "caller reinitialization clears old owner and list membership");
        irp->Tail.Overlay.Thread=self;IoQueueThreadIrp(irp);unlink_packet(irp);IoFreeIrp(irp);
    }
}

static void native_request_case(POBJECT_STRING name)
{
    OBJECT_ATTRIBUTES oa={.RootDirectory=NULL,.ObjectName=name,.Attributes=OBJ_CASE_INSENSITIVE};
    IO_STATUS_BLOCK iosb;HANDLE file=NULL,event=NULL;
    /* This public driver owns a neither-buffered-nor-direct request. */
    device->Flags&=~(0x10u|4u|0x00200000u);delayed=0;native_request=1;
    regression_require(NtCreateFile(&file,GENERIC_READ|SYNCHRONIZE,&oa,&iosb,NULL,0,
                                    FILE_SHARE_READ,FILE_OPEN,0)==0,"open title device through native I/O manager");
    regression_check(dispatched_thread==self,"native create publishes public thread before title dispatch");
    regression_require(NtCreateEvent(&event,NULL,NotificationEvent,FALSE)==0,"create native request completion event");
    UCHAR buffer[32]={0};LARGE_INTEGER offset={.QuadPart=0},timeout={.QuadPart=-50000000};
    NTSTATUS status=NtReadFile(file,event,NULL,NULL,&iosb,buffer,sizeof(buffer),&offset);
    tap_comment("native_read status=%08lx iosb=%08lx information=%lu flags=%08lx dispatches=%lu",
                (ULONG)status,(ULONG)iosb.Status,(ULONG)iosb.Information,device->Flags,dispatches);
    regression_check(status==0||status==STATUS_PENDING,"native request reaches title driver");
    if(status!=0&&status!=STATUS_PENDING){NtClose(event);NtClose(file);native_request=0;return;}
    regression_require(NtWaitForSingleObject(event,FALSE,&timeout)==0,"native request completion returns to event");
    regression_check(dispatched_thread==self&&iosb.Status==0&&iosb.Information==sizeof(buffer),
                     "native to title to completion preserves thread and exact IOSB");
    unsigned good=1;for(unsigned n=0;n<sizeof(buffer);n++)good&=buffer[n]==0x6a;
    regression_check(good,"native request receives exact title driver bytes");
    NtClose(event);NtClose(file);native_request=0;
}

static VOID NTAPI worker(PVOID context)
{
    (void)context;
    LARGE_INTEGER timeout={.QuadPart=-50000000};
    if(KeWaitForSingleObject(&submitted,Executive,KernelMode,FALSE,&timeout)==0) {
        PIRP irp=pending;
        irp->IoStatus.Status=STATUS_SUCCESS;irp->IoStatus.Information=0x1234;
        IofCompleteRequest(irp,0);
        completion_returned=1;
    }
    KeSetEvent(&finish,0,FALSE);
    PsTerminateSystemThread(0);
}

static void queue_cases(void)
{
    PIRP a=IoAllocateIrp(1),b=IoAllocateIrp(1);
    regression_require(a&&b,"allocate two public packets");
    regression_check(a->ThreadListEntry.Flink==&a->ThreadListEntry,
                     "fresh packet is unlinked");
    a->Tail.Overlay.Thread=self;b->Tail.Overlay.Thread=self;
    a->IoStatus.Status=0x5a5a5a5a;a->IoStatus.Information=0xa5a5a5a5;
    IoQueueThreadIrp(a);
    regression_check(a->Tail.Overlay.Thread==self,"queue retains public thread field");
    regression_check(a->IoStatus.Status==0x5a5a5a5a&&a->IoStatus.Information==0xa5a5a5a5,
                     "queue retains status sentinel");
    regression_check(a->ThreadListEntry.Flink!=&a->ThreadListEntry&&
                     a->ThreadListEntry.Flink->Blink==&a->ThreadListEntry&&
                     a->ThreadListEntry.Blink->Flink==&a->ThreadListEntry,
                     "queue links packet consistently");
    IoQueueThreadIrp(b);
    regression_check(b->ThreadListEntry.Flink==&a->ThreadListEntry&&
                     a->ThreadListEntry.Blink==&b->ThreadListEntry,"queue inserts second packet at front");
    unlink_packet(b);unlink_packet(a);IoFreeIrp(b);IoFreeIrp(a);
}

static void complete_case(unsigned kind,unsigned async)
{
    KEVENT event;IO_STATUS_BLOCK iosb;LARGE_INTEGER offset={.QuadPart=0};
    LARGE_INTEGER timeout={.QuadPart=-50000000};
    UCHAR buffer[32]={0};PIRP irp;HANDLE thread=NULL;
    KeInitializeEvent(&event,NotificationEvent,FALSE);
    KeInitializeEvent(&submitted,NotificationEvent,FALSE);
    KeInitializeEvent(&finish,NotificationEvent,FALSE);
    memset(&iosb,0xee,sizeof(iosb));
    delayed=async;pending=NULL;completion_returned=dispatches=0;
    if(async)regression_require(PsCreateSystemThread(&thread,NULL,worker,NULL,FALSE)==0,
                                "start cross-thread completion worker");
    if(kind==0)irp=IoBuildSynchronousFsdRequest(2,device,buffer,sizeof(buffer),&offset,&event,&iosb);
    else if(kind==1)irp=IoBuildDeviceIoControlRequest(0x222007,device,buffer,8,buffer,8,FALSE,&event,&iosb);
    else {
        irp=IoBuildAsynchronousFsdRequest(2,device,buffer,sizeof(buffer),&offset,&iosb);
        if(irp){irp->UserEvent=&event;IoQueueThreadIrp(irp);}
    }
    regression_require(irp!=NULL,"public builder allocates packet");
    tap_comment("builder kind=%u async=%u thread=%p self=%p current=%p",kind,async,
                irp->Tail.Overlay.Thread,self,KeGetCurrentThread());
    regression_check(irp->Tail.Overlay.Thread==self,"public builder exposes referenced thread identity");
    /* Caller writes its held public reference into the published IRP field. */
    irp->Tail.Overlay.Thread=self;
    NTSTATUS status=IofCallDriver(device,irp);
    regression_check(status==(async?STATUS_PENDING:STATUS_SUCCESS),"dispatch returns expected immediate or pending status");
    regression_check(dispatches==1&&dispatched_thread==self,"title dispatch observes unchanged public thread identity");
    regression_require(KeWaitForSingleObject(&event,Executive,KernelMode,FALSE,&timeout)==0,
                        "completion reaches issuer event");
    regression_check(iosb.Status==0&&iosb.Information==0x1234,"completion writes exact issuer IOSB");
    if(async) {
        regression_require(KeWaitForSingleObject(&finish,Executive,KernelMode,FALSE,&timeout)==0,
                            "other-thread completion returns");
        regression_check(completion_returned==1,"completion queued to issuer from another thread");
        regression_require(NtWaitForSingleObject(thread,FALSE,&timeout)==0,"completion worker terminates");
        NtClose(thread);
    }
}

int main(void)
{
    regression_begin();
    regression_require(ObReferenceObjectByHandle((HANDLE)-2,&PsThreadObjectType,(PVOID *)&self)==0,
                        "hold current thread object reference");
    regression_check(offsetof(IRP,Tail.Overlay.Thread)==0x50&&offsetof(IRP,ThreadListEntry)==8,
                     "public packet field offsets match ABI");
    queue_cases();
    for(unsigned i=0;i<14;i++)driver.MajorFunction[i]=dispatch;
    static char device_name[]="\\Device\\threadirpqualification";
    OBJECT_STRING name={.Length=sizeof(device_name)-1,.MaximumLength=sizeof(device_name),.Buffer=device_name};
    regression_require(IoCreateDevice(&driver,0,&name,0x22,FALSE,&device)==0,
                        "create isolated title device");
    for(unsigned kind=0;kind<3;kind++)for(unsigned async=0;async<2;async++)complete_case(kind,async);
    start_and_retain_cases();native_request_case(&name);
    IoDeleteDevice(device);ObfDereferenceObject(self);
    regression_finish();
}
