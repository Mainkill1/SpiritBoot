/* SPDX-License-Identifier: GPL-2.0-or-later
 * Pure OHCI/XID descriptor helpers. Hardware ownership and MMIO remain in the
 * native adapter; these bodies are independently host tested.
 */
#include "boot_xid.h"

#define OHCI_ED_MPS_SHIFT 16u
#define OHCI_TD_R (1u << 18)
#define OHCI_TD_DP_SHIFT 19u
#define OHCI_TD_DI_7 (7u << 21)
#define OHCI_TD_DATA0 (2u << 24)
#define OHCI_TD_DATA1 (3u << 24)
#define OHCI_TD_CC_NA (SB_OHCI_CC_NOT_ACCESSED << 28)
#define OHCI_PTR_MASK 0xfffffff0u

SB_INIT_CODE static void put16(uint8_t *p, uint16_t value)
{
    p[0] = (uint8_t)value;
    p[1] = (uint8_t)(value >> 8);
}

bool sb_ohci_prepare_control(SbOhciControl *c, uint32_t cpa,
                             uint32_t data_pa, uint8_t address,
                             uint8_t max_packet, uint8_t request_type,
                             uint8_t request, uint16_t value,
                             uint16_t index, uint16_t length)
{
    uint32_t td0, td1, td2, tail;
    bool input;

    if (!c || (cpa & 15u) || (data_pa && (data_pa & 3u)) ||
        address > 127u ||
        !(max_packet == 8u || max_packet == 16u ||
          max_packet == 32u || max_packet == 64u) ||
        (length && !data_pa))
        return false;

    *c = (SbOhciControl){0};
    td0 = cpa + (uint32_t)offsetof(SbOhciControl, td[0]);
    td1 = cpa + (uint32_t)offsetof(SbOhciControl, td[1]);
    td2 = cpa + (uint32_t)offsetof(SbOhciControl, td[2]);
    tail = cpa + (uint32_t)offsetof(SbOhciControl, td[3]);
    input = (request_type & 0x80u) != 0;

    c->setup[0] = request_type;
    c->setup[1] = request;
    put16(c->setup + 2, value);
    put16(c->setup + 4, index);
    put16(c->setup + 6, length);

    c->ed.flags = address | ((uint32_t)max_packet << OHCI_ED_MPS_SHIFT);
    c->ed.head = td0;
    c->ed.tail = tail;

    c->td[0].flags = OHCI_TD_CC_NA | OHCI_TD_DI_7 | OHCI_TD_DATA0;
    c->td[0].cbp = cpa + (uint32_t)offsetof(SbOhciControl, setup);
    c->td[0].be = c->td[0].cbp + 7u;
    c->td[0].next = length ? td1 : td2;

    if (length) {
        c->td[1].flags = OHCI_TD_CC_NA | OHCI_TD_DI_7 | OHCI_TD_DATA1 |
                         ((input ? 2u : 1u) << OHCI_TD_DP_SHIFT) |
                         (input ? OHCI_TD_R : 0u);
        c->td[1].cbp = data_pa;
        c->td[1].be = data_pa + length - 1u;
        c->td[1].next = td2;
    }

    c->td[2].flags = OHCI_TD_CC_NA | OHCI_TD_DATA1 |
                     ((input ? 1u : 2u) << OHCI_TD_DP_SHIFT);
    c->td[2].next = tail;
    return true;
}

bool sb_ohci_control_complete(const SbOhciControl *c, uint16_t length)
{
    if (!c || (c->ed.head & 1u) ||
        (c->ed.head & OHCI_PTR_MASK) != (c->ed.tail & OHCI_PTR_MASK))
        return false;
    if ((c->td[0].flags >> 28) != 0u ||
        (length && (c->td[1].flags >> 28) != 0u) ||
        (c->td[2].flags >> 28) != 0u)
        return false;
    return true;
}

bool sb_xid_decode_report(const uint8_t *r, size_t bytes, uint32_t *buttons)
{
    uint16_t digital;
    uint32_t out = 0;

    if (!r || !buttons || bytes < SB_XID_REPORT_BYTES ||
        r[1] < SB_XID_REPORT_BYTES)
        return false;
    digital = (uint16_t)r[2] | ((uint16_t)r[3] << 8);
    if (digital & 0x0010u) out |= SB_START;
    if (digital & 0x0001u) out |= SB_UP;
    if (digital & 0x0002u) out |= SB_DOWN;
    if (digital & 0x0004u) out |= SB_LEFT;
    if (digital & 0x0008u) out |= SB_RIGHT;
    if (r[4]) out |= SB_A;
    if (r[5]) out |= SB_B;
    if (r[6]) out |= SB_X;
    *buttons = out;
    return true;
}
