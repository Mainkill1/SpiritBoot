/* SPDX-License-Identifier: GPL-2.0-or-later
 * Public-API diagnostic derived from recorder generation 3. This generation
 * adds one disposable raw-device control to the order-aware timing split.
 */
#include <xboxkrnl/xboxkrnl.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "tap.h"
#include "replay-requests.h"
#define COUNT 1024u
#define DEPTH 12u
#define PAGE 4096u
#define CHUNK 65536u
#define FILE_BYTES 51625984u
#define RAW_DEVICE_BASE 7937024000ull
#define CANARY 0xd3u
#define NOMINAL_HZ 733333333ull
#ifndef STATUS_INVALID_DEVICE_REQUEST
#define STATUS_INVALID_DEVICE_REQUEST ((NTSTATUS)0xc0000010)
#endif
_Static_assert(sizeof(requests)/sizeof(requests[0])==2*COUNT,"exact two public1024-request metadata sequences required");
_Static_assert(sizeof(ULONG)==4,"public Xbox ULONG ABI required");
static const char data_path[]="\\Device\\Harddisk0\\Partition1\\pr248-v3-generated-replay.tmp";
static const char raw_path[]="\\Device\\Harddisk0\\Partition0";
struct Observation {
 const struct Request *request;
 UCHAR *buffer;
 ULONG slice_offset,slice_bytes;
 IO_STATUS_BLOCK io;
 volatile ULONG apcs,settled;
 ULONG submit,callback_status,callback_information,pointer_match;
 bool oracle_good;
 ULONGLONG issue,submit_return,apc_entry,ready;
};
static struct Observation records[COUNT];
static struct Observation *active[DEPTH];
static UCHAR *slab,*seed_block;
static ULONG slab_bytes,payload_bytes,pressure_count,foreign_callbacks;
static PVOID pressure[256];
static HANDLE file_handle;
static bool callbacks_live;
static ULONGLONG apc_batch_ticks,caller_batch_ticks,first_issue,last_ready,last_caller,lifetime_ticks;
static ULONGLONG submit_ticks,post_return_ticks,return_after_apc_ticks;
static ULONG max_active_slots,actual_submissions,oracle_failures;
static ULONG verified_operations,verified_bytes;
static bool raw_device;
static NTSTATUS seed_flush_status;
#ifdef STORAGE_IO_HOST_TEST
ULONGLONG recorder_host_ticks(void);
static ULONGLONG ticks(void){return recorder_host_ticks();}
#else
static ULONGLONG ticks(void){ULONG a,d;__asm__ __volatile__("rdtsc":"=a"(a),"=d"(d)::"memory");return ((ULONGLONG)d<<32)|a;}
#endif
static UCHAR pattern(ULONG offset){return (UCHAR)((offset*37u)^(offset>>8)^(offset>>17)^0xa7u);}
static bool free_pages(ULONG *pages){MM_STATISTICS s={0};s.Length=sizeof(s);if(MmQueryStatistics(&s)!=0)return false;*pages=s.AvailablePages;return true;}
static void phase(const char *name){tap_comment("STORAGE-IO-V6-PHASE phase=%s",name);tap_drain();}
static bool restore_pressure(void){
 ULONG pages;if(!free_pages(&pages))return false;
 while(pages<900&&pressure_count){MmFreeContiguousMemory(pressure[--pressure_count]);if(!free_pages(&pages))return false;}
 while(pages>900&&pressure_count<256){ULONG n=pages-900;if(n>64)n=64;PVOID p=MmAllocateContiguousMemory(n*PAGE);if(!p)return false;pressure[pressure_count++]=p;if(!free_pages(&pages))return false;}
 return pages==900;
}
static bool allocate_resident(ULONG dataset){
 ULONG cursor=0;payload_bytes=0;memset(records,0,sizeof(records));
 for(ULONG i=0;i<COUNT;i++){
  const struct Request *r=&requests[dataset*COUNT+i];
  if(r->length==0||r->length>CHUNK||r->alignment>=PAGE||r->offset>FILE_BYTES-r->length)return false;
  ULONG span=(r->alignment+r->length+PAGE-1)&~(PAGE-1);
  if(cursor>0xffffffffu-span)return false;
  records[i].request=r;records[i].slice_offset=cursor;records[i].slice_bytes=span;cursor+=span;payload_bytes+=r->length;
 }
 if(cursor!=(dataset?10477568u:14823424u)||payload_bytes!=(dataset?6526464u:10871296u))return false;
 slab_bytes=cursor;slab=MmAllocateContiguousMemory(slab_bytes);if(!slab||((uintptr_t)slab&(PAGE-1)))return false;
 for(ULONG i=0;i<COUNT;i++)records[i].buffer=slab+records[i].slice_offset+records[i].request->alignment;
 seed_block=MmAllocateContiguousMemory(CHUNK);return seed_block!=NULL;
}
static bool open_data(bool write){
 const char *path=raw_device?raw_path:data_path;ANSI_STRING name={(USHORT)strlen(path),(USHORT)(strlen(path)+1),(PCHAR)path};OBJECT_ATTRIBUTES a={0};IO_STATUS_BLOCK io;memset(&io,0x5a,sizeof(io));a.ObjectName=&name;a.Attributes=OBJ_CASE_INSENSITIVE;
 ULONG disposition=raw_device?FILE_OPEN:(write?FILE_SUPERSEDE:FILE_OPEN);ULONG share=raw_device?(FILE_SHARE_READ|FILE_SHARE_WRITE):FILE_SHARE_READ;
 NTSTATUS s=NtCreateFile(&file_handle,GENERIC_READ|(write?GENERIC_WRITE:0)|SYNCHRONIZE,&a,&io,NULL,FILE_ATTRIBUTE_NORMAL,share,disposition,FILE_NO_INTERMEDIATE_BUFFERING|FILE_NON_DIRECTORY_FILE|(write?FILE_SYNCHRONOUS_IO_NONALERT:0));
 return s==0&&io.Status==0;
}
static bool seed_file(void){
 IO_STATUS_BLOCK io;for(ULONG offset=0;offset<FILE_BYTES;offset+=CHUNK){ULONG n=FILE_BYTES-offset;if(n>CHUNK)n=CHUNK;for(ULONG j=0;j<n;j++)seed_block[j]=pattern(offset+j);LARGE_INTEGER at={.QuadPart=(raw_device?RAW_DEVICE_BASE:0)+offset};memset(&io,0x5a,sizeof(io));NTSTATUS s=NtWriteFile(file_handle,NULL,NULL,NULL,&io,seed_block,n,&at);if(s!=0||io.Status!=0||io.Information!=n){tap_comment("STORAGE-IO-V6-ERROR stage=seed-write logical_offset=%u device_offset=%llu bytes=%u submit_status=%08x io_status=%08x information=%u",(unsigned)offset,(ULONGLONG)at.QuadPart,(unsigned)n,(unsigned)s,(unsigned)io.Status,(unsigned)io.Information);return false;}}
 memset(&io,0x5a,sizeof(io));NTSTATUS s=NtFlushBuffersFile(file_handle,&io);seed_flush_status=s;if(raw_device&&s==(NTSTATUS)STATUS_INVALID_DEVICE_REQUEST)return true;if(s!=0||io.Status!=0){tap_comment("STORAGE-IO-V6-ERROR stage=seed-flush submit_status=%08x io_status=%08x information=%u",(unsigned)s,(unsigned)io.Status,(unsigned)io.Information);return false;}return true;
}
static void prepare_buffers(void){
 memset(slab,CANARY,slab_bytes);
 for(ULONG i=0;i<COUNT;i++){
  struct Observation *o=&records[i];for(ULONG j=0;j<o->request->length;j++)o->buffer[j]=(UCHAR)~pattern(o->request->offset+j);
  memset(&o->io,0x5a,sizeof(o->io));o->apcs=o->settled=0;o->submit=0x5a5a5a5a;o->callback_status=o->callback_information=0x5a5a5a5a;o->pointer_match=0;o->oracle_good=false;o->issue=o->submit_return=o->apc_entry=o->ready=0;
 }
 memset(active,0,sizeof(active));foreign_callbacks=0;phase("prepared");
}
static void NTAPI completion(PVOID context,PIO_STATUS_BLOCK io,ULONG reserved){
 ULONGLONG entered=ticks();(void)reserved;uintptr_t p=(uintptr_t)context,first=(uintptr_t)records;
 if(p<first||p>=first+sizeof(records)||(p-first)%sizeof(records[0])){++foreign_callbacks;return;}
 struct Observation *o=context;++o->apcs;
 if(o->apcs==1){o->apc_entry=entered;o->ready=entered;o->pointer_match=io==&o->io;o->callback_status=o->io.Status;o->callback_information=o->io.Information;}
 __asm__ __volatile__("":::"memory");o->settled=1;
}
static bool run_batch(ULONG depth){
 ULONG next=0,finished=0,outstanding=0;max_active_slots=actual_submissions=0;first_issue=last_ready=last_caller=apc_batch_ticks=caller_batch_ticks=lifetime_ticks=submit_ticks=post_return_ticks=return_after_apc_ticks=0;
 callbacks_live=true;ULONGLONG timeout_start=ticks();
 while(finished<COUNT){
  for(ULONG slot=0;slot<depth;slot++)if(active[slot]&&active[slot]->settled){active[slot]=NULL;--outstanding;++finished;}
  for(ULONG slot=0;slot<depth&&next<COUNT;slot++)if(!active[slot]){
   struct Observation *o=&records[next++];active[slot]=o;LARGE_INTEGER at={.QuadPart=(raw_device?RAW_DEVICE_BASE:0)+o->request->offset};o->issue=ticks();if(!first_issue)first_issue=o->issue;
   NTSTATUS s=NtReadFile(file_handle,NULL,completion,o,&o->io,o->buffer,o->request->length,&at);o->submit_return=ticks();o->submit=s;++actual_submissions;++outstanding;if(outstanding>max_active_slots)max_active_slots=outstanding;
   if(s!=STATUS_SUCCESS&&s!=STATUS_PENDING)o->settled=1; /* Failure, never a fabricated APC/ready timestamp. */
  }
  bool pending=false;for(ULONG slot=0;slot<depth;slot++)if(active[slot]&&!active[slot]->settled)pending=true;
  if(pending){LARGE_INTEGER yield={0};KeDelayExecutionThread(UserMode,TRUE,&yield);}
  if(ticks()-timeout_start>NOMINAL_HZ*30){tap_comment("STORAGE-IO-V6-ERROR stage=timeout outstanding=%u buffers_retained_until_poweroff=1",(unsigned)outstanding);return false;}
 }
 callbacks_live=false;
 for(ULONG i=0;i<COUNT;i++){ULONGLONG caller=records[i].ready>records[i].submit_return?records[i].ready:records[i].submit_return;if(records[i].ready>last_ready)last_ready=records[i].ready;if(caller>last_caller)last_caller=caller;if(records[i].ready>=records[i].issue)lifetime_ticks+=records[i].ready-records[i].issue;if(records[i].submit_return>=records[i].issue)submit_ticks+=records[i].submit_return-records[i].issue;if(records[i].ready>=records[i].submit_return)post_return_ticks+=records[i].ready-records[i].submit_return;else return_after_apc_ticks+=records[i].submit_return-records[i].ready;}
 apc_batch_ticks=last_ready>=first_issue?last_ready-first_issue:0;caller_batch_ticks=last_caller>=first_issue?last_caller-first_issue:0;return true;
}
static ULONG verify_all(void){
 ULONG failures=foreign_callbacks;verified_operations=verified_bytes=0;phase("oracle_begin");
 for(ULONG i=0;i<COUNT;i++){
  struct Observation *o=&records[i];bool protocol_bad=false,timing_bad=false,payload_bad=false,prefix_bad=false,tail_bad=false;
  protocol_bad=o->apcs!=1||!o->pointer_match||(o->submit!=0&&o->submit!=STATUS_PENDING)||o->callback_status!=0||o->callback_information!=o->request->length||o->io.Status!=0||o->io.Information!=o->request->length;
  timing_bad=o->issue<first_issue||o->submit_return<o->issue||o->apc_entry!=o->ready||o->ready<o->issue||o->ready>last_ready||(o->submit_return>o->ready?o->submit_return:o->ready)>last_caller;
  for(ULONG j=0;j<o->request->length;j++)if(o->buffer[j]!=pattern(o->request->offset+j))payload_bad=true;
  ULONG prefix=o->request->alignment,tail=prefix+o->request->length;
  for(ULONG j=0;j<prefix;j++)if(slab[o->slice_offset+j]!=CANARY)prefix_bad=true;
  for(ULONG j=tail;j<o->slice_bytes;j++)if(slab[o->slice_offset+j]!=CANARY)tail_bad=true;
  bool bad=protocol_bad||timing_bad||payload_bad||prefix_bad||tail_bad;
  if(bad&&failures<16)tap_comment("STORAGE-IO-V6-ORACLE-FAIL index=%u protocol=%u timing=%u payload=%u prefix=%u tail=%u submit_status=%08x callback_status=%08x callback_information=%u io_status=%08x information=%u apcs=%u pointer_match=%u issue=%llu submit_return=%llu apc_entry=%llu ready=%llu first_issue=%llu last_ready=%llu last_caller=%llu",(unsigned)i,protocol_bad?1u:0u,timing_bad?1u:0u,payload_bad?1u:0u,prefix_bad?1u:0u,tail_bad?1u:0u,(unsigned)o->submit,(unsigned)o->callback_status,(unsigned)o->callback_information,(unsigned)o->io.Status,(unsigned)o->io.Information,(unsigned)o->apcs,(unsigned)o->pointer_match,o->issue,o->submit_return,o->apc_entry,o->ready,first_issue,last_ready,last_caller);
  o->oracle_good=!bad;if(bad)++failures;else {++verified_operations;verified_bytes+=o->request->length;}
 }
 return failures;
}
static bool cleanup(void){
 if(callbacks_live)return false; /* Never free possibly in-flight caller buffers on a timeout. */
 bool good=true;if(file_handle){if(NtClose(file_handle)!=0)good=false;file_handle=NULL;}
 while(pressure_count)MmFreeContiguousMemory(pressure[--pressure_count]);
 if(seed_block){MmFreeContiguousMemory(seed_block);seed_block=NULL;}if(slab){MmFreeContiguousMemory(slab);slab=NULL;}return good;
}
int recorder_execute(ULONG dataset,ULONG depth,ULONG pressure_target,bool warm){
 bool setup=false;ULONG failures=0,pages=0,warm_failures=0;const char *error=NULL;
 if(dataset>2||(depth!=1&&depth!=4&&depth!=12)||(pressure_target!=0&&pressure_target!=900)){error="selection";goto done;}
 raw_device=dataset==2;if(!allocate_resident(raw_device?0:dataset)){error="resident-allocation";goto done;}
 if(!open_data(true)){error="seed-open";goto done;}if(!seed_file()){error="seed";goto done;}
 if(NtClose(file_handle)!=0){error="seed-close";goto done;}file_handle=NULL;
 if(!open_data(false)){error="open-async-read";goto done;}
 prepare_buffers();if(pressure_target&&!restore_pressure()){error="pressure-setup";goto done;}
 if(warm){phase("warmup_begin");if(!run_batch(depth)){error="warmup-timeout";goto done;}warm_failures=verify_all();tap_comment("STORAGE-IO-V6-SETUP warmup_oracle_failures=%u",(unsigned)warm_failures);if(warm_failures){error="warmup-oracle";goto done;}prepare_buffers();if(pressure_target&&!restore_pressure()){error="pressure-after-warmup";goto done;}}
 if(!free_pages(&pages)||(pressure_target&&pages!=900)){error="pressure-before-measurement";goto done;}
 tap_comment("STORAGE-IO-V6-META version=6 fixture_generation=6 counter=rdtsc nominal_hz=%llu timing=order_aware_submit_and_apc oracle=post_batch_full_bytes route=%s dataset=%u qd_requested=%u pressure_target=%u cache=%s payload_bytes=%u slab_bytes=%u records_bytes=%u raw_base=%llu seed_flush_status=%08x",NOMINAL_HZ,raw_device?"raw-device":"fatx-file",(unsigned)(raw_device?0:dataset),(unsigned)depth,(unsigned)pressure_target,warm?"warm":"cold-ish",(unsigned)payload_bytes,(unsigned)slab_bytes,(unsigned)sizeof(records),raw_device?RAW_DEVICE_BASE:0,(unsigned)seed_flush_status);
 phase("measured_ready"); /* No buffer work, verification or output between first issue and last APC entry. */
 if(!run_batch(depth)){error="measured-timeout";goto done;}
 phase("timing_end");oracle_failures=verify_all();failures=oracle_failures;setup=true;
 for(ULONG i=0;i<COUNT;i++){struct Observation *o=&records[i];tap_comment("STORAGE-IO-V6-OP index=%u offset=%u bytes=%u alignment=%u slice_offset=%u slice_bytes=%u issue=%llu submit_return=%llu apc_entry=%llu ready=%llu apc_lifetime_ticks=%llu submit_ticks=%llu post_return_to_apc_ticks=%llu return_after_apc_ticks=%llu completion_order=%s submit_status=%08x io_status=%08x information=%u apcs=%u pointer_match=%u oracle_good=%u",(unsigned)i,(unsigned)o->request->offset,(unsigned)o->request->length,(unsigned)o->request->alignment,(unsigned)o->slice_offset,(unsigned)o->slice_bytes,o->issue,o->submit_return,o->apc_entry,o->ready,o->ready>=o->issue?o->ready-o->issue:0,o->submit_return>=o->issue?o->submit_return-o->issue:0,o->ready>=o->submit_return?o->ready-o->submit_return:0,o->submit_return>o->ready?o->submit_return-o->ready:0,o->ready<o->submit_return?"apc-before-return":"return-before-apc",(unsigned)o->submit,(unsigned)o->callback_status,(unsigned)o->callback_information,(unsigned)o->apcs,(unsigned)o->pointer_match,o->oracle_good?1u:0u);}
 tap_comment("STORAGE-IO-V6-CASE operations_expected=%u operations_completed=%u bytes_completed=%u apc_batch_ticks=%llu caller_batch_ticks=%llu first_issue=%llu last_ready=%llu last_caller=%llu caller_lifetime_sum_ticks=%llu submit_sum_ticks=%llu post_return_to_apc_sum_ticks=%llu return_after_apc_sum_ticks=%llu caller_occupancy=issue_to_apc_entry qd_requested=%u max_active_slots=%u measured_pages_before=%u failures=%u oracle=post_batch_full_bytes route=%s",(unsigned)COUNT,(unsigned)verified_operations,(unsigned)verified_bytes,apc_batch_ticks,caller_batch_ticks,first_issue,last_ready,last_caller,lifetime_ticks,submit_ticks,post_return_ticks,return_after_apc_ticks,(unsigned)depth,(unsigned)max_active_slots,(unsigned)pages,(unsigned)failures,raw_device?"raw-device":"fatx-file");
done:
 if(error){tap_comment("STORAGE-IO-V6-ERROR stage=%s",error);++failures;}
 bool cleaned=cleanup();if(!cleaned)++failures;
 tap_comment("STORAGE-IO-V6-END operations_submitted=%u failures=%u cleanup_complete=%u callback_buffers_retained=%u",(unsigned)actual_submissions,(unsigned)failures,cleaned?1u:0u,callbacks_live?1u:0u);
 return setup&&failures==0?0:1;
}
