/* SPDX-License-Identifier: GPL-2.0-or-later
 * Diagnostic only: read CPU memory-type state without changing it.
 * The byte-swap leaf is from our owned SpiritBoot build, not another BIOS.
 */
#include <xboxkrnl/xboxkrnl.h>
#include <stdint.h>
#include <string.h>
#include "tap.h"

#define U(x) ((unsigned long)(x))
#define PAGE_BYTES 4096U
#define ROUNDS 17U
#define CALLS 32768U
typedef ULONG (FASTCALL *leaf_fn)(ULONG);
static volatile uint32_t sink;

static void cpu(unsigned leaf, unsigned *a, unsigned *b, unsigned *c, unsigned *d)
{
    __asm__ volatile("cpuid" : "=a"(*a), "=b"(*b), "=c"(*c), "=d"(*d)
                     : "a"(leaf), "c"(0) : "memory");
}

static uint64_t ticks(void)
{
    unsigned a, b, c, d, low, high;
    cpu(0, &a, &b, &c, &d);
    __asm__ volatile("rdtsc" : "=a"(low), "=d"(high) : : "memory");
    return ((uint64_t)high << 32) | low;
}

static void msr(unsigned index)
{
    unsigned low, high;
    __asm__ volatile("rdmsr" : "=a"(low), "=d"(high) : "c"(index));
    tap_comment("MSR index=%08x value=%08x%08x", index, high, low);
}

static int page(const char *label, void *address, unsigned cr3)
{
    volatile unsigned *directory = MmMapIoSpace(cr3 & ~4095U, PAGE_BYTES, PAGE_READONLY);
    if (!directory) return 0;
    uintptr_t va = (uintptr_t)address;
    unsigned pde = directory[va >> 22], entry = 0, large = (pde >> 7) & 1;
    MmUnmapIoSpace((void *)directory, PAGE_BYTES);
    if (!(pde & 1)) return 0;
    if (large) entry = pde;
    else {
        volatile unsigned *table = MmMapIoSpace(pde & ~4095U, PAGE_BYTES, PAGE_READONLY);
        if (!table) return 0;
        entry = table[(va >> 12) & 1023];
        MmUnmapIoSpace((void *)table, PAGE_BYTES);
    }
    if (!(entry & 1)) return 0;
    unsigned physical = large ? (entry & 0xFFC00000U) + (va & 0x3FFFFFU)
                              : (entry & ~4095U) + (va & 4095U);
    if (physical != MmGetPhysicalAddress(address)) return 0;
    tap_comment("PAGE label=%s va=%08lx pa=%08x entry=%08x large=%u",
                label, U(va), physical, entry, large);
    return 1;
}

static ULONG FASTCALL empty(ULONG value) { return value; }

static __attribute__((noinline)) uint64_t calls(leaf_fn fn)
{
    uint32_t total = 0;
    uint64_t start = ticks();
    for (unsigned i = 0; i < CALLS; ++i) total += fn(i ^ 0x12345678U);
    uint64_t elapsed = ticks() - start;
    sink = total;
    return elapsed;
}

static __attribute__((noinline)) uint64_t reads(volatile unsigned char *data)
{
    uint32_t total = 0;
    uint64_t start = ticks();
    for (unsigned i = 0; i < CALLS; ++i) total += data[i & 127];
    uint64_t elapsed = ticks() - start;
    sink = total;
    return elapsed;
}

int main(void)
{
    static const unsigned char expected[] = {0x89, 0xC8, 0x0F, 0xC8, 0xC3};
    unsigned a, b, c, d, cr0, cr3, cr4, phys_bits = 36;
    int ok = 0;
    unsigned char *ram = NULL;
    leaf_fn kernel = RtlUlongByteSwap;
    tap_puts("== rom-memory-types BEGIN schema=1 ==\n");
    cpu(1, &a, &b, &c, &d);
    unsigned features = d;
    if ((features & ((1U << 4) | (1U << 5) | (1U << 12) | (1U << 16))) !=
                    ((1U << 4) | (1U << 5) | (1U << 12) | (1U << 16))) goto done;
    cpu(0x80000000U, &a, &b, &c, &d);
    if (a >= 0x80000008U) {
        cpu(0x80000008U, &a, &b, &c, &d);
        phys_bits = a & 255;
    }
    __asm__ volatile("mov %%cr0,%0" : "=r"(cr0));
    __asm__ volatile("mov %%cr3,%0" : "=r"(cr3));
    __asm__ volatile("mov %%cr4,%0" : "=r"(cr4));
    tap_comment("CPU phys_bits=%u edx=%08x", phys_bits, features);
    tap_comment("CONTROL cr0=%08x cr3=%08x cr4=%08x", cr0, cr3, cr4);
    if (!(cr0 & (1U << 31)) || (cr4 & (1U << 5))) goto done; /* Non-PAE only. */
    msr(0xFE); msr(0x2FF); msr(0x277);
    unsigned low, high;
    __asm__ volatile("rdmsr" : "=a"(low), "=d"(high) : "c"(0xFE));
    unsigned count = low & 255;
    if (count > 16) goto done;
    for (unsigned i = 0; i < count * 2; ++i) msr(0x200 + i);
    if (!page("kernel", (void *)kernel, cr3)) goto done;
    if (memcmp((void *)kernel, expected, sizeof(expected))) goto done;
    ram = MmAllocateContiguousMemoryEx(PAGE_BYTES * 2, 0, 0xFFFFFFFFU,
                                       PAGE_BYTES, PAGE_EXECUTE_READWRITE);
    if (!ram) goto done;
    memset(ram, 0xCC, PAGE_BYTES * 2);
    memcpy(ram, expected, sizeof(expected));
    memcpy(ram + PAGE_BYTES - 2, expected, sizeof(expected));
    memcpy(ram + 128, (const void *)kernel, 128);
    if (!page("ram", ram, cr3) || !page("ram-cross", ram + PAGE_BYTES - 2, cr3) ||
        !page("ram-cross-next", ram + PAGE_BYTES, cr3)) goto done;
    leaf_fn copy = (leaf_fn)ram, crossing = (leaf_fn)(ram + PAGE_BYTES - 2);
    for (unsigned i = 0; i < 1024; ++i) {
        unsigned value = i * 0x13579BDFU;
        unsigned answer = __builtin_bswap32(value);
        if (kernel(value) != answer || copy(value) != answer || crossing(value) != answer) goto done;
    }
    for (unsigned round = 0; round < ROUNDS; ++round) {
        uint64_t overhead = calls(empty);
        /* Alternate within the process; round zero is first-loop, not cold cache. */
        uint64_t native, copied;
        uint32_t first_sum;
        if (round & 1) {
            copied = calls(copy); first_sum = sink; native = calls(kernel);
        } else {
            native = calls(kernel); first_sum = sink; copied = calls(copy);
        }
        if (sink != first_sum) goto done;
        uint32_t checksum = sink;
        uint64_t boundary = calls(crossing);
        if (sink != checksum) goto done;
        uint64_t kernel_data = reads((void *)kernel);
        uint32_t data_sum = sink;
        uint64_t ram_data = reads(ram + 128);
        if (sink != data_sum) goto done;
        tap_comment("SAMPLE round=%u calls=%u overhead=%llu kernel=%llu ram=%llu cross=%llu table_kernel=%llu table_ram=%llu checksum=%08x",
                    round, CALLS, overhead, native, copied, boundary, kernel_data, ram_data, checksum);
    }
    ok = 1;
done:
    if (ram) MmFreeContiguousMemory(ram);
    tap_puts(ok ? "== rom-memory-types END schema=1 status=PASS ==\n"
                : "== rom-memory-types END schema=1 status=FAIL ==\n");
    tap_drain();
    for (;;) __asm__ volatile("pause");
}
