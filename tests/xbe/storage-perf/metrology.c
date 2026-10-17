/* SPDX-License-Identifier: GPL-2.0-or-later
 * Diagnostic clock relation only; no storage latency/throughput claim. */
#include <xboxkrnl/xboxkrnl.h>
#include "tap.h"
static ULONGLONG ticks(void){ULONG a,d;__asm__ __volatile__("rdtsc":"=a"(a),"=d"(d)::"memory");return((ULONGLONG)d<<32)|a;}
int main(void) {
 tap_version(13);tap_plan(1);
 tap_comment("STORAGE-CLOCK-READY fixture_generation=2 diagnostic_revision=2 samples=50 purpose=host_wall_diagnostic deadline_counter=qpc");tap_drain();
 LARGE_INTEGER attach={.QuadPart=-50000000};KeDelayExecutionThread(KernelMode,FALSE,&attach);
 const ULONG microseconds[]={1000,10000,100000,1000000,5000000};
 ULONGLONG qhz=KeQueryPerformanceFrequency();
 ULONG index=0;
 for(ULONG repeat=0;repeat<5;repeat++)for(ULONG span=0;span<5;span++)for(ULONG busy=0;busy<2;busy++,index++) {
  tap_comment("STORAGE-CLOCK-ARM index=%lu",index);tap_drain();
  tap_puts("<");tap_drain();ULONGLONG q=KeQueryPerformanceCounter(),a=ticks();
  LARGE_INTEGER wait={.QuadPart=-(LONGLONG)microseconds[span]*10};
  /* QPC frequency calibrates QPC only. RDTSC remains independently observed. */
  if(busy){ULONGLONG target=qhz*microseconds[span]/1000000u;while(KeQueryPerformanceCounter()-q<target)__asm__ __volatile__("pause");}
  else KeDelayExecutionThread(KernelMode,FALSE,&wait);
  ULONGLONG b=ticks(),r=KeQueryPerformanceCounter();tap_puts(">");tap_drain();
  tap_comment("STORAGE-CLOCK-SAMPLE index=%lu requested_us=%lu busy=%lu rdtsc_ticks=%llu qpc_ticks=%llu qpc_hz=%llu",index,microseconds[span],busy,b-a,r-q,qhz);
 }
 tap_comment("STORAGE-CLOCK-END samples=%lu storage_operations=0",index);tap_ok(1,"diagnostic clock markers emitted; host relation evaluated separately");tap_drain();
 LARGE_INTEGER finish={.QuadPart=-5000000};KeDelayExecutionThread(KernelMode,FALSE,&finish);
 HalWriteSMBusValue(0x20,0x02,FALSE,0x80);for(;;)__asm__ __volatile__("hlt");
}
