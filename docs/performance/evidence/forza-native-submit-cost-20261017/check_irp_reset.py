#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Exercise exact owned initializer/reuse bodies against a host layout oracle.

This is a preparatory semantic check, not a native ABI or timing benchmark.
No source is changed. Optional mutations must fail to validate the byte oracle.
"""
import argparse
from pathlib import Path
import os
import subprocess
import tempfile


PLATFORM = r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define VOID void
#define NTAPI
#define IN
#define OUT
#define ASSERT assert
#define IOTRACE(...) ((void)0)
#define RtlZeroMemory(p,n) memset((p),0,(n))
#define IO_TYPE_IRP 6
typedef unsigned char UCHAR;
typedef unsigned short USHORT;
typedef signed char CCHAR;
typedef int32_t NTSTATUS;
typedef struct LIST_ENTRY { struct LIST_ENTRY *Flink,*Blink; } LIST_ENTRY;
typedef struct IO_STACK_LOCATION { unsigned char opaque[36]; } IO_STACK_LOCATION,*PIO_STACK_LOCATION;
typedef struct IRP {
    USHORT Type,Size;
    unsigned char untouched_a[13];
    LIST_ENTRY ThreadListEntry;
    struct { NTSTATUS Status; uintptr_t Information; } IoStatus;
    CCHAR StackCount,CurrentLocation;
    unsigned char ApcEnvironment,AllocationFlags;
    void *CancelRoutine;
    unsigned char untouched_b[23];
    struct { struct { PIO_STACK_LOCATION CurrentStackLocation; } Overlay; } Tail;
} IRP,*PIRP;
static struct { UCHAR ApcStateIndex; } current_thread;
#define KeGetCurrentThread() (&current_thread)
#define InitializeListHead(p) ((p)->Flink=(p)->Blink=(p))
#define IsListEmpty(p) ((p)->Flink==(p))
'''

HARNESS = r'''
static unsigned observations;
static void check_case(unsigned offset,unsigned bytes,unsigned stack,unsigned apc,unsigned reuse)
{
    _Alignas(64) unsigned char actual[66048],expected[66048];
    memset(actual,0xa5,sizeof(actual));memset(expected,0xa5,sizeof(expected));
    PIRP irp=(PIRP)(actual+offset),want=(PIRP)(expected+offset);
    current_thread.ApcStateIndex=(UCHAR)apc;
    if(reuse) {
        /* Supply only the reuse preconditions; all other bytes remain poison. */
        irp->Size=(USHORT)bytes;irp->StackCount=(CCHAR)stack;
        irp->AllocationFlags=0xd3;irp->CancelRoutine=NULL;
        InitializeListHead(&irp->ThreadListEntry);
        IoReuseIrp(irp,(NTSTATUS)0xc0000120u);
    } else IoInitializeIrp(irp,(USHORT)bytes,(CCHAR)stack);
    memset(want,0,bytes);
    want->Type=IO_TYPE_IRP;want->Size=(USHORT)bytes;
    want->StackCount=(CCHAR)stack;want->CurrentLocation=(CCHAR)(stack+1);
    want->ApcEnvironment=(UCHAR)apc;
    /* Expected pointers intentionally point into actual, not the oracle copy. */
    want->Tail.Overlay.CurrentStackLocation=(PIO_STACK_LOCATION)(irp+1)+stack;
    want->ThreadListEntry.Flink=want->ThreadListEntry.Blink=&irp->ThreadListEntry;
    if(reuse) { want->IoStatus.Status=(NTSTATUS)0xc0000120u;want->AllocationFlags=0xd3; }
    if(memcmp(actual,expected,sizeof(actual))) {
        unsigned bad=0;while(actual[bad]==expected[bad])++bad;
        fprintf(stderr,"reset mismatch offset=%u bytes=%u stack=%u apc=%u reuse=%u at=%u actual=%02x expected=%02x\n",
                offset,bytes,stack,apc,reuse,bad,actual[bad],expected[bad]);exit(1);
    }
    ++observations;
}
int main(void)
{
    const unsigned stacks[]={0,1,2,8,126};
    for(unsigned offset=64;offset<128;offset+=_Alignof(IRP))
        for(unsigned s=0;s<sizeof(stacks)/sizeof(*stacks);++s)
            for(unsigned tail=0;tail<16;++tail)
                for(unsigned apc=0;apc<2;++apc)
                    for(unsigned reuse=0;reuse<2;++reuse)
                        check_case(offset,sizeof(IRP)+stacks[s]*sizeof(IO_STACK_LOCATION)+tail,stacks[s],apc,reuse);
    for(unsigned tail=0;tail<4;++tail)
        for(unsigned reuse=0;reuse<2;++reuse)
            check_case(64,65535-tail,1,1,reuse);
    printf("%u full-reset observations; complete packet, header, reuse flags and surrounding bytes match\n",observations);
    return 0;
}
'''


def body(source, name):
    start = source.index('\n' + name + '(')
    opening = source.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return 'VOID NTAPI ' + source[start + 1:end] + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--mutation', choices=('truncate-tail', 'overrun-tail'))
    args = parser.parse_args()
    source = (args.source_root / 'ntoskrnl/io/iomgr/irp.c').read_text()
    functions = body(source, 'IoInitializeIrp') + body(source, 'IoReuseIrp')
    if args.mutation:
        before = 'RtlZeroMemory(Irp, PacketSize);'
        if before not in functions:
            raise SystemExit('mutation requires the original baseline reset expression')
        length = '(PacketSize & ~3u)' if args.mutation == 'truncate-tail' else '((PacketSize + 3u) & ~3u)'
        functions = functions.replace(before, f'RtlZeroMemory(Irp, {length});', 1)
    with tempfile.TemporaryDirectory(prefix='owned-irp-reset-') as temporary:
        root = Path(temporary)
        test = root / 'test.c'
        test.write_text(PLATFORM + functions + HARNESS)
        executable = root / 'test'
        subprocess.run([os.environ.get('CC', 'clang'), '-std=c11', '-O1', '-g',
                        '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined',
                        '-fno-omit-frame-pointer', str(test), '-o', str(executable)], check=True)
        return subprocess.run([str(executable)], env=dict(os.environ,
                              ASAN_OPTIONS='halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1')).returncode


if __name__ == '__main__':
    raise SystemExit(main())
