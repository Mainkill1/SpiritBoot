# Geometry integration anchors

Facts only, 2026-10-14. These names and source coordinates identify integration/exclusion points; they do not supply the old body, private declaration or a response algorithm. Coordinates are for the composed baseline; a future staging tree may move them.

| Anchor | Baseline coordinate | Ownership / scope |
| --- | --- | --- |
| Retained enclosing dispatch, `PartMgrDeviceControl` | `drivers/storage/partmgr/partmgr.c:1251` | owns final status assignment and the one upper-IRP completion for locally handled control requests |
| Extended-geometry control dispatch entry | `drivers/storage/partmgr/partmgr.c:1272` | calls a local status-returning handler using owner extension and upper IRP; the fresh adapter can satisfy that interface under a new name |
| Old local handler, `FdoIoctlDiskGetDriveGeometryEx` | `drivers/storage/partmgr/partmgr.c:465` | old implementation body stays excluded from fresh author inputs and must be excluded from the complete backend if replaced independently |
| Old private type, `DISK_GEOMETRY_EX_INTERNAL` | `drivers/storage/partmgr/partmgr.h:26` | not a needed ABI; omitted from the scoped approved header copy; exclude from complete-backend author inputs/use; standard public declarations and checked numeric facts supply the response shapes |
| Existing status-only lower-query interface, `IssueSyncIoControlRequest` | `drivers/storage/partmgr/utils.c:19` | declaration is public to the retained owner; behavior lacks returned byte count; old body is not approved as author reference |

The fresh adapter owns its lower child query and owner snapshot lifetime, and supplies final status and bounded Information to the enclosing dispatch. It does not complete the upper IRP. The enclosing dispatch continues to own completion exactly once. No change to the partition offset/namespace/layout enumeration contract is implied by these anchors.

The independently authored sized-query/composer adapter is a bounded geometry cleanup task. A complete storage backend still requires separate actual class/lower link, native behavior, ownership, source-grant and notice qualification. Excluding this single old wrapper does not establish whole-candidate closure.
