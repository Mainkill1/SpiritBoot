# Complete-candidate storage source and license map

This map binds the storage-class replacement in assembled Roswell tree
`abebfef7a717e0379057b5087b8ff71e75279018` to the exact release64 image
`cff12e2cd1b1af1faf0060b676d8ffc37f8256400b12edfe5ad3b2a191943db9`.
It inventories the storage replacement by compiled unit and function group. It
is source-review evidence, not legal advice or a substitute for the final
whole-image provenance review.

## Linked owned implementation

All units in this table declare `SPDX-License-Identifier:
GPL-2.0-or-later`. Patches `0138`, `0139`, `0140`, and `0141` add the final
optical profile, disk owner, native adapter, boot driver, and lower cache
publication integration. Earlier locked patches add the bounded request,
packet, geometry, and cache primitives. The exact class-replacement linker
input is `libnxstorage.a`, except `geometry_owner_adapter.c`, which is compiled
into the retained GPL PartMgr archive. The `nxcache` archive is also linked by
the retained lower ATA driver for the publication endpoint described below.

| Source unit | Functions or code owned by the unit | SHA-256 |
| --- | --- | --- |
| `request.c` | Request validation and initialization; per-request cache classification; `nx_start`; command construction; bounded pump and quarantine; result capture; `nx_lower_done`; `nx_cancel` | `3f60a3991cc2100bf7a699dd4fb1a3d3e61b9518fc6c9df6d2ce8077e1701552` |
| `native_packet.c` | MDL/data-range validation; `nx_packet_prepare`; `nx_packet_capture`; owned SRB/IRP field population | `8f278db3fcd78075d56c5154d508c12e57642f05c56be5590399e68f09f4ab35` |
| `native_adapter.c` | Port callbacks; envelope/slot lifetime; child completion and cancellation; lower cache observation binding; adapter initialization/seal/submit; class-device creation; read/write, flush, PnP, and control dispatch | `56ecfa331699733c159b98f08065246504afbbc0fd9d7149e8270300e609aa1a` |
| `driver.c` | Status translation; disk object-directory ownership; class creation/seal; owner forwarding; default dispatch; AddDevice; driver installation; public `DiskDriverEntry` and `CdromDriverEntry` | `6c971abfcc8394d1652aa0daead9313c40a2cb2b9f9284e21d269a32fb59da21` |
| `geometry_composer.c` | Public geometry response validation and bounded initialized-prefix composition | `9aa37527ca497180337a58216e11d3b458fe2cec06c484618c62ce756876cfc9` |
| `geometry_owner_adapter.c` | PartMgr basic-geometry query and extended-geometry owner snapshot/composition | `173e60a70d5ca0bb6b4651c70e162a118647c34bb84d3846c89062d1c6a29fc1` |
| `cache_query.c` | Public cache-property query validation and response encoding | `6fbf2d5d76a9cb62eb2d81b3945c5f1d057c7119ab2a54e647cd5b4f64ecfcbf` |
| `cache_property.c` | Generation/ticket state; invalidate/revoke/start/current/publish; one-load observation/current check; raw ATA cache-fact read; public snapshot | `e926c962c07f4a531768cc4980a9446f296a17f2b452c0e44d0c7443538f22fb` |
| `nxdisk_owner.c` | Driver/device state machine; class identity; configuration checks; disk/optical control routing; read/write/flush admission; stop/seal | `3a411d0468a5c7eb1a5d10299e1e23ba82c14f605c165a8c8df87d174d2b1361` |
| `nxcdrom_profile.c` | Immutable optical class profile and owned runtime-dispatch selection | `ab7a51e240c9e9cac04f6a4830530d0b0a318e5b635f85a7f127d087d593518b` |

The associated owned headers carry the same `GPL-2.0-or-later` identifier.
They define replacement-owned state and narrow public-interface facts; they do
not include `classp.h`, `classpnp.h`, `disk.h`, or `srbhelper.h`.

| Owned header | SHA-256 |
| --- | --- |
| `request.h` | `4f791f7647270b46feadff138af54ad92f74800b1d863568c80933fd1d00447a` |
| `native_packet.h` | `d70269f48be6dd9dac0c5b5bffd42bf949b24f907b8840d9a48d73972edce5b4` |
| `native_adapter.h` | `9c40be9f1413b5384bb9c92f6e9c41b4190cc467079575b7a149d4a97c321b67` |
| `native_driver.h` | `dc09358c6b54150be850a52360336d0fd9449731af05eaf206f6296ab7c76d0a` |
| `geometry_composer.h` | `f5de15599fbeaf91310347502a31a7eb769a5507ad0db04764cc0ded68ab4b52` |
| `geometry_kernel_api.h` | `ef779611c8b1b53bf1cddc05f9fa543bebff49798c51ddeefd4d11ed3a559cf7` |
| `geometry_target_assertions.h` | `c2f93a36d6087b8a8868925e8dff40e71dc50739ebf9c637324ce5a416db9f68` |
| `geometry_owner_adapter.h` | `8dc2d598b89aff69cc8b4a5e49e6510058cb685499f406b5f9404de63cf84bfd` |
| `cache_query.h` | `9bffbd5d2bd64cc946fe725af0663938e43557d56200217fe6c96642b9b55590` |
| `cache_property.h` | `6aba70dbda7b914ed00116716bf7b80ce710af70625544753185777b7c4a6e0a` |
| `nxdisk_owner.h` | `d45540ba7d8d867745798bb6af1a9ead563537ae8971dad08b2525876d160f25` |
| `nxcdrom_profile.h` | `43d17c132fcd5ce74c2247117d156f3920c3e1b38d2d294eb83209096576b529` |

## Lower ATA cache-publication integration

Patch `0141` carries the independently authored GPL-2.0-or-later publication
adapter into the retained ATA/ATAPI driver. Existing ATA/ATAPI files retain
their MIT notices; the new bridge and include fragments state
GPL-2.0-or-later. The neutral shared ATA request fields are in a dual
GPL-2.0-or-later-or-MIT header. `pciidex.h` retains its existing repository
`COPYING` notice. These hashes are the exact source bytes used by the four
qualified candidate builds. In this table, `nxstorage/*` is relative to
`drivers/storage/class`, `atapi/*` and `pciidex/*` are relative to
`drivers/storage/ide`, and `ata_shared.h` is under
`sdk/include/reactos/drivers/ata`.

| Source | License notice | Publication role | SHA-256 |
| --- | --- | --- | --- |
| `nxstorage/native_capture.inc` | GPL-2.0-or-later | Transaction writer/result capture helpers included by the ATA driver | `c7348e71f7380053dfc1cb2b351a25dc90a575f9a89271158fd9244a503b4952` |
| `nxstorage/native_hook.inc` | GPL-2.0-or-later | Exact lower PDO cache-property endpoint included by the ATA driver | `2c710f4d15a4b8e5f46738be58ea1ef3acdcd601be112645b496e1b06c0ebe45` |
| `atapi/nxcache_bridge.c` | GPL-2.0-or-later | Validated lower-PDO binding to publication state | `fa307ef010b90f57070476f6402b3fca7ec503292483ba585f331f5eabe961d6` |
| `atapi/atapi.h` | MIT | Per-device publication state and worker-result storage | `7d89428478fe8c8c87ac0b78325a23bb4ae65a5f293d6317465f4b2af556bd7a` |
| `atapi/dev_config.c` | MIT | Revoke and republish around device reconfiguration | `1b97f36e058ba5a87f6ac5dab9b9fc8a8c7d4ac72222e7f76a11f60459b715fb` |
| `atapi/dev_identify.c` | MIT | IDENTIFY request classification and coherent publication | `08aeb7293d841e428197cb575196f90928a0ee03b856288f39998d7b8f0c45bf` |
| `atapi/enum.c` | MIT | Enumeration-time invalidation and publication lifetime | `bbcf6507670066f2b673164c8c2d20af69a4a75fbe4855f06238bb29e769aa37` |
| `atapi/ioctl.c` | MIT | Public write-cache-property dispatch route | `6ad47597fbc554f3e5dae3f117f1701b055fa76744b1759de3a0d3b91c7952c1` |
| `atapi/pdo.c` | MIT | PDO initialization and removal revocation | `cf458a99dbba1fd7ec5b1a1ef5d24a01b0cd9b5238d5b425b1bb3a387d436682` |
| `atapi/portstate.c` | MIT | Actual request start and raw terminal-result capture | `a33695eb9d500ad1bd3ae0ad4c9e1ee3c8651f88e7887eec7b4f2cbc6fb5ad7a` |
| `atapi/satl.c` | MIT | Runtime capacity/addressing publication | `c553bbabc6014c7bd7c6fd92d114ad5713b9672e994c93130d1ba40c7ef2bc3a` |
| `atapi/scsi.c` | MIT | Internal request classification and result handoff | `ba3771cee0688589cdfcebccf6d9528a13e69e828a5961ba85e1661004d8fd8b` |
| `atapi/CMakeLists.txt` | repository build metadata | Links `nxcache` and the lower bridge | `9608f67851ee5a7f4962d12c4c53cd1180e373cc265a02d653d982450a15bc93` |
| `pciidex/pciidex.h` | repository `COPYING` notice | Compile-time request layout assertion | `9abad95e00701b9c4545ae5e8008547e8b2f9f0819007654f60fc2bb40ba6105` |
| `ata_shared.h` | GPL-2.0-or-later OR MIT | Neutral request metadata shared by ATA and PCI IDE code | `142d746c4963d69273e8bf93eec1f47529ab9563084bda9caee73d615eb47268` |

## Interface declarations used by the linked units

| Interface source | Terms recorded in the source | Use in the replacement |
| --- | --- | --- |
| generated `sdk/include/ddk/ntddk.h`, from `sdk/include/xdk/ntddk.template.h` | Public-domain notice: “THIS SOFTWARE IS NOT COPYRIGHTED” | Kernel object, IRP, MDL, device, synchronization, allocation, and Zw declarations |
| `sdk/include/ddk/srb.h` | w32api public-domain notice retained in the file | Public `SCSI_REQUEST_BLOCK`, SRB constants, and lower-driver ABI |
| `sdk/include/psdk/ntdddisk.h` | w32api public-domain notice retained in the file | Disk IOCTL values and public geometry structures |
| `sdk/include/psdk/ntddcdrm.h` | w32api public-domain notice retained in the file | CD-ROM IOCTL values and public TOC structures |
| `sdk/include/wine/ntddstor.h` | LGPL-2.1-or-later notice | Storage IOCTL values and public property structures |
| `sdk/lib/drivers/sptilib/*` | MIT notice, copyright Dmitry Borisov | Existing linked SCSI pass-through support library; no identified legacy helper symbol is retained in the final PE |
| GCC runtime | GCC Runtime Library Exception-covered toolchain input, recorded by the build evidence | Compiler support routines used by the complete kernel |

These declarations describe the public binary interface used to talk to the
existing I/O manager and ATA/ATAPI lower driver. The replacement does not call
or wrap the 22 audited `srbhelper.h`/`classpnp.h` helper bodies or the five
audited SCSI helper implementations. The exact-build PE-symbol and owned-source
sentinels report none of those identities.

## Present in corresponding source but absent from the candidate link

| Source | Recorded terms | Disposition |
| --- | --- | --- |
| `drivers/storage/class/classpnp/*` | MS-PL | Historical/reference backend source; `libclasspnp.a` is absent from the complete-candidate expanded link and resolved inputs |
| `drivers/storage/class/disk/*` | MS-PL | Historical/reference backend source; `libdisk.a` is absent from the complete-candidate expanded link and resolved inputs |
| old `drivers/storage/class/nxcdrom/*` | mixed retained implementation dependent on ClassPnP | `libnxcdrom.a` is absent from the complete-candidate expanded link and resolved inputs |
| `nxstorage/packet_srb_declaration.h` | Original w32api public-domain notice retained | Host/declaration fixture input (`4df27f8528d3c94f0d6570b55ce0e596681f9381b69e67c083b00978e6c8ea66`); native production uses `sdk/include/ddk/srb.h` |
| `nxstorage/sense_header.c` and `.h` | GPL-2.0-only | Independently authored source/test primitive (`86abe5be4ca77a27f4a1861ab9285ecefbfdc44a0281892bff860235ba7cbbfb` / `7d27ffcdb74681373894b9c89a4be6440227a47f4e30de117a2f267104c67e2b`); no object from it is present in the exact candidate linker map |

Keeping differently licensed historical source with its notices does not make
it a candidate linker input. The build backend is explicit and fail-closed;
`complete-candidate` rejects the three old class archives and identified
legacy/helper symbols.

## Review conclusion and remaining scope

The identified MS-PL ClassPnP/Disk implementation is replaced at the static
class-driver boundary in this exact candidate. Each new linked storage unit has
an explicit GPL-2.0-or-later grant, and every directly included external
storage interface header has public-domain or LGPL-2.1-or-later terms recorded
above. No incompatible storage helper body identified by the v1.0 audit is a
known candidate input.

The final release gate still needs an independent reviewer to check optimized
inline/data attribution, all transitive whole-kernel inputs, complete
corresponding source and notices, and the accuracy of the authorship records.
This map therefore supports closing the implementation portion of #245 without
making a blanket “100% GPL” or legal-compliance certification.
