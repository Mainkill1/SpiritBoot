/* SPDX-License-Identifier: GPL-2.0-or-later
 * Owned nonperformance lifetime probe: hold until scoped supervisor timeout. */
#include <xboxkrnl/xboxkrnl.h>
#include "tap.h"
int main(void) {
 tap_version(13); tap_plan(1);
 tap_comment("STORAGE-LIFETIME-HOLD fixture_generation=2 data_writes=0 expected_completion=owned_timeout");
 tap_drain();
 for(;;) { LARGE_INTEGER wait={.QuadPart=-1000000}; KeDelayExecutionThread(KernelMode,FALSE,&wait); }
}
