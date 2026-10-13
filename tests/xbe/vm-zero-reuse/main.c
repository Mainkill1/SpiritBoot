/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <windows.h>
#include <xboxkrnl/xboxkrnl.h>
#include <string.h>
#include "regression.h"
static BOOLEAN filled(const UCHAR *p, UCHAR byte)
{
    for (ULONG i = 0; i < 4096; ++i) if (p[i] != byte) return FALSE;
    return TRUE;
}
int main(void)
{
    regression_begin();
    for (unsigned scenario = 0; scenario < 4; ++scenario) {
        PVOID base = NULL; SIZE_T size = 3 * 4096;
        regression_require(NT_SUCCESS(NtAllocateVirtualMemory(&base, 0, &size,
                            MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE)),
                            "reserve and commit three VM pages");
        PUCHAR p = base;
        regression_check(filled(p, 0), "default fresh left VM page is entirely zero");
        regression_check(filled(p + 4096, 0), "default fresh middle VM page is entirely zero");
        regression_check(filled(p + 8192, 0), "default fresh right VM page is entirely zero");
        memset(p, 0x31, 4096); memset(p + 4096, 0xa7, 4096); memset(p + 8192, 0x73, 4096);
        PVOID middle = p + 4096; SIZE_T one = 4096;
        regression_require(NT_SUCCESS(NtFreeVirtualMemory(&middle, &one, MEM_DECOMMIT)),
                            "decommit only dirty middle VM page");
        regression_check(filled(p, 0x31), "left VM sentinel survives middle decommit");
        regression_check(filled(p + 8192, 0x73), "right VM sentinel survives middle decommit");
        middle = p + 4096; one = 4096;
        regression_require(NT_SUCCESS(NtAllocateVirtualMemory(&middle, 0, &one,
                            MEM_COMMIT, PAGE_READWRITE)), "recommit dirty middle VM page");
        regression_check(middle == p + 4096, "recommit preserves requested middle VM address");
        regression_check(filled(middle, 0), "default recommitted dirty VM page is entirely zero");
        regression_check(filled(p, 0x31), "left VM sentinel survives middle recommit");
        regression_check(filled(p + 8192, 0x73), "right VM sentinel survives middle recommit");
        size = 0;
        regression_require(NT_SUCCESS(NtFreeVirtualMemory(&base, &size, MEM_RELEASE)),
                            "release VM reservation and all committed pages");
    }
    regression_finish();
}
