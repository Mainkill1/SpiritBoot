# Minimal future platform inputs

No platform adapter or owner synchronization code is implemented here.
The parent has held adapter expansion while the native A/A baseline freeze
remains incomplete. This document describes the future boundary only.

The retained adapter would supply:

1. A completed lower query's exact status bits, a readable base-response
   address and its actual supplied extent, and the actual returned initialized
   count. The base must contain public geometry followed by exact byte length.
   Its lifetime covers the composer call. If geometry and length were obtained
   separately, the adapter must validate both completed statuses and returned
   sizes before constructing a fresh base. There is no cached-success input.
2. One owner-approved immutable metadata snapshot: current style; separate
   availability and value for the MBR signature and MBR checksum; and the
   16-byte public GUID memory image and availability for GPT. RAW and BRFR
   have no identity payload. No private owner types cross this boundary.
3. The writable caller output address and the actual output capacity.

The owner establishes snapshot consistency using its existing synchronization
and lifetime contract. The composer assumes that has already happened.
It neither holds a lock through a lower query nor owns lower completion.
Concurrent host calls with independently stable snapshots do not validate
retained-owner update/query synchronization or native request lifetime.

Before any linked native use, the adapter must assert actual target-header
sizes and offsets: sizeof(DISK_GEOMETRY)==24; DISK_GEOMETRY_EX DiskSize at 24
and Data at 32; sizeof(DISK_PARTITION_INFO)==24 and its union at 8; public
DISK_INT13_INFO size 16, DISK_EX_INT13_INFO size 32 with ExSectorsPerDrive at 16;
DISK_DETECTION_INFO size 56 with its ExInt13 member at 24. The standalone
checks model Windows x86 eight-byte integer alignment; they do not prove
the retained build uses those exact types or packing. A disagreement blocks
integration until the ABI is independently settled.

The result is a neutral outcome plus the unchanged lower status bits and
initialized prefix count. The platform maps the outcome using approved
NTSTATUS declarations. Lower failures must keep their exact status; no
incomplete lower status may become a successful geometry response. Other
candidate mappings can use the published geometry-request status family,
but exact historical error choices remain unmeasured. Information must be
the result's initialized_bytes, which is zero on every failure.

The revised composer matches admitted native returned counts at output
32/40/56/64/112/128/256. It returns min(caller capacity, 112), clears every
reported byte, and emits only complete fitting meaningful records. Short
optional tails are unavailable padding; their size field is zero when the
whole field fits. A zero partition size is an observed convention rather
than the documented valid public structure size. Future consumers must
honor both returned bounds and the record size before reading metadata.

Native integration still needs identity/checksum availability, BRFR caller
mapping, full detection-byte expectations, and unmeasured boundary queries.
DetectNone remains a declared policy choice and does not preserve a real
lower BIOS detection record. Native boot/partition behavior and full parity
have not been qualified. No native adapter exists in this package.
