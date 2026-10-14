# Compiled minimal native ABI inventory

The same declaration-only SARCH_XBOX/i386 probe verified 250 scalar/layout/constant/prototype facts, with zero executable .text bytes. `native-abi-facts.json`/`.h` contain only measured numeric facts, no SDK helper implementation, private class structure, or source-shaped algorithm. They cover fields requested by the independent adapter design and are not permission to import an unchecked full target header.

| Type | Size | Alignment |
| --- | --- | --- |
| IRP | 128 | 8 |
| MDL | 28 | 4 |
| IO_STACK_LOCATION | 36 | 4 |
| IO_STATUS_BLOCK | 8 | 4 |
| DEVICE_OBJECT | 184 | 8 |
| DRIVER_OBJECT | 176 | 4 |
| DRIVER_EXTENSION | 20 | 4 |
| FILE_OBJECT | 132 | 4 |
| VPB | 88 | 4 |
| KDPC | 28 | 4 |

The Xbox target materially differs from ordinary desktop structures. Examples: IRP.MdlAddress=108, AssociatedIrp.SystemBuffer=112, CancelRoutine=116, IoStatus=16, Tail.Overlay.DriverContext=60, Tail.Overlay.Thread=80, Tail.Overlay.CurrentStackLocation=92. DRIVER_OBJECT.MajorFunction=12, DeviceObject=128, DriverExtension=148, DriverInit=168. DEVICE_OBJECT.DeviceExtension=24, AttachedDevice=76, VPB=88, StackSize=30, AlignmentRequirement=36. IO_STACK_LOCATION.DeviceIoControl input length=12, output length=4, type3 pointer=8, control code=16; Scsi.Srb=4; completion/context=28/32. These examples are measured offsets, not fabricated standard layouts.

The full numeric packet includes each selected field's offset and sizeof, original MDL fields, parent cancellation/pending/context fields, stack read/write/control/START fields, driver/device/file/VPB fields, write-through/paging/device/completion constants, and public callback calling conventions. All five NTAPI callback-type comparisons and ten linked-function prototype comparisons passed (numeric value 1). `target-api-declarations.h` matches those ten probed linked prototypes; IoInitializeIrp and IoCancelIrp remain source/API-verified declarations from the previous packet, rather than falsely claimed as part of these ten checks.

Use the facts to verify separately approved native type declarations at the actual candidate build. Partial-MDL PFN storage extends beyond sizeof(MDL), so a 28-byte descriptor alone does not provision an arbitrary segment. DataBuffer still uses the original MDL virtual-address domain; numeric field availability does not authorize lifetime violations or private layout borrowing. The public fields in DriverContext are storage availability facts, not a proof that every upper caller permits arbitrary context overwrite.

Prototype/header-only availability and lifetime rules remain in TARGET-API-AVAILABILITY.md and COMPLETION-OWNERSHIP.md. Runtime PnP/INIT, lower references, upper FATX leases, and cancellation protocol correctness are behavioral requirements beyond these numeric declarations. Additional unprobed fields/functions default to excluded/unknown pending review; no native execution or adapter implementation was performed.
