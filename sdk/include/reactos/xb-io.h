/* SPDX-License-Identifier: GPL-2.0-or-later */
#pragma once
/* Native private IRP flag: Xbox SG always publishes a final result, including
 * inline errors, synchronous-file errors and cancellation. Not a title flag. */
#define IRP_XB_SG_COMPLETION 0x00010000UL
