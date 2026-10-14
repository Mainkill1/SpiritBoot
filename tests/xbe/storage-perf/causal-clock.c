/* SPDX-License-Identifier: GPL-2.0-or-later
 * Separate causal-marker diagnostic; no storage operation or performance claim. */
#include <xboxkrnl/xboxkrnl.h>
#include "tap.h"
typedef struct { ULONGLONG q_before, q_after, t_before, t_after; } BRACKET;
static ULONGLONG ticks(void) {
 ULONG a,d;__asm__ __volatile__("rdtsc":"=a"(a),"=d"(d)::"memory");
 return ((ULONGLONG)d<<32)|a;
}
static BRACKET marker(ULONG index, ULONG sample, const char *edge) {
 BRACKET value;
 value.q_before=KeQueryPerformanceCounter();value.t_before=ticks();
 tap_comment("STORAGE-CAUSAL-MARKER index=%lu sample=%lu edge=%s",index,sample,edge);
 tap_drain();
 value.t_after=ticks();value.q_after=KeQueryPerformanceCounter();
 return value;
}
static void report(ULONG index, BRACKET value) {
 tap_comment("STORAGE-CAUSAL-BOUND marker=%lu counter=qpc before=%llu after=%llu",index,value.q_before,value.q_after);
 tap_comment("STORAGE-CAUSAL-BOUND marker=%lu counter=rdtsc before=%llu after=%llu",index,value.t_before,value.t_after);
}
int main(void) {
 tap_version(13);tap_plan(1);
 ULONGLONG qhz=KeQueryPerformanceFrequency();
 tap_comment("STORAGE-CAUSAL-READY fixture_generation=2 diagnostic_revision=3 samples=50 markers=100 purpose=causal_counter_brackets deadline_counter=qpc qpc_hz=%llu",qhz);
 tap_drain();
 LARGE_INTEGER attach={.QuadPart=-50000000};KeDelayExecutionThread(KernelMode,FALSE,&attach);
 tap_comment("STORAGE-CAUSAL-ARM samples=50");tap_drain();
 const ULONG microseconds[]={1000,10000,100000,1000000,5000000};ULONG index=0;
 for(ULONG repeat=0;repeat<5;repeat++)for(ULONG span=0;span<5;span++)for(ULONG busy=0;busy<2;busy++,index++) {
  BRACKET begin=marker(index*2,index,"begin");
  LARGE_INTEGER wait={.QuadPart=-(LONGLONG)microseconds[span]*10};
  if(busy){ULONGLONG target=qhz*microseconds[span]/1000000u;while(KeQueryPerformanceCounter()-begin.q_after<target)__asm__ __volatile__("pause");}
  else KeDelayExecutionThread(KernelMode,FALSE,&wait);
  BRACKET end=marker(index*2+1,index,"end");
  report(index*2,begin);report(index*2+1,end);
  tap_comment("STORAGE-CAUSAL-SAMPLE index=%lu requested_us=%lu busy=%lu",index,microseconds[span],busy);
 }
 tap_comment("STORAGE-CAUSAL-END samples=%lu markers=%lu storage_operations=0",index,index*2);
 tap_ok(1,"causal markers emitted; independent backend and rate qualification required");tap_drain();
 /* Untimed evidence-collection grace, separately declared in the frozen plan. */
 LARGE_INTEGER finish={.QuadPart=-50000000};KeDelayExecutionThread(KernelMode,FALSE,&finish);
 HalWriteSMBusValue(0x20,0x02,FALSE,0x80);for(;;)__asm__ __volatile__("hlt");
}
