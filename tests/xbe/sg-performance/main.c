/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <xboxkrnl/xboxkrnl.h>
#include "tap.h"
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#define MAX_PAGES 512
#define SAMPLES 7
static PUCHAR source,flat;
static FILE_SEGMENT_ELEMENT segments[MAX_PAGES+1];
static UCHAR output[32768];
static ULONG checks,failures;
static void check(bool value,const char *text){++checks;if(value)tap_ok(checks,text);else {tap_not_ok(checks,text);++failures;}}
static const char path[]="\\Device\\Harddisk0\\Partition1\\spiritboot-sg-perf.tmp";
typedef NTSTATUS (NTAPI *GATHER)(HANDLE,HANDLE,PIO_APC_ROUTINE,PVOID,PIO_STATUS_BLOCK,PFILE_SEGMENT_ELEMENT,ULONG,PLARGE_INTEGER);
static UCHAR pattern(ULONG page,ULONG offset,ULONG sample){return (UCHAR)(page*19+offset*13+sample*7);}
static bool open_file(HANDLE *h){
 ANSI_STRING name={(USHORT)(sizeof(path)-1),(USHORT)sizeof(path),(PCHAR)path};OBJECT_ATTRIBUTES oa={0};IO_STATUS_BLOCK io;
 oa.ObjectName=&name;oa.Attributes=OBJ_CASE_INSENSITIVE;
 return NtCreateFile(h,GENERIC_READ|GENERIC_WRITE|SYNCHRONIZE,&oa,&io,NULL,FILE_ATTRIBUTE_NORMAL,0,FILE_SUPERSEDE,FILE_SYNCHRONOUS_IO_NONALERT|FILE_NON_DIRECTORY_FILE|FILE_NO_INTERMEDIATE_BUFFERING)==STATUS_SUCCESS;
}
static void prepare(ULONG pages,ULONG sample){
 memset(source,0xEE,2*MAX_PAGES*PAGE_SIZE);
 for(ULONG i=0;i<pages;i++){
  ULONG index=(i*73)&(pages-1);PUCHAR p=source+2*index*PAGE_SIZE;
  segments[i].Alignment=0;segments[i].Buffer=p;
  for(ULONG j=0;j<PAGE_SIZE;j++)p[j]=pattern(i,j,sample);
  memcpy(flat+i*PAGE_SIZE,p,PAGE_SIZE);
 }
 segments[pages].Alignment=0;segments[pages].Buffer=NULL;
}
static bool verify(HANDLE h,ULONG pages,ULONG sample){
 IO_STATUS_BLOCK io;LARGE_INTEGER offset={0};ULONG total=pages*PAGE_SIZE;
 for(ULONG at=0;at<total;){ULONG count=total-at;if(count>sizeof(output))count=sizeof(output);offset.QuadPart=at;
  if(NtReadFile(h,NULL,NULL,NULL,&io,output,count,&offset)!=STATUS_SUCCESS||io.Information!=count)return false;
  for(ULONG j=0;j<count;j++)if(output[j]!=pattern((at+j)/PAGE_SIZE,(at+j)%PAGE_SIZE,sample))return false;
  at+=count;
 }
 for(ULONG i=0;i<pages;i++){PUCHAR p=segments[i].Buffer;for(ULONG j=0;j<PAGE_SIZE;j++)if(p[j]!=pattern(i,j,sample))return false;}
 for(ULONG i=0;i<MAX_PAGES;i++)for(ULONG j=0;j<PAGE_SIZE;j++)if(source[(2*i+1)*PAGE_SIZE+j]!=0xEE)return false;
 FILE_NETWORK_OPEN_INFORMATION info;
 return NtQueryInformationFile(h,&io,&info,sizeof(info),FileNetworkOpenInformation)==STATUS_SUCCESS&&info.EndOfFile.QuadPart==MAX_PAGES*PAGE_SIZE;
}
int main(void){
 tap_version(13);tap_plan(2+2*5*SAMPLES);bool all=true;HANDLE h=NULL;IO_STATUS_BLOCK io;
 source=MmAllocateContiguousMemory(2*MAX_PAGES*PAGE_SIZE);flat=MmAllocateContiguousMemory(MAX_PAGES*PAGE_SIZE);
 bool ready=source&&flat&&open_file(&h);check(ready,"allocate separated source pages and synchronous noncached file");if(!ready){tap_comment("setup failed");tap_drain();HalWriteSMBusValue(0x20,0x02,FALSE,0x80);for(;;)__asm__ __volatile__("hlt");}
 FILE_END_OF_FILE_INFORMATION eof;eof.EndOfFile.QuadPart=MAX_PAGES*PAGE_SIZE;
 ready=NtSetInformationFile(h,&io,&eof,sizeof(eof),FileEndOfFileInformation)==STATUS_SUCCESS;check(ready,"preallocate transfer extent outside measured calls");all&=ready;
 ULONGLONG frequency=KeQueryPerformanceFrequency();tap_comment("SG-META version=1 frequency=%llu samples=%u max_pages=%u",(unsigned long long)frequency,SAMPLES,MAX_PAGES);
 ULONG sizes[]={1,2,16,128,512};
 for(ULONG mode=0;mode<2;mode++)for(ULONG k=0;k<5;k++)for(ULONG sample=0;sample<SAMPLES;sample++){
  ULONG pages=sizes[k],bytes=pages*PAGE_SIZE;prepare(pages,sample);LARGE_INTEGER offset={0};
  ULONGLONG start=KeQueryPerformanceCounter();
  NTSTATUS status=mode?NtWriteFile(h,NULL,NULL,NULL,&io,flat,bytes,&offset):((GATHER)NtWriteFileGather)(h,NULL,NULL,NULL,&io,segments,bytes,&offset);
  ULONGLONG end=KeQueryPerformanceCounter();
  bool good=status==STATUS_SUCCESS&&io.Status==STATUS_SUCCESS&&io.Information==bytes&&verify(h,pages,sample);all&=good;
  tap_comment("SG mode=%s pages=%lu sample=%lu bytes=%lu ticks=%llu correct=%u status=%08lx io=%08lx information=%lu",mode?"flat":"gather",pages,sample,bytes,(unsigned long long)(end-start),good,(ULONG)status,(ULONG)io.Status,(ULONG)io.Information);
  check(good,"same bytes, source sentinels, status and EOF after synchronous write");
 }
 if(h)NtClose(h);if(source)MmFreeContiguousMemory(source);if(flat)MmFreeContiguousMemory(flat);
 tap_comment("SG-SUMMARY samples=70 failures=%u",all?0:1);tap_comment("== sg-performance end %s ==",all?"PASS":"FAIL");
 tap_drain();HalWriteSMBusValue(0x20,0x02,FALSE,0x80);for(;;)__asm__ __volatile__("hlt");
}
