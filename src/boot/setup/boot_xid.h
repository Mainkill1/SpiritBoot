/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef SPIRITBOOT_BOOT_XID_H
#define SPIRITBOOT_BOOT_XID_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "boot_setup.h"

#define SB_XID_REPORT_BYTES 20u
#define SB_OHCI_CC_NOT_ACCESSED 15u

typedef struct {
    uint32_t flags;
    uint32_t tail;
    uint32_t head;
    uint32_t next;
} SbOhciEd;

typedef struct {
    uint32_t flags;
    uint32_t cbp;
    uint32_t next;
    uint32_t be;
} SbOhciTd;

typedef struct {
    SbOhciEd ed;
    SbOhciTd td[4];
    uint8_t setup[8];
} SbOhciControl;

/* Builds one endpoint-zero transfer. All supplied physical addresses must be
 * 32-bit, naturally aligned and owned by the caller until completion. */
SB_INIT_CODE bool sb_ohci_prepare_control(SbOhciControl *control,
                             uint32_t control_pa,
                             uint32_t data_pa,
                             uint8_t address,
                             uint8_t max_packet,
                             uint8_t request_type,
                             uint8_t request,
                             uint16_t value,
                             uint16_t index,
                             uint16_t length);

/* Success requires every scheduled TD to retire without an OHCI condition
 * code and the ED to reach its dummy tail. */
SB_INIT_CODE bool sb_ohci_control_complete(const SbOhciControl *control,
                                           uint16_t length);

/* Decode the original-Xbox 20-byte XID gamepad input report into the menu's
 * normalized edge-button model. Analog face buttons are treated as pressed
 * when their byte is nonzero. */
SB_INIT_CODE bool sb_xid_decode_report(const uint8_t *report, size_t bytes,
                                       uint32_t *buttons);

#endif
