/* SPDX-License-Identifier: GPL-2.0-or-later
 * Original declaration-only packet, 2026-10-14.
 * Types and calling conventions require approved target ABI definitions.
 * No header-only helper or function implementation is included.
 */
#pragma once

PIRP NTAPI IoBuildDeviceIoControlRequest(ULONG IoControlCode,
    PDEVICE_OBJECT DeviceObject, PVOID InputBuffer, ULONG InputBufferLength,
    PVOID OutputBuffer, ULONG OutputBufferLength, BOOLEAN InternalDeviceIoControl,
    PKEVENT Event, PIO_STATUS_BLOCK IoStatusBlock);
VOID NTAPI KeInitializeEvent(PKEVENT Event, EVENT_TYPE Type, BOOLEAN State);
LONG NTAPI KeSetEvent(PKEVENT Event, KPRIORITY Increment, BOOLEAN Wait);
NTSTATUS NTAPI KeWaitForSingleObject(PVOID Object, KWAIT_REASON WaitReason,
    KPROCESSOR_MODE WaitMode, BOOLEAN Alertable, PLARGE_INTEGER Timeout);
