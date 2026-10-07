/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <ntoskrnl.h>
#include <xb-debug.h>

/* KeInitializeInterrupt / Connect / Disconnect are NDK (ndk/kefuncs.h)
 * prototypes, not part of the DDK headers xbe.c includes -- declare them
 * locally. */
NTKERNELAPI
VOID
NTAPI
KeInitializeInterrupt(IN PKINTERRUPT Interrupt,
                      IN PKSERVICE_ROUTINE ServiceRoutine,
                      IN PVOID ServiceContext,
                      IN PKSPIN_LOCK SpinLock,
                      IN ULONG Vector,
                      IN KIRQL Irql,
                      IN KIRQL SynchronizeIrql,
                      IN KINTERRUPT_MODE InterruptMode,
                      IN BOOLEAN ShareVector,
                      IN CHAR ProcessorNumber,
                      IN BOOLEAN FloatingSave);
NTKERNELAPI BOOLEAN NTAPI KeConnectInterrupt(IN PKINTERRUPT Interrupt);
NTKERNELAPI BOOLEAN NTAPI KeDisconnectInterrupt(IN PKINTERRUPT Interrupt);

/* KINTERRUPT shadow.  Xbox KINTERRUPT is 112 bytes; NT's is 484 (60-byte
 * header + 424-byte DispatchCode tail).  Letting NT initialise into the
 * caller's buffer writes 372 bytes past the end.  Maintain an NT-shaped
 * buffer per Xbox KINTERRUPT and dispatch the lifecycle through it. */
typedef struct _XBE_INTERRUPT_SHADOW
{
    PKINTERRUPT XboxInterrupt;          /* title's pointer -- lookup key */
    BOOLEAN DriverOwned;               /* tombstone survives unbind */
    PKINTERRUPT BorrowedInterrupt;      /* active hardware owner, if borrowed */
    /* 512 bytes is comfortably > NT's sizeof(KINTERRUPT) (484) and a clean
     * paragraph round.  C_ASSERT below pins down the choice. */
    UCHAR       NtInterruptStorage[512];
} XBE_INTERRUPT_SHADOW;

#define XBE_INTERRUPT_SHADOW_SLOTS 8

static XBE_INTERRUPT_SHADOW XeInterruptShadows[XBE_INTERRUPT_SHADOW_SLOTS];

static XBE_INTERRUPT_SHADOW *
XeInterruptGetShadow(PKINTERRUPT XboxInt, BOOLEAN Allocate)
{
    KIRQL OldIrql;
    XBE_INTERRUPT_SHADOW *Result = NULL;
    ULONG i;

    KeRaiseIrql(HIGH_LEVEL, &OldIrql);
    for (i = 0; i < XBE_INTERRUPT_SHADOW_SLOTS; i++)
    {
        if (XeInterruptShadows[i].XboxInterrupt == XboxInt)
        {
            Result = &XeInterruptShadows[i];
            break;
        }
    }
    if (Result == NULL && Allocate)
    {
        for (i = 0; i < XBE_INTERRUPT_SHADOW_SLOTS; i++)
        {
            if (XeInterruptShadows[i].XboxInterrupt == NULL)
            {
                XeInterruptShadows[i].XboxInterrupt = XboxInt;
                RtlZeroMemory(XeInterruptShadows[i].NtInterruptStorage,
                              sizeof(XeInterruptShadows[i].NtInterruptStorage));
                Result = &XeInterruptShadows[i];
                break;
            }
        }
    }
    KeLowerIrql(OldIrql);
    return Result;
}

/* Associate a public interrupt with the driver's actual IRQ object. */
VOID XeInterruptBindNative(PKINTERRUPT Xbox, PKINTERRUPT Native)
{
    XBE_INTERRUPT_SHADOW *shadow = XeInterruptGetShadow(Xbox, TRUE);
    if (shadow) {
        KIRQL old;
        KeRaiseIrql(HIGH_LEVEL, &old);
        shadow->DriverOwned = TRUE;
        shadow->BorrowedInterrupt = Native;
        KeLowerIrql(old);
    }
}
static PKINTERRUPT XeInterruptNative(XBE_INTERRUPT_SHADOW *shadow)
{
    return shadow->BorrowedInterrupt ? shadow->BorrowedInterrupt :
           (PKINTERRUPT)shadow->NtInterruptStorage;
}

/* Xbox KeInitializeInterrupt has no caller-supplied spin lock and no SMP
 * params; NT's does.  Pass NULL for the lock (use KINTERRUPT's built-in
 * one), mirror Irql as the synchronize IRQL, pin processor 0 without FP
 * save.  Writes 484 bytes into the *shadow*; the title's buffer is left
 * alone (its address is still the lookup key for Connect/Disconnect). */
VOID NTAPI
XeKeInitializeInterrupt(PKINTERRUPT Interrupt,
                          PKSERVICE_ROUTINE ServiceRoutine,
                          PVOID ServiceContext,
                          ULONG Vector,
                          KIRQL Irql,
                          KINTERRUPT_MODE InterruptMode,
                          BOOLEAN ShareVector)
{
    XBE_INTERRUPT_SHADOW *Shadow = XeInterruptGetShadow(Interrupt, TRUE);
    if (Shadow == NULL)
    {
        XbDbg("KeInitializeInterrupt: shadow table full, KINTERRUPT %p "
                 "ignored\n", Interrupt);
        return;
    }
    if (Shadow->DriverOwned) return; /* title cannot replace active IRQ owner */
    KeInitializeInterrupt((PKINTERRUPT)Shadow->NtInterruptStorage,
                          ServiceRoutine, ServiceContext,
                          NULL, Vector, Irql, Irql, InterruptMode,
                          ShareVector, 0, FALSE);
}

/* Title KINTERRUPT leaves ActualLock NULL.  NT's KeSynchronizeExecution
 * derefs Interrupt->ActualLock at +0x1C; KefAcquireSpinLockAtDpcLevel then
 * bugchecks with IRQL_NOT_GREATER_OR_EQUAL.  Route through the shadow's NT
 * KINTERRUPT (stamps ActualLock = &SpinLock) so the lock is real.
 * If no shadow exists, just call the routine directly -- uniprocessor Xbox
 * makes the lock a no-op anyway and titles expect forward progress. */
BOOLEAN NTAPI
XeKeSynchronizeExecution(_In_ PKINTERRUPT Interrupt,
                           _In_ PKSYNCHRONIZE_ROUTINE SynchronizeRoutine,
                           _In_opt_ PVOID SynchronizeContext)
{
    XBE_INTERRUPT_SHADOW *Shadow = XeInterruptGetShadow(Interrupt, FALSE);
    if (Shadow == NULL)
    {
        XbDbg("KeSynchronizeExecution(%p): no shadow; running "
                 "uncontended\n", Interrupt);
        return SynchronizeRoutine(SynchronizeContext);
    }
    if (Shadow->DriverOwned) {
        /* Xbox is UP: DPC level excludes pageable driver teardown while the
         * borrowed pointer is inspected and used. No lock spans the callback,
         * so nested synchronization remains safe. Teardown unbinds at HIGH. */
        KIRQL old = KeGetCurrentIrql();
        BOOLEAN result;
        if (old < DISPATCH_LEVEL) KeRaiseIrql(DISPATCH_LEVEL, &old);
        result = Shadow->BorrowedInterrupt ?
            KeSynchronizeExecution(Shadow->BorrowedInterrupt,
                                   SynchronizeRoutine, SynchronizeContext) : FALSE;
        if (old < DISPATCH_LEVEL) KeLowerIrql(old);
        return result;
    }
    return KeSynchronizeExecution(XeInterruptNative(Shadow),
                                  SynchronizeRoutine, SynchronizeContext);
}

/* No-shadow means KeInitializeInterrupt was never called for this
 * KINTERRUPT -- a caller bug; log and refuse. */
BOOLEAN NTAPI
XeKeConnectInterrupt(PKINTERRUPT Interrupt)
{
    XBE_INTERRUPT_SHADOW *Shadow = XeInterruptGetShadow(Interrupt, FALSE);
    if (Shadow == NULL)
    {
        XbDbg("KeConnectInterrupt(%p): no shadow; ignored\n", Interrupt);
        return FALSE;
    }
    if (Shadow->DriverOwned) {
        KIRQL old = KeGetCurrentIrql();
        BOOLEAN connected;
        if (old < DISPATCH_LEVEL) KeRaiseIrql(DISPATCH_LEVEL, &old);
        connected = Shadow->BorrowedInterrupt && Shadow->BorrowedInterrupt->Connected;
        if (old < DISPATCH_LEVEL) KeLowerIrql(old);
        return connected;
    }
    return KeConnectInterrupt(XeInterruptNative(Shadow));
}

BOOLEAN NTAPI
XeKeDisconnectInterrupt(PKINTERRUPT Interrupt)
{
    XBE_INTERRUPT_SHADOW *Shadow = XeInterruptGetShadow(Interrupt, FALSE);
    if (Shadow == NULL)
        return FALSE;
    if (Shadow->DriverOwned) return FALSE; /* driver owns lifecycle, even detached */
    return KeDisconnectInterrupt(XeInterruptNative(Shadow));
}
