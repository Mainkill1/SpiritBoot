#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Compile exact production bodies; independent oracles plus work counters.

Usage: check.py SOURCE_ROOT OUTPUT [--optimized] [--compare OTHER_SOURCE_ROOT]
Counters are injected only into extracted host translation units, never shipped.
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import random
import re
import subprocess
import sys

sys.set_int_max_str_digits(0)

HERE = Path(__file__).resolve().parent
U = C.c_uint32
B = C.c_ubyte
P = C.c_void_p
checks = 0


def check(value, description):
    global checks
    checks += 1
    assert value, description


def function(text, name):
    """Named, brace-balanced production function, failing on missing markers."""
    hit = re.search(r'\b' + name + r'\s*\([^;]*?\)\s*\{', text)
    assert hit, name
    start = text.rfind('\n\n', 0, hit.start()) + 2
    brace = text.index('{', hit.start())
    depth = 1
    end = brace + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end] + '\n'


SHIM = r'''
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdlib.h>
#include <assert.h>
typedef uint32_t ULONG, *PULONG, PFN_NUMBER, PFN_COUNT;
typedef uint16_t USHORT, *PUSHORT;
typedef uint8_t UCHAR, *PUCHAR, BOOLEAN, KIRQL;
typedef uint64_t ULONGLONG;
typedef uintptr_t ULONG_PTR;
typedef size_t SIZE_T;
typedef void VOID, *PVOID;
typedef int INT;
#define NTAPI
#define IN
#define _In_
#define _Out_
#define _Inout_
#define _In_reads_(n)
#define _In_reads_bytes_(n)
#define _Out_writes_(n)
#define _Inout_updates_(n)
#define C_ASSERT(x) _Static_assert(x, #x)
#define FIELD_OFFSET(t,f) offsetof(t,f)
#define TRUE 1
#define FALSE 0
#define NonPagedPool 0
#define PAGE_SIZE 4096UL
#define PAGE_SHIFT 12
#define ASSERT assert
#define UNREFERENCED_PARAMETER(x) (void)(x)
uint64_t counters[16];
static ULONG fail_alloc;
static VOID *copy_memory(VOID *d, const VOID *s, SIZE_T n) {
 counters[3]+=n;return memcpy(d,s,n);
}
static VOID zero_memory(VOID *p, SIZE_T n) { counters[4]+=n;memset(p,0,n); }
#define RtlCopyMemory copy_memory
#define RtlZeroMemory zero_memory
static VOID *ExAllocatePoolWithTag(ULONG p,SIZE_T n,ULONG t) {
 (void)p;(void)t;++counters[5];return fail_alloc ? NULL : malloc(n);
}
static VOID ExFreePool(VOID *p) { ++counters[6];free(p); }
VOID reset_counters(VOID) { memset(counters,0,sizeof(counters)); }
VOID set_oom(ULONG v) { fail_alloc=v; }
'''


def build(root, output):
    root, output = Path(root), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    crypto = (root / 'ntoskrnl/xb/crypto.c').read_text()
    sha = (root / 'sdk/lib/cryptlib/sha1.c').read_text().replace('#include "sha1.h"', '')
    sha = sha.replace('static void SHA1Transform(ULONG State[5], UCHAR Buffer[64])\n{',
                      'static void SHA1Transform(ULONG State[5], UCHAR Buffer[64])\n{\n ++counters[7];')
    prefix = crypto[crypto.index('typedef struct _XC_SHA_CONTEXT'):crypto.index('/* RC4 key schedule.')]
    # Skip unrelated resumed-HMAC routines, retaining exact Xc wrapper bodies.
    prefix = prefix[:prefix.index('/*\n * HMAC-SHA1 resumed')] + ''.join(
        function(crypto, n) for n in ['XcpSHAInit', 'XcpSHAUpdate', 'XcpSHAFinal'])
    prefix = prefix.replace('XcpShaLoad(SHA_CTX *Ctx, const XC_SHA_CONTEXT *Xc)\n{',
                            'XcpShaLoad(SHA_CTX *Ctx, const XC_SHA_CONTEXT *Xc)\n{\n uint64_t before=counters[3];')
    prefix = prefix.replace('\n}\n', '\n}\n', 1)
    load = function(prefix, 'XcpShaLoad')
    load_counted = load[:-2] + ' counters[8]+=counters[3]-before;\n}\n'
    prefix = prefix.replace(load, load_counted)
    bn = crypto[crypto.index('#define BN_MAX_WORDS'):crypto.index('/* --- RSA public-key')]
    bn = bn.replace('Carry += (ULONGLONG)A[j] * B[i]', '++counters[11]; Carry += (ULONGLONG)A[j] * B[i]')
    bn = bn.replace('Factor = T[0] * MInv;', '++counters[12]; Factor = T[0] * MInv;')
    bn = bn.replace('Carry = ((ULONGLONG)Factor * M[0]', '++counters[11]; Carry = ((ULONGLONG)Factor * M[0]')
    bn = bn.replace('Carry += (ULONGLONG)Factor * M[j]', '++counters[11]; Carry += (ULONGLONG)Factor * M[j]')
    bn = bn.replace('BnDoubleMod(Result, (Value[i / 32]', '++counters[13], BnDoubleMod(Result, (Value[i / 32]')
    for name in ['BnMontMul', 'BnMulMod']:
        f = function(bn, name)
        bn = bn.replace(f, f.replace('{', '{\n ++counters[0]; counters[1]+=(A==B);', 1))
    des = crypto[crypto.index('#define DES_TABLE_BYTES'):crypto.index('/* --- the crypto vector')]
    f = function(des, 'DesLoadKey')
    f = f.replace('Value |= (UCHAR)', '++counters[2], Value |= (UCHAR)')
    f = f.replace('Key->Round[r][k] = Value;', '++counters[9]; Key->Round[r][k] = Value;')
    des = des.replace(function(des, 'DesLoadKey'), f)
    exports = '\n'.join('extern __typeof__(' + name + ') host_' + name + ' __attribute__((alias("' + name + '")));'
        for name in ['XcpSHAInit', 'XcpSHAUpdate', 'XcpSHAFinal', 'XcpModExp', 'XcpKeyTable', 'XcpBlockCrypt', 'XcpBlockCryptCBC'])
    crypto_unit = SHIM + '\ntypedef struct { UCHAR Buffer[64]; ULONG State[5],Count[2]; } SHA_CTX, *PSHA_CTX;\n' + sha + prefix + bn + des + exports + '\nVOID decode_table(PUCHAR out, const UCHAR *table) { DES_KEY k; DesLoadKey(&k,table);memcpy(out,&k,sizeof(k)); }\n'

    pool = (root / 'ntoskrnl/xb/mm/poolpages.c').read_text()
    pool_range = function(pool, 'NxppTestRange')
    pool_range = pool_range.replace('NxppUsedMap[i >> 5]', 'read_map(i >> 5)')
    search = pool[pool.index('    /* First fit from the rotating hint'):pool.index('    /* Back the run;')]
    search = search[:search.index('    if (Start == (ULONG)-1)\n    {\n        KeReleaseSpinLock')]
    search = search.replace('if (NxppTestRange', 'if ((++counters[10], NxppTestRange')
    # Added instrumentation wraps only condition evaluation.
    search = search.replace('Count))', 'Count)))').replace('&Next))', '&Next)))')
    pool_unit = SHIM + r'''
#define NXPP_PAGES 4096
static ULONG NxppScanHint, NxppUsedMap[128];
static ULONG read_map(ULONG i) { ++counters[0];return NxppUsedMap[i]; }
VOID set_map(ULONG i,ULONG v) { NxppUsedMap[i]=v; }
''' + pool_range + '\nULONG pool_find(ULONG Count,ULONG Hint) { ULONG Start; NxppScanHint=Hint;\n' + search + '\nreturn Start; }\n'

    sysva = function((root / 'ntoskrnl/xb/mm/sysva.c').read_text(), 'NxpSysVaFindHoleLocked')
    sysva = sysva.replace('Pde[Va >> 22]', '(++counters[0], Pde[Va >> 22])').replace('Pte[Va >> PAGE_SHIFT]', '(++counters[1], Pte[Va >> PAGE_SHIFT])')
    sys_unit = SHIM + r'''
static ULONG pdes[1024], ptes[1048576];
#define NXK_PDE_BASE pdes
#define NXK_PTE_BASE ptes
#define NXK_SYSMEM_BASE 0xD0000000UL
#define NXK_SYSMEM_LIMIT 0xD4000000UL
VOID set_pde(ULONG i,ULONG v) { pdes[0xD0000000UL/0x400000+i]=v; }
VOID set_pte(ULONG i,ULONG v) { ptes[0xD0000000UL/4096+i]=v; }
''' + sysva + '\nULONG_PTR sys_find(ULONG n) { return NxpSysVaFindHoleLocked(n); }\n'

    ob = (root / 'ntoskrnl/xb/obcreate.c').read_text()
    remember = function(ob, 'XobRememberType')
    remember = remember.replace('CONTAINING_RECORD(Entry, XB_TITLE_TYPE, Link)->Type == Type', '(++counters[0], CONTAINING_RECORD(Entry, XB_TITLE_TYPE, Link)->Type == Type)')
    registry_unit = SHIM + r'''
typedef struct _LIST_ENTRY { struct _LIST_ENTRY *Flink,*Blink; } LIST_ENTRY,*PLIST_ENTRY;
typedef struct { LIST_ENTRY Link; PVOID Type; } XB_TITLE_TYPE,*PXB_TITLE_TYPE;
#define CONTAINING_RECORD(p,t,f) ((t *)((char *)(p)-offsetof(t,f)))
static LIST_ENTRY XobTitleTypes;
static ULONG XobTitleTypeCount, XobTitleTypeLock, locked, race;
static VOID InitializeListHead(PLIST_ENTRY h) { h->Flink=h->Blink=h; }
static VOID InsertTailList(PLIST_ENTRY h,PLIST_ENTRY e) {
 e->Flink=h;e->Blink=h->Blink;h->Blink->Flink=e;h->Blink=e;
}
static VOID KeAcquireSpinLock(ULONG *l,KIRQL *i) { (void)l;*i=0;assert(!locked);locked=1; }
static VOID KeReleaseSpinLock(ULONG *l,KIRQL i) { (void)l;(void)i;assert(locked);locked=0; }
static VOID XobRememberType(PVOID Type);
static VOID *registry_alloc(ULONG p,SIZE_T n,ULONG t) {
 assert(!locked);
 if(race) { race=0;XobRememberType((PVOID)(uintptr_t)999); }
 return ExAllocatePoolWithTag(p,n,t);
}
#define ExAllocatePoolWithTag registry_alloc
''' + remember + r'''
VOID registry_reset(VOID) {
 if(XobTitleTypeCount) { PLIST_ENTRY e=XobTitleTypes.Flink;
 while(e!=&XobTitleTypes) { PLIST_ENTRY next=e->Flink;free(e);e=next; } }
 XobTitleTypeCount=0;memset(&XobTitleTypes,0,sizeof(XobTitleTypes));
}
ULONG remember_type(ULONG t,ULONG r) { race=r;XobRememberType((PVOID)(uintptr_t)t);return XobTitleTypeCount; }
'''
    units = dict(crypto=crypto_unit, pool=pool_unit, sysva=sys_unit, registry=registry_unit)
    libs = {}
    for name, unit in units.items():
        src, so = output / (name + '.c'), output / (name + '.so')
        src.write_text(unit)
        command = ['cc', '-std=c11', '-O2', '-g', '-shared', '-fPIC', '-DSARCH_XBOX', '-Wall', '-Wextra', '-Wno-multichar', '-Wno-unused-function', str(src), '-o', str(so)]
        subprocess.run(command, check=True)
        lib = libs[name] = C.CDLL(str(so.resolve()))
        lib.counters = (C.c_uint64 * 16).in_dll(lib, 'counters')
    for name in ['XcpSHAInit', 'XcpSHAUpdate', 'XcpSHAFinal', 'XcpKeyTable', 'XcpBlockCrypt', 'XcpBlockCryptCBC']:
        getattr(libs['crypto'], 'host_' + name).restype = None
    libs['crypto'].host_XcpModExp.restype = U
    libs['pool'].pool_find.restype = U
    libs['sysva'].sys_find.restype = C.c_size_t
    return libs


def run(libs, optimized):
    rng = random.Random(0x7807)
    work = {}
    pool = libs['pool']
    patterns = [[1] * 4096, [i % 2 for i in range(4096)], [int(i % 256 == 255) for i in range(4096)], [0] * 4096]
    patterns += [[int(rng.random() < .2) for _ in range(4096)] for _ in range(4)]
    for pi, bits in enumerate(patterns):
        for i in range(128):
            pool.set_map(i, sum(bits[i * 32 + j] << j for j in range(32)))
        for count in [1, 2, 4, 16, 256, 1024, 4096, 4097, 0]:
            for hint in [0, 1, 15, 255, 2048, 4095]:
                starts = list(range(hint, 4096 - count + 1)) + list(range(0, min(hint, 4096 - count + 1)))
                expected = next((i for i in starts if not any(bits[i:i + count])), 0xffffffff)
                pool.reset_counters()
                got = pool.pool_find(count, hint)
                check(got == expected, f'pool first fit pattern={pi} count={count} hint={hint}: {got}/{expected}')
                if (pi, count, hint) == (2, 256, 0):
                    work['pool'] = list(pool.counters)
                    if optimized:
                        check(pool.counters[0] == 4096, 'pool conflict skip must read 4096 bits')

    sys = libs['sysva']
    for pattern in range(5):
        pdes = [int(pattern == 1 or (pattern > 1 and i % 2 == 0)) for i in range(16)]
        bits = [int(pdes[i // 1024] and (pattern == 1 or (pattern == 2 and i % 71 == 0) or (pattern == 3 and i < 700) or (pattern == 4 and i % 1024 > 1000))) for i in range(16384)]
        for i, v in enumerate(pdes):
            sys.set_pde(i, v)
        for i, v in enumerate(bits):
            sys.set_pte(i, v)
        for count in [0, 1, 16, 1024, 1025, 4096, 16384, 16385]:
            expected = next((0xD0000000 + i * 4096 for i in range(16385 - count) if count and not any(bits[i:i + count])), 0)
            sys.reset_counters()
            check(sys.sys_find(count) == expected, f'sys first fit pattern={pattern} count={count}')
            if (pattern, count) == (0, 4096):
                work['sysva'] = list(sys.counters)
                if optimized:
                    check(sys.counters[0] == 4, 'sys absent span must read four PDEs')

    reg = libs['registry']
    for n in [1, 8, 64]:
        reg.registry_reset()
        reg.reset_counters()
        for i in range(1, n + 1):
            check(reg.remember_type(i, 0) == i, 'registry insertion')
        work['registry-cold' + str(n)] = list(reg.counters)
        reg.reset_counters()
        for i in range(1, n + 1):
            check(reg.remember_type(i, 0) == n, 'registry duplicate')
        work['registry' + str(n)] = list(reg.counters)
        if optimized:
            check(reg.counters[5] == 0 and reg.counters[6] == 0, 'known registry no allocation')
    reg.registry_reset()
    reg.set_oom(1)
    check(reg.remember_type(1, 0) == 0, 'lazy registry silent OOM')
    reg.set_oom(0)
    check(reg.remember_type(1, 0) == 1, 'registry recovery after OOM')
    reg.registry_reset()
    check(reg.remember_type(999, 1) == 1, 'registry controlled duplicate allocation race')
    check(reg.counters[6] >= 1, 'registry duplicate race frees redundant node')
    reg.registry_reset()
    check(reg.remember_type(1000, 1) == 2, 'registry concurrent different type insertion')
    reg.registry_reset()

    crypto = libs['crypto']
    mod = crypto.host_XcpModExp
    for words in [1, 2, 32, 64, 512]:
        exps = [0, 1, 2, 3, 65537, 1 << 31, (1 << 32) - 1]
        for exponent in exps:
            for modulus in [0, 1, 2, 17, (1 << (words * 32)) - 59, (1 << (words * 32)) - 60]:
                # Large-word dense/highbit even cases remain bounded by using
                # a small numeric modulus; exercise full-width with exponents <=3.
                if words >= 64 and exponent > 3 and modulus > 17:
                    continue
                base = (1 << (words * 32 - 1)) + 123
                arr = lambda value: (U * words)(*((value >> (32 * i)) & 0xffffffff for i in range(words)))
                for alias in ['none', 'base', 'exp', 'mod']:
                    a, e, m = arr(base), arr(exponent), arr(modulus)
                    out = dict(base=a, exp=e, mod=m).get(alias, arr(0xA5))
                    old = bytes(out)
                    crypto.reset_counters()
                    status = mod(out, a, e, m, words)
                    check(status == bool(modulus), 'modexp zero modulus status')
                    got = int.from_bytes(bytes(out), 'little')
                    if modulus:
                        # Baseline even modulus exponent zero returns one even
                        # for modulus one (odd conversion yields zero).
                        check(got == pow(base, exponent, modulus), f'modexp pow W={words} E={exponent} Mbits={modulus.bit_length()} alias={alias}')
                    else:
                        check(bytes(out) == old, 'modexp rejected output untouched')
                    if (words, exponent, modulus, alias) == (1, 3, 17, 'none'):
                        work['modexp'] = list(crypto.counters)
                        if optimized:
                            check(crypto.counters[1] == 1, 'only one useful square for exponent three')
                    if (words, exponent, modulus, alias) == (1, 3, 2, 'none'):
                        work['modexp-even'] = list(crypto.counters)
    a = (U * 513)(*([0xA5] * 513)); e = (U * 513)(3); m = (U * 513)(17)
    for words in [0, 513]:
        check(mod(a, a, e, m, words) == 0 and a[0] == 0xA5, 'modexp word bound rejection')
    crypto.set_oom(1)
    check(mod(a, a, e, m, 1) == 0 and a[0] == 0xA5, 'modexp allocation failure output')
    crypto.set_oom(0)
    # Multiword top-bit and dense exponents, plus full-width random operands.
    for words in [1, 2, 32]:
        for exponent in [1 << (words * 32 - 1), (1 << (words * 32)) - 1]:
            for modulus in [17, 18]:
                arr = lambda value: (U * words)(*((value >> (32 * i)) & 0xffffffff for i in range(words)))
                a, e, m, out = arr(5), arr(exponent), arr(modulus), arr(0)
                check(mod(out,a,e,m,words)==1 and int.from_bytes(bytes(out),'little')==pow(5,exponent,modulus), 'modexp multiword highbit/dense independent oracle')
        for _ in range(4):
            modulus=rng.getrandbits(words*32) | 2
            base=rng.getrandbits(words*32)
            exponent=rng.choice([0,1,2,3,65537])
            a,e,m,out=arr(base),arr(exponent),arr(modulus),arr(0)
            check(mod(out,a,e,m,words)==1 and int.from_bytes(bytes(out),'little')==pow(base,exponent,modulus),'modexp random independent oracle')

    data = bytes(rng.randrange(256) for _ in range(1048576 + 64))
    sha_records = []
    for remainder in range(64):
        for length in [0, 1, 55, 56, 63, 64, 65, 4096, 1048576]:
            for offset in range(4):
                context = (B * 128)(*([0xCC] * 128))
                ptr = C.byref(context, offset)
                digest = (B * 20)()
                crypto.host_XcpSHAInit(ptr)
                message = data[:remainder + length]
                first = C.create_string_buffer(message[:remainder])
                crypto.host_XcpSHAUpdate(ptr, first, remainder)
                crypto.reset_counters()
                body = C.create_string_buffer(message[remainder:])
                crypto.host_XcpSHAUpdate(ptr, body, length)
                if (remainder, length, offset) == (0, 1, 0):
                    work['sha'] = list(crypto.counters)
                    if optimized:
                        check(crypto.counters[8] == 28, 'empty live SHA prefix loads 28 bytes')
                if (remainder, length, offset) == (63, 1, 0):
                    work['sha63'] = list(crypto.counters)
                sha_records.append(bytes(context))
                crypto.host_XcpSHAFinal(ptr, digest)
                check(bytes(digest) == hashlib.sha1(message).digest(), f'SHA independent digest r={remainder} l={length} o={offset}')
                check(bytes(context)[offset:offset + 24] == b'\xcc' * 24, 'SHA reserved canary')
                check(bytes(context)[offset + 52:offset + 116] == bytes(64), 'SHA final full buffer reset')
                check(bytes(context)[:offset] == b'\xcc' * offset and bytes(context)[offset + 116:] == b'\xcc' * (12 - offset), 'SHA outside canaries')
                sha_records.append(bytes(context))

    # Streamed splits, count carry, input/context and digest/context aliases.
    # The independent digest covers valid stream counts; synthetic carry and
    # overlapping final output retain complete baseline state as the oracle.
    for offset in range(4):
        context = (B * 132)(*([0xCC] * 132))
        ptr = C.byref(context, offset)
        crypto.host_XcpSHAInit(ptr)
        cursor = 0
        while cursor < 4096:
            length = min(rng.randrange(1, 131), 4096 - cursor)
            part = C.create_string_buffer(data[cursor:cursor + length])
            crypto.host_XcpSHAUpdate(ptr, part, length)
            sha_records.append(bytes(context))
            cursor += length
        digest = (B * 20)()
        crypto.host_XcpSHAFinal(ptr, digest)
        check(bytes(digest) == hashlib.sha1(data[:4096]).digest(), 'SHA random split independent oracle')
        for carry in [False, True]:
            for input_at in [0, 24, 44, 52, 68]:
                for length in [0, 1, 16, 55, 64]:
                    context = (B * 132)(*([0xCC] * 132))
                    ptr = C.byref(context, offset)
                    crypto.host_XcpSHAInit(ptr)
                    count = 0xfffffff0 if carry else 16
                    raw = count.to_bytes(4, 'little')
                    for i, value in enumerate(raw):
                        context[offset + 48 + i] = value
                    crypto.host_XcpSHAUpdate(ptr, C.byref(context, offset + input_at), length)
                    if carry and length >= 16:
                        check(int.from_bytes(bytes(context)[offset + 44:offset + 48], 'little') >= 1, 'SHA count carry')
                    sha_records.append(bytes(context))
                    for output_at in [0, 24, 44, 52, 96]:
                        clone = (B * 132).from_buffer_copy(context)
                        crypto.host_XcpSHAFinal(C.byref(clone, offset), C.byref(clone, offset + output_at))
                        sha_records.append(bytes(clone))

    des_records = []
    # Independent FIPS DES and published three-key EDE known answers.
    for cipher, key, plain, expected in [
        (0, '133457799BBCDFF1', '0123456789ABCDEF', '85E813540F0AB405'),
        (1, '0123456789ABCDEF23456789ABCDEF01456789ABCDEF0123', 'FEDCBA9876543210', '0737F6C53750D4A4')]:
        table = (B * 384)(); keybuf = C.create_string_buffer(bytes.fromhex(key))
        crypto.host_XcpKeyTable(cipher, table, keybuf)
        out = (B * 8)(); inp = C.create_string_buffer(bytes.fromhex(plain))
        crypto.reset_counters()
        crypto.host_XcpBlockCrypt(cipher, out, inp, table, 1)
        check(bytes(out) == bytes.fromhex(expected), 'DES independent known answer')
        work['des' + str(cipher)] = list(crypto.counters)
        if optimized:
            check(crypto.counters[2] == 0, 'DES reversal has no per-bit iterations')
    for six in range(64):
        # One packed slot for every schedule round/S-box; wrap bit positions
        # are encoded independently rather than copying the decoder.
        for box in range(8):
            table = bytearray(128)
            shift = ((box // 2) * 8 + (6 if box % 2 else 2)) % 32
            word = sum(((six >> b) & 1) << ((shift + b) % 32) for b in range(6))
            for round in range(16):
                at = round * 8 + (box % 2) * 4
                table[at:at + 4] = word.to_bytes(4, 'little')
            # Expose exact decoder output for exhaustive bit equivalence.
            tablebuf = C.create_string_buffer(bytes(table)); decoded = (B * 128)()
            crypto.decode_table(decoded, tablebuf)
            check(all(decoded[r * 8 + box] == int(f'{six:06b}'[::-1], 2) for r in range(16)), 'DES exhaustive reverse6')
    for cipher in [0, 1, 2, 0xffffffff]:
        for op in [0, 1, 2]:
            for offset in range(4):
                table = (B * 388)(*([0xA7] * 388))
                key = C.create_string_buffer(bytes(range(24)))
                crypto.host_XcpKeyTable(U(cipher), C.byref(table, offset), key)
                table[offset + 7] ^= 0x91  # public table remains mutable
                for length in list(range(16)) + [64, 4096]:
                    for inplace in [False, True]:
                        inp = C.create_string_buffer(b'\xa9' * offset + data[:length] + b'\xcc' * 8)
                        out = inp if inplace else C.create_string_buffer(b'\xa9' * offset + b'\xcc' * (length + 8))
                        fb = C.create_string_buffer(b'\x19' * 8)
                        crypto.host_XcpBlockCryptCBC(U(cipher), length, C.byref(out,offset), C.byref(inp,offset), C.byref(table, offset), op, fb)
                        check(out.raw[offset + length // 8 * 8:] == (data[length // 8 * 8:length] + b'\xcc' * 8 + b'\x00' if inplace else b'\xcc' * (length % 8 + 8) + b'\x00'), 'DES CBC untouched tails')
                        check(out.raw[:offset] == b'\xa9' * offset, 'DES leading canary')
                        des_records.append(out.raw + fb.raw)
    work['state_hashes'] = dict(sha=hashlib.sha256(b''.join(sha_records)).hexdigest(), des=hashlib.sha256(b''.join(des_records)).hexdigest())
    return work


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source_root')
    parser.add_argument('output')
    parser.add_argument('--optimized', action='store_true')
    parser.add_argument('--compare')
    args = parser.parse_args()
    libs = build(args.source_root, Path(args.output) / 'candidate')
    actual = run(libs, args.optimized)
    if args.compare:
        other = run(build(args.compare, Path(args.output) / 'baseline'), False)
        check(actual['state_hashes'] == other['state_hashes'], 'whole SHA contexts and DES CBC baseline differential')
        actual = dict(candidate=actual, baseline=other)
    (Path(args.output) / 'work.json').write_text(json.dumps(actual, indent=2) + '\n')
    print(f'kernel optimization oracle checks: {checks}/{checks} passed')


if __name__ == '__main__':
    main()
