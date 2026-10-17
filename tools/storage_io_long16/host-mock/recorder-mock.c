/* Actual new production C body with synthetic public kernel-service faults. */
#define STORAGE_IO_HOST_TEST 1
#include <xboxkrnl/xboxkrnl.h>
#include <assert.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include "../recorder.c"
static const char *mode;static ULONG live_allocations,read_calls,write_calls,pass_reads,protection_checks;
static ULONGLONG fake_tick;
static struct Pending {PVOID callback,context,data;IO_STATUS_BLOCK *io;ULONG n,offset;} pending[COUNT];
static ULONG queued,mock_depth;static ULONG mock_pages=14000;static bool protected;
static struct Allocation {PVOID pointer;ULONG pages;} owned[512];
static bool synchronous_seed,raw_device;
ULONGLONG recorder_host_ticks(void){return ++fake_tick;}
static void slab_protect(int permission){if(slab){assert(mprotect(slab,slab_bytes,permission)==0);protected=permission!= (PROT_READ|PROT_WRITE);}}
PVOID MmAllocateContiguousMemory(ULONG n){if(!strcmp(mode,"allocation-failure"))return NULL;void *p=NULL;assert(posix_memalign(&p,4096,(n+4095)&~4095u)==0);for(ULONG i=0;i<512;i++)if(!owned[i].pointer){owned[i]=(struct Allocation){p,(n+4095)/4096};break;}++live_allocations;mock_pages-=(n+4095)/4096;return p;}
void MmFreeContiguousMemory(PVOID p){if(p){bool found=false;for(ULONG i=0;i<512;i++)if(owned[i].pointer==p){mock_pages+=owned[i].pages;owned[i].pointer=NULL;found=true;break;}assert(found);free(p);--live_allocations;}}
NTSTATUS MmQueryStatistics(MM_STATISTICS *m){m->AvailablePages=mock_pages;return 0;}
NTSTATUS NtCreateFile(HANDLE *h,ULONG access,OBJECT_ATTRIBUTES *oa,IO_STATUS_BLOCK *io,PVOID size,ULONG attrs,ULONG share,ULONG disposition,ULONG options){(void)access;(void)size;(void)attrs;(void)share;(void)disposition;synchronous_seed=(options&FILE_SYNCHRONOUS_IO_NONALERT)!=0;raw_device=oa&&oa->ObjectName&&oa->ObjectName->Buffer&&!strcmp(oa->ObjectName->Buffer,"\\Device\\Harddisk0\\Partition0");*h=(HANDLE)1;io->Status=0;io->Information=0;return 0;}
NTSTATUS NtClose(HANDLE h){(void)h;return 0;}
NTSTATUS NtWriteFile(HANDLE h,PVOID event,PVOID cb,PVOID ctx,IO_STATUS_BLOCK *io,PVOID p,ULONG n,LARGE_INTEGER *at){(void)h;(void)event;(void)cb;(void)ctx;(void)p;(void)at;if(!synchronous_seed)return STATUS_PENDING;if(!strcmp(mode,"write-failure")&&++write_calls==10)return STATUS_UNSUCCESSFUL;io->Status=0;io->Information=n;return 0;}
NTSTATUS NtFlushBuffersFile(HANDLE h,IO_STATUS_BLOCK *io){(void)h;if(!strcmp(mode,"flush-unsupported"))return (NTSTATUS)0xc0000010;io->Status=0;io->Information=0;return 0;}
static void verify_all_poisoned(void){
 for(ULONG i=0;i<COUNT;i++){
  struct Observation *o=&records[i];assert(o->buffer==slab+o->slice_offset+o->request->alignment);assert(o->slice_offset+o->slice_bytes<=slab_bytes);
  assert(((uintptr_t)o->buffer&4095)==o->request->alignment);
  for(ULONG j=0;j<o->request->length;j++)assert(o->buffer[j]==(UCHAR)~pattern(o->request->offset+j));
  if(i)assert(records[i-1].slice_offset+records[i-1].slice_bytes<=o->slice_offset);
 }
}
NTSTATUS NtReadFile(HANDLE h,PVOID event,PVOID cb,PVOID ctx,IO_STATUS_BLOCK *io,PVOID data,ULONG n,LARGE_INTEGER *at){
 (void)h;(void)event;assert(!synchronous_seed);if(pass_reads++==0){verify_all_poisoned();if(!strcmp(mode,"protect"))slab_protect(PROT_READ);}
 ULONG logical=(ULONG)(at->QuadPart-(raw_device?RAW_DEVICE_BASE:0));
 ++read_calls;
 if(!strcmp(mode,"submit-error")&&read_calls==10)return STATUS_UNSUCCESSFUL;
 if(!strcmp(mode,"apc-before-return")){
  for(ULONG j=0;j<n;j++)((UCHAR *)data)[j]=pattern(logical+j);
  io->Status=0;io->Information=n;((void (*)(PVOID,PIO_STATUS_BLOCK,ULONG))cb)(ctx,io,0);return STATUS_PENDING;
 }
 assert(queued<COUNT);pending[queued++]=(struct Pending){cb,ctx,data,io,n,logical};return STATUS_PENDING;
}
NTSTATUS KeDelayExecutionThread(int mode_unused,int alert,LARGE_INTEGER *delay){
 (void)mode_unused;(void)delay;assert(alert);
 if(!queued){ULONG settled=0,live=0;for(ULONG i=0;i<COUNT;i++)settled+=records[i].settled!=0;for(ULONG i=0;i<DEPTH;i++)live+=active[i]!=NULL;fprintf(stderr,"empty wait submissions=%u settled=%u active=%u reads=%u\n",actual_submissions,settled,live,read_calls);abort();}
 ULONG n=queued;queued=0;
 if(!strcmp(mode,"no-apc")){fake_tick+=NOMINAL_HZ*31;queued=n;return 0;}
 if(!strcmp(mode,"clock-rollback")&&read_calls<=mock_depth)fake_tick=0;
 for(ULONG i=0;i<n;i++){
  struct Pending *p=&pending[i];if(protected)slab_protect(PROT_READ|PROT_WRITE);
  bool nofill=!strcmp(mode,"no-fill")||(!strcmp(mode,"no-fill-measured")&&read_calls>COUNT);
  ULONG fill=!strcmp(mode,"partial-fill")?p->n/2:p->n;
  UCHAR *dst=(!strcmp(mode,"alias")&&read_calls>1)?records[0].buffer:p->data;
  if(!nofill)for(ULONG j=0;j<fill;j++)dst[j]=pattern(p->offset+j);
  if(!strcmp(mode,"late-mutation")&&read_calls>COUNT/2)records[0].buffer[0]=(UCHAR)~pattern(records[0].request->offset);
  if(!strcmp(mode,"prefix-corruption"))slab[records[0].slice_offset]=CANARY^1;
  p->io->Status=!strcmp(mode,"wrong-status")?STATUS_UNSUCCESSFUL:0;p->io->Information=!strcmp(mode,"wrong-info")?p->n-1:p->n;
  if(!strcmp(mode,"protect")){slab_protect(PROT_NONE);++protection_checks;}
  IO_STATUS_BLOCK foreign={0};((void (*)(PVOID,PIO_STATUS_BLOCK,ULONG))p->callback)(p->context,!strcmp(mode,"wrong-pointer")?&foreign:p->io,0);
  if(!strcmp(mode,"duplicate-apc"))((void (*)(PVOID,PIO_STATUS_BLOCK,ULONG))p->callback)(p->context,p->io,0);
  if(!strcmp(mode,"protect"))slab_protect(PROT_READ);
 }
 return 0;
}
void tap_comment(const char *fmt,...){
 va_list a;va_start(a,fmt);char text[1024];vsnprintf(text,sizeof(text),fmt,a);va_end(a);
 if(strstr(text,"phase=oracle_begin")&&protected)slab_protect(PROT_READ|PROT_WRITE);
 if(strstr(text,"phase=prepared"))pass_reads=0;
 if(strstr(text,"V6-META")||strstr(text,"V6-CASE")||strstr(text,"V6-ORACLE-FAIL")||strstr(text,"V6-SETUP")||strstr(text,"V6-END")||strstr(text,"V6-ERROR"))puts(text);
}
void tap_drain(void){}void tap_version(unsigned x){(void)x;}void tap_plan(unsigned x){(void)x;}void tap_ok(unsigned x,const char *s){(void)x;(void)s;}void tap_not_ok(unsigned x,const char *s){(void)x;(void)s;}
int main(int argc,char **argv){
 assert(argc==6);mode=argv[1];ULONG dataset=atoi(argv[2]),depth=atoi(argv[3]),pressure_target=atoi(argv[4]);bool warm=atoi(argv[5]);
 mock_depth=depth;int failed=recorder_execute(dataset,depth,pressure_target,warm);
 printf("VERDICT %s cleanup_live_allocations=%u callback_protection_checks=%u route=%s\n",failed?"failed":"passed",live_allocations,protection_checks,raw_device?"raw-device":"fatx-file");
 if(!strcmp(mode,"no-apc")){assert(callbacks_live&&live_allocations>0);}else {assert(queued==0);assert(live_allocations==0);}return 0;
}
