/* SPDX-License-Identifier: GPL-2.0-or-later
 * Public Win32 ABI; USER desktop PowerShell pipe, owned bounded job lifetime. */
typedef unsigned short WCHAR;
typedef unsigned int DWORD;
typedef int BOOL;
typedef void *HANDLE;
typedef __UINTPTR_TYPE__ SIZE_T;
typedef unsigned long long U64;
typedef struct {DWORD cb;WCHAR *reserved,*desktop,*title;DWORD x,y,xsize,ysize,xchars,ychars,fill,flags;unsigned short show,reserved2size;unsigned char *reserved2;HANDLE in,out,err;} STARTUPINFOW;
typedef struct {HANDLE process,thread;DWORD pid,tid;} PROCESS_INFORMATION;
typedef struct {U64 process_time,job_time;DWORD flags;SIZE_T min_working_set,max_working_set;DWORD active_limit;SIZE_T affinity;DWORD priority,scheduling;} BASIC_LIMITS;
typedef struct {U64 read_ops,write_ops,other_ops,read_bytes,write_bytes,other_bytes;} IO_COUNTERS;
typedef struct {BASIC_LIMITS basic;IO_COUNTERS io;SIZE_T process_memory,job_memory,peak_process_memory,peak_job_memory;} EXTENDED_LIMITS;
typedef struct {U64 user_time,kernel_time,period_user_time,period_kernel_time;DWORD faults,total_processes,active_processes,total_terminated;} BASIC_ACCOUNTING;
_Static_assert(sizeof(EXTENDED_LIMITS)==144,"public Win64 job limit ABI");
_Static_assert(sizeof(BASIC_ACCOUNTING)==48,"public Win64 accounting ABI");
__declspec(dllimport) DWORD __stdcall GetModuleFileNameW(HANDLE,WCHAR*,DWORD);
__declspec(dllimport) DWORD __stdcall GetEnvironmentVariableW(const WCHAR*,WCHAR*,DWORD);
__declspec(dllimport) WCHAR *__stdcall GetCommandLineW(void);
__declspec(dllimport) BOOL __stdcall SetEnvironmentVariableW(const WCHAR*,const WCHAR*);
__declspec(dllimport) BOOL __stdcall CreateProcessW(const WCHAR*,WCHAR*,void*,void*,BOOL,DWORD,void*,const WCHAR*,STARTUPINFOW*,PROCESS_INFORMATION*);
__declspec(dllimport) DWORD __stdcall WaitForSingleObject(HANDLE,DWORD);
__declspec(dllimport) BOOL __stdcall GetExitCodeProcess(HANDLE,DWORD*);
__declspec(dllimport) BOOL __stdcall CloseHandle(HANDLE);
__declspec(dllimport) HANDLE __stdcall GetStdHandle(DWORD);
__declspec(dllimport) void __stdcall ExitProcess(DWORD);
__declspec(dllimport) HANDLE __stdcall CreateJobObjectW(void*,const WCHAR*);
__declspec(dllimport) BOOL __stdcall SetInformationJobObject(HANDLE,int,void*,DWORD);
__declspec(dllimport) BOOL __stdcall AssignProcessToJobObject(HANDLE,HANDLE);
__declspec(dllimport) BOOL __stdcall QueryInformationJobObject(HANDLE,int,void*,DWORD,DWORD*);
__declspec(dllimport) BOOL __stdcall TerminateJobObject(HANDLE,unsigned int);
__declspec(dllimport) BOOL __stdcall TerminateProcess(HANDLE,unsigned int);
__declspec(dllimport) DWORD __stdcall ResumeThread(HANDLE);
__declspec(dllimport) DWORD __stdcall GetTickCount(void);
__declspec(dllimport) void __stdcall Sleep(DWORD);
__declspec(dllimport) HANDLE __stdcall CreateFileW(const WCHAR*,DWORD,DWORD,void*,DWORD,DWORD,HANDLE);
__declspec(dllimport) BOOL __stdcall WriteFile(HANDLE,const void*,DWORD,DWORD*,void*);
__declspec(dllimport) DWORD __stdcall GetLastError(void);
static WCHAR root[1024],exe[2048],cmd[32768],station[128],desktop[128],evidence[4096];
static EXTENDED_LIMITS limits;
static char receipt[1024];
#include "pipe-commands.h"
__declspec(dllimport) DWORD __stdcall GetCurrentThreadId(void);
__declspec(dllimport) HANDLE __stdcall GetProcessWindowStation(void);
__declspec(dllimport) HANDLE __stdcall GetThreadDesktop(DWORD);
__declspec(dllimport) BOOL __stdcall GetUserObjectInformationW(HANDLE,int,void*,DWORD,DWORD*);
static BOOL equal_wide(const WCHAR *a,const WCHAR *b){while(*a&&*a==*b){++a;++b;}return *a==*b;}
static void append(WCHAR *out,const WCHAR *in){while(*out)++out;while((*out++=*in++));}
static WCHAR *skip_executable(WCHAR *text){if(*text=='"'){++text;while(*text&&*text!='"')++text;if(*text)++text;}else while(*text&&*text!=' ')++text;while(*text==' ')++text;return text;}
static void field(const char *key,DWORD value){char *out=receipt;while(*out)++out;while(*key)*out++=*key++;*out++='=';char digits[10];DWORD count=0;do{digits[count++]=(char)('0'+value%10);value/=10;}while(value);while(count)*out++=digits[--count];*out++='\n';*out=0;}
static BOOL write_receipt(void){DWORD length=GetEnvironmentVariableW((const WCHAR*)L"PR248_NATIVE_EVIDENCE",evidence,4096);if(!length||length>4000)return 0;append(evidence,(const WCHAR*)L"\\native-job-lifetime.txt");HANDLE f=CreateFileW(evidence,0x40000000,1,(void*)0,2,0x80,(HANDLE)0);if(f==(HANDLE)(SIZE_T)-1)return 0;DWORD n=0,written=0;while(receipt[n])++n;BOOL ok=WriteFile(f,receipt,n,&written,(void*)0)&&written==n;CloseHandle(f);return ok;}
void mainCRTStartup(void){
    if(!GetEnvironmentVariableW((const WCHAR*)L"SystemRoot",root,1024))ExitProcess(110);
    append(exe,root);append(exe,(const WCHAR*)L"\\System32\\WindowsPowerShell\\v1.0\\powershell.exe");
    DWORD required=0;
    if(!GetUserObjectInformationW(GetProcessWindowStation(),2,station,sizeof(station),&required) ||
       !GetUserObjectInformationW(GetThreadDesktop(GetCurrentThreadId()),2,desktop,sizeof(desktop),&required))ExitProcess(114);
    if(!equal_wide(station,(const WCHAR*)L"WinSta0") || !equal_wide(desktop,(const WCHAR*)L"Default"))ExitProcess(115);
    SetEnvironmentVariableW((const WCHAR*)L"PR248_NATIVE_WINDOW_STATION",station);
    SetEnvironmentVariableW((const WCHAR*)L"PR248_NATIVE_DESKTOP",desktop);
    SetEnvironmentVariableW((const WCHAR*)L"PR248_NATIVE_ARGUMENT_LINE",skip_executable(GetCommandLineW()));
    SetEnvironmentVariableW((const WCHAR*)L"PR248_NATIVE_SERVER_COMMAND",PIPE_SERVER_COMMAND);
    append(cmd,(const WCHAR*)L"\"");append(cmd,exe);
    append(cmd,(const WCHAR*)L"\" -NoProfile -NonInteractive -EncodedCommand ");append(cmd,PIPE_CLIENT_COMMAND);
    /* This anonymous job handle is not inherited: wrapper failure closes the
       last handle and kills descendants. No child uses breakaway flags. */
    HANDLE job=CreateJobObjectW((void*)0,(WCHAR*)0);if(!job)ExitProcess(116);
    limits.basic.flags=0x2000; /* JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE */
    if(!SetInformationJobObject(job,9,&limits,sizeof(limits))){CloseHandle(job);ExitProcess(117);}
    STARTUPINFOW start={0};PROCESS_INFORMATION process={0};start.cb=sizeof(start);start.flags=0x100;
    start.in=GetStdHandle((DWORD)-10);start.out=GetStdHandle((DWORD)-11);start.err=GetStdHandle((DWORD)-12);
    /* Assign while suspended. Failed assignment terminates this exact handle
       without executing client code; there is no uncontained fallback. */
    if(!CreateProcessW(exe,cmd,(void*)0,(void*)0,1,4,(void*)0,(WCHAR*)0,&start,&process)){CloseHandle(job);ExitProcess(112);}
    DWORD status=119,wait_result=0xffffffff,assigned=0,resumed=0;
    if(!AssignProcessToJobObject(job,process.process)){
        TerminateProcess(process.process,119);WaitForSingleObject(process.process,5000);
    }else{
        assigned=1;
        if(ResumeThread(process.thread)==0xffffffff)status=120;
        else{
            resumed=1;wait_result=WaitForSingleObject(process.process,170000);
            if(wait_result==0){if(!GetExitCodeProcess(process.process,&status)||status==259)status=121;}
            else status=wait_result==258?124:125;
        }
    }
    /* Clear owned descendants even after the client exits with an orphan.
       The job handle stays authoritative after all parents have exited. */
    BOOL terminated=TerminateJobObject(job,126);
    BASIC_ACCOUNTING accounting={0};DWORD query_ok=0,cleared=0,start_tick=GetTickCount();
    do{
        query_ok=QueryInformationJobObject(job,1,&accounting,sizeof(accounting),(DWORD*)0);
        if(query_ok&&accounting.active_processes==0){cleared=1;break;}
        Sleep(10);
    }while((DWORD)(GetTickCount()-start_tick)<5000);
    field("version",2);field("client_pid",process.pid);field("client_suspended_before_assignment",1);
    field("assigned_to_owned_job",assigned);field("client_resumed",resumed);field("client_wait_result",wait_result);
    field("client_deadline_ms",170000);field("kill_on_job_close",1);field("job_terminate_succeeded",terminated);
    field("job_query_succeeded",query_ok);field("active_processes_after_cleanup",accounting.active_processes);
    field("owned_descendants_cleared",cleared);field("client_exit_status",status);
    BOOL recorded=write_receipt();CloseHandle(process.thread);CloseHandle(process.process);CloseHandle(job);
    if(!cleared||!terminated)status=127;if(!recorded)status=128;ExitProcess(status);
}
