# Optical candidate input exposure ledger

Author: `/root/pr248_optical_driver_impl`
Product base: `7215382c7ca5545b7baa38c26cc868b0d57687bb`

This author did not open a legacy `nxcdrom`, ClassPnP, or disk-class
implementation body, an extracted-body fixture, disassembly, or any patch
containing those excluded bodies.  Directory and Git listings were used only
to locate the approved package and confirm repository identity.

## Approved specifications and declaration facts read

* `README.md`
* `docs/BUILD_AND_RUN.md`
* `docs/storage-replacement/clean-room-inputs/README.md`
* `docs/storage-replacement/clean-room-inputs/README-PRODUCT.md`
* `docs/storage-replacement/clean-room-inputs/approved-inputs.json`
* `docs/storage-replacement/clean-room-inputs/CONTRACT.md`
* `docs/storage-replacement/clean-room-inputs/ACCEPTANCE.md`
* `docs/storage-replacement/clean-room-inputs/CALLER-MATRIX.md`
* `docs/storage-replacement/clean-room-inputs/PUBLIC-REFERENCES.md`
* `docs/storage-replacement/clean-room-inputs/CLOSURE-FACTS.md`
* `docs/storage-replacement/clean-room-inputs/COMPLETION-OWNERSHIP.md`
* `docs/storage-replacement/clean-room-inputs/TARGET-API-AVAILABILITY.md`
* `docs/storage-replacement/clean-room-inputs/NATIVE-ABI-INVENTORY.md`
* `docs/storage-replacement/clean-room-inputs/native-abi-facts.{json,h}`
* `docs/storage-replacement/clean-room-inputs/status-facts.h`
* `docs/storage-replacement/clean-room-inputs/target-api-declarations.h`
* `docs/storage-replacement/clean-room-inputs/geometry-api-declarations.h`
* `docs/storage-replacement/clean-room-inputs/SRB-ABI-FACTS.json`
* `docs/storage-replacement/clean-room-inputs/ATA-CACHE-GLUE-FACTS.md`
* `docs/storage-replacement/boot-dependency-audit/README.md`
* `docs/storage-replacement/boot-dependency-audit/DECLARATION-FACTS.json`
* `docs/storage-replacement/boot-dependency-audit/BOOT-DEPENDENCY-REVIEW.md`
* `docs/storage-replacement/independent-implementation/native-adapter-plan/PLAN.md`
* `docs/storage-replacement/independent-implementation/native-adapter-plan/BOUNDED-PACKET-SCOPE.md`
* `docs/storage-replacement/independent-implementation/native-adapter-plan/NEXT-NATIVE-TASKS.md`
* `docs/storage-replacement/independent-implementation/native-adapter-plan/INPUT-EXPOSURE-LEDGER.json`
* `docs/storage-replacement/independent-implementation/native-adapter-plan/EXPORT-MANIFEST.json`

The exact approved hashes were checked before reading these public-domain
declaration files from the separate source checkout:

* `/home/codex/xemu-shader-workbench-handoff/spiritboot-kernel-source/sdk/include/psdk/ntddcdrm.h`
* `/home/codex/xemu-shader-workbench-handoff/spiritboot-kernel-source/sdk/include/psdk/ntdddisk.h`
* `/home/codex/xemu-shader-workbench-handoff/spiritboot-kernel-source/sdk/include/psdk/ntddstor.h`
* `/home/codex/xemu-shader-workbench-handoff/spiritboot-kernel-source/sdk/include/ddk/srb.h`

## Independently owned implementation inputs read

* `patches/roswell/0126-storage-backend-evidence.patch`
* `patches/roswell/0127-independent-storage-primitives.patch`
* `patches/roswell/0129-independent-cache-query-primitive.patch`
* `patches/roswell/0130-independent-geometry-owner-adapter.patch`
* `patches/roswell/0131-independent-cache-publication-primitive.patch`
* `patches/roswell/0132-nxstorage-freestanding-gcc-checks.patch`
* `patches/roswell/0133-independent-zero-domain-mdl.patch`
* `patches/roswell/0134-independent-native-packet-primitive.patch`
* `patches/roswell/0135-independent-sense-header-primitive.patch`
* `tests/host/test_nxstorage_production.py`
* generated owned-only views of `nxstorage/{request,native_packet,sense_header}.{c,h}`
* generated owned-only views of `nxstorage/CMakeLists.txt`,
  `packet_host_platform.h`, `packet_native_platform.h`,
  `native_packet_test.c`, and `check_packet.py`
* `/home/codex/xemu-shader-workbench-handoff/.scratch/nxdisk-approved.ca1Zz8/drivers/storage/class/nxstorage/nxdisk_owner.h`

The native-adapter author supplied the frozen `native_adapter.h` public surface
and exact initial optical configuration in an inter-agent message.  No adapter
implementation body was read.  Repository integration/evidence files inspected
were `scripts/build-firmware.py`, `tools/firmware.py`,
`tools/storage_link_record.py`, `tools/storage_artifact_record.py`,
`.github/workflows/firmware.yml`, and `sources/firmware-lock.json`.

## Non-input checks

Git object/type/status, worktree lists, filenames, hashes and build/test output
were inspected as provenance or verification metadata.  An exact-base Roswell
worktree was created only to attempt patch-context validation; no excluded
source body from that worktree was opened.  The earlier product patch stack is
needed before patch 0126 applies, so that isolated attempt established no
candidate build result.
