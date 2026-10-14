/* Execute the actual owned Win32 wrapper with synthetic lifetime API outcomes. */
#include <stdio.h>
#include <string.h>
#include <setjmp.h>
#define __declspec(x)
#define __stdcall
#include "../windows-launch.c"
static jmp_buf ended;
static const char *fault;
static unsigned order, assign_order, resume_order, created_flags, kills, process_kills;
static DWORD exit_status;
static WCHAR environment_root[] = L"C:\\Windows";
static WCHAR evidence_root[] = L"C:\\owned-evidence";
static WCHAR argument_line[] = L"native-launch.exe -config_path owned.toml";
static DWORD copy_wide(WCHAR *out, const WCHAR *in, DWORD capacity) {
    DWORD n=0; while(in[n]) ++n;
    if(n+1>capacity) return n+1;
    for(DWORD i=0;i<=n;i++)out[i]=in[i]; return n;
}
DWORD GetModuleFileNameW(HANDLE a,WCHAR *b,DWORD n){(void)a;return copy_wide(b,argument_line,n);}
DWORD GetEnvironmentVariableW(const WCHAR *name,WCHAR *out,DWORD n){return copy_wide(out,equal_wide(name,(WCHAR*)L"SystemRoot")?environment_root:evidence_root,n);}
WCHAR *GetCommandLineW(void){return argument_line;}
BOOL SetEnvironmentVariableW(const WCHAR *a,const WCHAR *b){(void)a;(void)b;return 1;}
DWORD GetCurrentThreadId(void){return 7;}
HANDLE GetProcessWindowStation(void){return (HANDLE)1;}
HANDLE GetThreadDesktop(DWORD id){(void)id;return (HANDLE)2;}
BOOL GetUserObjectInformationW(HANDLE h,int kind,void *out,DWORD bytes,DWORD *needed){(void)kind;*needed=16;copy_wide(out,h==(HANDLE)1?(WCHAR*)L"WinSta0":(WCHAR*)L"Default",bytes/2);return 1;}
HANDLE GetStdHandle(DWORD id){(void)id;return (HANDLE)3;}
BOOL CreateProcessW(const WCHAR *a,WCHAR *b,void *c,void *d,BOOL e,DWORD flags,void *f,const WCHAR *g,STARTUPINFOW *s,PROCESS_INFORMATION *p){(void)a;(void)b;(void)c;(void)d;(void)e;(void)f;(void)g;(void)s;created_flags=flags;p->process=(HANDLE)10;p->thread=(HANDLE)11;p->pid=99;return 1;}
DWORD WaitForSingleObject(HANDLE h,DWORD timeout){(void)h;(void)timeout;return !strcmp(fault,"timeout")?258:0;}
BOOL GetExitCodeProcess(HANDLE h,DWORD *code){(void)h;*code=0;return 1;}
BOOL CloseHandle(HANDLE h){(void)h;return 1;}
void ExitProcess(DWORD code){exit_status=code;longjmp(ended,1);}
HANDLE CreateJobObjectW(void *a,const WCHAR *b){(void)a;(void)b;return (HANDLE)20;}
BOOL SetInformationJobObject(HANDLE h,int c,void *info,DWORD n){(void)h;(void)c;(void)info;return n==144;}
BOOL AssignProcessToJobObject(HANDLE h,HANDLE p){(void)h;(void)p;assign_order=++order;return strcmp(fault,"assign-failure")!=0;}
DWORD ResumeThread(HANDLE h){(void)h;resume_order=++order;return 1;}
BOOL TerminateJobObject(HANDLE h,unsigned code){(void)h;(void)code;++kills;return 1;}
BOOL TerminateProcess(HANDLE h,unsigned code){(void)h;(void)code;++process_kills;return 1;}
BOOL QueryInformationJobObject(HANDLE h,int c,void *info,DWORD n,DWORD *written){(void)h;(void)c;memset(info,0,n);((DWORD*)info)[10]=kills&&strcmp(fault,"rundown-unconfirmed")?0:2;if(written)*written=n;return strcmp(fault,"query-failure")!=0;}
DWORD GetTickCount(void){static DWORD tick;tick+=100;return tick;}
void Sleep(DWORD ms){(void)ms;}
HANDLE CreateFileW(const WCHAR *p,DWORD a,DWORD b,void *c,DWORD d,DWORD e,HANDLE f){(void)p;(void)a;(void)b;(void)c;(void)d;(void)e;(void)f;return (HANDLE)30;}
BOOL WriteFile(HANDLE h,const void *p,DWORD n,DWORD *written,void *o){(void)h;(void)p;(void)o;*written=n;return 1;}
DWORD GetLastError(void){return 5;}
int main(int argc,char **argv){if(argc!=2)return 2;fault=argv[1];if(!setjmp(ended))mainCRTStartup();printf("flags=%u assign_order=%u resume_order=%u job_kills=%u process_kills=%u exit=%u\n",created_flags,assign_order,resume_order,kills,process_kills,(unsigned)exit_status);return 0;}
