/* SPDX-License-Identifier: GPL-2.0-or-later
 * Bridge the nxdk channel object to the existing primary ATAPI channel.
 * Hardware IRQ ownership remains PCIIDEX's; the console interrupt is borrowed.
 * Mutable callbacks replace the corresponding operation and may chain their
 * saved original once inside the callback. Defaults never claim a second IRQ.
 */
#include <ntoskrnl.h>
#include <reactos/xb-ide.h>
__declspec(align(16)) NX_IDE_CHANNEL IdexChannelObject;
static BOOLEAN IdeInitialized;
static PKSERVICE_ROUTINE HardwareIsr;
static PVOID HardwareContext;
static PKINTERRUPT HardwareInterrupt;
static BOOLEAN IrqResult, IrqChained;
static BOOLEAN (*StartOperation)(PVOID, PVOID);
static PVOID StartChannel, StartRequest;
static BOOLEAN StartResult;
static ULONG RequestGeneration;
static VOID (*FinishOperation)(PVOID);
static PVOID FinishRequest;
static BOOLEAN (*NextOperation)(PVOID);
static PVOID NextPort;
static BOOLEAN NextResult;
static VOID (*TimeoutOperation)(PVOID, ULONG);
static PVOID TimeoutPort;
static ULONG TimeoutSlot;
static PIO_TIMER_ROUTINE TimerOperation;
static PDEVICE_OBJECT TimerDevice;
static PVOID TimerPort;

static VOID NTAPI IdeInterrupt(VOID)
{
    if (HardwareIsr && HardwareInterrupt && !IrqChained) {
        IrqChained = TRUE;
        IrqResult = HardwareIsr(HardwareInterrupt, HardwareContext);
    }
}
static VOID NTAPI IdeStart(PDEVICE_OBJECT Device, PIRP Irp)
{
    UNREFERENCED_PARAMETER(Device); UNREFERENCED_PARAMETER(Irp);
    if (StartOperation) {
        BOOLEAN (*routine)(PVOID, PVOID) = StartOperation;
        StartOperation = NULL; /* chaining twice must not issue a second command */
        StartResult = routine(StartChannel, StartRequest);
    }
}
static VOID NTAPI IdeFinish(VOID)
{
    if (FinishOperation) {
        VOID (*routine)(PVOID) = FinishOperation;
        PVOID request = FinishRequest;
        FinishOperation = NULL;
        routine(request);
    }
}
static VOID NTAPI IdeNext(VOID)
{
    if (NextOperation) {
        BOOLEAN (*routine)(PVOID) = NextOperation;
        NextOperation = NULL;
        NextResult = routine(NextPort);
    }
}
static VOID NTAPI IdeTimeout(VOID)
{
    if (TimeoutOperation) {
        VOID (*routine)(PVOID, ULONG) = TimeoutOperation;
        TimeoutOperation = NULL;
        routine(TimeoutPort, TimeoutSlot);
    }
}
static BOOLEAN NTAPI IdePoll(VOID)
{ return !IdexChannelObject.StartPacketBusy; }
static VOID NTAPI IdeTimerDpc(PKDPC Dpc, PVOID Context, PVOID A1, PVOID A2)
{
    UNREFERENCED_PARAMETER(Dpc); UNREFERENCED_PARAMETER(Context);
    UNREFERENCED_PARAMETER(A1); UNREFERENCED_PARAMETER(A2);
    if (TimerOperation) TimerOperation(TimerDevice, TimerPort);
}
static VOID IdeInitialize(VOID)
{
    if (IdeInitialized) return;
    IdeInitialized = TRUE;
    IdexChannelObject.InterruptRoutine = IdeInterrupt;
    IdexChannelObject.FinishIoRoutine = IdeFinish;
    IdexChannelObject.PollResetCompleteRoutine = IdePoll;
    IdexChannelObject.TimeoutExpiredRoutine = IdeTimeout;
    IdexChannelObject.StartPacketRoutine = IdeStart;
    IdexChannelObject.StartNextPacketRoutine = IdeNext;
    IdexChannelObject.MaximumIoRetries = 3;
    KeInitializeDeviceQueue(&IdexChannelObject.DeviceQueue);
    KeInitializeDpc(&IdexChannelObject.TimerDpc, IdeTimerDpc, NULL);
    KeInitializeTimer(&IdexChannelObject.Timer);
}
VOID NxkIdeSetHardwareIsr(PKSERVICE_ROUTINE Routine, PVOID Context)
{ IdeInitialize(); HardwareIsr = Routine; HardwareContext = Context; }
BOOLEAN NTAPI NxkIdeIsr(PKINTERRUPT Interrupt, PVOID Context)
{
    UNREFERENCED_PARAMETER(Context);
    if (!HardwareIsr || !HardwareContext) return FALSE;
    HardwareInterrupt = Interrupt; IrqResult = FALSE; IrqChained = FALSE;
    ++IdexChannelObject.InterruptObject.ServiceCount;
    IdexChannelObject.InterruptRoutine();
    HardwareInterrupt = NULL;
    return IrqResult;
}
VOID NxkIdeBindInterrupt(PKINTERRUPT Native)
{
    IdeInitialize();
    IdexChannelObject.InterruptIrql = Native->Irql;
    IdexChannelObject.InterruptObject.ServiceRoutine = NxkIdeIsr;
    IdexChannelObject.InterruptObject.ServiceContext = HardwareContext;
    IdexChannelObject.InterruptObject.BusInterruptLevel = Native->Vector;
    IdexChannelObject.InterruptObject.Irql = Native->Irql;
    IdexChannelObject.InterruptObject.Connected = Native->Connected;
    IdexChannelObject.InterruptObject.ShareVector = Native->ShareVector;
    IdexChannelObject.InterruptObject.Mode = Native->Mode;
    XeInterruptBindNative((PKINTERRUPT)&IdexChannelObject.InterruptObject, Native);
}
/* Disable device interrupts first; unpublish before disconnect frees the IRQ.
 * The channel key prevents a secondary/unrelated teardown from clearing it. */
VOID NxkIdeUnbindChannel(PVOID Channel)
{
    KIRQL old;
    /* Pageable teardown on UP: cancel any future timer work before removing
     * its channel/context. Do not take timer locks at HIGH_LEVEL. */
    if (Channel == HardwareContext && TimerOperation) NxkIdeStopTimer(TimerPort);
    KeRaiseIrql(HIGH_LEVEL, &old);
    if (Channel == HardwareContext) {
        XeInterruptBindNative((PKINTERRUPT)&IdexChannelObject.InterruptObject, NULL);
        HardwareIsr = NULL; HardwareContext = NULL; HardwareInterrupt = NULL;
        StartOperation = NULL; StartChannel = NULL; StartRequest = NULL;
        FinishOperation = NULL; FinishRequest = NULL;
        NextOperation = NULL; NextPort = NULL;
        TimeoutOperation = NULL; TimeoutPort = NULL;
        IdexChannelObject.CurrentIrp = NULL;
        IdexChannelObject.StartPacketBusy = FALSE;
        IdexChannelObject.StartPacketRequested = FALSE;
        IdexChannelObject.ExpectingBusMasterInterrupt = FALSE;
        IdexChannelObject.DeviceQueue.Busy = FALSE;
        IdexChannelObject.Timeout = 0;
        IdexChannelObject.PhysicalRegionDescriptorTablePhysical = 0;
        RtlZeroMemory(&IdexChannelObject.InterruptObject,
                      sizeof(IdexChannelObject.InterruptObject));
        ++RequestGeneration;
    }
    KeLowerIrql(old);
}
VOID NxkIdeInitializeCompletion(PKDEFERRED_ROUTINE Routine)
{ IdeInitialize(); KeInitializeDpc(&IdexChannelObject.FinishDpc, Routine, NULL); }
PKDPC NxkIdeCompletionDpc(VOID) { return &IdexChannelObject.FinishDpc; }
VOID NxkIdeStartTimer(PDEVICE_OBJECT Device, PVOID Port, PIO_TIMER_ROUTINE Routine)
{
    LARGE_INTEGER due;
    TimerDevice = Device; TimerPort = Port; TimerOperation = Routine;
    due.QuadPart = -10000000;
    KeSetTimerEx(&IdexChannelObject.Timer, due, 1000, &IdexChannelObject.TimerDpc);
}
VOID NxkIdeStopTimer(PVOID Port)
{
    if (TimerPort != Port) return;
    KeCancelTimer(&IdexChannelObject.Timer);
    KeRemoveQueueDpc(&IdexChannelObject.TimerDpc);
    TimerOperation = NULL; TimerDevice = NULL; TimerPort = NULL;
    NextOperation = NULL; NextPort = NULL;
    TimeoutOperation = NULL; TimeoutPort = NULL;
}
BOOLEAN NxkIdeStartRequest(PVOID Channel, PVOID Request,
    BOOLEAN (*Start)(PVOID, PVOID), PDEVICE_OBJECT Device, PIRP Irp, ULONG Timeout)
{
    if (Channel != HardwareContext) return Start(Channel, Request);
    ++RequestGeneration;
    IdexChannelObject.CurrentIrp = Irp;
    IdexChannelObject.StartPacketBusy = TRUE;
    IdexChannelObject.DeviceQueue.Busy = TRUE;
    IdexChannelObject.StartPacketRequested = TRUE;
    IdexChannelObject.ExpectingBusMasterInterrupt = TRUE;
    IdexChannelObject.Timeout = (UCHAR)min(Timeout, 255);
    StartChannel = Channel; StartRequest = Request; StartOperation = Start;
    StartResult = FALSE;
    IdexChannelObject.StartPacketRoutine(Device, Irp);
    StartOperation = NULL;
    IdexChannelObject.StartPacketRequested = FALSE;
    return StartResult;
}
VOID NxkIdeFinishRequest(PVOID Request, VOID (*Finish)(PVOID), PIRP Irp)
{
    /* Shared completion DPC can also carry an unrelated secondary channel. */
    if (IdexChannelObject.CurrentIrp != Irp) { Finish(Request); return; }
    ULONG generation = RequestGeneration;
    IdexChannelObject.ExpectingBusMasterInterrupt = FALSE;
    IdexChannelObject.StartPacketBusy = FALSE;
    IdexChannelObject.DeviceQueue.Busy = FALSE;
    FinishRequest = Request; FinishOperation = Finish;
    IdexChannelObject.FinishIoRoutine();
    FinishOperation = NULL;
    /* Completion may requeue this exact IRP: pointer equality is insufficient. */
    if (generation == RequestGeneration) IdexChannelObject.CurrentIrp = NULL;
}
BOOLEAN NxkIdeStartNext(PVOID Port, BOOLEAN (*StartNext)(PVOID))
{
    if (TimerPort != Port) return StartNext(Port);
    NextPort = Port; NextOperation = StartNext; NextResult = FALSE;
    IdexChannelObject.StartNextPacketRoutine(); NextOperation = NULL;
    return NextResult;
}
VOID NxkIdeTimeout(PVOID Port, ULONG Slot, VOID (*Timeout)(PVOID, ULONG))
{
    if (TimerPort != Port) { Timeout(Port, Slot); return; }
    IdexChannelObject.Timeout = 0;
    TimeoutPort = Port; TimeoutSlot = Slot; TimeoutOperation = Timeout;
    IdexChannelObject.TimeoutExpiredRoutine(); TimeoutOperation = NULL;
}

BOOLEAN NxkIdeResetComplete(PVOID Channel)
{
    if (Channel != HardwareContext) return TRUE;
    /* The native reset is synchronous; poll the title hook only after its
     * actual completion. Default poll therefore observes completed reset. */
    IdexChannelObject.StartPacketBusy = FALSE;
    IdexChannelObject.ExpectingBusMasterInterrupt = FALSE;
    return IdexChannelObject.PollResetCompleteRoutine();
}
VOID NxkIdeSetTimeout(PVOID Port, ULONG Seconds)
{
    if (Port == TimerPort) IdexChannelObject.Timeout = (UCHAR)min(Seconds, 255);
}
