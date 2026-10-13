/* SPDX-License-Identifier: GPL-2.0-or-later
 * Owned FATX fixture; public Xbox calls only. Disk latency comes from the
 * original emulator's documented QMP throttle, never a replaced IDE callback.
 */
#include <windows.h>
#include <xboxkrnl/xboxkrnl.h>
#include <stdio.h>
#include "regression.h"

#define DEPTH 4
#define MAX_READ (512*1024)
#define FILE_BYTES (8*1024*1024)
#define GUARD 4096
#define STRIDE (MAX_READ+2*GUARD)
#define MAGIC 0x7183ac95u
#define IOSB_SENTINEL ((NTSTATUS)0x13579bdf)
#define SHARE (FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE)
#define WAIT_MS 20000

typedef struct Slot {
    ULONG before;
    IO_STATUS_BLOCK io;
    ULONG after;
    HANDLE event, issued, file;
    ULONG offset, length, issuer_id;
    PKTHREAD issuer;
    volatile ULONG worker_result;
    volatile ULONG callbacks, errors, was_pending, event_pending;
    NTSTATUS returned;
    UCHAR *buffer;
    UCHAR salt;
    ULONG exiting;
} Slot;
static Slot slots[DEPTH];
static UCHAR *arena;
static HANDLE gate;
static const char path[]="\\Device\\Harddisk0\\Partition4\\async-life.bin";
static ULONG total_reads, pending_reads, unfinished_reads;

static UCHAR pattern(ULONG n,UCHAR salt) {
    return (UCHAR)(n^(n>>8)^(n>>16)^salt);
}
static HANDLE open_file(const char *name,ULONG access,ULONG disposition,ULONG options) {
    HANDLE file=NULL;ANSI_STRING string;IO_STATUS_BLOCK io;
    RtlInitAnsiString(&string,name);
    OBJECT_ATTRIBUTES attrs={NULL,&string,OBJ_CASE_INSENSITIVE};
    NTSTATUS status=NtCreateFile(&file,access|SYNCHRONIZE,&attrs,&io,NULL,0,
        SHARE,disposition,FILE_NON_DIRECTORY_FILE|options);
    if(status)tap_comment("open status=%08lx name=%s",(ULONG)status,name);
    regression_require(status==0,"open owned shared file");
    return file;
}
static HANDLE reader(void) {
    return open_file(path,GENERIC_READ,FILE_OPEN,FILE_NO_INTERMEDIATE_BUFFERING);
}
static HANDLE writer(void) {
    return open_file(path,GENERIC_WRITE|DELETE,FILE_OPEN,
        FILE_SYNCHRONOUS_IO_NONALERT|FILE_NO_INTERMEDIATE_BUFFERING);
}
static void populate(HANDLE file,UCHAR salt) {
    IO_STATUS_BLOCK io;ULONG bad=0;
    for(ULONG at=0;at<FILE_BYTES;at+=MAX_READ) {
        for(ULONG n=0;n<MAX_READ;n++)arena[n]=pattern(at+n,salt);
        LARGE_INTEGER offset={.QuadPart=at};
        NTSTATUS s=NtWriteFile(file,NULL,NULL,NULL,&io,arena,MAX_READ,&offset);
        bad+=s!=0 || io.Information!=MAX_READ;
    }
    regression_require(!bad,"populate exact owned file generation");
}
static void prepare(Slot *s,HANDLE file,ULONG offset,ULONG length,UCHAR salt) {
    s->before=s->after=MAGIC;s->io.Status=IOSB_SENTINEL;s->io.Information=MAGIC;
    s->file=file;s->offset=offset;s->length=length;s->salt=salt;
    s->callbacks=s->errors=s->was_pending=s->event_pending=s->exiting=0;
    s->returned=IOSB_SENTINEL;s->worker_result=MAGIC;ResetEvent(s->event);ResetEvent(s->issued);
    memset(s->buffer-GUARD,0xb6,GUARD);
    memset(s->buffer,0xcc,length);
    memset(s->buffer+length,0x6b,GUARD);
}
static void NTAPI completed(DWORD error,DWORD bytes,PVOID context) {
    Slot *s=NULL;
    for(unsigned n=0;n<DEPTH;n++)if(context==&slots[n].io)s=&slots[n];
    if(!s)regression_require(0,"completion has exact public IOSB context");
    if(error || bytes!=s->length || KeGetCurrentThread()!=s->issuer ||
       s->io.Status!=0 || s->io.Information!=s->length ||
       s->before!=MAGIC || s->after!=MAGIC)s->errors++;
    s->callbacks++;
}
static void issue(Slot *s,BOOLEAN apc) {
    s->issuer=KeGetCurrentThread();s->issuer_id=GetCurrentThreadId();
    LARGE_INTEGER offset={.QuadPart=s->offset};
    s->returned=NtReadFile(s->file,s->event,
        apc?(PIO_APC_ROUTINE)NtUserIoApcDispatcher:NULL,
        apc?(PVOID)completed:NULL,&s->io,s->buffer,s->length,&offset);
    s->was_pending=s->returned==STATUS_PENDING;
    s->event_pending=WaitForSingleObject(s->event,0)==WAIT_TIMEOUT;
    SetEvent(s->issued);
}
static void wait_slot(Slot *s,BOOLEAN apc) {
    regression_require(NT_SUCCESS(s->returned),"read accepted by public API");
    regression_require(WaitForSingleObject(s->event,WAIT_MS)==WAIT_OBJECT_0,
        "request event signals before deadline");
    if(apc) {
        DWORD limit=GetTickCount()+WAIT_MS;
        while(!s->callbacks && (LONG)(limit-GetTickCount())>0)SleepEx(1,TRUE);
        regression_require(s->callbacks==1 && !s->errors,
            "one APC on issuer with exact context status and byte count");
    }
}
static void verify(Slot *s,BOOLEAN require_iosb) {
    ULONG bad=0,guards=0;
    for(ULONG n=0;n<s->length;n++)bad+=s->buffer[n]!=pattern(s->offset+n,s->salt);
    for(ULONG n=0;n<GUARD;n++)guards+=s->buffer[(LONG)n-GUARD]!=0xb6 || s->buffer[s->length+n]!=0x6b;
    regression_check(!bad,"all returned bytes match requested offset and generation");
    regression_check(!guards && s->before==MAGIC && s->after==MAGIC,
        "buffer and IOSB boundary guards survive completion");
    if(require_iosb)regression_check(s->io.Status==0 && s->io.Information==s->length,
        "IOSB publishes exact successful status and length");
    total_reads++;pending_reads+=s->was_pending;unfinished_reads+=s->event_pending;
}
static void warm(HANDLE file,UCHAR salt) {
    prepare(&slots[0],file,0,4096,salt);issue(&slots[0],FALSE);
    wait_slot(&slots[0],FALSE);verify(&slots[0],TRUE);
}
static LONGLONG position(HANDLE file) {
    IO_STATUS_BLOCK io;FILE_POSITION_INFORMATION info;
    regression_require(NtQueryInformationFile(file,&io,&info,sizeof(info),FilePositionInformation)==0,
        "query file position through public API");
    return info.CurrentByteOffset.QuadPart;
}
static void queued(HANDLE file,UCHAR salt,ULONG length,ULONG iteration) {
    for(ULONG n=0;n<DEPTH;n++) {
        ULONG at=((iteration*53+n*197)%(FILE_BYTES/length))*length;
        prepare(&slots[n],file,at,length,salt);issue(&slots[n],TRUE);
    }
    for(ULONG n=0;n<DEPTH;n++){wait_slot(&slots[n],TRUE);verify(&slots[n],TRUE);}
    SleepEx(0,TRUE);
    for(ULONG n=0;n<DEPTH;n++)regression_check(slots[n].callbacks==1,"no duplicate APC after alertable drain");
}
static DWORD WINAPI issuer_thread(LPVOID context) {
    Slot *s=context;
    if(!s->exiting)WaitForSingleObject(gate,WAIT_MS);
    issue(s,TRUE);
    if(s->exiting){s->worker_result=0;return 0;}
    DWORD limit=GetTickCount()+WAIT_MS;
    while(!s->callbacks && (LONG)(limit-GetTickCount())>0)SleepEx(1,TRUE);
    s->worker_result=s->callbacks==1 && !s->errors?0:1;
    return s->worker_result;
}
static void concurrent(HANDLE file,UCHAR salt) {
    HANDLE threads[DEPTH];ResetEvent(gate);
    for(ULONG n=0;n<DEPTH;n++) {
        prepare(&slots[n],file,(n+1)*MAX_READ,MAX_READ,salt);
        threads[n]=CreateThread(NULL,16384,issuer_thread,&slots[n],0,NULL);
        regression_require(threads[n]!=NULL,"create independent read issuer");
    }
    SetEvent(gate);
    for(ULONG n=0;n<DEPTH;n++) {
        regression_require(WaitForSingleObject(threads[n],WAIT_MS)==WAIT_OBJECT_0,"concurrent issuer completes");
        DWORD code=1;BOOL queried=GetExitCodeThread(threads[n],&code);
        tap_comment("concurrent slot=%lu queried=%lu exit=%08lx worker=%lu callbacks=%lu errors=%lu issuer_id=%08lx",
            n,(ULONG)queried,code,slots[n].worker_result,slots[n].callbacks,slots[n].errors,slots[n].issuer_id);
        regression_check(slots[n].worker_result==0 && slots[n].callbacks==1 && !slots[n].errors,
            "same-file concurrent issuer receives its exact APC");
        regression_require(WaitForSingleObject(slots[n].event,0)==WAIT_OBJECT_0,"concurrent request event is signaled");
        verify(&slots[n],TRUE);CloseHandle(threads[n]);
    }
}
typedef struct Mutation {
    HANDLE file;
    ULONG kind, saw_pending;
    NTSTATUS status;
} Mutation;
static Mutation mutation;
static DWORD WINAPI mutate(LPVOID context) {
    Mutation *m=context;IO_STATUS_BLOCK io;
    m->saw_pending=WaitForSingleObject(slots[0].event,0)==WAIT_TIMEOUT;
    if(m->kind==0)m->status=NtClose(m->file);
    else if(m->kind==1) {
        FILE_END_OF_FILE_INFORMATION eof={.EndOfFile={.QuadPart=0}};
        m->status=NtSetInformationFile(m->file,&io,&eof,sizeof(eof),FileEndOfFileInformation);
    } else {
        FILE_DISPOSITION_INFORMATION disposition={.DeleteFile=TRUE};
        m->status=NtSetInformationFile(m->file,&io,&disposition,sizeof(disposition),FileDispositionInformation);
    }
    return 0;
}
static void mutation_case(ULONG kind,UCHAR salt) {
    HANDLE file=reader(),other=writer();warm(file,salt);
    prepare(&slots[0],file,2*MAX_READ,MAX_READ,salt);issue(&slots[0],TRUE);
    mutation=(Mutation){.file=kind?other:file,.kind=kind,.status=IOSB_SENTINEL};
    HANDLE thread=CreateThread(NULL,16384,mutate,&mutation,0,NULL);
    regression_require(thread!=NULL,"create close truncate or delete contender");
    wait_slot(&slots[0],TRUE);verify(&slots[0],TRUE);
    regression_require(WaitForSingleObject(thread,WAIT_MS)==WAIT_OBJECT_0,"metadata contender finishes after pending I/O");
    tap_comment("mutation kind=%lu read_pending=%lu event_pending=%lu contender_pending=%lu status=%08lx",
        kind,slots[0].was_pending,slots[0].event_pending,mutation.saw_pending,(ULONG)mutation.status);
    regression_check(mutation.status==0,"close truncate or delete operation succeeds");
    regression_check(mutation.saw_pending,"metadata operation began with request event unsignaled");
    CloseHandle(thread);
    if(kind==1) {
        Slot *s=&slots[0];prepare(s,file,0,4096,salt);s->io.Status=0;s->io.Information=0;
        issue(s,FALSE);NTSTATUS status=s->returned;
        if(status==STATUS_PENDING) {
            regression_require(WaitForSingleObject(s->event,WAIT_MS)==WAIT_OBJECT_0,"truncated EOF completion arrives");
            status=s->io.Status;
        }
        tap_comment("truncated read returned=%08lx effective=%08lx bytes=%lu",(ULONG)s->returned,(ULONG)status,s->io.Information);
        regression_check(status==(NTSTATUS)STATUS_END_OF_FILE && s->io.Information==0,
            "truncate publishes zero-length EOF through a subsequent read");
        ULONG changed=0;for(ULONG n=0;n<s->length;n++)changed+=s->buffer[n]!=0xcc;
        regression_check(changed==0,"truncated EOF leaves request buffer unchanged");
        populate(other,(UCHAR)(salt+1));warm(file,(UCHAR)(salt+1));
    }
    if(kind)regression_require(NtClose(file)==0,"close post-mutation reader");
    regression_require(NtClose(other)==0,"close metadata handle");
    if(kind==2) {
        ANSI_STRING name;RtlInitAnsiString(&name,path);OBJECT_ATTRIBUTES attrs={NULL,&name,OBJ_CASE_INSENSITIVE};
        IO_STATUS_BLOCK io;HANDLE missing=NULL;
        NTSTATUS status=NtCreateFile(&missing,GENERIC_READ|SYNCHRONIZE,&attrs,&io,NULL,0,SHARE,
            FILE_OPEN,FILE_NON_DIRECTORY_FILE|FILE_NO_INTERMEDIATE_BUFFERING);
        tap_comment("deleted reopen status=%08lx",(ULONG)status);
        regression_check(status==(NTSTATUS)STATUS_OBJECT_NAME_NOT_FOUND,"deleted fixture disappears after final close");
        if(NT_SUCCESS(status))NtClose(missing);
    }
}
static MM_STATISTICS statistics(void) {
    MM_STATISTICS s={.Length=sizeof(s)};
    regression_require(MmQueryStatistics(&s)==0,"query public memory statistics");return s;
}
static void exiting_case(HANDLE file,UCHAR salt,ULONG n) {
    prepare(&slots[0],file,MAX_READ*(1+n%8),MAX_READ,salt);slots[0].exiting=1;
    HANDLE thread=CreateThread(NULL,16384,issuer_thread,&slots[0],0,NULL);
    regression_require(thread!=NULL,"create issuer that exits with outstanding read");
    regression_require(WaitForSingleObject(slots[0].issued,WAIT_MS)==WAIT_OBJECT_0,"exiting issuer submits request");
    regression_require(WaitForSingleObject(thread,WAIT_MS)==WAIT_OBJECT_0,"issuer exit and cancellation finish");
    ULONG event=WaitForSingleObject(slots[0].event,0)==WAIT_OBJECT_0;
    tap_comment("exit round=%lu pending=%lu unfinished=%lu event=%lu apc=%lu iosb=%08lx bytes=%lu",
        n,slots[0].was_pending,slots[0].event_pending,event,slots[0].callbacks,(ULONG)slots[0].io.Status,slots[0].io.Information);
    regression_check(NT_SUCCESS(slots[0].returned),"exiting issuer read was accepted");
    regression_check(slots[0].callbacks==0,"exited issuer has no user APC delivery");
    /* Event and IOSB publication on a dead issuer are observations, not the
     * lifetime fence. Thread exit is the public cancellation/rundown fence. */
    verify(&slots[0],FALSE);CloseHandle(thread);
    /* A subsequent full read proves the file resource was released after
     * cancellation; a write/truncate would also exercise exclusive acquisition. */
    warm(file,salt);
}
int main(void) {
    regression_begin();tap_comment("async qualification v2: public API owned fixture; QMP HDD throttle required");
    arena=MmAllocateContiguousMemory(DEPTH*STRIDE);
    regression_require(arena!=NULL,"allocate persistent aligned request storage");
    for(ULONG n=0;n<DEPTH;n++) {
        slots[n].buffer=arena+n*STRIDE+GUARD;
        slots[n].event=CreateEvent(NULL,TRUE,FALSE,NULL);
        slots[n].issued=CreateEvent(NULL,TRUE,FALSE,NULL);
        regression_require(slots[n].event && slots[n].issued,"create persistent request events");
    }
    gate=CreateEvent(NULL,TRUE,FALSE,NULL);regression_require(gate!=NULL,"create issuer start gate");
    HANDLE output=open_file(path,GENERIC_WRITE|DELETE,FILE_OVERWRITE_IF,
        FILE_SYNCHRONOUS_IO_NONALERT|FILE_NO_INTERMEDIATE_BUFFERING);
    populate(output,0x37);regression_require(NtClose(output)==0,"close noncached fixture writer");
    HANDLE file=reader();warm(file,0x37);
    LONGLONG before=position(file);
    tap_comment("phase concurrent");concurrent(file,0x37);
    regression_check(position(file)==before,"explicit asynchronous offsets preserve file position");
    tap_comment("phase steady");
    for(ULONG n=0;n<16;n++)queued(file,0x37,4096,n);
    MM_STATISTICS start=statistics();
    for(ULONG n=16;n<272;n++) {
        queued(file,0x37,4096,n);
        if(n%64==15) {
            MM_STATISTICS s=statistics();
            tap_comment("steady round=%lu available=%lu pool=%lu cache=%lu stack=%lu",n,s.AvailablePages,s.PoolPagesCommitted,s.CachePagesCommitted,s.StackPagesCommitted);
        }
    }
    MM_STATISTICS end=statistics();
    tap_comment("steady start available=%lu pool=%lu; end available=%lu pool=%lu",start.AvailablePages,start.PoolPagesCommitted,end.AvailablePages,end.PoolPagesCommitted);
    regression_check(end.AvailablePages+8>=start.AvailablePages,"1024 reads retain available pages within eight-page allowance");
    regression_check(end.PoolPagesCommitted<=start.PoolPagesCommitted+8,"1024 reads retain pool pages within eight-page allowance");
    tap_comment("phase issuer-exit");
    for(ULONG n=0;n<8;n++)exiting_case(file,0x37,n);
    regression_require(NtClose(file)==0,"close persistent lifetime reader");
    tap_comment("phase close");mutation_case(0,0x37);
    tap_comment("phase truncate");mutation_case(1,0x37);
    tap_comment("phase delete");mutation_case(2,0x38);
    tap_comment("totals reads=%lu status_pending=%lu event_unsignaled_on_return=%lu",total_reads,pending_reads,unfinished_reads);
    regression_check(unfinished_reads>32,"real requests remained outstanding after public API return");
    for(ULONG n=0;n<DEPTH;n++){CloseHandle(slots[n].event);CloseHandle(slots[n].issued);}
    CloseHandle(gate);MmFreeContiguousMemory(arena);regression_finish();
}
