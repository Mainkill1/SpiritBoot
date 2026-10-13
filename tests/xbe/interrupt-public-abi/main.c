/* SPDX-License-Identifier: GPL-2.0-or-later
 * Independently authored public ABI probe; no reference implementation input.
 */
#include <xboxkrnl/xboxkrnl.h>
#include <stdio.h>
#include <string.h>
#include "tap.h"

#define PMC_INTR_ENABLE (*(volatile ULONG *)0xfd000140UL)
#define PCRTC_INTR (*(volatile ULONG *)0xfd600100UL)
#define PCRTC_INTR_ENABLE (*(volatile ULONG *)0xfd600140UL)
#define VBLANK 1UL

static struct {
    ULONG prefix[16];
    KINTERRUPT interrupt;
    ULONG suffix[128];
} guarded;
static KEVENT observed;
static KDPC observed_dpc;
static volatile ULONG callback_count;
static volatile ULONG callback_interrupt;
static volatile ULONG callback_context;
static volatile ULONG dpc_count;
static volatile ULONG dpc_irql;
static ULONG owned_context = 0x49525133UL;
static unsigned checks;
static unsigned failures;

static void check(int pass, const char *name)
{
    ++checks;
    if (pass) tap_ok(checks, name);
    else { ++failures; tap_not_ok(checks, name); }
}

static VOID NTAPI signal_observed(PKDPC dpc, PVOID context,
                                 PVOID argument1, PVOID argument2)
{
    (void)dpc;
    (void)argument1;
    (void)argument2;
    dpc_irql = KeGetCurrentIrql();
    ++dpc_count;
    KeSetEvent((PKEVENT)context, 0, FALSE);
}

static BOOLEAN NTAPI service(PKINTERRUPT interrupt, PVOID context)
{
    if (!(PCRTC_INTR & VBLANK)) return FALSE;
    PCRTC_INTR = VBLANK;
    callback_interrupt = (ULONG)interrupt;
    callback_context = (ULONG)context;
    ++callback_count;
    /* Event signaling requires DISPATCH_LEVEL or below. The ISR runs
     * at DIRQL; defer signaling through an owned DPC. */
    KeInsertQueueDpc(&observed_dpc, NULL, NULL);
    return TRUE;
}

static int guards_ok(void)
{
    unsigned i;
    for (i = 0; i < sizeof(guarded.prefix)/sizeof(guarded.prefix[0]); ++i)
        if (guarded.prefix[i] != 0xa5a5a5a5UL) return 0;
    for (i = 0; i < sizeof(guarded.suffix)/sizeof(guarded.suffix[0]); ++i)
        if (guarded.suffix[i] != 0xa5a5a5a5UL) return 0;
    return 1;
}

static void finish(void) __attribute__((noreturn));
static void finish(void)
{
    tap_comment("checks=%u failures=%u", checks, failures);
    tap_plan(checks);
    tap_puts("# interrupt_identity_probe_finished\n");
    tap_drain();
    HalWriteSMBusValue(0x20, 0x02, FALSE, 0x80);
    for (;;) __asm__ __volatile__("hlt");
}

int main(void)
{
    KIRQL irql = 0;
    ULONG vector, pmc, pcrtc;
    BOOLEAN connected, disconnected;
    NTSTATUS wait_status = STATUS_UNSUCCESSFUL;
    LARGE_INTEGER timeout;

    tap_version(14);
    memset(&guarded, 0xa5, sizeof(guarded));
    KeInitializeEvent(&observed, NotificationEvent, FALSE);
    KeInitializeDpc(&observed_dpc, signal_observed, &observed);
    vector = HalGetInterruptVector(3, &irql);
    tap_comment("public_object=%08lx bytes=%lu irq3_vector=%lu irql=%u context=%08lx",
                (ULONG)&guarded.interrupt, (ULONG)sizeof(KINTERRUPT), vector,
                (unsigned)irql, (ULONG)&owned_context);
    check(sizeof(KINTERRUPT) == 112, "public interrupt structure is 112 bytes");
    check(vector != 0 && irql > DISPATCH_LEVEL, "IRQ3 yields a usable public vector and IRQL");
    if (!vector) finish();

    KeInitializeInterrupt(&guarded.interrupt, service, &owned_context,
                          vector, irql, LevelSensitive, TRUE);
    check(guards_ok(), "initialization stays within the public object");
    check(guarded.interrupt.BusInterruptLevel == 3,
          "initialization publishes the hardware IRQ level");
    check(guarded.interrupt.ServiceRoutine == service, "initialization publishes the service routine");
    check(guarded.interrupt.ServiceContext == &owned_context, "initialization publishes the supplied context");
    check(guarded.interrupt.Irql == irql, "initialization publishes the public IRQL");
    check(guarded.interrupt.ShareVector && guarded.interrupt.Mode == LevelSensitive,
          "initialization publishes sharing and trigger mode");
    check(!guarded.interrupt.Connected, "initialized interrupt starts disconnected");
    tap_comment("initialized_bus_level=%lu irql=%lu connected=%u service_count=%lu",
                guarded.interrupt.BusInterruptLevel, guarded.interrupt.Irql,
                (unsigned)guarded.interrupt.Connected, guarded.interrupt.ServiceCount);

    pmc = PMC_INTR_ENABLE;
    pcrtc = PCRTC_INTR_ENABLE;
    PCRTC_INTR_ENABLE = 0;
    PCRTC_INTR = VBLANK;
    connected = KeConnectInterrupt(&guarded.interrupt);
    check(connected, "owned interrupt connects");
    check(guarded.interrupt.Connected == TRUE, "connect publishes public connected state");
    if (connected) {
        PCRTC_INTR_ENABLE = VBLANK;
        PMC_INTR_ENABLE = 1;
        timeout.QuadPart = -20000000LL;
        wait_status = KeWaitForSingleObject(&observed, Executive, KernelMode,
                                            FALSE, &timeout);
    }
    PCRTC_INTR_ENABLE = 0;
    PMC_INTR_ENABLE = pmc;
    PCRTC_INTR = VBLANK;
    disconnected = connected ? KeDisconnectInterrupt(&guarded.interrupt) : FALSE;
    KeRemoveQueueDpc(&observed_dpc);
    PCRTC_INTR_ENABLE = pcrtc;
    tap_comment("wait=%08lx callbacks=%lu received_object=%08lx received_context=%08lx dpcs=%lu dpc_irql=%lu",
                (ULONG)wait_status, callback_count, callback_interrupt, callback_context,
                dpc_count, dpc_irql);
    check(wait_status == STATUS_SUCCESS && callback_count != 0 &&
          dpc_count != 0 && dpc_irql == DISPATCH_LEVEL,
          "bounded vblank interrupt and deferred notification reach the owned handlers");
    check(callback_interrupt == (ULONG)&guarded.interrupt, "handler receives the original public interrupt object");
    check(callback_context == (ULONG)&owned_context, "handler receives the supplied context");
    check(disconnected, "owned interrupt disconnects");
    check(!guarded.interrupt.Connected, "disconnect clears public connected state");
    check(guards_ok(), "complete lifecycle preserves neighboring guards");
    finish();
}
