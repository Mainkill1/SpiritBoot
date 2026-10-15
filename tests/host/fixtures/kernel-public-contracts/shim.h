/* SPDX-License-Identifier: GPL-2.0-only
 * Host-only boundary shim for the actual PCI adapter functions. */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define FALSE 0
#define TRUE 1
#define HIGH_LEVEL 31
#define PCI_CFG_ADDR 0xCF8
#define PCI_CFG_DATA 0xCFC

typedef uint8_t UCHAR, BOOLEAN, KIRQL, *PUCHAR;
typedef uint16_t USHORT, *PUSHORT;
typedef uint32_t ULONG, *PULONG;
typedef void VOID, *PVOID;
typedef ULONG KSPIN_LOCK;
typedef struct _PCI_SLOT_NUMBER {
    union {
        struct {
            ULONG DeviceNumber : 5;
            ULONG FunctionNumber : 3;
            ULONG Reserved : 24;
        } bits;
        ULONG AsULONG;
    } u;
} PCI_SLOT_NUMBER;

static KSPIN_LOCK HalpPCIConfigLock;
static KIRQL current_irql;
static unsigned raise_count, acquire_count, release_count, clear_count;
static unsigned address_count, read_count, write_count;
static ULONG active_address;
static unsigned widths[64], port_offsets[64];
static ULONG values[64], addresses[64];
static UCHAR config_bytes[256];

static void RtlFillMemory(PVOID buffer, ULONG length, UCHAR value)
{
    memset(buffer, value, length);
}

static void RtlCopyMemory(PVOID destination, const void *source, ULONG length)
{
    memcpy(destination, source, length);
}

static void KeRaiseIrql(KIRQL requested, KIRQL *old)
{
    assert(requested == HIGH_LEVEL && raise_count == 0 && current_irql == 11);
    *old = current_irql;
    current_irql = requested;
    ++raise_count;
}

static void KeAcquireSpinLockAtDpcLevel(KSPIN_LOCK *lock)
{
    assert(lock == &HalpPCIConfigLock && current_irql == HIGH_LEVEL);
    assert(acquire_count == 0 && release_count == 0);
    ++acquire_count;
}

static void KeReleaseSpinLock(KSPIN_LOCK *lock, KIRQL old)
{
    assert(lock == &HalpPCIConfigLock && old == 11 && clear_count == 1);
    assert(acquire_count == 1 && release_count == 0);
    ++release_count;
    current_irql = old;
}

static void write_port(ULONG port, ULONG value, unsigned width)
{
    if (port == PCI_CFG_ADDR) {
        if (value == 0) {
            assert(acquire_count == 1 && release_count == 0);
            ++clear_count;
        } else {
            assert(current_irql == HIGH_LEVEL && acquire_count == 1);
            active_address = value;
            addresses[address_count++] = value;
        }
        return;
    }
    assert(port >= PCI_CFG_DATA && port < PCI_CFG_DATA + 4);
    assert(active_address != 0 && write_count < 64);
    widths[write_count] = width;
    port_offsets[write_count] = port - PCI_CFG_DATA;
    values[write_count] = value;
    ++write_count;
}

static ULONG read_port(ULONG port, unsigned width)
{
    assert(port >= PCI_CFG_DATA && port < PCI_CFG_DATA + 4);
    assert(active_address != 0 && read_count < 64);
    ULONG offset = (active_address & 0xfc) + (port - PCI_CFG_DATA);
    ULONG value = 0;
    memcpy(&value, config_bytes + offset, width);
    widths[read_count] = width;
    port_offsets[read_count] = port - PCI_CFG_DATA;
    values[read_count] = value;
    ++read_count;
    return value;
}

#define WRITE_PORT_ULONG(port, value) write_port((ULONG)(uintptr_t)(port), (ULONG)(value), 4)
#define WRITE_PORT_USHORT(port, value) write_port((ULONG)(uintptr_t)(port), (USHORT)(value), 2)
#define WRITE_PORT_UCHAR(port, value) write_port((ULONG)(uintptr_t)(port), (UCHAR)(value), 1)
#define READ_PORT_ULONG(port) ((ULONG)read_port((ULONG)(uintptr_t)(port), 4))
#define READ_PORT_USHORT(port) ((USHORT)read_port((ULONG)(uintptr_t)(port), 2))
#define READ_PORT_UCHAR(port) ((UCHAR)read_port((ULONG)(uintptr_t)(port), 1))

static void reset_trace(void)
{
    current_irql = 11;
    raise_count = acquire_count = release_count = clear_count = 0;
    address_count = read_count = write_count = 0;
    active_address = 0;
    memset(widths, 0, sizeof(widths));
    memset(port_offsets, 0, sizeof(port_offsets));
    memset(values, 0, sizeof(values));
    memset(addresses, 0, sizeof(addresses));
    for (unsigned i = 0; i < sizeof(config_bytes); ++i)
        config_bytes[i] = (UCHAR)(i ^ 0xa5);
}
