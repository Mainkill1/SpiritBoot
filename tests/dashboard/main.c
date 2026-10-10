/* SPDX-License-Identifier: GPL-2.0-or-later
 * Original public-API dashboard fixture. No proprietary firmware code.
 */
#include <xboxkrnl/xboxkrnl.h>
#include <hal/debug.h>
#include <hal/video.h>
#include <hal/xbox.h>
#include <stdint.h>
#include "tap.h"

#define BUFFER_BYTES (64 * 1024)
#define U(x) ((unsigned long)(x))

static void delay_ms(unsigned milliseconds)
{
    LARGE_INTEGER interval = { .QuadPart = -(int64_t)milliseconds * 10000 };
    KeDelayExecutionThread(KernelMode, FALSE, &interval);
}

static void snapshot(const char *stage)
{
    MM_STATISTICS mm = { .Length = sizeof(mm) };
    PS_STATISTICS ps = { .Length = sizeof(ps) };
    NTSTATUS a = MmQueryStatistics(&mm);
    NTSTATUS b = PsQueryStatistics(&ps);
    tap_comment("DASH_STATS stage=%s mm=%08lx ps=%08lx total=%lu available=%lu pool=%lu stack=%lu cache=%lu image=%lu threads=%lu",
                stage, U(a), U(b), U(mm.TotalPhysicalPages), U(mm.AvailablePages),
                U(mm.PoolPagesCommitted), U(mm.StackPagesCommitted),
                U(mm.CachePagesCommitted), U(mm.ImagePagesCommitted), U(ps.ThreadCount));
}

int main(void)
{
    tap_puts("== memory-dashboard BEGIN schema=1 ==\n");
    tap_comment("DASH_PATH %.*s", XeImageFileName->Length, XeImageFileName->Buffer);
    snapshot("early");
    tap_puts("DASH_EARLY_READY\n");
    tap_drain();
    /* Host captures before this diagnostic allocates buffers or a framebuffer. */
    delay_ms(5000);

#ifdef DASHBOARD_LAUNCH_DVD
    /* A separate launch build adds no marker buffers or framebuffer. */
    tap_puts("DASH_LAUNCH_REQUEST path=D:\\default.xbe\n");
    tap_drain();
    XLaunchXBE("D:\\default.xbe");
    tap_puts("DASH_LAUNCH_RETURN unexpected=1\n");
    tap_drain();
    for (;;) delay_ms(1000);
#else
    for (unsigned n = 0; n < 3; ++n) {
        uint32_t *buffer = MmAllocateContiguousMemoryEx(
            BUFFER_BYTES, 0x00400000, 0x03bfffff, 4096, PAGE_READWRITE);
        if (!buffer) {
            tap_comment("DASH_BUFFER index=%u allocation=failed", n);
            continue;
        }
        uintptr_t physical = MmGetPhysicalAddress(buffer);
        unsigned zero_words = 0;
        for (unsigned i = 0; i < BUFFER_BYTES / sizeof(*buffer); ++i) {
            if (buffer[i] == 0) ++zero_words;
            buffer[i] = 0xc1000001 | ((physical + i * 4) & 0x0ffffffc);
        }
        tap_comment("DASH_BUFFER index=%u physical=%08lx bytes=%u initial_zero_words=%u persist=0",
                    n, U(physical), BUFFER_BYTES, zero_words);
        /* Keep allocated until reset. No access outside buffers we own. */
    }
    BOOL video = XVideoSetMode(640, 480, 32, REFRESH_DEFAULT);
    tap_comment("DASH_VIDEO success=%u", (unsigned)video);
    if (video) {
        debugPrint("MEMORY DASHBOARD PROBE\n\nDashboard launch succeeded.\n\nCold/warm RAM observation fixture.\nNo retail game or BIOS code is included.\n\nKeep this screen open for the host capture.\n");
    }
    snapshot("held");
    tap_puts("DASH_HELD_READY\n");
    tap_drain();
    for (;;) delay_ms(1000);
#endif
}
