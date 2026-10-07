/* SPDX-License-Identifier: GPL-2.0-or-later
 * Public XboxDev/nxdk IDE_CHANNEL_OBJECT ABI, revision
 * 14d5ee97e73347c973f1f57b68b79ec08c9e77f2. Native interrupt uses an adapter.
 */
#pragma once

typedef struct _NX_IDE_INTERRUPT {
    PVOID ServiceRoutine, ServiceContext;
    ULONG BusInterruptLevel, Irql;
    UCHAR Connected, ShareVector, Mode, Padding;
    ULONG ServiceCount, DispatchCode[22];
} NX_IDE_INTERRUPT;
typedef VOID (NTAPI *NX_IDE_VOID_ROUTINE)(VOID);
typedef VOID (NTAPI *NX_IDE_START_ROUTINE)(PDEVICE_OBJECT, PIRP);
typedef BOOLEAN (NTAPI *NX_IDE_POLL_ROUTINE)(VOID);
typedef struct _NX_IDE_CHANNEL {
    NX_IDE_VOID_ROUTINE InterruptRoutine, FinishIoRoutine;
    NX_IDE_POLL_ROUTINE PollResetCompleteRoutine;
    NX_IDE_VOID_ROUTINE TimeoutExpiredRoutine;
    NX_IDE_START_ROUTINE StartPacketRoutine;
    NX_IDE_VOID_ROUTINE StartNextPacketRoutine;
    KIRQL InterruptIrql;
    BOOLEAN ExpectingBusMasterInterrupt, StartPacketBusy, StartPacketRequested;
    UCHAR Timeout, IoRetries, MaximumIoRetries;
    PIRP CurrentIrp;
    KDEVICE_QUEUE DeviceQueue;
    ULONG PhysicalRegionDescriptorTablePhysical;
    KDPC TimerDpc, FinishDpc;
    KTIMER Timer;
    NX_IDE_INTERRUPT InterruptObject;
} NX_IDE_CHANNEL;
C_ASSERT(sizeof(KDEVICE_QUEUE) == 12);
C_ASSERT(sizeof(KDPC) == 28);
C_ASSERT(sizeof(KTIMER) == 40);
C_ASSERT(sizeof(NX_IDE_INTERRUPT) == 112);
C_ASSERT(sizeof(NX_IDE_CHANNEL) == 264);
C_ASSERT(FIELD_OFFSET(NX_IDE_CHANNEL, StartPacketRoutine) == 0x10);
C_ASSERT(FIELD_OFFSET(NX_IDE_CHANNEL, CurrentIrp) == 0x20);
extern NX_IDE_CHANNEL IdexChannelObject;

VOID NxkIdeSetHardwareIsr(PKSERVICE_ROUTINE Routine, PVOID Context);
BOOLEAN NTAPI NxkIdeIsr(PKINTERRUPT Interrupt, PVOID Context);
VOID NxkIdeBindInterrupt(PKINTERRUPT Native);
VOID NxkIdeUnbindChannel(PVOID Channel);
VOID NxkIdeInitializeCompletion(PKDEFERRED_ROUTINE Routine);
PKDPC NxkIdeCompletionDpc(VOID);
VOID NxkIdeStartTimer(PDEVICE_OBJECT Device, PVOID Port, PIO_TIMER_ROUTINE Routine);
VOID NxkIdeStopTimer(PVOID Port);
/* Driver request types stay private to ATAPI: adapters carry opaque state. */
BOOLEAN NxkIdeStartRequest(PVOID Channel, PVOID Request,
    BOOLEAN (*Start)(PVOID, PVOID), PDEVICE_OBJECT Device, PIRP Irp, ULONG Timeout);
VOID NxkIdeFinishRequest(PVOID Request, VOID (*Finish)(PVOID), PIRP Irp);
BOOLEAN NxkIdeStartNext(PVOID Port, BOOLEAN (*StartNext)(PVOID));
VOID NxkIdeTimeout(PVOID Port, ULONG Slot, VOID (*Timeout)(PVOID, ULONG));
VOID XeInterruptBindNative(PKINTERRUPT Xbox, PKINTERRUPT Native);

BOOLEAN NxkIdeResetComplete(PVOID Channel);
VOID NxkIdeSetTimeout(PVOID Port, ULONG Seconds);
