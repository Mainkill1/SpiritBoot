# Shared interrupt page allocator metadata

The read-only metadata probe passed19/19 functional checks and all12 expected phase byte SHA1 checks. All12,288 DMA IRQs, notifications, accepted DPC insertions, single-item DPC batches and request completions were counted. The channel remains at physical03baa868 and the active baseline IRQ entry at03baa444. The probe reused the exact matched-baseline ROM5729831c0fec0a571d6565509e154726487c0eb52f87e0e21f77ec245bfe44b3; only the title fixture was extended to read allocator-owned headers after each phase.

All four 8-byte NXP_HEADER records on VA c102d000 (physical03baa000) are stable across all12 phases, with class index5 (1,024-byte block including8-byte header) and magic4e58 (allocated). No object payload or title/game contents were inspected.

| Pool header VA | Payload VA | Tag value | Tag bytes | Native allocation meaning |
|---|---|---|---|---|
| c102d000 | c102d008 | 69766544 | Devi | Device-object allocation |
| c102d400 | c102d408 | 6e696f49 | Ioin | IO_INTERRUPT containing the active KINTERRUPT |
| c102d800 | c102d808 | 58656449 | IdeX | PCIIDE channel-data array |
| c102dc00 | c102dc08 | 69766544 | Devi | Another device-object allocation |

Source evidence on exact async4:

- `ntoskrnl/xb/mm/pool.c:73` defines Tag/ClassIndex/Magic as the8-byte NXP_HEADER; class5 is1,024bytes, and live magic is4e58.
- `ntoskrnl/include/internal/tag.h:87` defines TAG_IO_INTERRUPT as 'nioI'; `ntoskrnl/io/iomgr/irq.c:60` allocates IO_INTERRUPT. `ntoskrnl/include/internal/io.h:320` puts FirstInterrupt at its start. This directly matches the independently captured native KINTERRUPT pointerc102d408.
- `drivers/storage/ide/pciidex/pciidex.h:32` defines TAG_PCIIDEX as 'XedI'; `chipset/pata_generic.c:1112` allocates Size×MaxChannels for the channel-data array. This directly matches independently captured ChanData c102d808.
- Device objects use the 'Devi' type tag (`ntoskrnl/xb/object-types.c:27` and native object type setup). `IopCreateDevice` requests the native body plus device extensions through ObCreateObject; `ObpAllocateObject`, `ntoskrnl/ob/oblife.c:793`, tags the entire object allocation. These headers identify the allocation category, not which specific driver/device each of the two instances belongs to. Object bodies may follow optional object-manager headers, so payload VA must not be treated as the DEVICE_OBJECT pointer without resolving those headers.

Two shared-page device allocations are now a concrete additional attribution lead, but there is no measurement establishing their write frequency or cost. DEVICE_OBJECT queue/current-IRP/reference fields are possible native write sites only after those specific devices are identified. A follow-up could record device creation metadata in owned IopCreateDevice (object/driver/extension addresses, type and dispatch function addresses) or enumerate known native device lists; neither requires reading user buffers. Do not claim that these two objects explain any fixed amount of the~27ms improvement.

The stronger presently established explanation is in IRQ-CODE-PAGE-MECHANISM.md: the actual original xemu executable invalidates every TB on the shared physical page when the completion store sees translated IRQ code there. Next-IRQ retranslation lies outside a guest timestamp placed inside that stub. This explains why the other measured channel stores are cheap, and motivates host retranslation counts/timing if complete attribution is needed.

Artifacts: `irq-pool-probe/main.c`, `run-irq-pool.ps1`, `irq-pool-results.json`, raw `evidence/storage-irq-pool-stock-baseline-*`. The JSON retains all48 header records, exact fixture hash, launch receipt and serial digest. Scheduled task CodexStorageIRQPool20261013 completed0; Windows slot was released.
