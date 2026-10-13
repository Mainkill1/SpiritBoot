"""The actual Xbox timer wrapper rejects malformed queue indexes before mutation."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class TimerApcModeTests(unittest.TestCase):
    def test_mode_validation_precedes_timer_mutation(self):
        patch = (ROOT / 'patches/roswell/0114-timer-apc-mode.patch').read_text()
        # Project the changed file's resulting hunk text, retaining actual code.
        resulting = '\n'.join(line[1:] for line in patch.splitlines()
                              if line.startswith((' ', '+')) and not line.startswith('+++'))
        wrapper = re.search(r'NTSTATUS NTAPI\nXeNtSetTimerEx\(.*?\n\}', resulting, re.S).group(0)
        harness = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#define NTAPI
#define KernelMode 0
#define UserMode 1
#define STATUS_INVALID_PARAMETER ((int32_t)0xc000000d)
typedef int32_t NTSTATUS, LONG;
typedef signed char KPROCESSOR_MODE;
typedef unsigned char BOOLEAN, *PBOOLEAN;
typedef void *HANDLE, *PVOID;
typedef struct { int64_t QuadPart; } LARGE_INTEGER, *PLARGE_INTEGER;
typedef void (*PTIMER_APC_ROUTINE)(void);
static struct {
    HANDLE handle; int64_t due; PTIMER_APC_ROUTINE routine;
    KPROCESSOR_MODE mode; PVOID context; BOOLEAN wake; LONG period;
    unsigned mutations;
} timer;
/* The kernel setter owns cancellation/rearming. Observing this boundary is
 * sufficient to prove rejection never reaches those mutations. */
static NTSTATUS NxkSetTimerMode(HANDLE handle, PLARGE_INTEGER due,
        PTIMER_APC_ROUTINE routine, KPROCESSOR_MODE mode, PVOID context,
        BOOLEAN wake, LONG period, PBOOLEAN previous) {
    timer.handle=handle;timer.due=due->QuadPart;timer.routine=routine;
    timer.mode=mode;timer.context=context;timer.wake=wake;timer.period=period;
    ++timer.mutations;if(previous)*previous=1;return 0;
}
''' + wrapper + r'''
static void callback(void) {}
int main(void) {
    LARGE_INTEGER due={-500000};BOOLEAN previous=0;
    int marker;HANDLE handle=&marker;
    for(int mode=0;mode<2;++mode) {
        assert(XeNtSetTimerEx(handle,&due,callback,mode,&marker,0,31,&previous)==0);
        assert(timer.handle==handle && timer.due==-500000 && timer.routine==callback);
        assert(timer.mode==mode && timer.context==&marker && timer.wake==0 && timer.period==31);
        assert(previous==1);
    }
    unsigned char before[sizeof(timer)];memcpy(before,&timer,sizeof(timer));
    signed char invalid[]={-128,-1,2,127};
    for(unsigned i=0;i<sizeof(invalid);++i) {
        previous=0x55;
        assert(XeNtSetTimerEx(handle,&due,callback,invalid[i],0,1,0,&previous)==STATUS_INVALID_PARAMETER);
        assert(!memcmp(before,&timer,sizeof(timer)) && previous==0x55);
        assert(XeNtSetTimerEx(handle,&due,0,invalid[i],0,1,0,&previous)==STATUS_INVALID_PARAMETER);
        assert(!memcmp(before,&timer,sizeof(timer)) && previous==0x55);
    }
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'timer-mode.c'
            binary=Path(directory)/'timer-mode'
            source.write_text(harness)
            subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror',
                            '-fsanitize=address,undefined',str(source),'-o',str(binary)],check=True)
            subprocess.run([str(binary)],check=True)
