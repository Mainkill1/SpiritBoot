/* SPDX-License-Identifier: GPL-2.0-or-later
 * Sustained replay of public Forza world-stream request metadata. */
#include <xboxkrnl/xboxkrnl.h>
#include <stdbool.h>
#include "tools/storage_io_long16/tap.h"

enum { PASSES = 16 };

int recorder_execute(ULONG dataset, ULONG depth, ULONG pressure_target, bool warm);

static __attribute__((noreturn)) void finish(void)
{
    tap_drain();
    LARGE_INTEGER delay = {.QuadPart = -5000000};
    KeDelayExecutionThread(KernelMode, FALSE, &delay);
    HalWriteSMBusValue(0x20, 0x02, FALSE, 0x80);
    for (;;) __asm__ __volatile__("hlt");
}

int main(void)
{
    int failed = 0;
    tap_version(13);
    tap_plan(1);
    tap_comment("STORAGE-FORZA-MAP-META version=1 source=public-api-metadata requests=1024 observed_title_high_water=10 reference_high_water=12 measured_qd=12 pressure_pages=900 passes=16");
    for (ULONG pass = 0; pass < PASSES; ++pass) {
        tap_comment("STORAGE-FORZA-MAP-PASS index=%u count=%u",
                    (unsigned)(pass + 1), (unsigned)PASSES);
        if (recorder_execute(0, 12, 900, true)) {
            failed = 1;
            break;
        }
    }
    if (failed)
        tap_not_ok(1, "Forza map streaming public request replay");
    else
        tap_ok(1, "Forza map streaming public request replay");
    finish();
}
