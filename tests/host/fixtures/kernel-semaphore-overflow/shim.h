/* SPDX-License-Identifier: GPL-2.0-only
 * Host-only kernel boundary/SEH shim. Actual production functions follow.
 * setjmp models exception filter decisions; native x86 SEH remains separate. */
#include <assert.h>
#include <limits.h>
#include <setjmp.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#define IN
#define OUT
#define OPTIONAL
#define NTAPI
#define PAGED_CODE() ((void)0)
#define DPRINT(...) ((void)0)
#define FALSE 0
#define TRUE 1
#define KernelMode 0
#define UserMode 1
#define DISPATCH_LEVEL 2
#define IO_NO_INCREMENT 0
#define SEMAPHORE_MODIFY_STATE 2
#define EXCEPTION_EXECUTE_HANDLER 1
#define EXCEPTION_CONTINUE_SEARCH 0
#define STATUS_SUCCESS ((int32_t)0)
#define STATUS_INVALID_PARAMETER ((int32_t)0xc000000d)
#define STATUS_INVALID_HANDLE ((int32_t)0xc0000008)
#define STATUS_SEMAPHORE_LIMIT_EXCEEDED ((int32_t)0xc0000047)
#define STATUS_ACCESS_VIOLATION ((int32_t)0xc0000005)
#define NT_SUCCESS(status) ((status) >= 0)
typedef int32_t LONG, NTSTATUS, KPRIORITY, *PLONG;
typedef unsigned char KIRQL, BOOLEAN;
typedef int KPROCESSOR_MODE;
typedef void VOID, *PVOID, *HANDLE;
typedef struct LIST_ENTRY { struct LIST_ENTRY *Flink, *Blink; } LIST_ENTRY;
typedef struct { unsigned char Type, Absolute, Size, Inserted;
                 LONG SignalState; LIST_ENTRY WaitListHead; } DISPATCHER_HEADER;
typedef struct { DISPATCHER_HEADER Header; LONG Limit; } KSEMAPHORE, *PKSEMAPHORE;
typedef struct { BOOLEAN WaitNext; KIRQL WaitIrql; } KTHREAD, *PKTHREAD;
static KTHREAD thread;
static KSEMAPHORE semaphore;
static int type_tag;
static void *ExSemaphoreObjectType = &type_tag;
static KPROCESSOR_MODE caller_mode;
static unsigned references, reference_calls, locks;
static NTSTATUS reference_status, lock_exception, probe_exception;
static LONG concurrent_state = -1;

typedef struct SEH_FRAME { jmp_buf target; struct SEH_FRAME *previous; } SEH_FRAME;
static SEH_FRAME *seh_frame;
static NTSTATUS exception_code;
static void ExRaiseStatus(NTSTATUS status)
{
    exception_code = status;
    assert(seh_frame != NULL);
    longjmp(seh_frame->target, 1);
}
#define _SEH2_GetExceptionCode() (exception_code)
#define _SEH2_TRY do { \
    SEH_FRAME frame; frame.previous = seh_frame; seh_frame = &frame; \
    volatile int handled = 0; int raised = setjmp(frame.target); \
    if (!raised) {
#define _SEH2_EXCEPT(filter) } else if ((handled = ((filter) == EXCEPTION_EXECUTE_HANDLER))) {
#define _SEH2_END } seh_frame = frame.previous; \
    if (raised && !handled) ExRaiseStatus(exception_code); } while (0)
#define _SEH2_YIELD(statement) do { seh_frame = frame.previous; statement; } while (0)
static KPROCESSOR_MODE KeGetPreviousMode(void) { return caller_mode; }
static KPROCESSOR_MODE ExGetPreviousMode(void) { return caller_mode; }
static void ProbeForWriteLong(PLONG output)
{
    assert(output != NULL);
    if (probe_exception) ExRaiseStatus(probe_exception);
}
static NTSTATUS ObReferenceObjectByHandle(HANDLE handle, unsigned access,
        PVOID type, KPROCESSOR_MODE mode, PVOID *object, PVOID info)
{
    ++reference_calls;
    assert(access == SEMAPHORE_MODIFY_STATE && type == ExSemaphoreObjectType);
    assert(mode == caller_mode && info == NULL);
    if (reference_status) return reference_status;
    if (handle != &semaphore) return STATUS_INVALID_HANDLE;
    ++references; *object = &semaphore; return STATUS_SUCCESS;
}
static void ObDereferenceObject(PVOID object)
{
    assert(object == &semaphore && references == 1); --references;
}
static KIRQL KiAcquireDispatcherLock(void)
{
    if (lock_exception) ExRaiseStatus(lock_exception);
    assert(locks == 0); ++locks;
    if (concurrent_state >= 0) semaphore.Header.SignalState = concurrent_state;
    return 1;
}
static void KiReleaseDispatcherLock(KIRQL old)
{
    assert(old == 1 && locks == 1); --locks;
}
#define ASSERT_SEMAPHORE(object) assert((object) == &semaphore)
#define ASSERT_IRQL_LESS_OR_EQUAL(level) assert((level) == DISPATCH_LEVEL)
static int IsListEmpty(LIST_ENTRY *head) { return head->Flink == head; }
static void KiWaitTest(DISPATCHER_HEADER *header, KPRIORITY increment)
{
    (void)header; (void)increment; assert(!"no waiters in this bounded host case");
}
static PKTHREAD KeGetCurrentThread(void) { return &thread; }
