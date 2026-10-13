/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <windows.h>
#include <xboxkrnl/xboxkrnl.h>
#include "regression.h"
#define MAGIC 0x45585432
#define BYTES 4192
#define EXTENT 8192
int main(void) {
 ULONG saved[2]={0};
 if(LaunchDataPage)memcpy(saved,LaunchDataPage->LaunchData,sizeof(saved));
 regression_begin();
 if(saved[0]==MAGIC) {
  PVOID buffer=(PVOID)saved[1];ULONG actual=MmQueryAllocationSize(buffer);
  tap_comment("restored base=%08lx query=%lu",saved[1],actual);
  regression_check(actual==EXTENT,"rounded persisted extent retains ownership");
  if(actual==EXTENT) {
   BOOLEAN good=TRUE;for(ULONG i=0;i<EXTENT;i++)if(((PUCHAR)buffer)[i]!=(UCHAR)(i^0x5a))good=FALSE;
   regression_check(good,"every byte survives including final-page tail");
   ULONG pa=MmGetPhysicalAddress(buffer);PVOID competing=MmAllocateContiguousMemoryEx(EXTENT,pa,pa+EXTENT-1,PAGE_SIZE,PAGE_READWRITE);
   regression_check(!competing,"persistent rounded range rejects competing allocation");
   if(competing)MmFreeContiguousMemory(competing);
   MmPersistContiguousMemory(buffer,actual,FALSE);MmFreeContiguousMemory(buffer);
   PVOID reused=MmAllocateContiguousMemoryEx(EXTENT,pa,pa+EXTENT-1,PAGE_SIZE,PAGE_READWRITE);
   regression_check(reused!=NULL,"unpersist and free returns all pages");if(reused)MmFreeContiguousMemory(reused);
  }
  saved[0]=0;memcpy(LaunchDataPage->LaunchData,saved,sizeof(saved));regression_finish();
 }
 PVOID buffer=MmAllocateContiguousMemoryEx(BYTES,0,0x3ffffff,PAGE_SIZE,PAGE_READWRITE);
 regression_require(buffer!=NULL,"allocate nonaligned persistent request");
 ULONG queried=MmQueryAllocationSize(buffer);tap_comment("initial requested=%u queried=%lu base=%08lx",BYTES,queried,(ULONG)buffer);
 regression_check(queried==EXTENT,"initial query reports rounded allocation");
 /* The native test intentionally persists the occupied complete page extent.
    The older BIOS's query error is recorded separately above. */
 for(ULONG i=0;i<EXTENT;i++)((PUCHAR)buffer)[i]=(UCHAR)(i^0x5a);
 MmPersistContiguousMemory(buffer,EXTENT,TRUE);
 LaunchDataPage=MmAllocateContiguousMemory(PAGE_SIZE);regression_require(LaunchDataPage!=NULL,"allocate launch metadata");
 memset(LaunchDataPage,0,PAGE_SIZE);LaunchDataPage->Header.dwLaunchDataType=0;strcpy(LaunchDataPage->Header.szLaunchPath,"\\Device\\CdRom0\\default.xbe");
 saved[0]=MAGIC;saved[1]=(ULONG)buffer;memcpy(LaunchDataPage->LaunchData,saved,sizeof(saved));MmPersistContiguousMemory(LaunchDataPage,PAGE_SIZE,TRUE);
 tap_comment("stage1 reset; stage2 reports restored results");tap_drain();HalReturnToFirmware(HalQuickRebootRoutine);return 1;
}
