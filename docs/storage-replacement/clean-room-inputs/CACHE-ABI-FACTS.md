# Compiled Xbox x86 cache ABI facts

Measured by a declaration-only cross-compile against the exact composed baseline's generated ntddk.h and public-domain ntddstor.h, 2026-10-14. The current prototype source's 50 source-header dependencies are byte-identical. No SDK helper body or whole unknown header is an author input. The probe emits constants only; its object has zero executable .text bytes. These are ABI observations, not a driver implementation or native runtime test.

`cache-abi-facts.json` and `cache-abi-facts.h` provide the numeric packet. The header uses prefixed constants and contains no function or macro implementation body. Do not substitute desktop Windows layout assumptions.

## Write-cache descriptor

STORAGE_WRITE_CACHE_PROPERTY is **28 bytes, alignment 4**. Its four enums are each 4 bytes; BOOLEAN is 1 byte. Returned padding byte 27 is part of sizeof and must be initialized when 28 bytes are claimed.

| Field | Offset | Size |
| --- | --- | --- |
| Version | 0 | 4 |
| Size | 4 | 4 |
| WriteCacheType | 8 | 4 |
| WriteCacheEnabled | 12 | 4 |
| WriteCacheChangeable | 16 | 4 |
| WriteThroughSupported | 20 | 4 |
| FlushCacheSupported | 24 | 1 |
| UserDefinedPowerProtection | 25 | 1 |
| NVCacheEnabled | 26 | 1 |
| trailing padding | 27 | 1 |

For this fixed descriptor, **Version=28 and Size=28** are public-interface-backed: [Microsoft’s Win32 structure documentation](https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ns-winioctl-storage_write_cache_property) defines Version as structure byte size and Size as total returned data bytes. The DDI page only calls Version a version number; the more explicit Win32 interface description supports the numeric convention. Appending data could change total Size without changing the fixed structure’s Version.

All WRITE_CACHE_TYPE values: Unknown=0, None=1, WriteBack=2, WriteThrough=3. All WRITE_CACHE_ENABLE values: Unknown=0, Disabled=1, Enabled=2. All WRITE_CACHE_CHANGE values: Unknown=0, NotChangeable=1, Changeable=2. All WRITE_THROUGH values: Unknown=0, NotSupported=1, Supported=2. The JSON/header retain the exact public enum identifiers for each value.

## Descriptor/query boundary

STORAGE_DESCRIPTOR_HEADER is **8 bytes, alignment 4**, Version at 0 (4 bytes), Size at 4 (4 bytes).

STORAGE_PROPERTY_QUERY is **12 bytes, alignment 4**. PropertyId is at 0 (4 bytes), QueryType at 4 (4 bytes), AdditionalParameters at 8 (declared array length/size 1), followed by three padding bytes. The two required enum fields occupy an 8-byte prefix, but the composed lower currently validates input against **sizeof=12**. A request supplying only that 8-byte prefix is not accepted by the current lower validation. Use 12 initialized bytes for the no-additional-parameters query, and do not confuse tail-array offset with sizeof.

PropertyStandardQuery=0, PropertyExistsQuery=1, PropertyMaskQuery=2, PropertyQueryMaxDefined=3. Relevant property IDs: StorageDeviceProperty=0, StorageAdapterProperty=1, StorageDeviceWriteCacheProperty=4, StorageAccessAlignmentProperty=6. IOCTL_STORAGE_QUERY_PROPERTY=0x002D1400. These values are interface facts; enumeration presence does not establish lower handler support.

## Probe identity and qualification

Toolchain image: spiritboot-toolchain at sha256:ae07b0897b48d511a166e9892c223118aaac7da21cdbf1f502c36b527b7310ca. Compiler: /usr/bin/i686-w64-mingw32-gcc, GCC 13-win32, i686-w64-mingw32. Definitions/include/ABI flags came from the exact ATAPI ioctl.c build rule; LTO was disabled solely to extract numeric constants from ordinary object data. Actual NTDDI_VERSION=0x05020100, WINVER/_WIN32_WINNT=0x0502, pointer/ULONG/NTSTATUS sizes=4. GCC assembly constants were independently cross-checked against the object's .rdata values.

Source-header hashes and probe/toolchain hashes are in `ABI-PROBE-RECEIPT.json`. Raw source/assembly/object/dependency records remain investigator-only. The packet does not approve transitive source implementations, change supported cache commands, certify physical persistence, or qualify other architectures/build profiles.
