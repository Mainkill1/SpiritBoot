# Separate read-only cache query primitive

Specification written before implementation from the newly approved
LOWER-CACHE-QUERY-PROPOSAL.md and CACHE-CAPABILITIES.md. The separately implemented
cache_query.c now uses the approved declaration-only cache ABI packet. The
request engine remains frozen. No lower I/O, ATA execution, interrupt, queue,
cache-setting, worker, allocation or timing behavior belongs to this component.

The future lower glue supplies one consistent by-value capability snapshot:
ATA HDD versus unsupported profile; command-set facts recognized; write-cache
supported and active indications; selected hardware-flush choice known; and the
actual selected opcode or explicit absence. The encoder never reaches into a
private device extension or parses an unapproved IDENTIFY layout. The caller
must obtain a coherent snapshot before calling; a by-value interface prevents
later state changes from producing a mixed reply within the primitive.

Recognized supported cache with active set is Enabled; the same recognized
supported cache with active clear is Disabled. Unrecognized facts, unsupported
cache facts or supported/active contradictions are conservatively Unknown.
None may be converted to Disabled merely because SYNCHRONIZE CACHE returned
success without a command. Flush support is credited only to a known supported
selected hardware opcode (0xE7 or 0xEA), with recognized consistent facts. The
lower glue supplies its actual selector result; the primitive does not guess
selection from partial flags or execute a command. A valid disabled cache can
still have flush capability. Enabled without selected flush is unqualified.

Cache type, changeability and native write-through remain public Unknown. The
read-only query does not claim that caching can be configured, that device FUA
is usable, or that class write-plus-flush is a native single-write capability.
Power-protection and NV-cache fields are conservatively false and give no
durability credit. Reserved/padding bytes in a claimed response are initialized.
Public meanings are documented by [STORAGE_WRITE_CACHE_PROPERTY](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntddstor/ns-ntddstor-_storage_write_cache_property),
[WRITE_CACHE_ENABLE](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntddstor/ne-ntddstor-write_cache_enable),
and [WRITE_THROUGH](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntddstor/ne-ntddstor-write_through).

Supported PropertyExistsQuery succeeds with no response bytes. Standard query
validates the public input minimum, then negotiates a descriptor header for a
short full buffer, and returns the exact full descriptor for sufficient output.
Unsupported query types/properties/profiles fail with zero bytes. Output shorter
than the descriptor header fails with no write. Only claimed response bytes are
written, including for oversized buffers. Buffered input/output aliasing must
work by capturing input fields before emitting output. Null buffers and malformed
metadata receive explicit bounded failures rather than memory access.

The approved CACHE-ABI-FACTS.md/cache-abi-facts packet measures Xbox x86 input
minimum 12, descriptor header 8, full descriptor 28, field offsets and enum
encodings. Four-byte fields use little-endian bytes; BOOLEAN fields occupy
24/25/26 and padding byte 27 is initialized. No native struct overlay is used,
so unaligned buffers work and host pointer/enum sizes cannot alter serialization.
Production names/extents/offsets in cache_query.h converge only where necessary
for the public ABI. Profile/snapshot/status names and validation organization are
independent choices, not target private structures or a copied query handler.

The primary [Win32 STORAGE_WRITE_CACHE_PROPERTY contract](https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ns-winioctl-storage_write_cache_property)
explicitly defines Version as the structure's byte size and Size as total
descriptor data bytes. The measured target structure is 28 with no appended
data, so both fields are 28. The header response also reports 28/28 while its
actual returned byte count is 8. This relies on published field semantics and
measured target layout; it does not import a desktop structure layout.

The public interface takes six uint32_t snapshot fields by value. Profile is
Unknown/ATA/Optical; Boolean facts must be exactly 0/1; selected flush is
None/0xE7/0xEA. Selection-known clear denies flush credit even when a valid
opcode is present. A recognized supported cache yields Enabled/Disabled from
active. Unsupported or contradictory support/active facts yield Unknown and
deny flush credit. A known disabled cache can report selected flush support.
The lower caller is responsible for proving that 0xEA was actually selected
under the necessary LBA48/valid support conditions, rather than passing an
extended support bit as an opcode selection. The encoder has no IDENTIFY input.

Error precedence is a candidate policy: short input, null readable input,
unsupported property/query, malformed snapshot, unsupported profile, Exists,
short standard output, then null writable output. Metadata errors do not write
output; all failure Information is zero. Additional query tail bytes are ignored
for this property after the required 12-byte extent is validated. Exists reports
capability-query availability for ATA with a well-formed snapshot, including
when actual cache state is Unknown. It writes no output and needs no output
pointer. Readable/writable extents and residency are caller responsibilities;
the function touches only the two four-byte query fields and 0/8/28 output bytes.

The result enum maps to native SUCCESS, BUFFER_TOO_SMALL, NOT_SUPPORTED,
INFO_LENGTH_MISMATCH, or INVALID_PARAMETER as documented in cache_query.h. The
pure module deliberately does not require a native NTSTATUS definition. Future
glue must map status and actual result.information to its child/parent IOSB.

Target ABI assertion strategy before glue is admitted:

1. Under the exact native target/compiler flags, include only separately
   reviewed native declarations and compile assertions for sizeof/alignment of
   STORAGE_PROPERTY_QUERY (12/4), STORAGE_DESCRIPTOR_HEADER (8/4), and
   STORAGE_WRITE_CACHE_PROPERTY (28/4). Assert enum and BOOLEAN widths.
2. Assert every encoded field's offsetof/width, query PropertyId/QueryType,
   header Version/Size, public property/query identifiers and relevant enum
   values against cache_query.h and the pinned fact packet. Require zero
   executable text for an assertion-only probe and fail the build on drift.
3. Assert sizeof(ULONG)==4 and the approved target little-endian x86 profile.
   Do not reinterpret native structures inside the pure encoder. Retain native
   header/toolchain identities and compare with ABI-PROBE-RECEIPT.json.
4. The current check-cache-freestanding.sh asserts own constants/offsets and
   fixture enum values against the approved numeric packet only. It does not
   claim that this author's independent clang host/i386 build parsed native
   declarations, proved new helper grants, or qualified a kernel adapter.

IRP/MDL/native device types are not used here. The separately approved native
inventory gives numeric compatibility facts but does not approve actual opaque
native definitions or helper bodies. Future cache glue still needs separately
reviewed native declarations, coherent snapshot/selector capture, cancellation,
lower/device reference and dispatch/control ownership. No lower handler has
been installed and no hardware command is executed by this module.

Acceptance fixtures cover enabled with 0xE7/0xEA, disabled with/without flush,
unrecognized and contradictory facts, enabled without flush, unsupported optical,
unknown hardware selector, minimum/short/exact/oversized output, correct version
and required size, every returned padding byte, input/output aliasing and no
hardware side effects. Qualification remains Unknown/unqualified unless disabled
cache or real enabled-cache synchronization is proved. Passing encoder tests
do not prove that a physical drive flushes or that new lower glue is installed.

tests/cache-query-red.log records 18 intended assertion failures and two
unsupported-path passes against a documented temporary red scaffold. The final
production C passes 20 fixture groups under ASan/UBSan with strict warnings.
Buffer loops exercise every input size 0..11 and output size 0..34, plus exact,
oversized and SIZE_MAX counts, null buffers, unaligned/fully aliased/partially
overlapping buffers, canaries, ignored query tail, malformed Boolean/profile/
opcode boundaries, input/snapshot immutability, native-Unknown/FUA fields and
all returned padding bytes. Literal expected bytes are not generated by the
production encoder or a matching struct overlay. i386 production text is 442
bytes (972-byte ELF), with no unresolved symbols; the numeric assertion object
contains zero text. These are host/freestanding compilation results only.

## Design-only lower glue plan

This plan uses the approved lower cache-capability/proposal facts, public
declaration packet and measured target ABI. No new lower source body was studied
for this plan. The pure encoder is currently unlinked and there is no installed
StorageDeviceWriteCacheProperty handler. ATA submission, cache configuration,
IRQ/queue behavior, discovery and the frozen request engine remain outside scope.

The future compatible MIT lower control boundary handles only the cache property
ID under IOCTL_STORAGE_QUERY_PROPERTY, preserving its other property handlers.
Input/property fields must be captured before any buffered response overwrites
the same SystemBuffer. The glue passes the actual input/output byte extents to
the encoder. It uses ordinary control IRP/lower-device residency and completes
the real control request with the encoder's Information; it must not synthesize
an extra hardware request or infer capability from a successful synchronization.

Capture a consistent snapshot from already retained ATA device/profile,
command-set validity, cache-support/active and negotiated selector facts. The
approved facts identify command-set validity in word 83, cache support in word
82 bit 5 and cache active in word 85 bit 5. Extended flush support is word 83
bit 13 and regular flush support bit 12, under the valid marker. The actual
retained selector prefers 0xEA when negotiated LBA48 and valid extended support
are both true; otherwise valid regular support selects 0xE7; otherwise select
None. Ext-only support without LBA48 yields None. These are snapshot facts,
not an IDENTIFY parser or permission to read an unapproved device layout.

Opcode selection capability must be separate from the cache-active early gate:
the current synchronization path can successfully issue no command for disabled
or unrecognized cache, and can also succeed with enabled cache when no opcode
is selected. A proved disabled cache can still report a real selectable flush
opcode. The query therefore reports recognized supported cache with inactive
clear as Disabled and independently reports known selected E7/EA support.
Unrecognized/unsupported/contradictory cache facts remain Unknown and receive
no flush credit from this conservative encoder, even if other cached opcode
bits are present. Neither no-command success nor FUA flags cleared by the
retained PATA write route justify Enabled/Disabled/Flush/WriteThrough claims.

The snapshot must describe one device state. If retained capability state is
immutable after Start, establish that lifecycle contract and copy the published
record under a live device reference. If it can change, capture all relevant
fields while holding the existing suitable lower lock, then release it before
encoding/completing; use the same lock to publish any refresh. Initialize an
unqualified record before discovery and publish qualification only after the
coherent state is complete. Do not add a healthy per-query allocation, clock,
worker or device command. No particular target lock/IRQL or mutability contract
has been exported, so the concrete capture mechanism remains a glue blocker.

| Pure result | Future native status | Actual Information |
| --- | --- | --- |
| OK/Exists | STATUS_SUCCESS | 0 |
| OK/short full buffer | STATUS_SUCCESS | 8; header Version=Size=28 |
| OK/full buffer | STATUS_SUCCESS | 28; byte 27 initialized |
| INPUT_SHORT | STATUS_BUFFER_TOO_SMALL | 0 |
| UNSUPPORTED | STATUS_NOT_SUPPORTED | 0 |
| OUTPUT_SHORT | STATUS_INFO_LENGTH_MISMATCH | 0 |
| INVALID | STATUS_INVALID_PARAMETER | 0 |

The native status constants must come from separately reviewed native
declarations; the pure result enum's numbers are not NTSTATUS bit patterns.
The assertion-only exact-target build must apply the earlier cache ABI strategy
and verify actual native control lengths/SystemBuffer/IOSB/callback declarations
before glue dereferences them. Current numeric facts alone neither provide the
underlying C type closure nor approve unreviewed inline bodies.

Remaining precise platform facts/declarations: reviewed types for the control
request and current stack plus symbolic native statuses; the actual cached
capability/negotiated-selector field declarations; whether/how those fields
change after Start; suitable existing lock/IRQL and reference/rundown rules
during a query and reset/removal; and the control route's completion/forwarding
ownership contract. No old sample, private helper or complete unknown SDK
header is requested. Acceptance for future glue includes real buffered aliasing,
all descriptor bounds, unknown/contradictory states, disabled-with-selected-flush,
enabled-without-selected-flush, Ext-only-without-LBA48, optical rejection,
coherent capture across allowed state change, reset/removal lifetime, exact
native statuses/Information and zero extra ATA commands. The primitive's current
tests are not evidence that those native glue acceptance cases passed.
