/* SPDX-License-Identifier: GPL-2.0-or-later
 * Independent public read/write/flush/scatter and optical timing probes. */
#include <xboxkrnl/xboxkrnl.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include "tap.h"
#include "suite-select.h"
#define N 1024u
#define PAGES 33u
#define SG_BYTES (PAGES*4096u)
#define EXTENT (4u*1024u*1024u)
static UCHAR *block,*scatter,*readback;
static ULONGLONG latency[N],hz;
static ULONG status[N],iosb_status[N],bytes[N];
static FILE_SEGMENT_ELEMENT segments[PAGES+1];
static const char hdd_path[]="\\Device\\Harddisk0\\Partition1\\pr248-families.tmp";
static const char dvd_path[]="\\Device\\CdRom0\\owned-data.bin";
static ULONGLONG tick(void){ULONG a,d;__asm__ __volatile__("rdtsc":"=a"(a),"=d"(d)::"memory");return ((ULONGLONG)d<<32)|a;}
static UCHAR pattern(ULONG offset){return (UCHAR)((offset*37u)^(offset>>8)^(offset>>17)^0xa7u);}
static ULONG available(void){MM_STATISTICS m={0};m.Length=sizeof(m);return MmQueryStatistics(&m)==0?m.AvailablePages:0;}
static __attribute__((noreturn)) void poweroff(void){tap_drain();LARGE_INTEGER wait={.QuadPart=-5000000};KeDelayExecutionThread(KernelMode,FALSE,&wait);HalWriteSMBusValue(0x20,0x02,FALSE,0x80);for(;;)__asm__ __volatile__("hlt");}
static void fatal(const char *s){tap_comment("STORAGE-PERF-ERROR stage=%s",s);poweroff();}
static ULONGLONG frequency(void){ULONGLONG v[5],qhz=KeQueryPerformanceFrequency();for(ULONG i=0;i<5;i++){LARGE_INTEGER wait={.QuadPart=-1000000};ULONGLONG q=KeQueryPerformanceCounter(),a=tick();KeDelayExecutionThread(KernelMode,FALSE,&wait);ULONGLONG b=tick(),r=KeQueryPerformanceCounter();v[i]=(b-a)*qhz/(r-q);}for(ULONG i=0;i<5;i++)for(ULONG j=i+1;j<5;j++)if(v[j]<v[i]){ULONGLONG t=v[i];v[i]=v[j];v[j]=t;}tap_comment("STORAGE-PERF-CLOCK min=%llu median=%llu max=%llu",v[0],v[2],v[4]);return v[2];}
static NTSTATUS open_path(const char *path,HANDLE *h,bool write,ULONG disposition){ANSI_STRING name={(USHORT)strlen(path),(USHORT)(strlen(path)+1),(PCHAR)path};OBJECT_ATTRIBUTES a={0};IO_STATUS_BLOCK io;memset(&io,0x5a,sizeof(io));a.ObjectName=&name;a.Attributes=OBJ_CASE_INSENSITIVE;return NtCreateFile(h,GENERIC_READ|(write?GENERIC_WRITE:0)|SYNCHRONIZE,&a,&io,NULL,FILE_ATTRIBUTE_NORMAL,FILE_SHARE_READ,disposition,FILE_SYNCHRONOUS_IO_NONALERT|FILE_NON_DIRECTORY_FILE|FILE_NO_INTERMEDIATE_BUFFERING);}
static void emit(const char *id,ULONG count,ULONG total,ULONGLONG elapsed,ULONG checks,ULONG failed,ULONG flush_calls,ULONG read_calls,ULONG write_calls,bool persistence){
#ifdef STORAGE_SUITE
 if(storage_warmup_only)return;id=storage_selected_id;
#endif
 for(ULONG i=0;i<count;i++)tap_comment("STORAGE-PERF-OP id=%s index=%lu ticks=%llu status=%08lx io_status=%08lx information=%lu apcs=0",id,i,latency[i],status[i],iosb_status[i],bytes[i]);tap_comment("STORAGE-PERF-CASE id=%s operations=%lu bytes=%lu ticks=%llu assertions=%lu failures=%lu flush_calls=%lu persistence=%u qd_actual=1 available_pages=%lu cache=%s read_calls=%lu write_calls=%lu",id,count,total,elapsed,checks,failed,flush_calls,persistence,available(),
#ifdef STORAGE_SUITE
 storage_selected_cache,
#else
 "warm",
#endif
 read_calls,write_calls);}
static ULONG dvd_read(HANDLE h){IO_STATUS_BLOCK io;ULONG failures=0;ULONGLONG first=0,last=0;for(ULONG i=0;i<N;i++){LARGE_INTEGER at={.QuadPart=i*4096u};for(ULONG j=0;j<4096;j++)block[j]=(UCHAR)~pattern(i*4096u+j);memset(&io,0x5a,sizeof(io));ULONGLONG a=tick();if(i==0)first=a;NTSTATUS s=NtReadFile(h,NULL,NULL,NULL,&io,block,4096,&at);bool match=true;for(ULONG j=0;j<4096;j++)if(block[j]!=pattern(i*4096u+j))match=false;last=tick();latency[i]=last-a;status[i]=s;iosb_status[i]=io.Status;bytes[i]=io.Information;ULONG bad=(s!=0)|((io.Status!=0)<<1)|((io.Information!=4096)<<2)|((!match)<<3);if(bad)++failures;}emit("dvd-owned-payload",N,EXTENT,last-first,N*4,failures,0,N,0,false);return failures;}
static ULONG sg_read(HANDLE h,bool fragmented){IO_STATUS_BLOCK io;ULONG failures=0;ULONGLONG first=0,last=0;for(ULONG i=0;i<N;i++){ULONG offset=((i*SG_BYTES)%(EXTENT-SG_BYTES))&~4095u;LARGE_INTEGER at={.QuadPart=offset};for(ULONG page=0;page<PAGES;page++){segments[page].Alignment=0;segments[page].Buffer=scatter+page*(fragmented?2:1)*4096;}segments[PAGES].Alignment=0;segments[PAGES].Buffer=NULL;if(fragmented)for(ULONG p=0;p<PAGES;p++)memset(scatter+(p*2+1)*4096,0xee,4096);for(ULONG page=0;page<PAGES;page++)for(ULONG j=0;j<4096;j++)((UCHAR *)segments[page].Buffer)[j]=(UCHAR)~pattern(offset+page*4096+j);memset(&io,0x5a,sizeof(io));ULONGLONG a=tick();if(i==0)first=a;NTSTATUS s=NtReadFileScatter(h,NULL,NULL,NULL,&io,segments,SG_BYTES,&at);bool match=true,canaries=true;for(ULONG page=0;page<PAGES;page++){UCHAR *p=segments[page].Buffer;for(ULONG j=0;j<4096;j++)if(p[j]!=pattern(offset+page*4096+j))match=false;if(fragmented)for(ULONG j=0;j<4096;j++)if(scatter[(page*2+1)*4096+j]!=0xee)canaries=false;}last=tick();latency[i]=last-a;status[i]=s;iosb_status[i]=io.Status;bytes[i]=io.Information;ULONG bad=(s!=0)|((io.Status!=0)<<1)|((io.Information!=SG_BYTES)<<2)|((!match)<<3)|((fragmented&&!canaries)<<4);if(bad)++failures;}emit(fragmented?"sg-fragmented-33-pages":"sg-split-33-pages",N,N*SG_BYTES,last-first,N*(fragmented?5:4),failures,0,N,0,false);return failures;}
static ULONG write_flush(HANDLE *h) {
 IO_STATUS_BLOCK io; ULONG failures=0,flushes=0,checks=0;
 ULONGLONG first=0,last=0;
 for(ULONG i=0;i<N;i++) {
  for(ULONG j=0;j<4096;j++) {
   block[j]=(UCHAR)(i*17u+j*13u+7u);
   readback[j]=(UCHAR)~block[j]; /* Every byte differs before EVERY read. */
  }
  LARGE_INTEGER at={.QuadPart=i*4096u};
  memset(&io,0x5a,sizeof(io)); ULONGLONG a=tick(); if(i==0)first=a;
  NTSTATUS w=NtWriteFile(*h,NULL,NULL,NULL,&io,block,4096,&at);
  ULONG ws=io.Status,wb=io.Information;
  memset(&io,0x5a,sizeof(io)); NTSTATUS f=NtFlushBuffersFile(*h,&io);
  ULONG fs=io.Status; if(f==0&&fs==0)++flushes;
  NTSTATUS close=NtClose(*h); *h=NULL;
  NTSTATUS o=open_path(hdd_path,h,true,FILE_OPEN),r=STATUS_UNSUCCESSFUL;
  memset(&io,0x5a,sizeof(io));
  if(o==0)r=NtReadFile(*h,NULL,NULL,NULL,&io,readback,4096,&at);
  bool match=true;
  for(ULONG j=0;j<4096;j++)if(readback[j]!=(UCHAR)(i*17u+j*13u+7u))match=false;
  /* Bitwise combination evaluates all eleven initialized predicates. */
  ULONG bad=(w!=0)|((ws!=0)<<1)|((wb!=4096)<<2)|((f!=0)<<3)|
   ((fs!=0)<<4)|((close!=0)<<5)|((o!=0)<<6)|((r!=0)<<7)|
   ((io.Status!=0)<<8)|((io.Information!=4096)<<9)|((!match)<<10);
  checks+=11; last=tick(); latency[i]=last-a;
  status[i]=bad?STATUS_UNSUCCESSFUL:0; iosb_status[i]=io.Status; bytes[i]=io.Information;
  if(bad)++failures;
  if(o!=0)fatal("write-reopen");
 }
 emit("write-api-flush-reopen",N,EXTENT,last-first,checks,failures,flushes,N,N,failures==0);
 return failures;
}
#ifdef STORAGE_SUITE
int storage_families_main(void)
#else
int main(void)
#endif
{tap_version(13);tap_plan(1);block=MmAllocateContiguousMemory(65536);readback=MmAllocateContiguousMemory(4096);scatter=MmAllocateContiguousMemory(PAGES*2*4096);if(!block||!readback||!scatter)fatal("buffers");HANDLE h=NULL,dvd=NULL;IO_STATUS_BLOCK io;if(open_path(hdd_path,&h,true,FILE_SUPERSEDE)!=0)fatal("hdd-open");for(ULONG offset=0;offset<EXTENT;offset+=65536){for(ULONG j=0;j<65536;j++)block[j]=pattern(offset+j);LARGE_INTEGER at={.QuadPart=offset};memset(&io,0x5a,sizeof(io));if(NtWriteFile(h,NULL,NULL,NULL,&io,block,65536,&at)!=0||io.Status!=0||io.Information!=65536)fatal("hdd-seed");}memset(&io,0x5a,sizeof(io));if(NtFlushBuffersFile(h,&io)!=0||io.Status!=0)fatal("seed-api-flush");if(open_path(dvd_path,&dvd,false,FILE_OPEN)!=0)fatal("dvd-open");hz=frequency();ULONGLONG overhead=~(ULONGLONG)0;for(ULONG i=0;i<1000;i++){ULONGLONG a=tick(),b=tick()-a;if(b<overhead)overhead=b;}tap_comment("STORAGE-PERF-META version=1 fixture_generation=2 counter=rdtsc frequency=%llu overhead_ticks=%llu",hz,overhead);ULONG failed=0,cases=0;
#ifdef STORAGE_SUITE
 for(ULONG pass=0;pass<(!strcmp(storage_selected_cache,"warm")?2u:1u);pass++) {
  storage_warmup_only=(!strcmp(storage_selected_cache,"warm")&&pass==0);
  ULONG result=0;
  if(!strcmp(storage_selected_base,"dvd-owned-payload"))result=dvd_read(dvd);
  else if(!strcmp(storage_selected_base,"sg-split-33-pages"))result=sg_read(h,false);
  else if(!strcmp(storage_selected_base,"sg-fragmented-33-pages"))result=sg_read(h,true);
  else if(!strcmp(storage_selected_base,"write-api-flush-reopen"))result=write_flush(&h);
  else fatal("selected-family");
  if(storage_warmup_only&&result)fatal("family-warmup");if(!storage_warmup_only){failed+=result;++cases;}
 }
#else
 failed+=dvd_read(dvd);failed+=sg_read(h,false);failed+=sg_read(h,true);failed+=write_flush(&h);cases=4;
#endif
 NtClose(h);NtClose(dvd);MmFreeContiguousMemory(block);MmFreeContiguousMemory(readback);MmFreeContiguousMemory(scatter);if(failed)tap_not_ok(1,"owned workload exact data/status/byte-count/canary/persistence checks");else tap_ok(1,"owned workload exact data/status/byte-count/canary/persistence checks");tap_comment("STORAGE-PERF-END cases=%lu failures=%lu",cases,failed);poweroff();}
