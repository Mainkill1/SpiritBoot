/* SPDX-License-Identifier: GPL-2.0-or-later */
#define _GNU_SOURCE
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <assert.h>
#include <sys/mman.h>

typedef uint32_t ULONG, *PULONG, ULONG_PTR, KSPIN_LOCK, *PKSPIN_LOCK;
typedef uint8_t UCHAR, BOOLEAN, KIRQL, *PKIRQL;
typedef int8_t CHAR, CCHAR;
typedef int16_t CSHORT;
typedef void VOID, *PVOID;
typedef enum { LevelSensitive, Latched } KINTERRUPT_MODE;
#define NTAPI __attribute__((stdcall))
#define FASTCALL __attribute__((fastcall))
#define IN
#define OUT
#define OPTIONAL
#define _In_
#define _In_opt_
#define NTKERNELAPI
#define TRUE 1
#define FALSE 0
#define HIGH_LEVEL 31
#define DISPATCH_LEVEL 2
#define IPI_LEVEL 29
#define MAXULONG UINT32_MAX
#define DISPATCH_LENGTH 106
#define InterruptObject 22
#define ASSERT assert
#define C_ASSERT(c) _Static_assert(c, #c)
#define FIELD_OFFSET(t, f) offsetof(t, f)
#define CONTAINING_RECORD(p, t, f) ((t *)((char *)(p) - offsetof(t, f)))
#define PtrToUlong(p) ((ULONG)(uintptr_t)(p))
#define RtlZeroMemory(p, n) memset(p, 0, n)
#define XbDbg(...) ((void)0)
#define DPRINT1(...) ((void)0)
#define UNREFERENCED_PARAMETER(x) ((void)(x))

typedef struct _KINTERRUPT KINTERRUPT, *PKINTERRUPT;
typedef BOOLEAN (NTAPI *PKSERVICE_ROUTINE)(PKINTERRUPT, PVOID);
typedef BOOLEAN (NTAPI *PKSYNCHRONIZE_ROUTINE)(PVOID);
typedef struct _LIST_ENTRY {
    struct _LIST_ENTRY *Flink, *Blink;
} LIST_ENTRY, *PLIST_ENTRY;
typedef struct { ULONG unused; } KTRAP_FRAME, *PKTRAP_FRAME;
typedef VOID (FASTCALL *PKINTERRUPT_ROUTINE)(PKTRAP_FRAME, PKINTERRUPT);

/* Test-owned NT5/i386 layout. Every field consumed by the extracted bodies is
 * present; the native dispatch-code bytes are copied but never executed. */
struct _KINTERRUPT {
    CSHORT Type, Size;
    LIST_ENTRY InterruptListEntry;
    PKSERVICE_ROUTINE ServiceRoutine;
    PVOID ServiceContext;
    KSPIN_LOCK SpinLock;
    ULONG TickCount;
    PKSPIN_LOCK ActualLock;
    PKINTERRUPT_ROUTINE DispatchAddress;
    ULONG Vector;
    KIRQL Irql, SynchronizeIrql;
    BOOLEAN FloatingSave, Connected;
    CCHAR Number;
    BOOLEAN ShareVector;
    KINTERRUPT_MODE Mode;
    ULONG ServiceCount, DispatchCount;
    ULONG DispatchCode[DISPATCH_LENGTH];
};
C_ASSERT(sizeof(void *) == 4);
C_ASSERT(sizeof(KINTERRUPT) == 484);
C_ASSERT(FIELD_OFFSET(KINTERRUPT, ServiceRoutine) == 0x0c);
C_ASSERT(FIELD_OFFSET(KINTERRUPT, ActualLock) == 0x1c);
C_ASSERT(FIELD_OFFSET(KINTERRUPT, Connected) == 0x2b);
C_ASSERT(FIELD_OFFSET(KINTERRUPT, DispatchCode) == 0x3c);

/* Independent public Xbox header: neither the production facade declaration
 * nor its native-pointer typedef is used as the expected memory layout. */
typedef struct {
    PKSERVICE_ROUTINE ServiceRoutine;
    PVOID ServiceContext;
    ULONG BusInterruptLevel, Irql;
    BOOLEAN Connected, ShareVector;
    UCHAR Mode, Padding;
    ULONG ServiceCount;
    ULONG DispatchCode[22];
} HOST_PUBLIC_INTERRUPT;
C_ASSERT(sizeof(HOST_PUBLIC_INTERRUPT) == 112);
C_ASSERT(FIELD_OFFSET(HOST_PUBLIC_INTERRUPT, ServiceRoutine) == 0);
C_ASSERT(FIELD_OFFSET(HOST_PUBLIC_INTERRUPT, ServiceContext) == 4);
C_ASSERT(FIELD_OFFSET(HOST_PUBLIC_INTERRUPT, Connected) == 0x10);
C_ASSERT(FIELD_OFFSET(HOST_PUBLIC_INTERRUPT, ServiceCount) == 0x14);
C_ASSERT(FIELD_OFFSET(HOST_PUBLIC_INTERRUPT, DispatchCode) == 0x18);

typedef enum { NoConnect, NormalConnect, ChainConnect, UnknownConnect } CONNECT_TYPE;
typedef struct { CONNECT_TYPE Type; PKINTERRUPT Interrupt; } DISPATCH_INFO;
typedef struct { ULONG InterruptCount; } HOST_PRCB;
static HOST_PRCB prcb;
static DISPATCH_INFO installed[64];
static KIRQL current_irql;
static CHAR KeNumberProcessors = 1;
static unsigned checks, failures, hal_enables, hal_disables, exits, spurious_exits;
static unsigned native_sync_acquires, affinity_calls, dispatcher_depth;
static BOOLEAN hal_admit = TRUE, hal_enable_result = TRUE;
static PKSPIN_LOCK held_lock;
static PKINTERRUPT protected_borrow;
static BOOLEAN inject_at_release;
static ULONG inject_vector;
static unsigned injected_dispatches;

#define CHECK(label, condition) do { \
    ++checks; if (!(condition)) { ++failures; \
    fprintf(stderr, "FAIL %s (line %u): %s\n", label, __LINE__, #condition); } \
} while (0)

/* A private deterministic initializer template, not copied reference code.
 * Its object marker makes native KeInitializeInterrupt patch within its own
 * 424-byte tail. The host calls the extracted C dispatchers directly. */
static struct { ULONG Words[DISPATCH_LENGTH]; ULONG Object; } HostTemplate;
#define KiInterruptTemplate (HostTemplate.Words)
#define KiInterruptTemplateObject (HostTemplate.Object)

VOID FASTCALL KiInterruptDispatch(PKTRAP_FRAME, PKINTERRUPT);
VOID FASTCALL KiChainedDispatch(PKTRAP_FRAME, PKINTERRUPT);
BOOLEAN NTAPI KeDisconnectInterrupt(PKINTERRUPT);

static HOST_PRCB *KeGetCurrentPrcb(void) { return &prcb; }
static KIRQL KeGetCurrentIrql(void) { return current_irql; }
static VOID KeRaiseIrql(KIRQL next, PKIRQL old)
{
    assert(next >= current_irql && next <= HIGH_LEVEL);
    /* Native synchronize reads the borrowed IRQL before this boundary. The
     * wrapper must already have excluded pageable teardown at DPC level. */
    if (protected_borrow && next == protected_borrow->SynchronizeIrql)
        CHECK("driver.synchronize.guard_irql", current_irql >= DISPATCH_LEVEL);
    *old = current_irql;
    current_irql = next;
}
static VOID KeLowerIrql(KIRQL next) { assert(next <= current_irql); current_irql = next; }
static KIRQL KfRaiseIrql(KIRQL next) { KIRQL old; KeRaiseIrql(next, &old); return old; }
static VOID KfLowerIrql(KIRQL next) { KeLowerIrql(next); }
static VOID KeInitializeSpinLock(PKSPIN_LOCK lock) { *lock = 0; }
static VOID KxAcquireSpinLock(PKSPIN_LOCK lock)
{
    assert(lock && !held_lock && !*lock && current_irql >= DISPATCH_LEVEL);
    *lock = 1; held_lock = lock;
}
static VOID KxReleaseSpinLock(PKSPIN_LOCK lock)
{
    assert(lock && lock == held_lock && *lock == 1);
    *lock = 0; held_lock = NULL;
}
static VOID KeAcquireSpinLockAtDpcLevel(PKSPIN_LOCK lock)
{ ++native_sync_acquires; KxAcquireSpinLock(lock); }
static VOID KeReleaseSpinLockFromDpcLevel(PKSPIN_LOCK lock) { KxReleaseSpinLock(lock); }
static VOID InitializeListHead(PLIST_ENTRY head) { head->Flink = head->Blink = head; }
static VOID InsertTailList(PLIST_ENTRY head, PLIST_ENTRY entry)
{ entry->Flink = head; entry->Blink = head->Blink; head->Blink->Flink = entry; head->Blink = entry; }
static VOID RemoveEntryList(PLIST_ENTRY entry)
{ entry->Blink->Flink = entry->Flink; entry->Flink->Blink = entry->Blink; }
static VOID KeSetSystemAffinityThread(ULONG affinity)
{ assert(affinity == 1 && current_irql <= DISPATCH_LEVEL); ++affinity_calls; }
static VOID KeRevertToUserAffinityThread(void) { assert(current_irql <= DISPATCH_LEVEL); }
static KIRQL KiAcquireDispatcherLock(void)
{ assert(current_irql <= DISPATCH_LEVEL && !dispatcher_depth); dispatcher_depth = 1; return KfRaiseIrql(DISPATCH_LEVEL); }
static VOID KiReleaseDispatcherLock(KIRQL old)
{
    assert(dispatcher_depth == 1 && current_irql == DISPATCH_LEVEL);
    dispatcher_depth = 0; KeLowerIrql(old);
    if (inject_at_release) {
        DISPATCH_INFO dispatch = installed[inject_vector];
        inject_at_release = FALSE;
        assert(dispatch.Type == NormalConnect && dispatch.Interrupt->Connected);
        ++injected_dispatches;
        KiInterruptDispatch(NULL, dispatch.Interrupt);
    }
}
static VOID KiGetVectorDispatch(ULONG vector, DISPATCH_INFO *dispatch)
{ assert(vector >= 0x30 && vector < 0x40); *dispatch = installed[vector]; }
static VOID KiConnectVectorToInterrupt(PKINTERRUPT interrupt, CONNECT_TYPE type)
{ assert(interrupt->Vector >= 0x30 && interrupt->Vector < 0x40); installed[interrupt->Vector] = (DISPATCH_INFO){type, interrupt}; }
static BOOLEAN HalEnableSystemInterrupt(ULONG vector, KIRQL irql, KINTERRUPT_MODE mode)
{ assert(vector >= 0x30 && vector < 0x40); (void)irql; (void)mode; ++hal_enables; return hal_enable_result; }
static VOID HalDisableSystemInterrupt(ULONG vector, KIRQL irql)
{ assert(vector >= 0x30 && vector < 0x40); (void)irql; ++hal_disables; }
static BOOLEAN HalBeginSystemInterrupt(KIRQL irql, ULONG vector, PKIRQL old)
{ assert(vector >= 0x30 && vector < 0x40); *old = current_irql; if (!hal_admit) return FALSE; current_irql = irql; return TRUE; }
static VOID KiExitInterrupt(PKTRAP_FRAME frame, KIRQL old, BOOLEAN spurious)
{ (void)frame; assert(!held_lock); ++exits; spurious_exits += spurious; current_irql = old; }

/*
 * @implemented
 */
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
                      IN BOOLEAN FloatingSave)
{
    ULONG i;
    PULONG DispatchCode = &Interrupt->DispatchCode[0], Patch = DispatchCode;

    /* Set the Interrupt Header */
    Interrupt->Type = InterruptObject;
    Interrupt->Size = sizeof(KINTERRUPT);

    /* Check if we got a spinlock */
    if (SpinLock)
    {
        Interrupt->ActualLock = SpinLock;
    }
    else
    {
        /* Use the built-in one */
        KeInitializeSpinLock(&Interrupt->SpinLock);
        Interrupt->ActualLock = &Interrupt->SpinLock;
    }

    /* Set the other settings */
    Interrupt->ServiceRoutine = ServiceRoutine;
    Interrupt->ServiceContext = ServiceContext;
    Interrupt->Vector = Vector;
    Interrupt->Irql = Irql;
    Interrupt->SynchronizeIrql = SynchronizeIrql;
    Interrupt->Mode = InterruptMode;
    Interrupt->ShareVector = ShareVector;
    Interrupt->Number = ProcessorNumber;
    Interrupt->FloatingSave = FloatingSave;
    Interrupt->TickCount = MAXULONG;
    Interrupt->DispatchCount = MAXULONG;

    /* Loop the template in memory */
    for (i = 0; i < DISPATCH_LENGTH; i++)
    {
        /* Copy the dispatch code */
        *DispatchCode++ = ((PULONG)KiInterruptTemplate)[i];
    }

    /* Jump to the last 4 bytes */
    Patch = (PULONG)((ULONG_PTR)Patch +
                     ((ULONG_PTR)&KiInterruptTemplateObject -
                      (ULONG_PTR)KiInterruptTemplate) - 4);

    /* Apply the patch */
    *Patch = PtrToUlong(Interrupt);

    /* Disconnect it at first */
    Interrupt->Connected = FALSE;
}

VOID
FASTCALL
KiInterruptDispatch(IN PKTRAP_FRAME TrapFrame,
                    IN PKINTERRUPT Interrupt)
{
    KIRQL OldIrql;

    /* Increase interrupt count */
    KeGetCurrentPrcb()->InterruptCount++;

    /* Begin the interrupt, making sure it's not spurious */
    if (HalBeginSystemInterrupt(Interrupt->SynchronizeIrql,
                                Interrupt->Vector,
                                &OldIrql))
    {
        /* Acquire interrupt lock */
        KxAcquireSpinLock(Interrupt->ActualLock);

        /* Call the ISR */
        Interrupt->ServiceRoutine(Interrupt, Interrupt->ServiceContext);

        /* Release interrupt lock */
        KxReleaseSpinLock(Interrupt->ActualLock);

        /* Now call the epilogue code */
        KiExitInterrupt(TrapFrame, OldIrql, FALSE);
    }
    else
    {
        /* Now call the epilogue code */
        KiExitInterrupt(TrapFrame, OldIrql, TRUE);
    }
}

VOID
FASTCALL
KiChainedDispatch(IN PKTRAP_FRAME TrapFrame,
                  IN PKINTERRUPT Interrupt)
{
    KIRQL OldIrql, OldInterruptIrql = 0;
    BOOLEAN Handled;
    PLIST_ENTRY NextEntry, ListHead;

    /* Increase interrupt count */
    KeGetCurrentPrcb()->InterruptCount++;

    /* Begin the interrupt, making sure it's not spurious */
    if (HalBeginSystemInterrupt(Interrupt->Irql,
                                Interrupt->Vector,
                                &OldIrql))
    {
        /* Get list pointers */
        ListHead = &Interrupt->InterruptListEntry;
        NextEntry = ListHead; /* The head is an entry! */
        while (TRUE)
        {
            /* Check if this interrupt's IRQL is higher than the current one */
            if (Interrupt->SynchronizeIrql > Interrupt->Irql)
            {
                /* Raise to higher IRQL */
                OldInterruptIrql = KfRaiseIrql(Interrupt->SynchronizeIrql);
            }

            /* Acquire interrupt lock */
            KxAcquireSpinLock(Interrupt->ActualLock);

            /* Call the ISR */
            Handled = Interrupt->ServiceRoutine(Interrupt,
                                                Interrupt->ServiceContext);

            /* Release interrupt lock */
            KxReleaseSpinLock(Interrupt->ActualLock);

            /* Check if this interrupt's IRQL is higher than the current one */
            if (Interrupt->SynchronizeIrql > Interrupt->Irql)
            {
                /* Lower the IRQL back */
                ASSERT(OldInterruptIrql == Interrupt->Irql);
                KfLowerIrql(OldInterruptIrql);
            }

            /* Check if the interrupt got handled and it's level */
            if ((Handled) && (Interrupt->Mode == LevelSensitive)) break;

            /* What's next? */
            NextEntry = NextEntry->Flink;

            /* Is this the last one? */
            if (NextEntry == ListHead)
            {
                /* Level should not have gotten here */
                if (Interrupt->Mode == LevelSensitive) break;

                /* As for edge, we can only exit once nobody can handle the interrupt */
                if (!Handled) break;
            }

            /* Get the interrupt object for the next pass */
            Interrupt = CONTAINING_RECORD(NextEntry, KINTERRUPT, InterruptListEntry);
        }

        /* Now call the epilogue code */
        KiExitInterrupt(TrapFrame, OldIrql, FALSE);
    }
    else
    {
        /* Now call the epilogue code */
        KiExitInterrupt(TrapFrame, OldIrql, TRUE);
    }
}

/*
 * @implemented
 */
BOOLEAN
NTAPI
KeConnectInterrupt(IN PKINTERRUPT Interrupt)
{
    BOOLEAN Connected, Error, Status;
    KIRQL Irql, OldIrql;
    UCHAR Number;
    ULONG Vector;
    DISPATCH_INFO Dispatch;

    /* Get data from interrupt */
    Number = Interrupt->Number;
    Vector = Interrupt->Vector;
    Irql = Interrupt->Irql;

#ifdef SARCH_XBOX
    /* Hardware interrupts occupy IDT entries 0x30 through 0x3f only.
     * Validate the full ULONG before HAL's UCHAR IDT conversion can wrap. */
    if ((Vector < 0x30) || (Vector >= 0x40)) return FALSE;
#endif

    /* Validate the settings */
    if ((Irql > HIGH_LEVEL) ||
        (Number >= KeNumberProcessors) ||
        (Interrupt->SynchronizeIrql < Irql) ||
        (Interrupt->FloatingSave))
    {
        return FALSE;
    }

    /* Set defaults */
    Connected = FALSE;
    Error = FALSE;

    /* Set the system affinity and acquire the dispatcher lock */
    KeSetSystemAffinityThread(1 << Number);
    OldIrql = KiAcquireDispatcherLock();

    /* Check if it's already been connected */
    if (!Interrupt->Connected)
    {
        /* Get vector dispatching information */
        KiGetVectorDispatch(Vector, &Dispatch);

        /* Check if the vector is already connected */
        if (Dispatch.Type == NoConnect)
        {
            /* Do the connection */
            Interrupt->Connected = Connected = TRUE;

            /* Initialize the list */
            InitializeListHead(&Interrupt->InterruptListEntry);

            /* Connect and enable the interrupt */
            KiConnectVectorToInterrupt(Interrupt, NormalConnect);
            Status = HalEnableSystemInterrupt(Vector, Irql, Interrupt->Mode);
            if (!Status) Error = TRUE;
        }
        else if ((Dispatch.Type != UnknownConnect) &&
                (Interrupt->ShareVector) &&
                (Dispatch.Interrupt->ShareVector) &&
                (Dispatch.Interrupt->Mode == Interrupt->Mode))
        {
            /* The vector is shared and the interrupts are compatible */
            Interrupt->Connected = Connected = TRUE;

            /*
             * Verify the IRQL for chained connect,
             */
#if defined(CONFIG_SMP)
            ASSERT(Irql <= SYNCH_LEVEL);
#else
            ASSERT(Irql <= (IPI_LEVEL - 2));
#endif

            /* Check if this is the first chain */
            if (Dispatch.Type != ChainConnect)
            {
                /* This is not supported */
                ASSERT(Dispatch.Interrupt->Mode != Latched);

                /* Setup the chainned handler */
                KiConnectVectorToInterrupt(Dispatch.Interrupt, ChainConnect);
            }

            /* Insert into the interrupt list */
            InsertTailList(&Dispatch.Interrupt->InterruptListEntry,
                           &Interrupt->InterruptListEntry);
        }
    }

    /* Unlock the dispatcher and revert affinity */
    KiReleaseDispatcherLock(OldIrql);
    KeRevertToUserAffinityThread();

    /* Check if we failed while trying to connect */
    if ((Connected) && (Error))
    {
        DPRINT1("HalEnableSystemInterrupt failed\n");
        KeDisconnectInterrupt(Interrupt);
        Connected = FALSE;
    }

    /* Return to caller */
    return Connected;
}

/*
 * @implemented
 */
BOOLEAN
NTAPI
KeDisconnectInterrupt(IN PKINTERRUPT Interrupt)
{
    KIRQL OldIrql, Irql;
    ULONG Vector;
    DISPATCH_INFO Dispatch;
    PKINTERRUPT NextInterrupt;
    BOOLEAN State;

#ifdef SARCH_XBOX
    /* Guard caller-owned settings before affinity shifts or IDT lookup. */
    if ((Interrupt->Vector < 0x30) || (Interrupt->Vector >= 0x40) ||
        ((UCHAR)Interrupt->Number >= KeNumberProcessors)) return FALSE;
#endif

    /* Set the affinity */
    KeSetSystemAffinityThread(1 << Interrupt->Number);

    /* Lock the dispatcher */
    OldIrql = KiAcquireDispatcherLock();

    /* Check if it's actually connected */
    State = Interrupt->Connected;
    if (State)
    {
        /* Get the vector and IRQL */
        Irql = Interrupt->Irql;
        Vector = Interrupt->Vector;

        /* Get vector dispatch data */
        KiGetVectorDispatch(Vector, &Dispatch);

        /* Check if it was chained */
        if (Dispatch.Type == ChainConnect)
        {
            /* Check if the top-level interrupt is being removed */
#if defined(CONFIG_SMP)
            ASSERT(Irql <= SYNCH_LEVEL);
#else
            ASSERT(Irql <= (IPI_LEVEL - 2));
#endif
            if (Interrupt == Dispatch.Interrupt)
            {
                /* Get the next one */
                Dispatch.Interrupt = CONTAINING_RECORD(Dispatch.Interrupt->
                                                       InterruptListEntry.Flink,
                                                       KINTERRUPT,
                                                       InterruptListEntry);

                /* Reconnect it */
                KiConnectVectorToInterrupt(Dispatch.Interrupt, ChainConnect);
            }

            /* Remove it */
            RemoveEntryList(&Interrupt->InterruptListEntry);

            /* Get the next one */
            NextInterrupt = CONTAINING_RECORD(Dispatch.Interrupt->
                                              InterruptListEntry.Flink,
                                              KINTERRUPT,
                                              InterruptListEntry);

            /* Check if this is the only one left */
            if (Dispatch.Interrupt == NextInterrupt)
            {
                /* Connect it in non-chained mode */
                KiConnectVectorToInterrupt(Dispatch.Interrupt, NormalConnect);
            }
        }
        else
        {
            /* Only one left, disable and remove it */
            HalDisableSystemInterrupt(Interrupt->Vector, Irql);
            KiConnectVectorToInterrupt(Interrupt, NoConnect);
        }

        /* Disconnect it */
        Interrupt->Connected = FALSE;
    }

    /* Unlock the dispatcher and revert affinity */
    KiReleaseDispatcherLock(OldIrql);
    KeRevertToUserAffinityThread();

    /* Return to caller */
    return State;
}

/*
 * @implemented
 */
BOOLEAN
NTAPI
KeSynchronizeExecution(IN OUT PKINTERRUPT Interrupt,
                       IN PKSYNCHRONIZE_ROUTINE SynchronizeRoutine,
                       IN PVOID SynchronizeContext OPTIONAL)
{
    BOOLEAN Success;
    KIRQL OldIrql;

    /* Raise IRQL */
    KeRaiseIrql(Interrupt->SynchronizeIrql,
                &OldIrql);

    /* Acquire interrupt spinlock */
    KeAcquireSpinLockAtDpcLevel(Interrupt->ActualLock);

    /* Call the routine */
    Success = SynchronizeRoutine(SynchronizeContext);

    /* Release lock */
    KeReleaseSpinLockFromDpcLevel(Interrupt->ActualLock);

    /* Lower IRQL */
    KeLowerIrql(OldIrql);

    /* Return status */
    return Success;
}

/* SPDX-License-Identifier: GPL-2.0-or-later */

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

/* SPDX-License-Identifier: GPL-2.0-or-later */
typedef struct {
    UCHAR Before[32];
    HOST_PUBLIC_INTERRUPT Public;
    UCHAR After[32];
} GUARDED_PUBLIC;
typedef struct {
    PKINTERRUPT Expected;
    PVOID Tag;
    KIRQL Irql;
    unsigned Calls;
    BOOLEAN Handled, InConnect, SawConnectWindow;
} ISR_CONTEXT;
typedef struct {
    PKSPIN_LOCK Lock;
    KIRQL Irql;
    unsigned Calls;
    BOOLEAN Result;
} SYNC_CONTEXT;
static SYNC_CONTEXT *expected_sync_context;

static VOID reset(void)
{
    memset(XeInterruptShadows, 0, sizeof(XeInterruptShadows));
    memset(installed, 0, sizeof(installed));
    memset(&prcb, 0, sizeof(prcb));
    current_irql = 0;
    held_lock = NULL;
    protected_borrow = NULL;
    hal_admit = hal_enable_result = TRUE;
    hal_enables = hal_disables = exits = spurious_exits = 0;
    native_sync_acquires = affinity_calls = dispatcher_depth = 0;
    inject_at_release = FALSE;
    injected_dispatches = 0;
    expected_sync_context = NULL;
    for (ULONG i = 0; i < DISPATCH_LENGTH; ++i)
        HostTemplate.Words[i] = 0x10203040u ^ (i * 0x01010101u);
}
static PKINTERRUPT public_key(GUARDED_PUBLIC *object)
{ return (PKINTERRUPT)&object->Public; }
static VOID seed(GUARDED_PUBLIC *object, UCHAR fill)
{ memset(object, fill, sizeof(*object)); object->Public.ServiceCount = 0x12345678; }
static VOID retained(const GUARDED_PUBLIC *object, const GUARDED_PUBLIC *before)
{
    CHECK("public.guard.before", !memcmp(object->Before, before->Before, sizeof(object->Before)));
    CHECK("public.guard.after", !memcmp(object->After, before->After, sizeof(object->After)));
    CHECK("public.service_count.preserved", object->Public.ServiceCount == before->Public.ServiceCount);
    CHECK("public.dispatch_tail.preserved", !memcmp(object->Public.DispatchCode, before->Public.DispatchCode, sizeof(object->Public.DispatchCode)));
    CHECK("public.padding.preserved", object->Public.Padding == before->Public.Padding);
}
static BOOLEAN NTAPI title_isr(PKINTERRUPT interrupt, PVOID context)
{
    ISR_CONTEXT *call = context;
    HOST_PUBLIC_INTERRUPT *public = (HOST_PUBLIC_INTERRUPT *)interrupt;
    ++call->Calls;
    CHECK("dispatch.original_public_identity", interrupt == call->Expected);
    CHECK("dispatch.original_context", context == call->Tag);
    CHECK("dispatch.public_connected", public->Connected == TRUE);
    CHECK("dispatch.at_device_irql", current_irql == call->Irql);
    CHECK("dispatch.native_lock_held", held_lock != NULL && *held_lock == 1);
    if (call->InConnect) {
        call->SawConnectWindow = TRUE;
        CHECK("dispatch.before_connect_return.connected", public->Connected == TRUE);
    }
    return call->Handled;
}
static BOOLEAN NTAPI sync_callback(PVOID context)
{
    SYNC_CONTEXT *call = context;
    ++call->Calls;
    CHECK("synchronize.original_context", call == expected_sync_context);
    CHECK("synchronize.actual_irql", current_irql == call->Irql);
    CHECK("synchronize.actual_lock", held_lock == call->Lock);
    return call->Result;
}
static VOID initialize(GUARDED_PUBLIC *object, ISR_CONTEXT *call, ULONG vector,
                       KINTERRUPT_MODE mode, BOOLEAN share)
{
    XeKeInitializeInterrupt(public_key(object), title_isr, call, vector,
                            call->Irql, mode, share);
    CHECK("public.header.routine", object->Public.ServiceRoutine == title_isr);
    CHECK("public.header.context", object->Public.ServiceContext == call);
    CHECK("public.header.bus_level", object->Public.BusInterruptLevel == vector - 0x30);
    CHECK("public.header.irql", object->Public.Irql == call->Irql);
    CHECK("public.header.disconnected", object->Public.Connected == FALSE);
    CHECK("public.header.share", object->Public.ShareVector == share);
    CHECK("public.header.mode", object->Public.Mode == (UCHAR)mode);
}
static ISR_CONTEXT isr_context(GUARDED_PUBLIC *object, KIRQL irql, BOOLEAN handled)
{
    ISR_CONTEXT call = { public_key(object), NULL, irql, 0, handled, FALSE, FALSE };
    return call;
}

static VOID facade_lifecycle(void)
{
    reset();
    GUARDED_PUBLIC first, second;
    seed(&first, 0xa5); seed(&second, 0x5a);
    GUARDED_PUBLIC first_before = first, second_before = second;
    ISR_CONTEXT one = isr_context(&first, 12, TRUE);
    ISR_CONTEXT two = isr_context(&second, 11, TRUE);
    one.Tag = &one; two.Tag = &two;
    initialize(&first, &one, 0x3b, LevelSensitive, FALSE);
    initialize(&second, &two, 0x3c, Latched, TRUE);
    GUARDED_PUBLIC second_initialized = second;
    retained(&first, &first_before); retained(&second, &second_before);
    XBE_INTERRUPT_SHADOW *s1 = XeInterruptGetShadow(public_key(&first), FALSE);
    XBE_INTERRUPT_SHADOW *s2 = XeInterruptGetShadow(public_key(&second), FALSE);
    CHECK("shadow.two_distinct_address_keys", s1 && s2 && s1 != s2);
    CHECK("shadow.repeated_lookup_same_key", s1 == XeInterruptGetShadow(public_key(&first), FALSE));
    if (!s1 || !s2) return;
    PKINTERRUPT n1 = XeInterruptNative(s1), n2 = XeInterruptNative(s2);
    CHECK("shadow.native_separate_from_public", n1 != public_key(&first) && n2 != public_key(&second));
    CHECK("shadow.native_size", n1->Size == 484 && n2->Size == 484);
    CHECK("shadow.built_in_actual_lock", n1->ActualLock == &n1->SpinLock && n2->ActualLock == &n2->SpinLock);
    CHECK("shadow.private_vector_irql", n1->Vector == 0x3b && n1->Irql == 12 && n1->SynchronizeIrql == 12);
    CHECK("shadow.private_mode_share", n2->Mode == Latched && n2->ShareVector == TRUE && n2->Number == 0 && !n2->FloatingSave);
    CHECK("shadow.native_template_patch", n1->DispatchCode[DISPATCH_LENGTH - 1] == PtrToUlong(n1));

    /* Native release lowers dispatcher IRQL after installation/enabling. An
     * admitted IRQ can run here while the exported Connect is still active. */
    inject_vector = 0x3b; inject_at_release = TRUE; one.InConnect = TRUE;
    CHECK("lifecycle.first_connect", XeKeConnectInterrupt(public_key(&first)) == TRUE);
    one.InConnect = FALSE;
    CHECK("dispatch.connect_window_exercised", injected_dispatches == 1 && one.Calls == 1 && one.SawConnectWindow);
    CHECK("lifecycle.public_connected", first.Public.Connected == TRUE && n1->Connected == TRUE);
    CHECK("lifecycle.old_irql_restored", current_irql == 0 && !held_lock);
    CHECK("lifecycle.second_key_unchanged", !memcmp(&second, &second_initialized, sizeof(second)));
    CHECK("lifecycle.second_connect", XeKeConnectInterrupt(public_key(&second)) == TRUE);
    CHECK("lifecycle.second_public_connected", second.Public.Connected == TRUE);
    CHECK("lifecycle.repeat_connect_false", XeKeConnectInterrupt(public_key(&first)) == FALSE && first.Public.Connected == TRUE);
    KiInterruptDispatch(NULL, n1); KiInterruptDispatch(NULL, n2);
    CHECK("dispatch.two_contexts_independent", one.Calls == 2 && two.Calls == 1 && prcb.InterruptCount == 3);
    CHECK("dispatch.exit_restores_irql", exits == 3 && current_irql == 0 && !held_lock);
    hal_admit = FALSE;
    KiInterruptDispatch(NULL, n1);
    CHECK("dispatch.spurious_does_not_call", one.Calls == 2 && exits == 4 && spurious_exits == 1 && current_irql == 0);
    hal_admit = TRUE;

    SYNC_CONTEXT sync = {n1->ActualLock, 12, 0, TRUE};
    expected_sync_context = &sync;
    CHECK("synchronize.true_return", XeKeSynchronizeExecution(public_key(&first), sync_callback, &sync) == TRUE);
    sync.Result = FALSE;
    CHECK("synchronize.false_return", XeKeSynchronizeExecution(public_key(&first), sync_callback, &sync) == FALSE);
    CHECK("synchronize.native_body_used", sync.Calls == 2 && native_sync_acquires == 2 && current_irql == 0 && !held_lock);
    CHECK("lifecycle.first_disconnect", XeKeDisconnectInterrupt(public_key(&first)) == TRUE);
    CHECK("lifecycle.public_disconnected", first.Public.Connected == FALSE && n1->Connected == FALSE);
    CHECK("lifecycle.repeat_disconnect_false", XeKeDisconnectInterrupt(public_key(&first)) == FALSE && first.Public.Connected == FALSE);
    CHECK("lifecycle.other_key_still_connected", second.Public.Connected == TRUE && n2->Connected == TRUE);
    CHECK("lifecycle.second_disconnect", XeKeDisconnectInterrupt(public_key(&second)) == TRUE && second.Public.Connected == FALSE);
    retained(&first, &first_before); retained(&second, &second_before);

    /* Reinitialization replaces only the documented header and private native
     * state; it retains the key, count, padding, opaque tail and guard bytes. */
    one.Irql = 10;
    initialize(&first, &one, 0x3d, Latched, TRUE);
    CHECK("lifecycle.reinitialize_same_shadow", s1 == XeInterruptGetShadow(public_key(&first), FALSE) && n1->Vector == 0x3d);
    CHECK("lifecycle.reinitialized_connect", XeKeConnectInterrupt(public_key(&first)) == TRUE);
    KiInterruptDispatch(NULL, n1);
    CHECK("lifecycle.reinitialized_callback", one.Calls == 3);
    CHECK("lifecycle.reinitialized_disconnect", XeKeDisconnectInterrupt(public_key(&first)) == TRUE);
    retained(&first, &first_before);
}

static VOID chain_dispatch(void)
{
    reset();
    GUARDED_PUBLIC first, second; seed(&first, 0x36); seed(&second, 0x63);
    GUARDED_PUBLIC a = first, b = second;
    ISR_CONTEXT one = isr_context(&first, 12, FALSE), two = isr_context(&second, 12, TRUE);
    one.Tag = &one; two.Tag = &two;
    initialize(&first, &one, 0x3b, LevelSensitive, TRUE);
    initialize(&second, &two, 0x3b, LevelSensitive, TRUE);
    CHECK("chain.first_connect", XeKeConnectInterrupt(public_key(&first)) == TRUE);
    CHECK("chain.second_connect", XeKeConnectInterrupt(public_key(&second)) == TRUE);
    CHECK("chain.native_route", installed[0x3b].Type == ChainConnect);
    KiChainedDispatch(NULL, installed[0x3b].Interrupt);
    CHECK("chain.both_public_identities", one.Calls == 1 && two.Calls == 1 && current_irql == 0 && !held_lock);
    CHECK("chain.first_disconnect", XeKeDisconnectInterrupt(public_key(&first)) == TRUE && first.Public.Connected == FALSE);
    CHECK("chain.remaining_native_route", installed[0x3b].Type == NormalConnect && second.Public.Connected == TRUE);
    KiInterruptDispatch(NULL, installed[0x3b].Interrupt);
    CHECK("chain.remaining_public_identity", one.Calls == 1 && two.Calls == 2);
    CHECK("chain.final_disconnect", XeKeDisconnectInterrupt(public_key(&second)) == TRUE && second.Public.Connected == FALSE);
    retained(&first, &a); retained(&second, &b);
}

static BOOLEAN NTAPI driver_isr(PKINTERRUPT interrupt, PVOID context)
{
    CHECK("driver.native_isr_identity", interrupt == context);
    CHECK("driver.native_isr_connected", interrupt->Connected == TRUE);
    return TRUE;
}
static VOID driver_owned_tombstone(void)
{
    reset();
    GUARDED_PUBLIC title; seed(&title, 0x69); GUARDED_PUBLIC before = title;
    PKINTERRUPT native = mmap(NULL, 4096, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    assert(native != MAP_FAILED);
    KeInitializeInterrupt(native, driver_isr, native, NULL, 0x3b, 12, 12, LevelSensitive, FALSE, 0, FALSE);
    CHECK("driver.native_connect", KeConnectInterrupt(native) == TRUE);
    XeInterruptBindNative(public_key(&title), native);
    XBE_INTERRUPT_SHADOW *shadow = XeInterruptGetShadow(public_key(&title), FALSE);
    CHECK("driver.binding", shadow && shadow->DriverOwned && shadow->BorrowedInterrupt == native);
    KINTERRUPT native_before = *native;
    unsigned connections = hal_enables, affinity = affinity_calls;
    ISR_CONTEXT prohibited = isr_context(&title, 12, TRUE); prohibited.Tag = &prohibited;
    XeKeInitializeInterrupt(public_key(&title), title_isr, &prohibited, 0x3c, 11, Latched, TRUE);
    CHECK("driver.initialize_cannot_replace_owner", !memcmp(&title, &before, sizeof(title)) && !memcmp(native, &native_before, sizeof(*native)));
    CHECK("driver.connect_observes_owner", XeKeConnectInterrupt(public_key(&title)) == TRUE);
    CHECK("driver.disconnect_refused", XeKeDisconnectInterrupt(public_key(&title)) == FALSE && native->Connected == TRUE);
    CHECK("driver.lifecycle_no_native_mutation", hal_enables == connections && affinity_calls == affinity && current_irql == 0);
    protected_borrow = native;
    SYNC_CONTEXT sync = {native->ActualLock, 12, 0, TRUE};
    expected_sync_context = &sync;
    CHECK("driver.synchronize_routes_to_owner", XeKeSynchronizeExecution(public_key(&title), sync_callback, &sync) == TRUE);
    CHECK("driver.synchronize_native_irql_lock", sync.Calls == 1 && native_sync_acquires == 1 && current_irql == 0);
    protected_borrow = NULL;
    KiInterruptDispatch(NULL, native);
    CHECK("driver.title_isr_never_called", prohibited.Calls == 0);
    CHECK("driver.public_bytes_untouched", !memcmp(&title, &before, sizeof(title)));
    CHECK("driver.native_disconnect", KeDisconnectInterrupt(native) == TRUE);
    XeInterruptBindNative(public_key(&title), NULL);
    CHECK("driver.tombstone_retains_ownership", shadow->DriverOwned && shadow->BorrowedInterrupt == NULL);
    CHECK("driver.released_storage_poisoned", mprotect(native, 4096, PROT_NONE) == 0);
    CHECK("driver.tombstone_connect_false", XeKeConnectInterrupt(public_key(&title)) == FALSE);
    CHECK("driver.tombstone_sync_false", XeKeSynchronizeExecution(public_key(&title), sync_callback, &sync) == FALSE);
    CHECK("driver.tombstone_disconnect_false", XeKeDisconnectInterrupt(public_key(&title)) == FALSE);
    XeKeInitializeInterrupt(public_key(&title), title_isr, &prohibited, 0x3b, 12, LevelSensitive, FALSE);
    CHECK("driver.tombstone_init_cannot_take_ownership", !memcmp(&title, &before, sizeof(title)) && sync.Calls == 1 && prohibited.Calls == 0);
    KINTERRUPT replacement = {0};
    KeInitializeInterrupt(&replacement, driver_isr, &replacement, NULL, 0x3b, 12, 12, LevelSensitive, FALSE, 0, FALSE);
    CHECK("driver.replacement_connect", KeConnectInterrupt(&replacement) == TRUE);
    XeInterruptBindNative(public_key(&title), &replacement);
    CHECK("driver.rebind_observes_new_owner", XeKeConnectInterrupt(public_key(&title)) == TRUE);
    sync.Lock = replacement.ActualLock;
    protected_borrow = &replacement;
    CHECK("driver.rebind_synchronize", XeKeSynchronizeExecution(public_key(&title), sync_callback, &sync) == TRUE);
    protected_borrow = NULL;
    CHECK("driver.rebind_keeps_public_bytes", sync.Calls == 2 && !memcmp(&title, &before, sizeof(title)) && current_irql == 0);
    CHECK("driver.replacement_disconnect", KeDisconnectInterrupt(&replacement) == TRUE);
    XeInterruptBindNative(public_key(&title), NULL);
    CHECK("driver.released_storage_unmapped", munmap(native, 4096) == 0);
}

static VOID rejection_and_capacity(void)
{
    reset();
    GUARDED_PUBLIC object; seed(&object, 0x7e); GUARDED_PUBLIC before = object;
    CHECK("missing_shadow.connect_false", XeKeConnectInterrupt(public_key(&object)) == FALSE);
    CHECK("missing_shadow.disconnect_false", XeKeDisconnectInterrupt(public_key(&object)) == FALSE);
    SYNC_CONTEXT fallback = {NULL, 0, 0, FALSE};
    expected_sync_context = &fallback;
    CHECK("missing_shadow.synchronize_fallback", XeKeSynchronizeExecution(public_key(&object), sync_callback, &fallback) == FALSE && fallback.Calls == 1 && native_sync_acquires == 0);
    CHECK("missing_shadow.public_untouched", !memcmp(&object, &before, sizeof(object)));
    const ULONG invalid[] = {0, 0x2f, 0x40, 255, 256, UINT32_MAX};
    ISR_CONTEXT call = isr_context(&object, 12, TRUE); call.Tag = &call;
    for (unsigned i = 0; i < sizeof(invalid) / sizeof(*invalid); ++i) {
        reset();
        XeKeInitializeInterrupt(public_key(&object), title_isr, &call, invalid[i], 12, LevelSensitive, FALSE);
        GUARDED_PUBLIC initialized = object;
        CHECK("invalid_vector.connect_false", XeKeConnectInterrupt(public_key(&object)) == FALSE);
        CHECK("invalid_vector.disconnect_false", XeKeDisconnectInterrupt(public_key(&object)) == FALSE);
        CHECK("invalid_vector.no_hardware_or_public_mutation", affinity_calls == 0 && hal_enables == 0 && hal_disables == 0 && !memcmp(&object, &initialized, sizeof(object)));
        retained(&object, &before);
    }
    reset();
    seed(&object, 0x7e);
    initialize(&object, &call, 0x3b, LevelSensitive, FALSE);
    hal_enable_result = FALSE;
    CHECK("failed_enable.connect_false", XeKeConnectInterrupt(public_key(&object)) == FALSE);
    CHECK("failed_enable.rollback_public_disconnected", object.Public.Connected == FALSE && installed[0x3b].Type == NoConnect && hal_disables == 1);
    retained(&object, &before);

    reset();
    GUARDED_PUBLIC objects[9]; ISR_CONTEXT contexts[9];
    for (unsigned i = 0; i < 9; ++i) {
        seed(&objects[i], 0x42); contexts[i] = isr_context(&objects[i], 12, TRUE); contexts[i].Tag = &contexts[i];
        GUARDED_PUBLIC saved = objects[i];
        XeKeInitializeInterrupt(public_key(&objects[i]), title_isr, &contexts[i], 0x3b, 12, LevelSensitive, FALSE);
        CHECK("shadow.capacity_bound", (XeInterruptGetShadow(public_key(&objects[i]), FALSE) != NULL) == (i < 8));
        retained(&objects[i], &saved);
        if (i == 8) {
            CHECK("shadow.full_table_public_untouched", !memcmp(&objects[i], &saved, sizeof(saved)));
            CHECK("shadow.full_table_connect_false", XeKeConnectInterrupt(public_key(&objects[i])) == FALSE);
        }
    }
    CHECK("shadow.exhaustion_does_not_replace_first_key", XeInterruptGetShadow(public_key(&objects[0]), FALSE)->XboxInterrupt == public_key(&objects[0]));
}

int main(void)
{
    facade_lifecycle();
    chain_dispatch();
    driver_owned_tombstone();
    rejection_and_capacity();
    printf("interrupt public ABI: %u assertions, %u failures; i386 public=112 native=484\n", checks, failures);
    return failures ? 1 : 0;
}
