/* SPDX-License-Identifier: GPL-2.0-or-later */
#pragma once
#include "tap.h"
#include <xboxkrnl/xboxkrnl.h>

static unsigned regression_checks, regression_failures;

static void regression_begin(void)
{
    tap_version(14);
}

static void regression_check(int passed, const char *description)
{
    ++regression_checks;
    if (passed) {
        tap_ok(regression_checks, description);
    } else {
        ++regression_failures;
        tap_not_ok(regression_checks, description);
    }
}

static void regression_finish(void) __attribute__((noreturn));
static void regression_finish(void)
{
    LARGE_INTEGER delay = { .QuadPart = -5000000 };
    tap_comment("checks=%u failures=%u", regression_checks, regression_failures);
    tap_plan(regression_checks);
    tap_drain();
    KeDelayExecutionThread(KernelMode, FALSE, &delay);
    HalWriteSMBusValue(0x20, 0x02, FALSE, 0x80);
    /* A failed shutdown remains a timeout, never a passing capture. */
    for (;;) __asm__ __volatile__("hlt");
}

static inline void regression_require(int passed, const char *description)
{
    regression_check(passed, description);
    if (!passed) regression_finish();
}
