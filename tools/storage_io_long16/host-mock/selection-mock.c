/* The actual production selection body, with only public file calls mocked. */
#define main unused_native_entry
#include "../main.c"
#undef main
#include <stdlib.h>
static const char *chosen;
NTSTATUS NtCreateFile(HANDLE *h,ULONG a,OBJECT_ATTRIBUTES *o,IO_STATUS_BLOCK *io,PVOID n,ULONG b,ULONG c,ULONG d,ULONG e){(void)a;(void)o;(void)n;(void)b;(void)c;(void)d;(void)e;*h=(HANDLE)1;io->Status=0;io->Information=0;return 0;}
NTSTATUS NtReadFile(HANDLE h,PVOID e,PVOID cb,PVOID ctx,IO_STATUS_BLOCK *io,PVOID data,ULONG n,LARGE_INTEGER *at){(void)h;(void)e;(void)cb;(void)ctx;(void)at;char document[512];if(!strcmp(chosen,"multiple"))snprintf(document,sizeof(document),"{\"resolved_plan\":{\"tests\":[{\"id\":\"fatx-d1-q4-p0-synthetic.warm\"},{\"id\":\"fatx-d0-q1-p0-synthetic.warm\"}]}}");else snprintf(document,sizeof(document),"{\"resolved_plan\":{\"tests\":[{\"id\":\"%s\"}]}}",chosen);size_t size=strlen(document);if(size>n)return STATUS_UNSUCCESSFUL;memcpy(data,document,size);io->Status=0;io->Information=size;return 0;}
NTSTATUS NtClose(HANDLE h){(void)h;return 0;}
int recorder_execute(ULONG d,ULONG q,ULONG p,bool warm){(void)d;(void)q;(void)p;(void)warm;return 0;}
NTSTATUS KeDelayExecutionThread(int m,int a,LARGE_INTEGER *d){(void)m;(void)a;(void)d;return 0;}
void HalWriteSMBusValue(int a,int b,int c,int d){(void)a;(void)b;(void)c;(void)d;abort();}
void tap_comment(const char *f,...){(void)f;}void tap_drain(void){}void tap_version(unsigned n){(void)n;}void tap_plan(unsigned n){(void)n;}void tap_ok(unsigned n,const char *s){(void)n;(void)s;}void tap_not_ok(unsigned n,const char *s){(void)n;(void)s;}
int main(int argc,char **argv){if(argc!=2)return 3;chosen=argv[1];ULONG d,q,p;bool warm;char selected[96];if(!select_case(&d,&q,&p,&warm,selected,sizeof(selected)))return 2;printf("selected=%s d=%u q=%u p=%u warm=%u\n",selected,d,q,p,warm?1:0);return 0;}
