# Public interface references

Browsed 2026-10-14. Documentation is behavioral reference material, not source-code reuse permission. No documentation example code is exported. Necessary convergence is confined to public names, numeric interface facts, structure layouts, CDB encoding, queue/status meanings and completion semantics.

| Source | Permitted lesson |
| --- | --- |
| [DRIVER_INITIALIZE](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/nc-wdm-driver_initialize) | entry signature, driver-object role, PASSIVE_LEVEL |
| [SCSI_REQUEST_BLOCK](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/srb/ns-srb-_scsi_request_block) | legacy ABI/status modifiers/directions, actual underrun bytes, queue release semantics |
| [Implementing completion](https://learn.microsoft.com/en-us/windows-hardware/drivers/kernel/implementing-an-iocompletion-routine) | allocated-child ownership, completion-stop return, pending and priority semantics |
| [IoSetCompletionRoutine](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/nf-wdm-iosetcompletionroutine) | callback context and nonpaged execution constraints |
| [Using MDLs](https://learn.microsoft.com/en-us/windows-hardware/drivers/kernel/using-mdls) | virtual vs physical description, original-address context, pinning/mapping lifetimes |
| [DISK geometry](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntdddisk/ni-ntdddisk-ioctl_disk_get_drive_geometry) | required output and status family |
| [DISK geometry EX](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntdddisk/ni-ntdddisk-ioctl_disk_get_drive_geometry_ex) | 32-byte base minimum, returned bytes, optional metadata |
| [DISK length](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntdddisk/ni-ntdddisk-ioctl_disk_get_length_info) | exact 64-bit byte length and short-buffer rejection |
| [Storage device number](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntddstor/ni-ntddstor-ioctl_storage_get_device_number) | public disk/partition number fields and length |
| [Storage verification](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntddstor/ni-ntddstor-ioctl_storage_check_verify) | optional change count, mounted-volume verification requirement |
| [CDROM TOC](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntddcdrm/ni-ntddcdrm-ioctl_cdrom_read_toc) | output size, actual returned count, media-error status family |
| [Seagate SCSI Commands Reference Manual, Rev M, June 2022](https://knowledge.seagate.com/files/staticfiles/support/docs/manual/Interface%20manuals/100293068m.pdf) | command names/opcodes as primary vendor documentation; does not prove Xbox drive support |

Official T10 index was checked for standard provenance, but published historical working drafts state member-only access. No access control was bypassed, no such draft was acquired, and no mirrored restricted draft is approved input. A direct historical T13 PDF link was unavailable through the web tool. The current lower-driver contract and public-domain interface declarations support the necessary command boundary; physical cache durability still needs independent verification.
