/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <windows.h>
#include <xboxkrnl/xboxkrnl.h>
#include "regression.h"
int main(void)
{
    regression_begin();
    regression_check(!MmIsAddressValid((PVOID)0xd3fff000), "unused SYSVA page is invalid");
    PVOID p = MmAllocateSystemMemory(8192, PAGE_READWRITE);
    regression_require(p != NULL, "allocate system pages");
    regression_check(MmIsAddressValid(p), "first live system page is valid");
    regression_check(MmIsAddressValid((PUCHAR)p + 8191), "last live system page is valid");
    regression_check(MmFreeSystemMemory(p, 8192) == 2, "free two system pages");
    regression_check(!MmIsAddressValid(p), "first freed system page is invalid");
    regression_check(!MmIsAddressValid((PUCHAR)p + 8191), "last freed system page is invalid");
    regression_finish();
}
