/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <windows.h>
#include <xboxkrnl/xboxkrnl.h>
#include "regression.h"
static volatile ULONG calls;
static PVOID observed_context;
static DWORD callback_thread;
static VOID NTAPI callback(PVOID context, ULONG low, LONG high)
{
    (void)low; (void)high;
    observed_context = context;
    callback_thread = GetCurrentThreadId();
    ++calls;
}
static void run_case(KPROCESSOR_MODE mode, BOOLEAN alertable, BOOLEAN cancel_pending)
{
    HANDLE timer = NULL, event = NULL;
    LARGE_INTEGER due = {.QuadPart = -500000}, timeout = {.QuadPart = -5000000};
    LARGE_INTEGER zero = {.QuadPart = 0};
    NTSTATUS status;
    static ULONG marker;
    ULONG started = GetTickCount();
    DWORD setter = GetCurrentThreadId();
    regression_require(NT_SUCCESS(NtCreateTimer(&timer, NULL, NotificationTimer)), "create timer");
    regression_require(NT_SUCCESS(NtCreateEvent(&event, NULL, NotificationEvent, FALSE)), "create unsignaled event");
    calls = 0; observed_context = NULL; callback_thread = 0;
    regression_require(NT_SUCCESS(NtSetTimerEx(timer, &due, callback, mode, &marker, FALSE, 0, NULL)), "arm timer callback");
    status = NtWaitForSingleObjectEx(event, UserMode, alertable, &timeout);
    tap_comment("mode=%u alertable=%u cancel=%u status=%08lx elapsed=%lu callbacks=%lu",
                (unsigned)mode, (unsigned)alertable, (unsigned)cancel_pending,
                (ULONG)status, GetTickCount() - started, calls);
    regression_check(status == ((mode == UserMode && alertable) ? STATUS_USER_APC : STATUS_TIMEOUT),
                     "wait status honors timer APC mode");
    if (mode == UserMode && !alertable) {
        regression_check(calls == 0, "user callback stays queued during nonalertable wait");
        if (cancel_pending) NtCancelTimer(timer, NULL);
        status = NtWaitForSingleObjectEx(event, UserMode, TRUE, &zero);
        regression_check(status == (cancel_pending ? STATUS_TIMEOUT : STATUS_USER_APC),
                         "queued user APC dispatch or cancellation controls next alertable wait");
    }
    regression_check(calls == (cancel_pending ? 0u : 1u), "callback count is exact");
    if (!cancel_pending) {
        regression_check(observed_context == &marker, "callback receives original context");
        regression_check(callback_thread == setter, "callback runs on setting thread");
    }
    NtCancelTimer(timer, NULL); NtClose(timer); NtClose(event);
}
int main(void)
{
    regression_begin();
    run_case(UserMode, TRUE, FALSE);
    run_case(UserMode, FALSE, FALSE);
    run_case(UserMode, FALSE, TRUE);
    run_case(KernelMode, TRUE, FALSE);
    regression_finish();
}
