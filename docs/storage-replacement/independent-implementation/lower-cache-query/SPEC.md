# Candidate-only read-only lower cache-property hook

Specification written before new glue code. Scope is a compatible ATA HDD cache
property extension calling the frozen nx_cache_query_encode. The request core
and encoder remain byte-identical. No property handler is currently installed;
root must gate any integration to LAB/CANDIDATE so released legacy ROM behavior
and bytes remain unchanged. There is no hardware/cache-setting/queue/IRQ change.

The initial specification and investigation updates retain their chronology.
The final section, "Corrected approved implementation contract", supersedes
pending-fact and tentative representation statements after receipt of the
approved manifest44 packet. INTEGRATION.md states final call-site requirements
and native qualification limits.

Approved source inspection found the PDO storage property route validates 12
input bytes, handles existing device/alignment/seek/trim IDs, and forwards other
IDs to the FDO. Its device-control owner acquires a remove lock, invokes the
property handler, sets status, completes the parent once, then releases the
remove lock with the saved IRP tag. The new cache case must clear ForwardToFdo,
write actual Information for every result (including zero errors/Exists), and
return status to that existing owner. The hook must not call IoCompleteRequest,
forward the IRP, queue it, or access parent/device/buffer after owner completion.
The retained owner's device epilogue remains protected by its remove lock; it
is not newly claimed to be free of all post-completion device access.

The device extension contains a 512-byte IdentifyDeviceData/IdentifyPacketData
union, Device.DeviceFlags (DEVICE_LBA48=4) and DeviceType. Transitive ATA type/
identify helper definitions are unapproved. Necessary narrow field/declaration
facts and cache producer/selector synchronization were requested, without helper
bodies. The original CACHE-CAPABILITIES supplied word82 support bit5, word85
active bit5, word83 validity/regular bit12/extended bit13 and E7/EA selector.
Investigator subsequently corrected that validity fact before functional code:
actual retained cache/flush predicates use CommandSetSupport.WordValid at word84
bits14..15. WordValid83 at word83 independently governs LBA48 negotiation.
Exact corrected declaration-object proof/packet is pending. Draft raw fixtures
now distinguish those facts and do not impose a public-standard word83 gate on
the actual retained cache/flush route.

Important observed mutation: the still-supported Xbox READ CAPACITY path builds
an IDENTIFY whose data destination is the cached union. Device.QueueLock does
not by itself stop DMA writes. Direct multi-field reads or two matching software
reads cannot establish coherence during hardware overwrite. The native glue
must receive one copied coherent view under an explicitly proved producer
contract: either snapshot only after discovery/refresh terminal completion while
no IDENTIFY writer runs, or a device-owned published copy invalidated before any
refresh and atomically republished after a complete successful refresh. Unknown
publication must remain Unknown. No direct unsynchronized read of that union
will be presented as native-ready.

The bounded production glue's platform boundary will copy one by-value raw view
containing profile, validity/support/active words and negotiated flags under its
caller-supplied coherence/lifetime contract. Native input/length/IOSB operations
come through narrow approved interface declarations, never a guessed opaque
IRP/MDL offset. The hook consumes the copy once and must not reach back into the
device after it begins encoding. Copied cache/selector facts are decoded without
calling an unapproved inline helper, executing an ATA command or crediting FUA.

The selector capability is independent of cache-active early success: valid
negotiated LBA48 plus valid extended support selects EA; otherwise valid regular
support selects E7; otherwise None. Ext-only without LBA48 is None. The retained
sync path can report success without any command for cache unrecognized/disabled
or for enabled cache with no selected opcode. The query never uses such success
as a source of facts. Optical returns NotSupported; invalid/contradictory cache
state remains public Unknown and receives no flush credit.

The encoder negotiates 12/8/28, initializes padding, supports aliased buffers,
and returns 0/8/28 bytes. Pure result status maps to native SUCCESS,
BUFFER_TOO_SMALL, NOT_SUPPORTED, INFO_LENGTH_MISMATCH, INVALID_PARAMETER. Source
calls native symbolic status names; their target scalar facts/actual target
declaration assertions must be supplied before native qualification. No heap,
worker, clock or per-request probe is introduced.

Tests will execute actual new production glue linked to the frozen encoder,
using independently authored lower/control-request/public-type doubles. They
must cover enabled/disabled/unrecognized/contradictory, E7/EA/None and Ext-only
without LBA48, optical, all input/output boundaries, Exists, aliasing, coherent
copied state versus later mutation, exactly one owner completion, zero device/
buffer access after completion, and no command/configuration/queue/IRQ activity.
Literal output/status expectations do not reimplement the production decoder.
The exact native ABI/producer contract and native P1 are separate gates.

The independent publication representation is one lock-free atomic uint32_t,
owned by the device. Initialize it with the profile and no qualification;
invalidate immediately before the actual cached-buffer hardware write starts
by retaining only the profile; publish an entire decoded raw view in one
release store after successful coherent terminal capture and addressing update,
before a successor writer can start. Query uses one acquire load. Every
published combination is indivisible and query never touches the DMA
destination. Publication is restricted to one serialized producer per device;
terminal failure leaves Unknown. All producer/lifetime operations require a
live lower-device reference. The producer must also cover discovery/reset/
negotiation changes and invalidate before changing any fact. This lifecycle
interface is independently designed; native producer wiring is not yet frozen.

Investigator's preliminary behavior-only message confirms that generic terminal
processing invokes translation completion under Device.QueueLock and may start
the successor before the old parent's IoCompleteRequest. Multiple refresh
requests may already be built/queued. Consequently invalidating only during
command construction, or publishing during old-parent completion, is insufficient.
Exact start/terminal/mutator anchors and declarations await the approved packet.

Own additional permitted source reads confirm that the visible READ CAPACITY
translation callback invokes the addressing update before formatting capacity.
It does not establish full successful IDENTIFY by itself. New publication must
independently reject failed/short/unproved transfer completion; an initially
assigned 512-byte transfer length is not sufficient byte-completion evidence.
The exact target success/transfer contract has been requested from investigator.
Future raw capture should use reviewed field/offset facts and character-byte
loads into the owned raw view, avoiding aliasing a native structure as an
unrelated USHORT array. No such capture body exists before those facts arrive.

Further preliminary investigator facts: translation can rewrite both raw
SrbStatus and DataTransferLength, so preserve writer classification and the
raw successful lower completion fact before invoking translation. Publish only
after addressing update, before successor start. Counted PIO success requires
BytesToTransfer==0 plus BUSY/DRQ clear and no ERROR/DEVICE_FAULT; raw requested
512 plus that success proves consumption. DMA controller/descriptor success has
no independent actual-byte counter and must be labeled an inferred lower
completion contract, not measured bytes. Initial/re-enumeration and post-config
copies plus PDO zeroing are additional producer/mutation boundaries. Exact
packet/anchor validation remains pending; these messages do not approve bodies.

Native hook code will use a conditional newly owned NxCacheQueryState member,
the already exposed SystemBuffer/input/output/Information interface fields,
and native symbolic statuses. It performs no parent completion. Host doubles
exercise the same hook; they are independent logical declarations, not an
attempt to reconstruct native IRP/device layout. Exact native compiler/field
assertions remain necessary. The raw-view validity-marker draft tests need the
requested target semantic clarification before final implementation evidence.

## Corrected approved implementation contract

Manifest44's ATA-CACHE-GLUE-FACTS/ata-cache-abi-facts and zero-text receipt now
establish word84 marker value1, exact512-byte/unaligned native IDENTIFY layout,
raw word offsets, every observed writer, real-start and pre/post-translation
anchors, PIO/DMA evidence distinction and lock-free four-byte compiler atomics.
The supplemental STATUS_NOT_SUPPORTED fact is also supplied. No whole helper,
ATA/native header or unlisted source body is approved by this packet.

New metadata is fixed device state (one uint32) plus one fixed request-owned
writer marker and copied terminal result. The marker retains destination class
Cached/Local, original IDENTIFY opcode and qualifying512-byte extent before
DataBuffer mapping; actual start captures final transfer path/proof and advances
the device epoch. Recognized starts invalidate even when their extent/proof is
unqualified. Foreign/data commands do not invalidate. Raw result status/count
are copied before translation and request reuse. Local results are not published
until the fresh identity was copied and its profile/flags are consistent.

The independently chosen atomic representation combines profile/cache/selected
opcode/proof bits with a23-bit generation. Begin/revoke clears qualification and
advances the generation; successful publish uses one CAS matching the exact
unknown token. Duplicate or older terminal events cannot replace a newer record.
Only8,388,606 writer generations are issued per resident device; exhaustion
reserves a poison epoch and never wraps. Mutation CAS retries are bounded16;
contention exhaustion closes qualification until object recreation. Query takes
one acquire load and writes via the frozen encoder. All accesses use compatible
compiler atomic builtins, without SDK atomic helper bodies/libatomic.

Counted PIO and controller-inferred DMA proof are separate publication tags.
Neither tag is physical durability evidence. Unknown/pending/error/short raw
results cannot publish; an initially512-byte request alone is insufficient.
Result-current checks prevent obsolete native producers from attempting raw
capture, but are not a hardware/serialization lock: the source-owned producer
must still prevent another writer/flag mutation during character-byte capture
and CAS. Queries never read raw data. Device/request rundown and external
producer serialization remain explicit platform preconditions.
