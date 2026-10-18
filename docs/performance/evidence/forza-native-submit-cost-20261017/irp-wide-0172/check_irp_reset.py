#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Exercise exact owned initializer/reuse bodies against a host layout oracle.

This is a candidate semantic check, not a native ABI or timing benchmark.
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
typedef size_t SIZE_T;
typedef void *PVOID;
typedef uint32_t ULONG;
typedef uintptr_t ULONG_PTR;
typedef unsigned char *PUCHAR;
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
static unsigned helper_observations;
static void check_helper(unsigned offset, unsigned bytes)
{
    _Alignas(64) unsigned char actual[66048], expected[66048];
    memset(actual, 0xa5, sizeof(actual));
    memset(expected, 0xa5, sizeof(expected));
    IopClearIrpPacket(actual + offset, (USHORT)bytes);
    memset(expected + offset, 0, bytes);
    if (memcmp(actual, expected, sizeof(actual))) {
        unsigned bad = 0;
        while (actual[bad] == expected[bad]) ++bad;
        fprintf(stderr, "helper mismatch offset=%u bytes=%u at=%u actual=%02x expected=%02x\n",
                offset, bytes, bad, actual[bad], expected[bad]);
        exit(1);
    }
    ++helper_observations;
}
int main(void)
{
    /* Each alignment residue; zero/short/all tails; observed parent/child sizes;
       boundaries around 256/512 and the full public USHORT range endpoint. */
    const unsigned lengths[] = {164, 416, 255, 256, 257, 511, 512, 513,
                                65528, 65529, 65530, 65531, 65532, 65533, 65534, 65535};
    for (unsigned offset = 64; offset < 128; ++offset) {
        for (unsigned bytes = 0; bytes < 32; ++bytes) check_helper(offset, bytes);
        for (unsigned i = 0; i < sizeof(lengths)/sizeof(*lengths); ++i)
            check_helper(offset, lengths[i]);
    }
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
    printf("%u helper observations; exact range at arbitrary byte alignments matches\n", helper_observations);
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
    parser.add_argument('--force-fallback', action='store_true',
                        help='undefine GNU compiler marker after platform headers to exercise portable branch')
    args = parser.parse_args()
    source = (args.source_root / 'ntoskrnl/io/iomgr/irp.c').read_text()
    if '\nIopClearIrpPacket(' not in source:
        raise SystemExit('FAIL: candidate full-range clear helper absent')
    functions = body(source, 'IopClearIrpPacket') + body(source, 'IoInitializeIrp') + body(source, 'IoReuseIrp')
    if args.mutation:
        # Mutate the exact helper's byte extent, then run both public and helper
        # oracles. The overrun arithmetic is explicitly bounded to USHORT.
        opening = functions.index('{') + 1
        expression = '(USHORT)(Length & ~3u)' if args.mutation == 'truncate-tail' else '(USHORT)((Length + 3u) & ~3u)'
        functions = functions[:opening] + '\n    Length = ' + expression + ';\n' + functions[opening:]
    with tempfile.TemporaryDirectory(prefix='owned-irp-reset-') as temporary:
        root = Path(temporary)
        test = root / 'test.c'
        configuration = '\n#undef __GNUC__\n' if args.force_fallback else ''
        notice = source[:source.index('/* INCLUDES')]
        test.write_text(notice + PLATFORM + configuration + functions + HARNESS)
        executable = root / 'test'
        subprocess.run([os.environ.get('CC', 'clang'), '-std=c11', '-O1', '-g',
                        '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined',
                        '-fno-omit-frame-pointer', '-fno-strict-aliasing', str(test), '-o', str(executable)], check=True)
        return subprocess.run([str(executable)], env=dict(os.environ,
                              ASAN_OPTIONS='halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1')).returncode


if __name__ == '__main__':
    raise SystemExit(main())
