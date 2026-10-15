# Complete-candidate storage source and license map

This map binds the storage-class replacement in assembled Roswell tree
`5e427e695c7790966191ed8a0a56b10a441c6ab8` to the exact release64 image
`3a273ba1f213bb2523dddfcf4755071403784f1e25affacef4a4a7b48d47f895`.
It inventories the storage replacement by compiled unit and function group. It
is source-review evidence, not legal advice or a substitute for the final
whole-image provenance review.

## Linked owned implementation

All units in this table declare `SPDX-License-Identifier:
GPL-2.0-or-later`. Patches `0138`, `0139`, and `0140` add the final optical
profile, disk owner, native adapter, and boot driver. Earlier locked patches add
the bounded request, packet, geometry, and cache primitives. The exact linker
input is `libnxstorage.a`, except `geometry_owner_adapter.c`, which is compiled
into the retained GPL PartMgr archive.

| Source unit | Functions or code owned by the unit | SHA-256 |
| --- | --- | --- |
| `request.c` | Request validation and initialization; `nx_start`; command construction; bounded pump; result capture; `nx_lower_done`; `nx_cancel` | `0a151418c7f42fe50be83bf216a0da1862ed8dd931e5d3826e2707078b368b30` |
| `native_packet.c` | MDL/data-range validation; `nx_packet_prepare`; `nx_packet_capture`; owned SRB/IRP field population | `8f278db3fcd78075d56c5154d508c12e57642f05c56be5590399e68f09f4ab35` |
| `native_adapter.c` | Port callbacks; envelope/slot lifetime; child completion and cancellation; adapter initialization/seal/submit; class-device creation; read/write, flush, PnP, and control dispatch | `f33e1b37c9cb2d1c04bb9c69edce5651cb75e9ae122259a30c47ba49e4bff46c` |
| `driver.c` | Status translation; disk object-directory ownership; class creation/seal; owner forwarding; default dispatch; AddDevice; driver installation; public `DiskDriverEntry` and `CdromDriverEntry` | `6c971abfcc8394d1652aa0daead9313c40a2cb2b9f9284e21d269a32fb59da21` |
| `geometry_composer.c` | Public geometry response validation and bounded initialized-prefix composition | `9aa37527ca497180337a58216e11d3b458fe2cec06c484618c62ce756876cfc9` |
| `geometry_owner_adapter.c` | PartMgr basic-geometry query and extended-geometry owner snapshot/composition | `173e60a70d5ca0bb6b4651c70e162a118647c34bb84d3846c89062d1c6a29fc1` |
| `cache_query.c` | Public cache-property query validation and response encoding | `6fbf2d5d76a9cb62eb2d81b3945c5f1d057c7119ab2a54e647cd5b4f64ecfcbf` |
| `cache_property.c` | Generation/ticket state; invalidate/revoke/start/current/publish; raw ATA cache-fact read; public snapshot | `8d6e452bc63f21ba88d33c769bbe364c735b2e9b969dff2f50eb147b43254852` |
| `nxdisk_owner.c` | Driver/device state machine; class identity; configuration checks; disk/optical control routing; read/write/flush admission; stop/seal | `3a411d0468a5c7eb1a5d10299e1e23ba82c14f605c165a8c8df87d174d2b1361` |
| `nxcdrom_profile.c` | Immutable optical class profile and owned runtime-dispatch selection | `ab7a51e240c9e9cac04f6a4830530d0b0a318e5b635f85a7f127d087d593518b` |

The associated owned headers carry the same `GPL-2.0-or-later` identifier.
They define replacement-owned state and narrow public-interface facts; they do
not include `classp.h`, `classpnp.h`, `disk.h`, or `srbhelper.h`.

| Owned header | SHA-256 |
| --- | --- |
| `request.h` | `bd4bbabdbe62de4aad52359eebd39008574e6b284ae557501e31dd4fffcec948` |
| `native_packet.h` | `d70269f48be6dd9dac0c5b5bffd42bf949b24f907b8840d9a48d73972edce5b4` |
| `native_adapter.h` | `9c40be9f1413b5384bb9c92f6e9c41b4190cc467079575b7a149d4a97c321b67` |
| `native_driver.h` | `dc09358c6b54150be850a52360336d0fd9449731af05eaf206f6296ab7c76d0a` |
| `geometry_composer.h` | `f5de15599fbeaf91310347502a31a7eb769a5507ad0db04764cc0ded68ab4b52` |
| `geometry_kernel_api.h` | `ef779611c8b1b53bf1cddc05f9fa543bebff49798c51ddeefd4d11ed3a559cf7` |
| `geometry_target_assertions.h` | `c2f93a36d6087b8a8868925e8dff40e71dc50739ebf9c637324ce5a416db9f68` |
| `geometry_owner_adapter.h` | `8dc2d598b89aff69cc8b4a5e49e6510058cb685499f406b5f9404de63cf84bfd` |
| `cache_query.h` | `9bffbd5d2bd64cc946fe725af0663938e43557d56200217fe6c96642b9b55590` |
| `cache_property.h` | `0cc5ae3fd57f4b299991e71d0f444b4dc4fd21ad278da5cf483140fa2b5b1658` |
| `nxdisk_owner.h` | `d45540ba7d8d867745798bb6af1a9ead563537ae8971dad08b2525876d160f25` |
| `nxcdrom_profile.h` | `43d17c132fcd5ce74c2247117d156f3920c3e1b38d2d294eb83209096576b529` |

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
