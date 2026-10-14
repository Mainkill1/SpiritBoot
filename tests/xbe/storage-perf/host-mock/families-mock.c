/* Synthetic statuses/media fault injection for actual independently owned C fixture. */
#include <xboxkrnl/xboxkrnl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <setjmp.h>
#include <time.h>
#include <unistd.h>
#include "tap.h"
char storage_selected_id[96]="write-api-flush-reopen.cold-ish";
char storage_selected_base[96]="write-api-flush-reopen";
char storage_selected_cache[16]="cold-ish";
int storage_warmup_only;
static UCHAR disk[4*1024*1024];static const char *mode;static jmp_buf stopped;
void *MmAllocateContiguousMemory(ULONG n){return malloc(n);}void MmFreeContiguousMemory(PVOID p){free(p);}
NTSTATUS MmQueryStatistics(MM_STATISTICS *s){s->AvailablePages=16000;return 0;}
NTSTATUS NtCreateFile(HANDLE *h,ULONG a,OBJECT_ATTRIBUTES *o,IO_STATUS_BLOCK *io,PVOID n,ULONG b,ULONG c,ULONG d,ULONG e){(void)a;(void)o;(void)n;(void)b;(void)c;(void)d;(void)e;*h=(HANDLE)1;io->Status=0;io->Information=0;return 0;}
NTSTATUS NtWriteFile(HANDLE h,PVOID a,PVOID b,PVOID c,IO_STATUS_BLOCK *io,PVOID data,ULONG n,LARGE_INTEGER *at){(void)h;(void)a;(void)b;(void)c;memcpy(disk+at->QuadPart,data,n);io->Status=0;io->Information=n;return 0;}
NTSTATUS NtReadFile(HANDLE h,PVOID a,PVOID b,PVOID c,IO_STATUS_BLOCK *io,PVOID data,ULONG n,LARGE_INTEGER *at){(void)h;(void)a;(void)b;(void)c;
 if(!strcmp(mode,"error-untouched"))return STATUS_UNSUCCESSFUL;
 if(strcmp(mode,"no-fill")){if(!strcmp(mode,"partial")){memcpy(data,disk+at->QuadPart,n/2);}else memcpy(data,disk+at->QuadPart,n);}
 if(strcmp(mode,"iosb-untouched")){io->Status=0;io->Information=n;}return 0;}
NTSTATUS NtReadFileScatter(HANDLE h,PVOID a,PVOID b,PVOID c,IO_STATUS_BLOCK *io,FILE_SEGMENT_ELEMENT *p,ULONG n,LARGE_INTEGER *at){(void)h;(void)a;(void)b;(void)c;(void)p;(void)n;(void)at;io->Status=STATUS_UNSUCCESSFUL;return STATUS_UNSUCCESSFUL;}
NTSTATUS NtFlushBuffersFile(HANDLE h,IO_STATUS_BLOCK *io){(void)h;io->Status=0;/* deliberately preserve previous information to test stale IOSB */return 0;}
NTSTATUS NtClose(HANDLE h){(void)h;return 0;}
ULONGLONG KeQueryPerformanceCounter(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (ULONGLONG)t.tv_sec*1000000000+t.tv_nsec;}
ULONGLONG KeQueryPerformanceFrequency(void){return 1000000000;}
NTSTATUS KeDelayExecutionThread(int a,int b,LARGE_INTEGER *d){(void)a;(void)b;(void)d;usleep(10);return 0;}
void HalWriteSMBusValue(int a,int b,int c,int d){(void)a;(void)b;(void)c;(void)d;longjmp(stopped,1);}
void tap_drain(void){}void tap_version(unsigned v){(void)v;}void tap_plan(unsigned v){(void)v;}void tap_ok(unsigned v,const char *s){(void)v;(void)s;}void tap_not_ok(unsigned v,const char *s){(void)v;(void)s;}
void tap_comment(const char *f,...){if(!strstr(f,"STORAGE-PERF-CASE")&&!strstr(f,"STORAGE-PERF-END")&&!strstr(f,"STORAGE-PERF-ERROR"))return;va_list a;va_start(a,f);vprintf(f,a);va_end(a);putchar('\n');}
int storage_families_main(void);
int main(int argc,char **argv){if(argc!=2)return 2;mode=argv[1];if(!setjmp(stopped))storage_families_main();return 0;}
