# Independent optical class profile

This specification freezes the optical part of the PR248 complete-candidate
backend.  It is an integration contract, not an implementation extracted from
the legacy optical class.  The complete candidate links only the independently
owned `nxstorage` archive; it does not retain the old `nxcdrom`, `classpnp`, or
`disk` archives.

## Observable behavior

* The `Cdrom` driver entry owned by the shared class-registration patch asks
  this profile to create exactly one `\\Device\\CdRom0` class device over the
  supplied lower optical PDO.  Creation also publishes
  `\\DosDevices\\CdRom0` and reports `FILE_DEVICE_CD_ROM`, removable-media and
  read-only characteristics.
* Initial media capacity is unknown.  The device remains present and its
  control path remains usable while capacity is zero.  A validated READ
  CAPACITY response may later publish media size inside the native adapter;
  the profile must not invent a disc size.
* The initial transfer contract uses 2048-byte optical sectors, 4096-byte
  pages, a 128 KiB byte limit, 33 spanned pages, no extra address-alignment
  restriction, a 65535-block command limit, disabled write cache, and at least
  one resident request slot.  The 33-page bound admits an odd-address 128 KiB
  range so the lower driver's supported PIO fallback remains reachable.
* Runtime read and write dispatches go through the shared native adapter.
  Writes are rejected there as media-write-protected.  Reads use adapter-owned
  READ(10) segmentation and the currently published media snapshot.
* Device controls go through the shared native adapter.  That boundary owns
  READ CAPACITY/media publication, format-0 LBA READ TOC capped at 804 bytes,
  TEST UNIT READY/check-verify, optical geometry, supported property
  forwarding, output initialization and short-buffer results.
* Flush and shutdown dispatches go through the shared adapter.  The profile
  introduces no success-only ClassPnP shim.
* Child allocation, SRB/sense/MDL ownership, terminal result capture,
  cancellation, completion-stop behavior, rundown and stale callback rejection
  are exclusively owned by the shared adapter.  The profile neither calls the
  child-completion/cancel entry points nor stores a child request pointer.
* Device creation failure is returned unchanged to the class-registration
  owner.  The profile publishes no second device or link and performs no
  fallback to a legacy class.

## Acceptance checks

Host tests compile the actual profile source with a deterministic adapter
double and prove the exact names, device type, characteristics, initial media
configuration and slot count passed to the one creation call.  They also prove
that read/write, device-control, flush and shutdown slots point at the frozen
shared-adapter dispatch functions and that the profile has no child
completion/cancel dependency.

A separate i386 freestanding compile uses declaration-only target facts.  The
final composed build must link `nxstorage` alone for the complete-candidate
class archive set, define `CdromDriverEntry` once through patch 0138, and leave
all runtime dispatch targets resident after the boot PnP seal.

Native behavior for reads, capacity/media, TOC, check-verify,
completion/cancellation and teardown is accepted only through patch 0140's
adapter tests and the final composed boot/runtime gates.  The profile host test
does not claim those transport behaviors.

## Permitted inputs used

* `docs/storage-replacement/clean-room-inputs/{README.md,README-PRODUCT.md,approved-inputs.json,CONTRACT.md,ACCEPTANCE.md,CALLER-MATRIX.md,PUBLIC-REFERENCES.md,CLOSURE-FACTS.md,COMPLETION-OWNERSHIP.md,TARGET-API-AVAILABILITY.md,NATIVE-ABI-INVENTORY.md,native-abi-facts.h,native-abi-facts.json,status-facts.h,target-api-declarations.h}`
* `docs/storage-replacement/boot-dependency-audit/{README.md,DECLARATION-FACTS.json,BOOT-DEPENDENCY-REVIEW.md}` (declaration/fact prose only)
* `docs/storage-replacement/independent-implementation/native-adapter-plan/NEXT-NATIVE-TASKS.md`
* independently owned patch primitives 0127, 0129 through 0135 and their
  checked `nxstorage` source/test outputs
* the approved exact public-domain declaration files `ntddcdrm.h`,
  `ntdddisk.h`, `ntddstor.h`, and `srb.h`, after their bytes matched the
  approved manifest hashes
* the frozen public `native_adapter.h` surface supplied by the independent
  adapter author

No legacy `nxcdrom`, ClassPnP, disk-class, extracted-body fixture,
disassembly, or patch carrying those implementation bodies was inspected.
