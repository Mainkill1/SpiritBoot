/* SPDX-License-Identifier: GPL-2.0-or-later
 * Independently assembled public-interface declaration packet, 2026-10-14.
 * No function/macro implementation or private SDK layout is supplied.
 * Public kernel types, NTAPI and FASTCALL must come from approved ABI inputs.
 * Header-only helpers are intentionally absent; see TARGET-API-AVAILABILITY.md.
 */
#pragma once

PIRP NTAPI IoAllocateIrp(CCHAR StackSize, BOOLEAN ChargeQuota);
VOID NTAPI IoFreeIrp(PIRP Irp);
VOID NTAPI IoInitializeIrp(PIRP Irp, USHORT PacketSize, CCHAR StackSize);
VOID NTAPI IoReuseIrp(PIRP Irp, NTSTATUS Status);
NTSTATUS FASTCALL IofCallDriver(PDEVICE_OBJECT DeviceObject, PIRP Irp);
VOID FASTCALL IofCompleteRequest(PIRP Irp, CCHAR PriorityBoost);
BOOLEAN NTAPI IoCancelIrp(PIRP Irp);
PMDL NTAPI IoAllocateMdl(PVOID VirtualAddress, ULONG Length,
                        BOOLEAN SecondaryBuffer, BOOLEAN ChargeQuota, PIRP Irp);
VOID NTAPI IoBuildPartialMdl(PMDL SourceMdl, PMDL TargetMdl,
                            PVOID VirtualAddress, ULONG Length);
VOID NTAPI IoFreeMdl(PMDL Mdl);
VOID NTAPI IoAcquireCancelSpinLock(PKIRQL Irql);
VOID NTAPI IoReleaseCancelSpinLock(KIRQL Irql);
