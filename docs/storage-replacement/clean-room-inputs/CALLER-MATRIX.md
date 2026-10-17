# Caller / device dependency matrix

Paths below identify target integration seams and necessary public symbols. They do not authorize reading excluded implementation source.

| Retained caller / path | Boundary it requires | Replacement obligation |
| --- | --- | --- |
| `ntoskrnl/io/iomgr/driver.c:IopFoldedInDrivers` | IoCreateDriver registration and creation order; NTAPI DRIVER_INITIALIZE | preserve Disk/Cdrom names and entry ABI in the registry; update static linking |
| `ntoskrnl/io/iomgr/driver.c:IopSealBootDriverPnp` | boot PnP completion before INIT discard | resident runtime dispatch; no AddDevice or PnP pointer into freed INIT |
| `ntoskrnl/xb/devtree.c` | PCI IDE channels, ATAPI devices, class and partmgr AddDevice/Start, BusRelations | class attachment/start must finish before HDD partmgr start; optical remains separate |
| `ntoskrnl/xb/devnode.c` | root PDO for power boot; child DeviceNode started/identity bookkeeping | retain kernel node validity; no new private class layout dependency |
| `ntoskrnl/include/internal/nx-devtree.h` | static-tree driver pointer declarations and kernel helper API | preserve kernel declaration/calling convention compatibility |
| `drivers/storage/partmgr` Start | STORAGE_GET_DEVICE_NUMBER on lower raw HDD | valid disk number 0 response or meaningful startup failure |
| `drivers/storage/partmgr` BusRelations refresh | GEOMETRY_EX and kernel IoReadPartitionTableEx reads | exact capacity + 512-byte FATX sectors; raw data reads work before partitions start |
| `drivers/storage/partmgr` partition I/O | one partition offset translation then lower data I/O | accept absolute raw offsets; do not translate twice |
| `drivers/storage/partmgr` flush/shutdown | raw class below partmgr | real ordered cache synchronization and error propagation |
| `ntoskrnl/fstub/fstubex.c` Xbox partition read | fixed FATX superblock probe reads, discovered layout | no class-owned MBR/GPT parser or duplicate FATX partition synthesis |
| `drivers/storage/partmgr/partition.c` Start | partition object naming/symbolic links and volume numbering | preserve device type/alignment/VPB behavior consumed above |
| `drivers/storage/mountmgr` | MOUNTDEV_QUERY_DEVICE_NAME / UNIQUE_ID on volumes; symbolic links | mostly answered by retained partition owner; no need to copy desktop class mount framework |
| `drivers/filesystems/vfatfs` | asynchronous/direct and scatter/gather I/O, leases, write/flush | preserve upper lifetimes, bytes/status and existing optimized work accounting |
| `drivers/filesystems/xdvdfs/xdvdfs.c` | ordinary lower sector READ IRPs; exact reply count; optical IOCTL forwarding | class READ(10), capacity, direct MDLs, sector tails and read-only policy |
| Existing optical namespace callers | CdRom0, legacy DOS link, geometry, TOC, verification | preserve these public names/controls without old private layouts or helpers |
| `ntoskrnl/xb/xbe.c` loader | CdRom0/default.xbe, Partition2/xboxdash.xbe | stable mounts and discovery order before loader reads |
| `drivers/storage/ide/atapi` | IRP_MJ_SCSI legacy SRB; OriginalRequest child's MDL; supplied sense | correctly sized resident SRB/IRP/MDL/buffer through final lower completion |
| `drivers/storage/ide/{pciide,pciidex}` | negotiated transfer/pages/alignment; interrupt/DMA PATA | keep lower hardware path and its limits; no direct ATA bypass |
| Static kernel build | single PE, archive/transitive-input selection | final candidate omits excluded class libraries and inherited helper implementation |

Mountmgr's Xbox build omits several desktop FT/partition-attribute queries; do not infer they are a required class surface from ungated source. Current kernel registration has XDVDFS followed by Vfatfs, without a folded Cdfs entry; stale source comments describing a Cdfs fallback are not authoritative composition evidence. Full formatted FATX canonical order is E,C,X,Y,Z; missing-signature dense-numbering behavior is an unresolved compatibility case.
