/* SPDX-License-Identifier: GPL-2.0-or-later
 * Actual IDE/interrupt modules with poisoned released IRQ storage. */
#include <ntoskrnl.h>
#include <sys/mman.h>
#include <stdio.h>
static PKINTERRUPT expected;
static ULONG callbacks, native_calls, starts_seen, finishes_seen;
static unsigned checks;
#define CHECK(c) do { ++checks; if (!(c)) { fprintf(stderr,"FAIL %u: %s\n",checks,#c); return 1; } } while(0)
VOID NTAPI KeInitializeInterrupt(PKINTERRUPT i,PKSERVICE_ROUTINE r,PVOID c,PKSPIN_LOCK l,
 ULONG v,KIRQL q,KIRQL s,KINTERRUPT_MODE m,BOOLEAN share,CHAR cpu,BOOLEAN f)
{ (void)r;(void)c;(void)l;(void)s;(void)cpu;(void)f;
 i->Initialized=TRUE;i->Vector=v;i->Irql=q;i->Mode=m;i->ShareVector=share;i->Connected=FALSE; }
BOOLEAN NTAPI KeConnectInterrupt(PKINTERRUPT i) { assert(i->Initialized);i->Connected=TRUE;return TRUE; }
BOOLEAN NTAPI KeDisconnectInterrupt(PKINTERRUPT i) { assert(i->Initialized);i->Connected=FALSE;return TRUE; }
BOOLEAN NTAPI KeSynchronizeExecution(PKINTERRUPT i,PKSYNCHRONIZE_ROUTINE r,PVOID c)
{ assert(i==expected); assert(i->Initialized);++native_calls;return r(c); }
#include "../../../ntoskrnl/xb/interrupt.c"
#include "../../../ntoskrnl/xb/ide.c"
static BOOLEAN sync_callback(PVOID p) { assert(p==(PVOID)7);++callbacks;return TRUE; }
static BOOLEAN irq(PKINTERRUPT i,PVOID p) { assert(i==expected);assert(p==(PVOID)1);return TRUE; }
static VOID timer(PDEVICE_OBJECT d, PVOID p) { (void)d; assert(p==(PVOID)3); }
static BOOLEAN start(PVOID c,PVOID r) { assert(c==(PVOID)1);assert(r==(PVOID)2);++starts_seen;return TRUE; }
static IRP same_irp;
static VOID finish_and_requeue(PVOID r)
{ assert(r==(PVOID)2);++finishes_seen;
  assert(NxkIdeStartRequest((PVOID)1,(PVOID)2,start,NULL,&same_irp,4)); }
static VOID finish_final(PVOID r) { assert(r==(PVOID)2);++finishes_seen; }
int main(void)
{
    PKINTERRUPT native = mmap(NULL,PAGE_SIZE,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    CHECK(native!=MAP_FAILED);
    native->Initialized=TRUE;native->Connected=TRUE;native->Irql=5;native->Vector=14;
    expected=native;
    NxkIdeSetHardwareIsr(irq,(PVOID)1);NxkIdeBindInterrupt(native);
    PKINTERRUPT public=(PKINTERRUPT)&IdexChannelObject.InterruptObject;
    CHECK(XeKeConnectInterrupt(public));
    CHECK(XeKeSynchronizeExecution(public,sync_callback,(PVOID)7));
    CHECK(callbacks==1&&native_calls==1&&current_irql==0);
    CHECK(!XeKeDisconnectInterrupt(public));
    NxkIdeStartRequest((PVOID)1,(PVOID)2,start,NULL,&same_irp,5);
    NxkIdeFinishRequest((PVOID)2,finish_and_requeue,&same_irp);
    CHECK(IdexChannelObject.CurrentIrp==&same_irp);
    CHECK(IdexChannelObject.StartPacketBusy&&IdexChannelObject.ExpectingBusMasterInterrupt);
    NxkIdeFinishRequest((PVOID)2,finish_final,&same_irp);
    CHECK(starts_seen==2&&finishes_seen==2);
    CHECK(!IdexChannelObject.CurrentIrp&&!IdexChannelObject.StartPacketBusy&&!IdexChannelObject.ExpectingBusMasterInterrupt);
    NxkIdeUnbindChannel((PVOID)9); /* unrelated teardown must preserve owner */
    CHECK(XeKeConnectInterrupt(public));
    NxkIdeStartTimer(NULL,(PVOID)3,timer);
    CHECK(IdexChannelObject.Timer.Armed);
    NxkIdeUnbindChannel((PVOID)1);
    CHECK(!IdexChannelObject.Timer.Armed&&!TimerOperation&&!TimerPort&&!TimerDevice);
    CHECK(mprotect(native,PAGE_SIZE,PROT_NONE)==0); /* released storage cannot be touched */
    CHECK(!XeKeConnectInterrupt(public));
    CHECK(!XeKeSynchronizeExecution(public,sync_callback,(PVOID)7));
    CHECK(!XeKeDisconnectInterrupt(public));
    CHECK(callbacks==1&&native_calls==1);
    CHECK(!IdexChannelObject.InterruptObject.Connected&&!HardwareContext&&!HardwareIsr);
    CHECK(!NxkIdeIsr(native,NULL));
    /* Reinitializing the public interrupt cannot acquire a second owner. */
    XeKeInitializeInterrupt(public,irq,NULL,14,5,LevelSensitive,FALSE);
    CHECK(!XeKeConnectInterrupt(public));
    KINTERRUPT replacement={.Initialized=TRUE,.Connected=TRUE,.Irql=5,.Vector=14};
    expected=&replacement;
    NxkIdeSetHardwareIsr(irq,(PVOID)1);NxkIdeBindInterrupt(expected);
    CHECK(XeKeConnectInterrupt(public));
    CHECK(XeKeSynchronizeExecution(public,sync_callback,(PVOID)7));
    CHECK(callbacks==2&&native_calls==2);
    NxkIdeUnbindChannel((PVOID)1);munmap(native,PAGE_SIZE);
    /* Failed connect leaves no native object and no channel context. */
    NxkIdeSetHardwareIsr(irq,(PVOID)1);NxkIdeUnbindChannel((PVOID)1);
    CHECK(!XeKeConnectInterrupt(public)&&!HardwareContext);
    printf("IDE lifecycle host checks: %u/%u passed\n",checks,checks);
    return 0;
}
