# PR #248: bounded boot and device dependency review

This source review completes the inspection of the four missing boot seams in
the P0 checklist. It does not complete replacement registration, native boot
qualification, provenance clearance, or the combined persistent-memory gate.
The audit is bound to Roswell base `1569e2e89fb47cc72b9c704a8884f98200432bd4`
with indexed assembled tree `7e891ec86f42b1313e5cd3453347836ac451ba79`.
`SOURCE-BINDING.json` contains file hashes, indexed blob IDs, and inclusive
source-range hashes. Every source file listed in that binding matched its
indexed bytes.

The investigator has inspected legacy implementation and is exposed. This
packet contains original prose, public/kernel declarations and numeric facts,
and source metadata only. It contains no copied implementation bodies, old
code-derived fixture, or instructions for reproducing private class internals.
The root agent must review it before extending the independent author's inputs.
No source or product file was edited, and no build, remote operation or native
test was performed.

## Registration and entry ABI

`IopFoldedInDrivers` has nine entries, in this order: Pci, pciide, atapi,
Disk, Cdrom, partmgr, MountMgr, Xdvdfs, Vfatfs. The first seven are in the
Driver object namespace; the final two are FileSystem objects. RAW is created
before the table. ClassPnP is a linked support library, not an independently
registered table entry. [B01, B03, B44]

Both the table and the fixed-tree header use `PDRIVER_INITIALIZE` rather than a
plain C function pointer. Its declared contract returns `NTSTATUS` and accepts
`DRIVER_OBJECT *` and `UNICODE_STRING *` with `NTAPI`; the common definition
maps `NTAPI` to `__stdcall`. `AddDevice` is also an `NTAPI` function, taking a
driver object and a physical device object. The disk and optical definitions
declare the matching entry convention, and their CMake targets rename the
symbol to `DiskDriverEntry` and `CdromDriverEntry`. These are source declaration
checks, not compiled ABI proof for a future replacement. [B01, B21, B37, B38,
B46, B49, B50]

`IoCreateDriver` publishes the named built-in driver object, supplies a service
path based on the last component of the object name, calls its initializer,
and releases the temporary service-path buffer when initialization returns.
The service path can be absent if its allocation fails. Driver code retaining
that input needs independent storage. Dispatch entries begin as the kernel's
invalid-request handler; null entries left by successful initialization are
repaired to that handler. Folded registration logs each failure and continues,
so reaching the end of the registration loop does not prove every required
driver initialized successfully. [B03, B05]

The Xbox path does not proceed through the registry-driven load-order loop.
Registration precedes fixed-tree enumeration; clearing DriverEntry-time
initialization flags precedes AddDevice/START; boot reinitialization callbacks
run after the enumeration pass. The later Xbox system-driver initializer
returns immediately. [B03, B04, B23, B24]

## Storage attachment and upper/lower boundaries

The hardware table has eleven entries and three driver-bound entries: the PCI
host bridge, AGP bridge and IDE controller. HDD/optical selection is performed
on devices returned by the IDE/ATAPI buses, not by a Disk entry in this top-level
hardware table. The entry pointer is used as an IDE-controller identity during
enumeration; actual attachment resolves the driver name in the object
namespace. The Disk/Cdrom entry declarations in `devtree.c` do not themselves
register those drivers. [B06, B07, B08, B17]

The retained attachment relationships are PCIIDE controller to channel PDO,
ATAPI channel driver to device PDO, then either HDD class plus partmgr or
optical class. The HDD branch starts the class before attaching partmgr;
partmgr then reports partition PDOs that each receive START. The optical
branch receives no partmgr attachment. Both class branches are resolved using
the stable Disk/Cdrom object names. A returned device ID identifying CdRom
selects the optical branch; an absent or unrecognized ID selects the HDD
branch. This is the observed source fallback, not proof that all identification
failure cases produce a correct native topology. [B15, B16]

START and BusRelations requests target the current top of the attached stack,
using its stack depth. Their caller event and result storage remain live while
a pending request completes. Resource-less child starts receive non-null empty
resource lists. The class must leave a usable stack for retained callers; the
boot code does not read a class extension to discover the lower device.
[B14, B15]

There is a repeated-START obligation: the orchestrator starts Disk, then starts
partmgr on the same device stack. Partmgr forwards its START to its lower
device, so the lower class receives another START request. A replacement must
handle that actual caller sequence; one successful initial START alone does
not establish compatibility. This review has not executed either START.
[B16, B57]

Partmgr stores its own extension and lower-device reference. Its startup needs
`IOCTL_STORAGE_GET_DEVICE_NUMBER` from the raw class; its partition refresh
needs raw extended geometry and partition-table reads. Partition objects use
their own extensions and carry the retained device type, stack depth,
alignment, sector size and direct-I/O characteristics. The prototype geometry
adapter changes one partmgr control response; it does not replace the HDD or
optical class lifecycle. The title loader still names CdRom0/default.xbe and
Harddisk0/Partition2/xboxdash.xbe. [B52–B61]

## Boot nodes and private-class assumptions

The requested boot sources directly include kernel interfaces; they do not
include ClassPnP's private header, call a Class helper, or dereference a
ClassPnP/Disk extension. The synthetic PDO has kernel bus-interface metadata;
node allocation associates a kernel `DEVICE_NODE` with the PDO's kernel object
extension. The node flags, instance identity and state-history fields are
standard kernel fields, not an embedded private class layout. The kernel PDO
validity predicate itself checks an associated enumerated device node.
[B09, B13, B18–B22, B39–B42]

Several comments explain these fields in terms of old ClassPnP consumers.
Those comments do not make the fields private implementation. They also do
not prove every field remains necessary after the full class replacement.
Deleting the fabricated nodes or their state bookkeeping requires a separate
retained-caller and compiled-closure review. Existing nodes are promoted to
enumerated/started state before the class AddDevice/START result is known.
Consequently a `DeviceNodeStarted` value is not a native success receipt.
[B13, B15, B19]

The kernel helper declarations in `nx-devtree.h` have no private class
parameter type. They provide fixed-tree iteration, direct PCI configuration
access, node allocation/state updates, root setup and initialization-flag
clearing. No declaration change is established as necessary by this audit.
The header has a C++ linkage boundary; it is still the existing kernel ABI,
not proof of the future replacement's compiled calling convention. [B21, B22]

Two historical explanations need a separate factual correction. Current Xbox
CMake excludes `po/power.c`, the desktop PnP manager and desktop device-interface
code. Phase-0/phase-1 power initialization calls are gated out, and the Xbox
system-driver function no longer traverses the root device. The root node is
still explicitly constructed by the current boot path. Thus “retained power
boot callers require the root PDO” is not supported by this assembled Xbox
composition. This is not authorization to remove the root node, or a finding
that no other compiled/public dependency exists. It narrows the stale comment
and CALLER-MATRIX explanation only. [B04, B20, B23, B25, B26, B30–B33]

The comments about device-node instance paths enabling desktop device-interface
and registry operations also overstate the current Xbox surface. Those desktop
implementation files are excluded, and partmgr's interface registration is
gated out. The audit keeps the published node identity contract and does not
use these comments as evidence of required private-helper reuse. [B31, B32,
B54]

## Initialization lifetime and memory limits

Seven driver names are sealed before initialization code is discarded: Pci,
pciide, atapi, Disk, Cdrom, partmgr and NxkBus. Their PnP dispatch is changed
to a resident invalid-request handler and their AddDevice pointer is cleared.
PCIIDE first closes/drains its protected boot PnP admission. The new class
must therefore finish required boot work before this boundary, retain its
runtime I/O/completion code, and introduce no pointer that can reach discarded
initialization code afterward. Source names in the registry, clear-list and
seal-list agree for Disk and Cdrom. The clear-list also contains a stale Cdfs
lookup; Cdfs is not in the actual folded registry. [B01, B02, B17, B27]

The source explicitly retains some boot resource allocations because drivers
can keep their addresses. Nodes, identity strings, synthetic PDOs, driver
objects and bus metadata also have persistent ownership. Table/resource
descriptors are assigned discardable data sections. These facts identify
allocation/lifetime categories; they do not establish linked section placement,
resident bytes, allocation high-water, leak freedom or the final candidate's
memory delta. No storage-specific native persistent/peak measurement was
created here. [B01, B07, B09, B13, B15, B17, B19, B20, B27]

## Present composition and narrow gate conclusion

The legacy-reference and partial-lab-prototype compositions still link Disk,
ClassPnP and the ClassPnP-dependent optical source. Both HDD and optical entries
call `ClassInitialize`; the optical source includes the private class header
and declares a matching class-extension layout/version requirement. The pure
nxstorage library currently has no driver registration body. The full-candidate
path refuses configuration without `nxstorage/driver.c`; its omission of the
old archives is not evidence that the currently retained optical implementation
has become independent. No complete candidate was built in this audit.
[B29, B43–B51]

The checklist's narrow P0 boot-file inspection can now be marked complete,
with this receipt: folded table declarations, names/order, entry calling
convention, three Xbox boot files/header, node assumptions and sealing are
reviewed. The caller/device matrix's boot subset can be supplemented with the
two factual corrections and repeated-START constraint above. The broad P0
dependency-plus-persistent-footprint item remains open where it requires actual
compiled/native attribution and allocation evidence. P3 replacement registration,
final device namespace, AddDevice/START outcomes, resident callback lifetime,
full class independence, P1 calibration and P4/P5 remain open.

Unknown native behavior includes failure handling at registration/ID query,
all lower/upper AddDevice/START outcomes, partition discovery/mount results,
post-seal PnP completion, hot removal/reset/rundown, storage allocation peaks,
and complete-candidate entry ABI/INIT layout. Source review cannot close them.
