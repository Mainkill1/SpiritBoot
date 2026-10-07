/* SPDX-License-Identifier: GPL-2.0-or-later
 * Independently implemented from public XboxDev/nxdk HAL declarations.
 * Storage remains caller-owned until removed or invoked. Unregister cancels
 * pending callbacks, but cannot cancel a callback already executing; callers
 * must keep that registration alive until its callback returns. Registration
 * during shutdown is ignored. Nested direct drains are inert. A nested
 * power request aborts only the current callback to our SEH drain boundary;
 * its noreturn callsite never resumes. Callbacks must release resources
 * before that call or through supported SEH unwind/finally cleanup. Normal
 * kernel APCs are suppressed during drain: callbacks must not await them.
 * Special APCs needed by synchronous native IO completion remain enabled.
 */
#include <ntoskrnl.h>
typedef struct _NX_SHUTDOWN_REGISTRATION NX_SHUTDOWN_REGISTRATION;
typedef VOID (NTAPI *NX_SHUTDOWN_CALLBACK)(NX_SHUTDOWN_REGISTRATION *);
struct _NX_SHUTDOWN_REGISTRATION {
    NX_SHUTDOWN_CALLBACK NotificationRoutine;
    LONG Priority;
    LIST_ENTRY ListEntry;
};
C_ASSERT(sizeof(NX_SHUTDOWN_REGISTRATION) == 16);
static LIST_ENTRY NxRegistered = { &NxRegistered, &NxRegistered };
static LIST_ENTRY NxPending = { &NxPending, &NxPending };
static KSPIN_LOCK NxShutdownLock;
static BOOLEAN NxShuttingDown;
static PETHREAD NxCallbackThread;
static KEVENT NxShutdownGate;
static BOOLEAN NxShutdownGateReady;
#define NX_SHUTDOWN_UNWIND_STATUS ((NTSTATUS)0xE0425842L)

static BOOLEAN NxRemoveRegistration(PLIST_ENTRY Head, NX_SHUTDOWN_REGISTRATION *Registration)
{
    PLIST_ENTRY e;
    for (e = Head->Flink; e != Head; e = e->Flink)
        if (e == &Registration->ListEntry) {
            RemoveEntryList(e); InitializeListHead(e); return TRUE;
        }
    return FALSE;
}
VOID NTAPI HalRegisterShutdownNotification(PVOID Storage, BOOLEAN Register)
{
    NX_SHUTDOWN_REGISTRATION *r = Storage;
    PLIST_ENTRY e;
    KIRQL irql;
    if (r == NULL) return;
    KeAcquireSpinLock(&NxShutdownLock, &irql);
    if (!Register) {
        NxRemoveRegistration(&NxRegistered, r);
        NxRemoveRegistration(&NxPending, r);
    } else if (!NxShuttingDown && r->NotificationRoutine != NULL) {
        /* Detect duplicates without trusting uninitialized caller link fields. */
        for (e = NxRegistered.Flink; e != &NxRegistered; e = e->Flink)
            if (e == &r->ListEntry) goto out;
        for (e = NxRegistered.Flink; e != &NxRegistered; e = e->Flink)
            if (CONTAINING_RECORD(e, NX_SHUTDOWN_REGISTRATION, ListEntry)->Priority < r->Priority)
                break;
        InsertTailList(e, &r->ListEntry); /* strictly lower: ties remain stable */
    }
out:
    KeReleaseSpinLock(&NxShutdownLock, irql);
}
static VOID NxDrainShutdownNotifications(VOID)
{
    KIRQL irql;
    KeAcquireSpinLock(&NxShutdownLock, &irql);
    if (NxShuttingDown) { KeReleaseSpinLock(&NxShutdownLock, irql); return; }
    if (!NxShutdownGateReady) {
        KeInitializeEvent(&NxShutdownGate, NotificationEvent, FALSE);
        NxShutdownGateReady = TRUE;
    }
    NxShuttingDown = TRUE;
    while (!IsListEmpty(&NxRegistered))
        InsertTailList(&NxPending, RemoveHeadList(&NxRegistered));
    KeReleaseSpinLock(&NxShutdownLock, irql);
    for (;;) {
        NX_SHUTDOWN_REGISTRATION *r;
        NX_SHUTDOWN_CALLBACK callback;
        KeAcquireSpinLock(&NxShutdownLock, &irql);
        if (IsListEmpty(&NxPending)) { KeReleaseSpinLock(&NxShutdownLock, irql); break; }
        r = CONTAINING_RECORD(RemoveHeadList(&NxPending), NX_SHUTDOWN_REGISTRATION, ListEntry);
        InitializeListHead(&r->ListEntry);
        callback = r->NotificationRoutine;
        NxCallbackThread = PsGetCurrentThread();
        KeReleaseSpinLock(&NxShutdownLock, irql);
        _SEH2_TRY {
            _SEH2_TRY {
                callback(r);
            } _SEH2_EXCEPT(_SEH2_GetExceptionCode() == NX_SHUTDOWN_UNWIND_STATUS ?
                          EXCEPTION_EXECUTE_HANDLER : EXCEPTION_CONTINUE_SEARCH) {
                /* Public return-to-firmware is noreturn: abandon this frame
                 * while allowing the remaining registration list to run. */
            } _SEH2_END;
        } _SEH2_FINALLY {
            NxCallbackThread = NULL;
        } _SEH2_END;
    }
}

/* Balanced for private direct-drain checks and on propagated exceptions.
 * HAL holds an additional outer guard through the nonreturning hardware
 * action, so this leave cannot deliver a normal APC on the reset owner. */
VOID NTAPI NxkShutdownNotifications(VOID)
{
    KeEnterCriticalRegion();
    _SEH2_TRY {
        NxDrainShutdownNotifications();
    } _SEH2_FINALLY {
        KeLeaveCriticalRegion();
    } _SEH2_END;
}

/* Latched for this boot. Title return wrapper avoids nested FS/launch work. */
BOOLEAN NTAPI NxkShutdownInProgress(VOID) { return NxShuttingDown; }

/* Only the active callback thread has the matching kernel unwind frame.
 * A different ordinary thread requesting reset cannot return either: park
 * until the outer action resets the machine, without raising an exception. */
DECLSPEC_NORETURN VOID NTAPI NxkShutdownAbortPowerRequest(VOID)
{
    KIRQL irql;
    BOOLEAN owner;
    KeAcquireSpinLock(&NxShutdownLock, &irql);
    owner = NxCallbackThread == PsGetCurrentThread();
    if (!NxShutdownGateReady) {
        KeInitializeEvent(&NxShutdownGate, NotificationEvent, FALSE);
        NxShutdownGateReady = TRUE;
    }
    KeReleaseSpinLock(&NxShutdownLock, irql);
    if (owner) RtlRaiseStatus(NX_SHUTDOWN_UNWIND_STATUS);
    for (;;) KeWaitForSingleObject(&NxShutdownGate, Executive, KernelMode, FALSE, NULL);
}
