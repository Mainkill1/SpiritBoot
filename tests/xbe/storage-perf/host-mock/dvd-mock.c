/* Fault injection executes the actual owned DVD loop with synthetic headers. */
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <setjmp.h>
#include <time.h>
#include <unistd.h>
#define main storage_dvd_main
#include "owned-dvd.c"
#undef main
static const char *mode;static unsigned reads;static jmp_buf stopped;static LONGLONG last_delay;
void *MmAllocateContiguousMemory(ULONG n){return malloc(n);}void MmFreeContiguousMemory(PVOID p){free(p);}
NTSTATUS MmQueryStatistics(MM_STATISTICS *s){s->AvailablePages=16000;return 0;}
NTSTATUS NtCreateFile(HANDLE *h,ULONG a,OBJECT_ATTRIBUTES *o,IO_STATUS_BLOCK *io,PVOID n,ULONG b,ULONG c,ULONG d,ULONG e){(void)a;(void)n;(void)b;(void)c;(void)d;(void)e;*h=strstr(o->ObjectName->Buffer,"CdRom0")?(HANDLE)2:(HANDLE)1;io->Status=0;io->Information=0;return 0;}
NTSTATUS NtReadFile(HANDLE h,PVOID a,PVOID b,PVOID c,IO_STATUS_BLOCK *io,PVOID data,ULONG n,LARGE_INTEGER *at){(void)a;(void)b;(void)c;(void)at;
 if(h==(HANDLE)1){const char *plan="{\"resolved_plan\":{\"tests\":[{\"id\":\"dvd-api-leaf-clean.cold-ish\"}]}}";memcpy(data,plan,strlen(plan));io->Status=0;io->Information=strlen(plan);return 0;}
 ++reads;if(!strcmp(mode,"error-untouched"))return STATUS_UNSUCCESSFUL;
 if(strcmp(mode,"no-fill")&&(!strcmp(mode,"fill")||strcmp(mode,"fill-once")||reads==1)){
  memcpy(data,dvd_clean_header,!strcmp(mode,"partial")?n/2:n);
 }
 if(strcmp(mode,"iosb-untouched")){io->Status=0;io->Information=n;}return 0;}
NTSTATUS NtQueryInformationFile(HANDLE h,IO_STATUS_BLOCK *io,PVOID out,ULONG n,ULONG type){(void)h;(void)n;(void)type;((FILE_STANDARD_INFORMATION*)out)->EndOfFile.QuadPart=DVD_CLEAN_FILE_BYTES;io->Status=0;io->Information=sizeof(FILE_STANDARD_INFORMATION);return 0;}
NTSTATUS IoDismountVolumeByName(ANSI_STRING *name){(void)name;return 0;}
NTSTATUS NtClose(HANDLE h){(void)h;return 0;}
ULONGLONG KeQueryPerformanceCounter(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (ULONGLONG)t.tv_sec*1000000000+t.tv_nsec;}
ULONGLONG KeQueryPerformanceFrequency(void){return 1000000000;}
NTSTATUS KeDelayExecutionThread(int a,int b,LARGE_INTEGER *d){(void)a;(void)b;last_delay=d->QuadPart;usleep(10);return 0;}
void HalWriteSMBusValue(int a,int b,int c,int d){(void)a;(void)b;(void)c;(void)d;printf("MOCK-DVD-POWEROFF last_delay_100ns=%lld\n",(long long)last_delay);longjmp(stopped,1);}
void tap_drain(void){}void tap_version(unsigned v){(void)v;}void tap_plan(unsigned v){(void)v;}void tap_ok(unsigned v,const char *s){(void)v;(void)s;}void tap_not_ok(unsigned v,const char *s){(void)v;(void)s;}
void tap_comment(const char *f,...){if(!strstr(f,"STORAGE-PERF-CASE")&&!strstr(f,"STORAGE-PERF-END")&&!strstr(f,"STORAGE-PERF-ERROR"))return;va_list a;va_start(a,f);vprintf(f,a);va_end(a);putchar('\n');}
int main(int argc,char **argv){if(argc!=2)return 2;mode=argv[1];if(!setjmp(stopped))storage_dvd_main();return 0;}
