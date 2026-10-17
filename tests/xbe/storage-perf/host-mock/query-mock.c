/* Execute the actual public observation source with untouched/partial outputs. */
#include <stdlib.h>
#include <stdarg.h>
#include <setjmp.h>
#define main storage_query_main
#include "query.c"
#undef main
static const char *mode;static UCHAR disk[4096];static jmp_buf stopped;
void *MmAllocateContiguousMemory(ULONG n){return malloc(n);}void MmFreeContiguousMemory(PVOID p){free(p);}
NTSTATUS NtCreateFile(HANDLE *h,ULONG a,OBJECT_ATTRIBUTES *o,IO_STATUS_BLOCK *io,PVOID n,ULONG b,ULONG c,ULONG d,ULONG e){(void)a;(void)n;(void)b;(void)c;(void)d;(void)e;*h=strstr(o->ObjectName->Buffer,"pr248-write")?(HANDLE)4:(strstr(o->ObjectName->Buffer,"CdRom0")?(HANDLE)3:(HANDLE)1);io->Status=0;io->Information=0;return 0;}
NTSTATUS NtDeviceIoControlFile(HANDLE h,PVOID a,PVOID b,PVOID c,IO_STATUS_BLOCK *io,ULONG code,PVOID in,ULONG in_n,PVOID out,ULONG out_n){(void)h;(void)a;(void)b;(void)c;(void)io;(void)code;(void)in;(void)in_n;(void)out;(void)out_n;return STATUS_UNSUCCESSFUL;}
NTSTATUS NtWriteFile(HANDLE h,PVOID a,PVOID b,PVOID c,IO_STATUS_BLOCK *io,PVOID data,ULONG n,LARGE_INTEGER *at){(void)h;(void)a;(void)b;(void)c;(void)at;memcpy(disk,data,n);io->Status=0;io->Information=n;return 0;}
NTSTATUS NtReadFile(HANDLE h,PVOID a,PVOID b,PVOID c,IO_STATUS_BLOCK *io,PVOID data,ULONG n,LARGE_INTEGER *at){(void)a;(void)b;(void)c;(void)at;if(h!=(HANDLE)4||!strcmp(mode,"error-untouched"))return STATUS_UNSUCCESSFUL;if(strcmp(mode,"no-fill"))memcpy(data,disk,!strcmp(mode,"partial")?n/2:n);if(strcmp(mode,"iosb-untouched")){io->Status=0;io->Information=n;}return 0;}
NTSTATUS NtFlushBuffersFile(HANDLE h,IO_STATUS_BLOCK *io){if(h==(HANDLE)4&&!strcmp(mode,"flush-error-untouched"))return STATUS_UNSUCCESSFUL;io->Status=0;return 0;}
NTSTATUS NtClose(HANDLE h){(void)h;return 0;}
NTSTATUS KeDelayExecutionThread(int a,int b,LARGE_INTEGER *d){(void)a;(void)b;(void)d;return 0;}
void HalWriteSMBusValue(int a,int b,int c,int d){(void)a;(void)b;(void)c;(void)d;longjmp(stopped,1);}
void tap_drain(void){}void tap_version(unsigned v){(void)v;}void tap_plan(unsigned v){(void)v;}void tap_ok(unsigned v,const char *s){(void)v;(void)s;}void tap_not_ok(unsigned v,const char *s){(void)v;(void)s;}
void tap_comment(const char *f,...){if(!strstr(f,"STORAGE-PERSIST")&&!(strstr(f,"STORAGE-FLUSH")&&strstr(f,"owned-write-file")))return;va_list a;va_start(a,f);vprintf(f,a);va_end(a);putchar('\n');}
int main(int argc,char **argv){if(argc!=2)return 2;mode=argv[1];if(!setjmp(stopped))storage_query_main();return 0;}
