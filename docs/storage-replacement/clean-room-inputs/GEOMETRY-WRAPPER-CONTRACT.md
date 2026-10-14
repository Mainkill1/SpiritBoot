# Independent extended-geometry wrapper requirements

Scope: replace only the retained partition manager's extended-geometry response wrapper from public interface requirements and target-owned partition metadata. This document supplies behavior, not a transcription or decomposition of any existing implementation. It does not approve excluded source files or certify license closure.

## Inputs and required outcomes

The operation is `IOCTL_DISK_GET_DRIVE_GEOMETRY_EX` on the HDD stack above the raw disk class. Input data is not required. Its buffered output contains geometry and 64-bit disk byte length, optionally followed by partition information and detection information. The base response requires 32 bytes on this x86 ABI. Use the public declarations in the package, with actual build size/offset assertions; do not import a private sample response type.

The retained raw-class response is authoritative for media geometry and exact capacity. The retained partition manager is authoritative for the partition-table style and identity it already knows. A successful above-partmgr response must combine those facts consistently without inventing a second partition table or altering disk geometry, partition state, namespace, or layout cache. Missing lower geometry, invalid sector size/capacity, or lower failure must produce an explicit failure; stale values must not be reported as a successful fresh query.

Every returned byte must be initialized. `IoStatus.Information` must describe the response actually made available, remain within the provided output length, and avoid claiming unwritten optional tail bytes. There is no requirement to preserve an old private structure's total size or its exact expression for calculating returned length. The candidate must declare its optional-tail policy and test it against independently observed compatibility before qualification.

If partition information is returned, its public size and style fields are valid, and the applicable identity comes from the current retained metadata: MBR signature/checksum when meaningful; GPT disk identity for GPT; initialized empty identity for RAW or unavailable identity. Do not expose bytes from a different union interpretation. Detection data, when returned, must be valid lower data or an explicitly initialized public no-detection response. A caller that only supplies the base buffer is not required to receive optional records. Do not write a partial public record or leave a gap claimed as returned.

Partition metadata read during an asynchronous or synchronous geometry request must be a consistent snapshot under the retained owner's synchronization contract. Caller buffers, lower requests and device state remain valid until their completion owners release them. The wrapper does not hold an upper partition-state lock over lower submission or waiting without a specific independently reviewed reason.

The class and wrapper must agree on which bytes exist. A class response containing only initialized geometry/capacity may be supplemented with complete fitting public records above partmgr; the wrapper must never infer initialized detection bytes solely from caller buffer capacity. Failed queries do not leak metadata or trigger unexpected disk writes.

## Acceptance cases

| Output/input case | Required result |
| --- | --- |
| 0 or 31 output bytes | BUFFER_TOO_SMALL, zero returned bytes, no output overrun |
| 32 output bytes, valid lower base response | successful base response; correct exact capacity/sector geometry; 32 initialized returned bytes |
| 40 output bytes | base query succeeds; no partially emitted optional record; returned count matches explicitly initialized response |
| enough output for complete partition record | returned public metadata is correct for current partition style; raw geometry unchanged |
| oversized output containing sentinel bytes | no uninitialized or sentinel bytes claimed as returned; no writes beyond output size |
| lower reports failure, malformed geometry, or impossible count | bounded failure, safe status/byte accounting; no success from stale values |
| lower returns base-only data while caller has large buffer | no invented detection tail; only actually initialized response counted |
| lower response includes a valid optional detection record | preserve valid facts and public bounds; avoid corrupting variable record positioning |
| repeated MBR/GPT/RAW metadata queries using deterministic retained-owner doubles | no wrong union bytes, stale identity, allocation leak, or request completion duplication |
| concurrent retained metadata update and geometry query | response uses one consistent owner-approved snapshot; no lock held through an unsafe lower wait |

Exact historical optional-length conventions, checksum absence, and RAW record details remain parity-observation targets. If the candidate chooses a documented correctness improvement, report it explicitly rather than claiming measured parity. Tests must compile the new production wrapper and use independently authored public-interface fixtures; no baseline-body extraction.

Primary public references: [GEOMETRY_EX request](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntdddisk/ni-ntdddisk-ioctl_disk_get_drive_geometry_ex), [geometry response structure](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntdddisk/ns-ntdddisk-_disk_geometry_ex), and [partition information](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntdddisk/ns-ntdddisk-_disk_partition_info).
