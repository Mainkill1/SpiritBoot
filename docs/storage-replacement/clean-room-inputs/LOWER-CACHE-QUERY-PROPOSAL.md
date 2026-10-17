# Minimal lower cache-capability query proposal

**Proposed, not implemented or tested.** This is a bounded read-only extension to the retained compatible ATAPI control boundary. It supplies standard StorageDeviceWriteCacheProperty information from already captured device IDENTIFY/capability state. It does not change ATA submission, command translation, device caching configuration, discovery commands, IRQ/DMA behavior, or the actual SYNCHRONIZE CACHE path.

## Public operation and scope

Use IRP_MJ_DEVICE_CONTROL / IOCTL_STORAGE_QUERY_PROPERTY with PropertyId StorageDeviceWriteCacheProperty, standard STORAGE_PROPERTY_QUERY input, and STORAGE_WRITE_CACHE_PROPERTY output. The existing public-domain ntddstor declarations in this package define the interface. Limit initial support to the retained ATA HDD path; ATAPI optical lacks the same ATA-cache proof and may return STATUS_NOT_SUPPORTED. The class obtains a response through the device stack, not by reading an unapproved lower extension layout.

The query performs no hardware command, cache enable/disable, FUA substitution, write, flush, or per-I/O probe. It is bounded by the fixed descriptor and uses a consistent retained capability snapshot. It may be used during Start and explicitly requested control operations, with the ordinary child/request/lower-device ownership rules. Existing adapter/device/alignment property behavior remains available.

## Required capability meaning

| Public response fact | Requirement |
| --- | --- |
| WriteCacheEnabled | Enabled only with valid command-set facts and both cache-support and cache-active indications. Valid supported cache with active indication clear is Disabled. Invalid validity marker or contradictory cached facts is Unknown; unsupported query is also Unknown to the class, never proof of Disabled. |
| FlushCacheSupported | True only when the current retained ATA SYNCHRONIZE CACHE route can select a hardware flush opcode from this snapshot. LBA48 plus valid Flush Cache Ext support selects 0xEA; otherwise valid Flush Cache support selects 0xE7. Ext-only support without the required LBA48 condition does not establish a selected opcode. False means this route lacks the proved command, regardless of lower success-only results. |
| WriteThroughSupported | Do not advertise native FUA capability from a flag that the retained PATA write path clears. Use the public Unknown/Unsupported indication unless a separately proved hardware write-through contract exists; class-implemented write-plus-flush is not native single-write FUA support. |
| WriteCacheType / WriteCacheChangeable | Use public Unknown when the retained snapshot does not establish these facts. The read-only extension does not claim cache configurability simply because the enable flag exists. |
| UserDefinedPowerProtection / NVCacheEnabled | No registry power-protection or battery-backed-cache credit may be advertised without retained/independent evidence. The initial profile can report conservative false values with the declared limitation that these fields provide no durability credit; it must not use them to justify skipping synchronization. |
| Version / Size / returned bytes | Correct public descriptor version/size, initialized response including padding, actual returned bytes bounded by caller output. Assert sizeof(STORAGE_WRITE_CACHE_PROPERTY) for the target ABI; ordinary x86 layout is 28 bytes. |

The exact retained enable test uses the word-83 command-set validity marker, word 82 bit 5 (Write Cache supported), and word 85 bit 5 (Write Cache active). Standard flush support is word 83 bit 12; extended flush support is word 83 bit 13 under that validity marker. The retained selector additionally depends on ATA device type and negotiated LBA48. A query may be more conservative about contradictory/invalid facts than the old helper, but that difference must be documented and tested.

The Boolean flush-support field does not encode cache-enabled state. A disabled cache may still support a flush opcode. Enabled/Unknown with unsupported flush is unqualified for durable barriers. Conversely, disabled caching must be independently established from valid capability state, not inferred from successful no-command synchronization.

## Buffer/status contract

Follow the retained lower's descriptor negotiation: input shorter than the required public query => STATUS_BUFFER_TOO_SMALL / 0; unsupported QueryType => STATUS_NOT_SUPPORTED / 0; supported PropertyExistsQuery => STATUS_SUCCESS / 0. A standard output shorter than STORAGE_DESCRIPTOR_HEADER => STATUS_INFO_LENGTH_MISMATCH / 0. A header-sized but short full-descriptor output returns an initialized header containing required size, STATUS_SUCCESS, and header bytes only. Full output returns STATUS_SUCCESS and exactly the initialized descriptor size. Unsupported device/profile returns STATUS_NOT_SUPPORTED / 0. No out-of-range buffer writes or stale padding.

## Existing behavior that this proposal must expose

Current Xbox MODE SENSE cache discovery, raw ATA pass-through discovery, and StorageDeviceWriteCacheProperty handling are absent. Current SYNCHRONIZE CACHE returns successful no-command completion both when cache is not recognized enabled and when no supported flush opcode is selected. Thus invalid/unknown flags or enabled-without-supported-flush do **not** currently cause an automatic lower error. The new query must make those conditions visible so the class can fail or report unsupported durability rather than accept that success as hardware proof.

When enabled cache and selected 0xE7/0xEA support are present, retained SYNCHRONIZE CACHE proceeds through the existing ATA task-file/PATA hardware command path and its eventual error handling. This proposal exposes that path's prerequisites; it does not certify physical drive-cache power-loss persistence.

Acceptance: valid enabled+0xE7, valid enabled+LBA48+0xEA, disabled cache with flush support, invalid validity marker, contradictory support/active facts, enabled+no flush, Ext-only without LBA48, optical rejection, every descriptor buffer boundary, consistent snapshot under lower state change, and zero hardware-command side effects from the query. Candidate code must be independently written and tested using these public facts and new production functions.

Public behavioral source: [write-cache property](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntddstor/ns-ntddstor-_storage_write_cache_property). Retained target source facts are summarized in CACHE-CAPABILITIES.md; no implementation body is supplied by this proposal.
