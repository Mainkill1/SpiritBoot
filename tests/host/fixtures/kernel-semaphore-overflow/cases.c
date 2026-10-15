/* SPDX-License-Identifier: GPL-2.0-only */
static unsigned checks;
static int verify(int condition, const char *name)
{
    ++checks;
    if (!condition) fprintf(stderr, "FAIL: %s (exception=%08x refs=%u locks=%u)\n",
                            name, (uint32_t)exception_code, references, locks);
    return condition;
}
#define CHECK(condition, name) do { if (!verify((condition), (name))) return 1; } while (0)

static void reset(KPROCESSOR_MODE mode, LONG count, LONG limit)
{
    assert(seh_frame == NULL);
    caller_mode = mode;
    semaphore.Header.SignalState = count; semaphore.Limit = limit;
    semaphore.Header.WaitListHead.Flink = &semaphore.Header.WaitListHead;
    semaphore.Header.WaitListHead.Blink = &semaphore.Header.WaitListHead;
    references = reference_calls = locks = 0;
    reference_status = lock_exception = probe_exception = 0;
    exception_code = 0; concurrent_state = -1;
}

static NTSTATUS invoke(HANDLE handle, LONG count, PLONG previous, int *escaped)
{
    SEH_FRAME outer; outer.previous = seh_frame; seh_frame = &outer;
    NTSTATUS result;
    if (setjmp(outer.target)) { *escaped = 1; result = exception_code; }
    else { *escaped = 0; result = NtReleaseSemaphore(handle, count, previous); }
    seh_frame = outer.previous;
    return result;
}

int main(void)
{
    for (int mode = KernelMode; mode <= UserMode; ++mode)
    {
        LONG previous = -77; int escaped = 0; NTSTATUS status;
        reset(mode, 3, 3);
        status = invoke(&semaphore, 1, &previous, &escaped);
#ifdef SARCH_XBOX
        CHECK(!escaped, "Xbox semaphore overflow returns status rather than escaping");
#else
        CHECK(escaped == (mode == KernelMode), "non-Xbox kernel exception propagation is unchanged");
#endif
        CHECK(status == STATUS_SEMAPHORE_LIMIT_EXCEEDED, "overflow has the documented status");
        CHECK(semaphore.Header.SignalState == 3 && previous == -77 && locks == 0,
              "overflow preserves count/output and releases the dispatcher lock");
        if (!escaped) CHECK(references == 0, "handled overflow releases the object reference");

        reset(mode, 0, 3); previous = -77;
        status = invoke(&semaphore, 2, &previous, &escaped);
        CHECK(!escaped && status == STATUS_SUCCESS && previous == 0 && semaphore.Header.SignalState == 2,
              "healthy release returns previous count and increments exactly");
        CHECK(references == 0 && locks == 0, "healthy release cleans up reference and lock");
        status = invoke(&semaphore, 1, NULL, &escaped);
        CHECK(!escaped && status == STATUS_SUCCESS && semaphore.Header.SignalState == 3,
              "optional previous output and exact limit remain supported");

        reset(mode, 0, 3); concurrent_state = 3; previous = -77;
        status = invoke(&semaphore, 1, &previous, &escaped);
#ifdef SARCH_XBOX
        CHECK(!escaped && references == 0, "concurrent fill before locked release returns status and cleans up");
#else
        CHECK(escaped == (mode == KernelMode), "concurrent fill preserves non-Xbox exception contract");
#endif
        CHECK(status == STATUS_SEMAPHORE_LIMIT_EXCEEDED && semaphore.Header.SignalState == 3 && previous == -77 && locks == 0,
              "overflow remains checked inside the actual dispatcher lock");

        reset(mode, 3, 3); concurrent_state = 2; previous = -77;
        status = invoke(&semaphore, 1, &previous, &escaped);
        CHECK(!escaped && status == STATUS_SUCCESS && previous == 2 && semaphore.Header.SignalState == 3,
              "concurrent drain before locked release cannot be falsely rejected by an unlocked precheck");

        reset(mode, 1, INT32_MAX); previous = -77;
        status = invoke(&semaphore, INT32_MAX, &previous, &escaped);
#ifdef SARCH_XBOX
        CHECK(!escaped && references == 0, "signed count wrap returns overflow status on Xbox");
#else
        CHECK(escaped == (mode == KernelMode), "count wrap preserves non-Xbox exception contract");
#endif
        CHECK(status == STATUS_SEMAPHORE_LIMIT_EXCEEDED && semaphore.Header.SignalState == 1 && previous == -77 && locks == 0,
              "wrapped release never changes the semaphore or output");

        for (int invalid = 0; invalid >= -1; --invalid)
        {
            reset(mode, 1, 3); previous = -77;
            status = invoke(&semaphore, invalid, &previous, &escaped);
            CHECK(!escaped && status == STATUS_INVALID_PARAMETER && reference_calls == 0 && previous == -77,
                  "nonpositive release is rejected before handle reference or output mutation");
        }
        reset(mode, 1, 3); previous = -77;
        status = invoke(NULL, 1, &previous, &escaped);
        CHECK(!escaped && status == STATUS_INVALID_HANDLE && references == 0 && locks == 0 && previous == -77,
              "invalid handle remains an error without a release");

        reset(mode, 1, 3); lock_exception = STATUS_ACCESS_VIOLATION; previous = -77;
        status = invoke(&semaphore, 1, &previous, &escaped);
        CHECK(status == STATUS_ACCESS_VIOLATION && escaped == (mode == KernelMode),
              "unrelated kernel-mode faults are not swallowed by the overflow fix");
        CHECK(semaphore.Header.SignalState == 1 && previous == -77 && locks == 0,
              "unrelated fault does not mutate count or output");
        if (!escaped) CHECK(references == 0, "user-mode exception status preserves reference cleanup");
    }
    reset(UserMode, 1, 3); probe_exception = STATUS_ACCESS_VIOLATION;
    LONG previous = -77; int escaped; NTSTATUS status = invoke(&semaphore, 1, &previous, &escaped);
    CHECK(!escaped && status == STATUS_ACCESS_VIOLATION && reference_calls == 0 && previous == -77,
          "user-mode output probe still precedes reference and release");
    printf("PASS semaphore status/exception/locked-state/cleanup checks=%u\n", checks);
    return 0;
}
