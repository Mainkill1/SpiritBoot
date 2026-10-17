/* SPDX-License-Identifier: GPL-2.0-only */
static unsigned checks;

static int verify(int condition, const char *name)
{
    ++checks;
    if (!condition)
        fprintf(stderr, "FAIL: %s\n", name);
    return condition;
}

#define CHECK(condition, name) do { if (!verify((condition), (name))) return 1; } while (0)

static unsigned reference_width(ULONG offset, ULONG remaining)
{
    ULONG remainder = remaining & 3;
    if ((offset & 3) == 0)
        return remainder == 0 ? 4 : remainder == 1 ? 1 : 2;
    if ((offset & 3) == 2)
        return remainder == 1 ? 1 : 2;
    return 1;
}

static ULONG slot(unsigned device, unsigned function)
{
    return (device & 31) | ((function & 7) << 5);
}

static int check_trace_shape(ULONG start, ULONG length, unsigned operations)
{
    ULONG offset = start, remaining = length;
    unsigned index = 0;
    while (remaining) {
        unsigned width = reference_width(offset, remaining);
        if (index >= operations || widths[index] != width ||
            port_offsets[index] != (offset & 3))
            return 0;
        offset += width;
        remaining -= width;
        ++index;
    }
    return index == operations;
}

int main(void)
{
    /* Every offset alignment x remaining-length remainder cell. */
    for (ULONG alignment = 0; alignment < 4; ++alignment) {
        for (ULONG remainder = 0; remainder < 4; ++remainder) {
            ULONG start = 0x40 + alignment;
            ULONG length = 8 + remainder;
            UCHAR output[16] = {0};
            reset_trace();
            PciCfgReadWriteBuffer(0, slot(3, 4), start, output, length, FALSE);
            CHECK(check_trace_shape(start, length, read_count),
                  "16-cell width policy matches retained PCI dereference policy");
            CHECK(memcmp(output, config_bytes + start, length) == 0,
                  "mixed-width reads copy the exact requested bytes");
            CHECK(raise_count == 1 && acquire_count == 1 && release_count == 1 &&
                  clear_count == 1 && current_irql == 11,
                  "one shared lock interval clears CF8 and restores IRQL");
        }
    }

    /* Bus/device/function fields and register alignment reach CF8 exactly. */
    {
        UCHAR output;
        reset_trace();
        PciCfgReadWriteBuffer(0x7e, slot(21, 6), 0xa1, &output, 1, FALSE);
        CHECK(address_count == 1 &&
              addresses[0] == (0x80000000UL | (0x7eUL << 16) |
                               (21UL << 11) | (6UL << 8) | 0xa0),
              "valid Type-1 address encoding preserves bus/device/function/register");
    }

    /* An unaligned 7-byte write is 1,2,4 and never performs a read/RMW. */
    {
        UCHAR input[7] = {0x10, 0x21, 0x32, 0x43, 0x54, 0x65, 0x76};
        reset_trace();
        PciCfgReadWriteBuffer(0, slot(5, 2), 0x41, input, sizeof(input), TRUE);
        CHECK(write_count == 3 && read_count == 0 &&
              widths[0] == 1 && widths[1] == 2 && widths[2] == 4,
              "mixed write uses exact-width cycles without read/modify/write");
        CHECK(values[0] == 0x10 && values[1] == 0x3221 &&
              values[2] == 0x76655443,
              "mixed write cycles preserve little-endian byte values");
        CHECK(port_offsets[0] == 1 && port_offsets[1] == 2 && port_offsets[2] == 0,
              "mixed write cycles select exact data-port lanes");
    }

    /* Only the console's absent devices are blacklisted. */
    {
        struct blocked_case { ULONG bus, slot, reg, len; } blocked[] = {
            {0, slot(0, 1), 0, 4}, {0, slot(0, 2), 0, 4},
            {1, slot(1, 0), 0, 4},
        };
        for (unsigned i = 0; i < sizeof(blocked) / sizeof(blocked[0]); ++i) {
            UCHAR buffer[8];
            memset(buffer, 0x3c, sizeof(buffer));
            reset_trace();
            PciCfgReadWriteBuffer(blocked[i].bus, blocked[i].slot,
                                  blocked[i].reg, buffer, blocked[i].len, FALSE);
            CHECK(address_count == 0 && read_count == 0 && write_count == 0 &&
                  raise_count == 0 && acquire_count == 0 && release_count == 0,
                  "blocked read path performs zero port and lock operations");
            for (ULONG j = 0; j < blocked[i].len; ++j)
                CHECK(buffer[j] == 0xff, "blocked read fills requested bytes with ff");
            memset(buffer, 0x3c, sizeof(buffer));
            reset_trace();
            PciCfgReadWriteBuffer(blocked[i].bus, blocked[i].slot,
                                  blocked[i].reg, buffer, blocked[i].len, TRUE);
            CHECK(address_count == 0 && read_count == 0 && write_count == 0 &&
                  raise_count == 0 && acquire_count == 0 && release_count == 0,
                  "blocked write path performs zero port and lock operations");
            CHECK(buffer[0] == 0x3c, "blocked write leaves caller bytes unchanged");
        }
    }

    /* Native public inputs use the low eight bus/register bits and ignore the
     * PCI_SLOT_NUMBER reserved bits, including across the 0xff boundary. */
    {
        UCHAR output[4] = {0};
        reset_trace();
        PciCfgReadWriteBuffer(256, slot(0, 0) | 0x100, 256,
                              output, 1, FALSE);
        CHECK(address_count == 1 && addresses[0] == 0x80000000UL &&
              output[0] == config_bytes[0],
              "bus/register wrap to eight bits and reserved slot bits are ignored");

        memset(output, 0, sizeof(output));
        reset_trace();
        PciCfgReadWriteBuffer(0, slot(0, 0), 255, output, 2, FALSE);
        CHECK(address_count == 2 && addresses[0] == 0x800000fcUL &&
              addresses[1] == 0x80000000UL,
              "register crossing wraps the next config address to zero");
        CHECK(output[0] == config_bytes[255] && output[1] == config_bytes[0],
              "register crossing returns bytes from both sides of the wrap");
    }

    reset_trace();
    PciCfgReadWriteBuffer(0, 0, 0, NULL, 4, FALSE);
    PciCfgReadWriteBuffer(0, 0, 0, config_bytes, 0, FALSE);
    CHECK(address_count == 0 && raise_count == 0,
          "null and zero-length requests perform no hardware operations");

    printf("PASS public PCI contracts checks=%u cells=16\n", checks);
    return 0;
}
