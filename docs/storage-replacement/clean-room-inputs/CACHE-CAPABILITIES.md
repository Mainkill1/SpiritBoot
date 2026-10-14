# Composed cache and transfer capability boundary

Labels are C/P/I/U as in COMPLETION-OWNERSHIP.md. These are source/API facts; no live drive capability or durability measurement is claimed.

## Available class-facing discovery

**C:** `IOCTL_STORAGE_QUERY_PROPERTY` with StorageAdapterProperty is available through the ATAPI device PDO and forwarded to its channel owner. Its result carries negotiated MaximumTransferLength, MaximumPhysicalPages, and AlignmentMask. Channel startup begins with a default PATA maximum of 128 KiB, then may reduce it to DMA map-register capacity; non-DMA fallback also determines a physical-page bound. Query and validate the returned descriptor/version/size rather than assuming 128 KiB or a fixed page count. Both byte length and the physical pages spanned by a segment matter, including the initial page offset. [Public adapter descriptor](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntddstor/ns-ntddstor-_storage_adapter_descriptor).

**C:** ATA MODE SENSE(6) and MODE SENSE(10), including the caching mode page, are compiled out of the Xbox HDD command switch. The retained MIT source has a caching-page producer for other configurations, but its presence in source does not make that query available on Xbox. ATAPI optical packet passthrough is different and does not prove a drive accepts a caching-page request.

**C:** StorageDeviceWriteCacheProperty is a public enumeration value but is not handled by the composed lower property dispatch. It ultimately receives the unsupported-property result. ATA/SCSI pass-through controls used for raw IDENTIFY access are also compiled out on Xbox. StorageDeviceProperty, alignment properties and INQUIRY do not by themselves expose all cache-enable/flush-support facts.

**I/R:** An independent class cannot infer cache disabled from an unsupported caching-page/property query. Either provide an explicitly reviewed compatible lower capability interface, independently enable an appropriate supported public discovery path, or mark cache capability unverified. Do not access an unapproved private layout or fabricate a descriptor to hide the gap. This packet does not choose the implementation of a new capability interface.

## Actual retained lower cache-sync behavior

**C:** The lower captures drive IDENTIFY data during discovery. It treats volatile write caching as enabled only when the command-set validity marker is recognized and both the supported and active WriteCache flags are set. Relevant public IDENTIFY facts are word 82 bit 5 (support), word 85 bit 5 (active), and the word-83 validity marker. Flush Cache support is word 83 bit 12; Flush Cache Ext support is word 83 bit 13, under that same validity test. [Public IDENTIFY declaration](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ata/ns-ata-_identify_device_data).

**C:** SYNCHRONIZE CACHE on a non-ATAPI ATA device has three observable branches: cache not recognized enabled => successful no-command result; enabled cache with no selected supported flush command => successful no-command result; enabled cache with selected flush command => hardware command and eventual completion/error. Selection prefers FLUSH CACHE EXT (0xEA) when LBA48 and its support flag are present, otherwise FLUSH CACHE (0xE7) when supported. This choice is not a USB policy. The hardware path ultimately writes the selected task-file command to the PATA command register and uses normal lower interrupt/polling/error completion.

**C/R:** Thus enabled cache really reaches ATA hardware flush when the lower IDENTIFY/capability prerequisites select a command. Enabled cache alone is not sufficient: unsupported or invalid capability flags can lead to apparent success without a flush command. No-command success cannot establish physical durability unless cache-disable facts are independently proven. A diagnostic hook/test must distinguish these branches and record the actual command or explicit no-command reason.

**C:** SRB_FUNCTION_FLUSH/SHUTDOWN themselves do not take that hardware-sync route. PATA read/write FUA is cleared. Neither is a cache-discovery or durability substitute. SYNCHRONIZE CACHE may take longer than an ordinary data request; use an explicit bounded policy compatible with physical flush latency and lower timeouts.

**R:** Qualify supported/enabled combinations, invalid IDENTIFY flags, unsupported flush, successful 0xE7/0xEA command, device error and timeout, ordered outstanding writes, and mixed HDD/DVD traffic. Verify lower error propagation and upper save ordering. Command-level correctness in xemu does not establish physical power-loss durability.

**U:** Actual IDENTIFY values for the frozen native baseline, firmware cache state on every physical Xbox drive, power-loss results, candidate capability-interface behavior and exact timeout policy remain unmeasured. Source tracing demonstrates an available command path, not that every deployed device takes it.
