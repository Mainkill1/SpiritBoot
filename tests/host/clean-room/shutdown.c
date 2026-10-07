/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <stdio.h>
#include "ntoskrnl.h"
#include "../../../ntoskrnl/xb/shutdown.c"
static unsigned count, seen[8], checks, failed;
static NX_SHUTDOWN_REGISTRATION regs[6];
static BOOLEAN raise_unexpected;
#define CHECK(c) do { ++checks; if (!(c)) { ++failed; printf("not ok %u - %s\n", checks, #c); } else printf("ok %u - %s\n", checks, #c); } while(0)
static void callback(NX_SHUTDOWN_REGISTRATION *r)
{
    unsigned id = (unsigned)(r - regs);
    seen[count++] = id;
    if (raise_unexpected) RtlRaiseStatus((NTSTATUS)0xE0771234);
    if (id == 0) {
        HalRegisterShutdownNotification(&regs[4], FALSE); /* detached pending */
        HalRegisterShutdownNotification(&regs[5], TRUE); /* ignored in drain */
        NxkShutdownNotifications(); /* nested drain inert */
    }
}
int main(void)
{
    for (unsigned i=0; i<6; ++i) { regs[i].NotificationRoutine=callback; regs[i].Priority=i<2 ? 100 : 20-(LONG)i; }
    HalRegisterShutdownNotification(&regs[5], FALSE); /* uninitialized links */
    for (unsigned i=0; i<5; ++i) HalRegisterShutdownNotification(&regs[i], TRUE);
    HalRegisterShutdownNotification(&regs[0], TRUE);
    HalRegisterShutdownNotification(&regs[1], TRUE);
    HalRegisterShutdownNotification(&regs[3], FALSE);
    CHECK(regs[0].ListEntry.Flink == &regs[1].ListEntry);
    NxkShutdownNotifications();
    CHECK(count == 3);
    CHECK(seen[0] == 0 && seen[1] == 1 && seen[2] == 2);
    CHECK(IsListEmpty(&NxRegistered) && IsListEmpty(&NxPending));
    CHECK(regs[0].ListEntry.Flink == &regs[0].ListEntry);
    CHECK(HostCriticalDepth[1]==0&&NxCallbackThread==NULL);
    NxkShutdownNotifications(); CHECK(count == 3);
    CHECK(HostCriticalDepth[1]==0&&NxCallbackThread==NULL);
    /* An unrelated callback exception propagates while finally balances
     * suppression and clears the owner before any normal APC can resume. */
    NxShuttingDown=FALSE;raise_unexpected=TRUE;
    HalRegisterShutdownNotification(&regs[0],TRUE);
    BOOLEAN caught=FALSE;
    _SEH2_TRY {
        NxkShutdownNotifications();
    } _SEH2_EXCEPT(_SEH2_GetExceptionCode()==(NTSTATUS)0xE0771234 ? 1 : 0) {
        caught=TRUE;
    } _SEH2_END;
    CHECK(caught&&HostCriticalDepth[1]==0&&NxCallbackThread==NULL);
    printf("shutdown host checks: %u/%u passed\n", checks-failed, checks);
    return failed ? 1 : 0;
}
