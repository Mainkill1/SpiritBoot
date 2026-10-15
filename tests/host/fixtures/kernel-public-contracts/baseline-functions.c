/* SPDX-License-Identifier: GPL-2.0-only
 * Pinned unchanged production helper used with the patch postimage. */

static ULONG
PciCfgAddress(UCHAR bus, UCHAR dev, UCHAR fn, UCHAR offset)
{
    return 0x80000000UL |
           ((ULONG)bus << 16) |
           ((ULONG)dev << 11) |
           ((ULONG)fn  << 8)  |
           (offset & 0xFC);
}
