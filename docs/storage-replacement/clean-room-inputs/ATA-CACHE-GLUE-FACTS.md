# Cached ATA capability and publication facts

Investigator-only research exported as original prose, numeric/interface facts and integration coordinates, 2026-10-14. This supplies no hook, capture function, atomic helper body or whole ATA/IDENTIFY helper header. The fresh author owns the implementation and tests. The proposed metadata extension is not implemented or native-qualified by this packet.

## Exact representation and retained selector

The declaration-only target probe establishes a packed 512-byte `IDENTIFY_DEVICE_DATA`, alignment1. Its `CommandSetSupport` declaration occupies six bytes starting at byte164 (ATA words82–84); `CommandSetActive` occupies six bytes starting at byte170 (words85–87). The word index is zero based; each raw ATA word is two bytes on this little-endian x86 target. The device extension's IDENTIFY DEVICE/PACKET views share the same 512-byte storage. Numeric offsets describe the baseline ABI; adding a candidate metadata field requires assertions against that candidate's own declarations.

| Interoperability fact | Raw word / value |
| --- | --- |
| Write-cache support | word82, bit5, mask0x0020 |
| Write-cache active | word85, bit5, mask0x0020 |
| Regular flush support | word83, bit12, mask0x1000 |
| Extended flush support | word83, bit13, mask0x2000 |
| LBA48 support | word83, bit10, mask0x0400 |
| Public word83 validity field, target name `WordValid83` | word83 bits14–15; recognized value1 gives0x4000, mask0xc000 |
| **Actual retained cache/flush validity field**, target name `WordValid` | **word84 bits14–15**; recognized value1 gives0x4000, mask0xc000 |
| ATA / ATAPI device type values | `DEV_ATA=1`, `DEV_ATAPI=2` |
| Actual optical transport discriminator | `Device.TransportFlags`, `DEVICE_IS_ATAPI=0x10`; this is separate from `Device.DeviceFlags` |
| Negotiated LBA48 discriminator | `Device.DeviceFlags`, `DEVICE_LBA48=0x4` |
| Hardware commands | regular flush0xe7, extended flush0xea, IDENTIFY DEVICE0xec, IDENTIFY PACKET0xa1 |

**Correction:** earlier cache packets said the retained cache/flush predicates use word83 validity. Their comments say word83, but their actual declared field is at word84. The new probe initializes each named bitfield independently and verifies its physical word/mask in the object; it distinguishes both markers without copying a predicate body. Cache-enabled recognition uses the word84 marker plus the word82 support and word85 active bits. Regular/extended flush support also uses that word84 marker. LBA48 negotiation separately uses word83 validity and its support bit, then stores the negotiated device flag. Source grants for the narrowly inspected IDENTIFY helper file explicitly offer GPL-2.0-or-later or MIT; its full body/header remains outside author inputs.

Observed retained route: non-ATAPI profile plus negotiated LBA48 and recognized extended support selects0xea; otherwise recognized regular support selects0xe7; otherwise no command is selected. Cache not recognized enabled, or enabled with no selected command, gives successful no-command synchronization. Recognized enabled cache plus a selected command takes the existing hardware/error path. A property response must expose the selected path and cannot treat no-command success as physical flush proof. No USB/FUA/cache-disable assumption follows.

Public ATA validity is a distinct contract. Manufacturer documentation places support and flush bits in words82/83; the public ATA-5 draft additionally specifies enabled-group validity at word87. A stricter candidate validity policy must be explicit; it must not silently describe a normative check as the current lower predicate. [Seagate IDENTIFY table](https://www.seagate.com/www-content/product-content/ssd-fam/600-pro-ssd/en-us/docs/100727924b.pdf), [ATA-5 draft, sections8.12.45–46](https://www.seagate.com/support/disc/manuals/ata/d1153r17.pdf).

## Every observed cached-data writer on this Xbox path

These are integration/lifetime facts about compatible retained lower code, not a decomposition of excluded sample implementation.

| Writer / state boundary | Compatible-source anchor | Scope and terminal facts |
| --- | --- | --- |
| Device construction zeroing | `atapi/pdo.c:753`, function `AtaPdoCreateDevice` | entire extension initialized before external PDO exposure; metadata begins Unknown |
| Initial identification and re-enumeration | `atapi/dev_identify.c:213`, function `AtaPortIdentifyDevice`; cached copy317 and profile assignment320 | worker IDENTIFY transfers into `Device.LocalBuffer`, then accepted identity is copied into cached union; this also applies to SAME_DEVICE refresh; new classification is finalized after the copy |
| Negotiated addressing update | `atapi/enum.c:182`, function `AtaDeviceSetAddressingMode`; callers `AtaPdoInit` and read-capacity terminal callback | clears/recomputes LBA/LBA48/FUA-related flags from cached identity; snapshot must include the actual selected flag after this update |
| Post-configuration refresh | `atapi/dev_config.c:343`, function `AtaPortDeviceProcessConfig`; fresh IDENTIFY389 and copy395 | configure can return early on hardware failure; success-only cached copy follows local-buffer IDENTIFY; configuration-event signaling alone does not establish successful fresh identity |
| Runtime cached-union transfer | `atapi/satl.c:381`, builder; READ CAPACITY submit871 | IDENTIFY writes directly to cached union, with exclusive/poll/data-in flags; READ CAPACITY10 and service-action READ CAPACITY16 both reach it on Xbox |
| Actual command start | `atapi/scsi.c:500`, function `AtaReqStartIo`; actual external start invocation522 | common PIO/DMA/internal path, after mappings/descriptor preparation and before hardware writes; construction time alone is too early for invalidation of already queued writers |
| Runtime terminal translation | `atapi/satl.c:759`, `AtaReqCompleteReadCapacity`; addressing update768 | invoked by generic completion under device QueueLock; invocation itself is not a success/byte-count proof |
| Runtime terminal ownership boundary | `atapi/scsi.c:262`, `AtaReqCompleteRequest` | raw result exists before translation callback; post-translation coherent snapshot must precede successor start and request storage reuse |
| Reset invalidation/re-identification | `atapi/portstate.c:165`, reset notification; reset worker298 | affected devices' software settings become unavailable; enumeration/configuration are scheduled; stale prior publication cannot survive reset/generation revocation |
| Removal / object lifetime | `atapi/pdo.c:85`, removal; free675 | queue frozen/flushed; final removal waits for remove-lock users before freeing extension; scalar record belongs to that same device lifetime |

The other shared IDENTIFY-builder caller is MODE SENSE; its ATA dispatch is Xbox-excluded. ATA INQUIRY uses cached inquiry data on Xbox and does not add an IDENTIFY transfer. MODE SELECT and ATA pass-through dispatch are also excluded. SMART and other inspected consumers read/copy data outward. Scoped searches and alias review found no additional cached-cache-word writers among compiled MIT ATA units.

The registered channel `SetDeviceData` callback is `pciidex/fdo.c:155`, GPL via its original COPYING reference; narrow investigator read was expressly authorized by the parent. It conditionally calls the ACPI interface. The Xbox `pciidex/acpi.c:49` MIT endpoint is a no-op and does not mutate the supplied identity. Thus this callback adds no Xbox writer. No callback body is exported.

## Real transfer, aliases and completion evidence

`Device.QueueLock` is not a lock over the hardware transfer into cached identity. The cached block can change while a property query bypasses the I/O queue. Runtime IDENTIFY may use PIO or controller DMA according to retained flags; do not characterize every IDENTIFY as DMA or immutable cached storage.

In the compatible MIT PATA data-in path (`pciidex/chipset/pata_io.c:681–700`), success requires that the remaining-byte count reaches zero, BUSY/DRQ clear, and no device error/fault remains. With the identified512-byte request, raw terminal success therefore establishes512 bytes consumed by that PIO path. `PataCompleteCommand` at168 stores the raw SRB result before notifying port completion. Raw `SRB_STATUS_SUCCESS=1`; requested length512 alone establishes no completion.

The DMA completion branch at750–760 reports success from controller/device error flags for the programmed descriptors. It does not supply an independent completed-byte counter. Expected512-byte descriptors plus raw controller success supports the retained logical transfer contract; it is not an independently counted or measured hardware512-byte result. Native acceptance must identify which proof applies, exercise controller errors, and verify returned identity where feasible. No native run or checksum measurement is claimed here.

The translation callback can run on started error paths. Its output formatter (`satl.c:294–302`) rewrites **both** SRB status and transfer length to the caller's capacity response. Those translated success/count values must not be mistaken for IDENTIFY success/512 bytes. Preserve independently owned pre-translation classification and raw completion facts if publication occurs later. Input task-file and saved output registers are separate declared storage; error saving does not itself overwrite the input opcode. Request storage is eventually recycled and must not be referenced after its owner releases it.

DataBuffer identity is not stable as a raw pointer: PIO mapping rewrites it at `scsi.c:739`, while local-buffer internal transfers select `Device.LocalBuffer` in the send path. A stable writer classification must be owned across construction, mappings, real start and raw terminal completion. No particular marker field, tracking structure or algorithm is prescribed. The cached destination, local-buffer destination, initial512-byte extent, device generation and command identity must remain unambiguous even when a mapped address differs.

## Proposed scalar ownership requirements

The device-owned capability record is metadata only and resides in nonpaged device storage. Queries read one coherent published scalar, never raw IDENTIFY/negotiated fields while those fields can change. Every relevant writer, initialization, reset/removal or classification change invalidates publication before mutable facts become unavailable. A built-but-queued IDENTIFY must invalidate again at actual start before any cached-buffer PIO/DMA write; otherwise an earlier writer can publish while a later queued writer begins.

Publication requires a coherent successful full identity for the current device/writer generation and the applicable negotiated flags. It occurs while later mutation cannot start, after addressing/classification updates, and before generic completion starts a successor. Failure, partial transfer, requeue or revoked generation leaves Unknown. An older terminal event must never restore Known after a later invalidation. Local-buffer IDENTIFY completion alone is too early to publish: the cache copy and applicable profile/flag consistency must first be established. Same-device refresh also needs publication; a new-device initialization hook alone misses it.

The worker serializes its own reset/enumeration/configuration actions and defers paused normal requests; that does not make the raw snapshot query safe by itself. The fresh author must provide a writer-generation/ownership proof and meaningful queued-writer/reset/error tests. No new ATA command, queue policy, IRQ flow or hardware settings change is required by these metadata invariants.

The retained PDO control dispatcher continues to own its remove lock and sole caller completion. The query hook supplies status/Information and declines forwarding for its recognized property. It never independently completes the parent or frees the device. `STATUS_NOT_SUPPORTED=0xc00000bb` is in the supplemental fact header. `STATUS_MORE_PROCESSING_REQUIRED=0xc0000016` is supplied as a numeric context fact; this query-routing contract does not use it as a hook return convention.

## Native atomic availability

Checked native `LONG`/`ULONG` are four bytes, alignment4. Target intrinsic type facts match `_InterlockedExchange`: `LONG (volatile LONG*, LONG)`, and `_InterlockedCompareExchange`: `LONG (volatile LONG*, LONG, LONG)` with ordinary C intrinsic types. Their public operations are atomic on aligned nonpaged storage; this is an interface fact, not authorization to copy target header implementations or invent standalone linker exports. [Exchange](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/nf-wdm-interlockedexchange), [compare/exchange](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/nf-wdm-interlockedcompareexchange).

The exact GCC13 target reports four-byte atomics always lock-free and `__GCC_ATOMIC_LONG_LOCK_FREE=2`. Header-free compiler interfaces are `__atomic_load_n(type*, order)`, `__atomic_store_n(type*, value, order)`, `__atomic_exchange_n(type*, value, order)`, and `__atomic_compare_exchange_n(type*, expected_pointer, desired, weak, success_order, failure_order)`. These are compiler builtins, not declarations for external functions. Acquire/release or sequential consistency can express a fresh author's independently chosen publication proof. All concurrent record accesses must use compatible atomic operations; volatile alone is insufficient. A naturally aligned four-byte scalar avoids a kernel libatomic dependency under the probed target. Candidate compilation must verify its own selected operations and linked inputs. [GCC atomic interface](https://gcc.gnu.org/onlinedocs/gcc/_005f_005fatomic-Builtins.html).

`ATA-CACHE-ABI-RECEIPT.json` pins compiler, flags, source/hash scope, declaration probe and independent object/assembly checks. The probe emits zero executable text; its incidental generated GUID data and complete dependencies stay investigator-only. All unknown/full transitive headers and helper bodies remain excluded.
