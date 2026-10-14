/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <windows.h>
#include <xboxkrnl/xboxkrnl.h>
#include <string.h>
#include "regression.h"
#define NXK_POOL_CENSUS 1
#define NXK_POOL_AUDIT 1
#include "pool-census.h"
#include "pool-audit.h"
#include "addresses.h"
static NXP_POOL_CENSUS_DATA saved;
static NXP_POOL_AUDIT scans, scan_check;
static KEVENT ready;
static unsigned errors;
static void snapshot(const char *phase) {
 volatile NXP_POOL_CENSUS_DATA *live=(volatile NXP_POOL_CENSUS_DATA *)(ULONG_PTR)CENSUS_ADDRESS;
 int complete=0;
 for(unsigned retry=0;retry<100;retry++) {
  ULONG sequence=live->Sequence;
  if(sequence&1)continue;
  memcpy(&saved,(const void *)live,sizeof(saved));
  if(sequence==live->Sequence && !(saved.Sequence&1)){complete=1;break;}
 }
 regression_require(complete&&saved.Magic==NXP_POOL_CENSUS_MAGIC&&saved.Schema==NXP_POOL_CENSUS_SCHEMA&&saved.Bytes==sizeof(saved),"stable build-pinned census snapshot");
 regression_check(saved.KeyOverflows==0&&saved.LargeOverflows==0&&saved.LargeFreeMisses==0&&saved.LifetimeOverflows==0&&saved.LifetimeMisses==0&&saved.UntrackedFrees==0&&saved.Saturations==0&&saved.PageUnderflows==0,"census integrity counters remain zero");
 ULONG counted=0;
 for(unsigned d=0;d<NXP_POOL_CENSUS_DOMAIN_COUNT;d++)for(unsigned c=0;c<NXP_POOL_CENSUS_CLASS_COUNT;c++) {
  NXP_POOL_CENSUS_PAGE_STATS *p=&saved.Pages[d][c];counted+=p->CurrentActive+p->CurrentEmpty;
  if(p->FreshRefills || p->EmptyReuses)tap_comment("pool_pages phase=%s domain=%u class=%u fresh=%lu reuse=%lu detach=%lu active=%lu empty=%lu peak_active=%lu peak_empty=%lu",phase,d,c,p->FreshRefills,p->EmptyReuses,p->Detaches,p->CurrentActive,p->CurrentEmpty,p->PeakActive,p->PeakEmpty);
 }
 regression_check(counted==saved.BucketPagesCurrent,"bucket page accounting is settled");
 tap_comment("pool_census phase=%s bytes=%lu alloc=%lu free=%lu bucket=%lu peak=%lu entries=%lu",phase,saved.Bytes,saved.Allocations,saved.Frees,saved.BucketPagesCurrent,saved.BucketPagesPeak,saved.EntryCount);
 for(unsigned i=0;i<NXP_POOL_CENSUS_KEY_SLOTS;i++) {
  NXP_POOL_CENSUS_ENTRY *e=&saved.Entries[i];
  if(e->Used)tap_comment("pool_bin phase=%s tag=%08lx bin=%u domain=%u alloc=%lu free=%lu live=%lu peak=%lu short=%lu medium=%lu retained=%lu",phase,e->Tag,e->Bin,e->Domain,e->Allocations,e->Frees,e->Live,e->Peak,e->LifeShort,e->LifeMedium,e->LifeRetained);
 }
 const void *scan_live=(const void *)(ULONG_PTR)AUDIT_ADDRESS;
 complete=0;
 for(unsigned retry=0;retry<100;retry++) {
  memcpy(&scans,scan_live,sizeof(scans));memcpy(&scan_check,scan_live,sizeof(scan_check));
  if(memcmp(&scans,&scan_check,sizeof(scans))==0){complete=1;break;}
 }
 regression_require(complete,"stable refill counter snapshot");
 regression_check(scans.SearchCalls==scans.HeadHits+scans.FallbackHits+scans.NotFound,"refill counter outcome conservation");
 tap_comment("pool_scan phase=%s bytes=%u calls=%lu head_checks=%lu head_hits=%lu fallback=%lu examined=%lu max=%lu hits=%lu misses=%lu reclaim=%lu",phase,(unsigned)sizeof(scans),scans.SearchCalls,scans.HeadChecks,scans.HeadHits,scans.FallbackCalls,scans.PagesExamined,scans.MaxPagesExamined,scans.FallbackHits,scans.NotFound,scans.Reclaims);
 for(unsigned i=0;i<129;i++)if(scans.ScanLength[i])tap_comment("pool_scan_hist phase=%s bucket=%u count=%lu",phase,i,scans.ScanLength[i]);
 MM_STATISTICS s={.Length=sizeof(s)};
 regression_require(MmQueryStatistics(&s)==0,"read public memory statistics");
 tap_comment("pool_memory phase=%s available=%lu pool=%lu stack=%lu image=%lu cache=%lu",phase,s.AvailablePages,s.PoolPagesCommitted,s.StackPagesCommitted,s.ImagePagesCommitted,s.CachePagesCommitted);
}
static VOID NTAPI worker(PVOID ignored) {
 (void)ignored;LARGE_INTEGER timeout={.QuadPart=-50000000};
 if(KeWaitForSingleObject(&ready,Executive,KernelMode,FALSE,&timeout)!=0)InterlockedIncrement((LONG *)&errors);
 PsTerminateSystemThread(0);
}
static VOID NTAPI startup(PKSTART_ROUTINE start,PVOID context) {start(context);PsTerminateSystemThread(0);}
static void thread_io(void) {
 HANDLE handles[32],ids[32];PETHREAD threads[32];
 KeInitializeEvent(&ready,NotificationEvent,FALSE);
 for(unsigned i=0;i<32;i++) {
  regression_require(PsCreateSystemThreadEx(&handles[i],0,16384,0,&ids[i],worker,NULL,TRUE,FALSE,startup)==0,"create retained kernel thread");
  regression_require(ObReferenceObjectByHandle(handles[i],&PsThreadObjectType,(PVOID *)&threads[i])==0,"reference retained kernel thread");
 }
 snapshot("threads32");
 for(unsigned i=0;i<32;i++)NtResumeThread(handles[i],NULL);
 KeSetEvent(&ready,0,FALSE);
 for(unsigned i=0;i<32;i++) {
  LARGE_INTEGER timeout={.QuadPart=-50000000};
  regression_require(KeWaitForSingleObject(threads[i],Executive,KernelMode,FALSE,&timeout)==0,"wait retained thread");
  NtClose(handles[i]);ObfDereferenceObject(threads[i]);
 }
 LARGE_INTEGER delay={.QuadPart=-1000000};KeDelayExecutionThread(KernelMode,FALSE,&delay);
 snapshot("threads_retired");
 PIRP irps[64];
 for(unsigned round=0;round<16;round++) {
  for(unsigned i=0;i<64;i++){irps[i]=IoAllocateIrp((CCHAR)(i%8+1));if(!irps[i])errors++;}
  if(round==0)snapshot("irp64");
  for(unsigned i=0;i<64;i++)if(irps[i])IoFreeIrp(irps[i]);
 }
 HANDLE file=CreateFileA("D:\\default.xbe",GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
 regression_require(file!=INVALID_HANDLE_VALUE,"open own guest image for file I/O");
 static unsigned char buffer[4096];
 for(unsigned i=0;i<128;i++) {
  DWORD bytes=0;SetFilePointer(file,0,NULL,FILE_BEGIN);
  if(!ReadFile(file,buffer,sizeof(buffer),&bytes,NULL)||bytes!=sizeof(buffer))errors++;
 }
 CloseHandle(file);snapshot("io_retired");
}
static void ladder(void) {
 static const unsigned sizes[]={0,1,8,16,24,32,64,96,128,192,256,384,512,768,1024,1536,2040,2384};
 PVOID blocks[18][32];
 for(unsigned c=0;c<18;c++)for(unsigned i=0;i<32;i++) {
  unsigned n=sizes[c];blocks[c][i]=ExAllocatePoolWithTag(n,0x4c616464);
  regression_require(blocks[c][i]!=NULL,"allocate frozen 18-size ladder");
  ULONG capacity=ExQueryPoolBlockSize(blocks[c][i]);
  if(capacity<n)errors++;
  memset(blocks[c][i],(int)(i+c),capacity);
 }
 snapshot("ladder_live");
 for(unsigned c=0;c<18;c++)for(unsigned i=0;i<32;i++) {
  ULONG capacity=ExQueryPoolBlockSize(blocks[c][i]);
  unsigned char *p=blocks[c][i];
  for(unsigned j=0;j<capacity;j++)if(p[j]!=(unsigned char)(i+c)){errors++;break;}
  ExFreePool(blocks[c][i]);
 }
 snapshot("ladder_retired");
 for(unsigned round=0;round<4096;round++) {
  unsigned n=sizes[round%18];PVOID p=ExAllocatePoolWithTag(n,0x4379726e);
  if(!p){errors++;break;}memset(p,0x35,ExQueryPoolBlockSize(p));ExFreePool(p);
 }
 snapshot("churn_retired");
}
int main(void) {
 regression_begin();tap_comment("pool_audit_build census=%08x scan=%08x",CENSUS_ADDRESS,AUDIT_ADDRESS);
 snapshot("boot");thread_io();ladder();regression_check(errors==0,"public pool contents and thread IRP file operations remain correct");regression_finish();
}
