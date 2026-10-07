/* SPDX-License-Identifier: GPL-2.0-or-later */
#define HOST_SHUTDOWN_WAIT_STUB
#define HOST_SHUTDOWN_SCHEDULING_HOOKS
#include <ntoskrnl.h>
#include <stdio.h>
#include <setjmp.h>
#include <assert.h>
#define HALXBOX_H_INCLUDED
#define _In_
#define EFLAGS_INTERRUPT_MASK 0x200
#define SMB_DEVICE_SMC_PIC16LC 0x10
#define SMC_REG_POWER 2
#define SMC_REG_POWER_RESET 1
#define SMC_REG_POWER_CYCLE 0x40
#define SMC_REG_POWER_SHUTDOWN 0x80
#define PASSIVE_LEVEL 0
#define HIGH_LEVEL 31
typedef enum { HalHaltRoutine,HalPowerDownRoutine,HalRestartRoutine,HalRebootRoutine } FIRMWARE_REENTRY;
static KIRQL test_irql;
static ULONG test_flags, hardware_calls, publish_calls, invalidations, callbacks, sequence[4], emitted_action;
static jmp_buf halted, parked;
static ULONG parks;
static BOOLEAN other_thread_test;
static BOOLEAN callback_after_reset;
static BOOLEAN expect_emergency;
static ULONG cas_unprotected, publication_unprotected, hardware_unprotected;
static ULONG owner_gap_unprotected, owner_suppressed, special_deliveries, phases_seen;
static KIRQL KeGetCurrentIrql(void) { return test_irql; }
static ULONG __readeflags(void) { return test_flags; }
static LONG InterlockedCompareExchange(volatile LONG *p,LONG value,LONG old)
{ LONG result=*p;if(result==old)*p=value;HostSchedulingHook(100);return result; }
static void _disable(void) { test_flags &= ~EFLAGS_INTERRUPT_MASK; }
#define __halt() longjmp(halted,1)
#define UNREACHABLE return
static void DbgBreakPoint(void) { assert(0); }
static void HalpXboxSmBusWriteByte(UCHAR dev,UCHAR reg,UCHAR action)
{ HostSchedulingHook(300);assert(dev==SMB_DEVICE_SMC_PIC16LC&&reg==SMC_REG_POWER);++hardware_calls;emitted_action=action; }
VOID NTAPI NxkMmPublishPersistence(BOOLEAN warm)
{ HostSchedulingHook(200);if(warm) { assert(test_irql==0&&(test_flags&EFLAGS_INTERRUPT_MASK));++publish_calls; }
  else ++invalidations; }
NTSTATUS KeWaitForSingleObject(PVOID p,ULONG reason,ULONG mode,BOOLEAN alert,PVOID timeout)
{ (void)p;(void)reason;(void)mode;(void)alert;(void)timeout;++parks;longjmp(parked,1); }
DECLSPEC_NORETURN VOID NTAPI HalReturnToFirmware(FIRMWARE_REENTRY);
#include "../../../ntoskrnl/xb/shutdown.c"
#include "../../../hal/halx86/xbox/reboot.c"
VOID HostSchedulingHook(ULONG phase)
{
    BOOLEAN normal_blocked = HostCriticalDepth[HostThreadIndex()] > 0;
    /* Model a pending normal kernel APC at every scheduling boundary, and a
     * special completion APC which remains deliverable independently. */
    if (phase==100) { if(!normal_blocked) ++cas_unprotected; phases_seen|=8; }
    if (phase==200&&!expect_emergency) { if(!normal_blocked) ++publication_unprotected; phases_seen|=16; }
    if (phase==300&&!expect_emergency) { if(!normal_blocked) ++hardware_unprotected; phases_seen|=32; }
    if (phase<=3 && NxCallbackThread==HostCurrentThread) {
        phases_seen|=1u<<(phase-1);
        if(!normal_blocked) ++owner_gap_unprotected; else ++owner_suppressed;
        ++special_deliveries; /* No guarded-region/SpecialApcDisable used. */
    }
}
static NX_SHUTDOWN_REGISTRATION regs[2];
static VOID NTAPI callback(NX_SHUTDOWN_REGISTRATION *r)
{
    assert(test_irql==0&&(test_flags&EFLAGS_INTERRUPT_MASK));
    sequence[callbacks++]=(ULONG)(r-regs);
    if(r==&regs[0]) {
        if(other_thread_test) {
            HostCurrentThread=(PVOID)2;
            if(!setjmp(parked)) HalReturnToFirmware(HalPowerDownRoutine);
            /* Restore the owner thread after the simulated other thread parks.
             * This is a scheduler model, not a return to its noreturn callsite. */
            HostCurrentThread=(PVOID)1;
            assert(!hardware_calls);
        } else {
            HalReturnToFirmware(HalPowerDownRoutine);
            callback_after_reset=TRUE; /* must be unreachable */
        }
    }
}
static VOID reset_test(void)
{
    test_irql=0;test_flags=EFLAGS_INTERRUPT_MASK;hardware_calls=publish_calls=invalidations=callbacks=0;
    HalpPowerActionStarted=0;NxShuttingDown=FALSE;NxCallbackThread=NULL;
    NxShutdownGateReady=FALSE;HostCurrentThread=(PVOID)1;HostExceptionFrame=NULL;
    parks=HostUnwinds=0;other_thread_test=callback_after_reset=expect_emergency=FALSE;
    memset(HostCriticalDepth,0,sizeof(HostCriticalDepth));
    cas_unprotected=publication_unprotected=hardware_unprotected=0;
    owner_gap_unprotected=owner_suppressed=special_deliveries=phases_seen=0;
    InitializeListHead(&NxRegistered);InitializeListHead(&NxPending);
    for(unsigned i=0;i<2;++i) { regs[i].NotificationRoutine=callback;regs[i].Priority=2-i;
        HalRegisterShutdownNotification(&regs[i],TRUE); }
}
static unsigned checks;
#define CHECK(c) do{++checks;if(!(c)){fprintf(stderr,"FAIL %u: %s\n",checks,#c);return 1;}}while(0)
int main(void)
{
    reset_test();
    if(!setjmp(halted)) HalReturnToFirmware(HalRebootRoutine);
    CHECK(callbacks==2&&sequence[0]==0&&sequence[1]==1);
    CHECK(hardware_calls==1&&emitted_action==SMC_REG_POWER_RESET);
    CHECK(publish_calls==1&&!invalidations);
    CHECK(!(test_flags&EFLAGS_INTERRUPT_MASK));
    CHECK(HostUnwinds==1&&!callback_after_reset&&!parks);
    CHECK(!cas_unprotected&&!publication_unprotected&&!hardware_unprotected);
    CHECK(!owner_gap_unprotected&&owner_suppressed>0&&special_deliveries>0);
    CHECK((phases_seen&63)==63);
    CHECK(HostCriticalDepth[1]==1); /* outer guard persists through reset */
    /* A subsequent command also cannot issue hardware twice. */
    test_flags=EFLAGS_INTERRUPT_MASK;
    if(!setjmp(parked)) HalReturnToFirmware(HalRestartRoutine);
    CHECK(parks==1&&HostUnwinds==1);
    CHECK(hardware_calls==1&&publish_calls==1);
    reset_test();other_thread_test=TRUE;
    if(!setjmp(halted)) HalReturnToFirmware(HalRebootRoutine);
    CHECK(callbacks==2&&hardware_calls==1&&emitted_action==SMC_REG_POWER_RESET);
    CHECK(parks==1&&HostUnwinds==0&&!callback_after_reset);
    CHECK(!cas_unprotected&&!publication_unprotected&&!hardware_unprotected&&!owner_gap_unprotected);
    CHECK(HostCriticalDepth[1]==1&&HostCriticalDepth[2]==0); /* loser balances only its own guard */
    reset_test();expect_emergency=TRUE;test_irql=HIGH_LEVEL;
    if(!setjmp(halted)) HalpReboot();
    CHECK(callbacks==0&&hardware_calls==1&&emitted_action==SMC_REG_POWER_RESET);
    CHECK(publish_calls==0&&invalidations==1);
    CHECK(HostCriticalDepth[1]==0);
    reset_test();expect_emergency=TRUE;test_flags=0;
    if(!setjmp(halted)) HalReturnToFirmware(HalRebootRoutine);
    CHECK(callbacks==0&&hardware_calls==1);
    CHECK(publish_calls==0&&invalidations==1);
    CHECK(HostCriticalDepth[1]==0);
    reset_test();expect_emergency=TRUE;test_irql=1; /* APC context is also unsafe for normal IO */
    if(!setjmp(halted)) HalReturnToFirmware(HalPowerDownRoutine);
    CHECK(callbacks==0&&hardware_calls==1&&emitted_action==SMC_REG_POWER_SHUTDOWN);
    CHECK(publish_calls==0&&invalidations==1);
    CHECK(HostCriticalDepth[1]==0);
    printf("HAL power action host checks: %u/%u passed\n",checks,checks);
    return 0;
}
