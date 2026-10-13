#!/usr/bin/env python3
"""Count actual SYSVA first-fit helper reads; this is work, not timing.

Usage: count-hole-work.py SOURCE_ROOT OUTPUT_DIRECTORY
The only body changes wrap the two production table reads with counters.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
root, out = (Path(a).resolve() for a in sys.argv[1:])
out.mkdir(parents=True, exist_ok=True)
spec = importlib.util.spec_from_file_location(
    "extract", root / "tests/host/kernel-performance/check.py")
extract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extract)
production = (root / "ntoskrnl/xb/mm/sysva.c").read_text()
body = extract.function(production, "NxpSysVaFindHoleLocked")
assert body.count("Pde[Va >> 22]") == 1
assert body.count("Pte[Va >> PAGE_SHIFT]") == 1
counted = body.replace("Pde[Va >> 22]", "ReadPde(Pde, Va >> 22)")
counted = counted.replace("Pte[Va >> PAGE_SHIFT]", "ReadPte(Pte, Va >> PAGE_SHIFT)")
shim = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uintptr_t ULONG_PTR;
typedef uint32_t ULONG;
typedef int BOOLEAN;
#define PAGE_SHIFT 12
#define PAGE_SIZE 4096u
#define NXK_SYSMEM_BASE 0xd0000000u
#define NXK_SYSMEM_LIMIT 0xd4000000u
static ULONG pdes[1024], ptes[1024*1024];
static unsigned pde_reads, pte_reads;
#define NXK_PDE_BASE ((uintptr_t)pdes)
#define NXK_PTE_BASE ((uintptr_t)ptes)
static ULONG ReadPde(volatile ULONG *p, unsigned n) {++pde_reads;return p[n];}
static ULONG ReadPte(volatile ULONG *p, unsigned n) {++pte_reads;return p[n];}
'''
cases = r'''
static void reset(int present) {
    memset(pdes,0,sizeof(pdes));memset(ptes,0,sizeof(ptes));
    if(present)for(unsigned i=0x340;i<0x350;i++)pdes[i]=3;
    pde_reads=pte_reads=0;
}
static void run(const char *name,unsigned pages,uintptr_t expected,unsigned pd,unsigned pt) {
    uintptr_t got=NxpSysVaFindHoleLocked(pages);
    assert(got==expected&&pde_reads==pd&&pte_reads==pt);
    printf("%s,%u,%lu,%u,%u\n",name,pages,(unsigned long)got,pde_reads,pte_reads);
}
int main(void) {
    reset(0);run("cold-one",1,NXK_SYSMEM_BASE,1,0);
    reset(1);run("warm-one",1,NXK_SYSMEM_BASE,1,1);
    reset(1);run("warm-64",64,NXK_SYSMEM_BASE,64,64);
    reset(1);for(unsigned i=0;i<4095;i++)ptes[0xd0000+i]=3;
    run("occupied-prefix-4095",1,NXK_SYSMEM_BASE+4095u*PAGE_SIZE,4096,4096);
    reset(1);for(unsigned i=1;i<16384;i+=2)ptes[0xd0000+i]=3;
    run("alternating-no-two-page-hole",2,0,16384,16384);
    reset(1);run("all-present-empty-full-aperture",16384,NXK_SYSMEM_BASE,16384,16384);
    reset(0);run("all-unbacked-full-aperture",16384,NXK_SYSMEM_BASE,16,0);
    reset(0);for(unsigned i=0;i<8;i++)pdes[0x340+i]=3;
    for(unsigned i=0;i<8192;i++)ptes[0xd0000+i]=3;
    run("occupied-half-then-unbacked-half",8192,NXK_SYSMEM_BASE+8192u*PAGE_SIZE,8200,8192);
    return 0;
}
'''
src, exe = out / "hole-work.c", out / "hole-work"
src.write_text(shim + counted + cases)
subprocess.run(["cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                str(src), "-o", str(exe)], check=True)
receipt = subprocess.run([str(exe)], check=True, text=True, capture_output=True)
rows = []
for line in receipt.stdout.splitlines():
    name, pages, va, pde, pte = line.split(",")
    rows.append(dict(case=name, pages=int(pages), result_va=hex(int(va)),
                     pde_reads=int(pde), pte_reads=int(pte)))
report = dict(helper_sha256=hashlib.sha256(body.encode()).hexdigest(),
              sysva_file_sha256=hashlib.sha256(production.encode()).hexdigest(),
              note="Host work counts from the actual helper; no elapsed-time claim.",
              rows=rows)
(out / "hole-work.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
