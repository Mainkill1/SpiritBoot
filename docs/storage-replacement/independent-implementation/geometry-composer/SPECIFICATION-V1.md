# Independent geometry composition specification

Frozen before writing the production composer, 2026-10-14.

The function is a synchronous, pure buffer composer. Its lower descriptor
contains a completed status, the address and extent of an independently
obtained extended-geometry base, and the actual initialized byte count.
An owner supplies one immutable partition-metadata snapshot for the call.
There are no lower submissions, waits, locks, writes to disk, allocations,
completion routines, worker threads, or clocks inside this function.

For this candidate, the wire base occupies 32 bytes: public geometry is 24
bytes and exact signed 64-bit byte capacity occupies the next eight bytes.
A public partition record occupies 24 bytes. The Windows x86 public
detection record occupies 56 bytes; its 64-bit members have eight-byte
alignment. The native adapter must assert these public ABI facts.

Outputs of 0 through 31 bytes fail with zero initialized bytes. A valid
32-through-55-byte output receives just the base. A 56-through-111-byte
output receives the base and a complete partition record. An output of at
least 112 bytes also receives a complete, zero-initialized DetectNone record.
All output bytes after the reported prefix retain their prior values.
There are no partial records or claimed gaps.

This is an explicit no-detection candidate policy. Optional lower tail
records are outside the input contract and are not inspected or copied.
The function never fabricates BIOS geometry from media geometry. DetectNone
is an explicit initialized response, not an inference that lower space was
written. Preserving an actual lower detection record is not implemented.

Only status zero is admitted as completed lower success. A status with its
high bit set is returned unchanged as lower failure; a positive nonzero
status is rejected as incomplete or unsupported completion. Short returned
data and counts exceeding the supplied lower extent fail. No lower data
is read after failure. Every failure reports zero initialized bytes and
leaves the caller buffer unchanged.

Candidate validity policy: exact byte capacity must be positive, signed
64-bit representable, and a whole number of sectors. Sector size must be
a power of two from 128 through 65536 inclusive. Tracks per cylinder and
sectors per track must be nonzero; cylinders may be zero but may not be
negative. CHS is preserved, not used to recompute or truncate capacity.
Media type is preserved without imposing a closed enumeration. These are
candidate correctness rules, not measured historical parity.

Snapshot styles are MBR (0), GPT (1), RAW (2), and caller-required Xbox BRFR
(128). MBR signature and checksum
have separate availability flags. Unavailable values are zero. GPT identity
is a 16-byte public GUID memory image when available, otherwise all zeros.
RAW and BRFR identity are always all zeros even if inactive input fields contain
stale values. The output union is cleared before writing its active member.
Other styles and nonboolean availability flags are rejected. BRFR uses its
public custom style value and has no invented MBR/GPT identity. This was
added before implementation following a behavior-only parent message that
the retained Xbox owner currently reports BRFR for its fixed layout.

The lower descriptor and metadata snapshot are stable and readable for the
duration of the call. The output extent is writable. The function takes
local copies before output writes, permitting lower/output aliasing. It
does not establish a coherent owner snapshot: that belongs to the owner's
existing synchronization and lifetime contract. A snapshot taken after
lower completion must be from a still-valid owner/device instance.

The result carries a neutral outcome, exact lower status bits, and the
initialized prefix length. The platform adapter maps neutral outcomes to
its own approved NTSTATUS declarations and preserves lower failures.
No stale cached success can be selected by this API.

Acceptance checks use newly authored literal wire fixtures against the
exact new production source. They cover size boundaries, sentinel guards,
union clearing, metadata availability, invalid status/count/geometry,
lower failure without readable data, exact capacity independent of CHS,
aliasing, repeated style changes, and independent concurrent invocations
using immutable snapshots. These tests prove only the composer boundary;
owner locking and native request completion remain adapter responsibilities.

New approved observation received before implementation: the baseline
public HDD query returns BUFFER_TOO_SMALL at 0/8/24 bytes, SUCCESS with
Information32 at 32 bytes, and SUCCESS with Information40 at 40 bytes.
The candidate's 40-byte query deliberately returns Information32. That
length convention is already a measured parity difference; full-tail
baseline observation was still outstanding when this specification froze.
