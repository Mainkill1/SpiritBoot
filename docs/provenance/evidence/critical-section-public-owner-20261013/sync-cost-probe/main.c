/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <windows.h>
#include <xboxkrnl/xboxkrnl.h>
#include "regression.h"
static RTL_CRITICAL_SECTION cs;
static void sample(unsigned mode,unsigned count,unsigned sample) {
 ULONGLONG start=KeQueryPerformanceCounter(),frequency=KeQueryPerformanceFrequency();
 unsigned successes=0;
 for(unsigned i=0;i<count;i++) {
  if(mode==0){RtlEnterCriticalSection(&cs);RtlLeaveCriticalSection(&cs);successes++;}
  else if(mode==1){if(RtlTryEnterCriticalSection(&cs)){successes++;RtlLeaveCriticalSection(&cs);}}
  else if(mode==2){KIRQL old=KfRaiseIrql(DISPATCH_LEVEL);KfLowerIrql(old);successes++;}
  else {RtlEnterCriticalSection(&cs);RtlEnterCriticalSection(&cs);RtlLeaveCriticalSection(&cs);RtlLeaveCriticalSection(&cs);successes++;}
 }
 ULONGLONG ticks=KeQueryPerformanceCounter()-start;
 tap_comment("sync mode=%u sample=%u count=%u ticks=%lu us=%lu successes=%u",mode,sample,count,(ULONG)ticks,(ULONG)(ticks*1000000/frequency),successes);
 regression_check(successes==count,"every bounded operation completes");
}
int main(void) {
 regression_begin();RtlInitializeCriticalSection(&cs);
 PVOID thread=KeGetCurrentThread();ULONG fs_thread;__asm__ __volatile__("movl %%fs:0x28,%0":"=r"(fs_thread));
 RtlEnterCriticalSection(&cs);
 tap_comment("owner export=%08lx fs28=%08lx stored=%08lx count=%ld recursion=%ld",(ULONG)thread,fs_thread,(ULONG)cs.OwningThread,cs.LockCount,cs.RecursionCount);
 regression_check((ULONG)thread==fs_thread,"public thread identities agree");
 regression_check(cs.OwningThread==thread,"critical section owner is the public thread");
 regression_check(RtlTryEnterCriticalSection(&cs),"same owner recursive try succeeds");RtlLeaveCriticalSection(&cs);RtlLeaveCriticalSection(&cs);
 for(unsigned mode=0;mode<4;mode++)for(unsigned s=0;s<8;s++)sample(mode,32768,s);
 regression_check(cs.LockCount==-1 && cs.RecursionCount==0 && !cs.OwningThread,"critical section ends fully released");
 regression_finish();
}
