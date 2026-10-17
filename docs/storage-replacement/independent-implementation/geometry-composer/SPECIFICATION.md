# Independent geometry composition specification

Revision 2 frozen before changing production prefix behavior, 2026-10-14.
The original complete-record-prefix policy is preserved in SPECIFICATION-V1.md.
This revision follows newly admitted behavior-only native observations; no
reference implementation or old tests were consulted.

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

Outputs of 0 through 31 bytes fail with zero initialized bytes. Every
successful call reports the smaller of caller capacity and 112 bytes. The
base occupies the first 32 bytes. Remaining reported bytes are deliberately
cleared before any optional record is emitted. A complete partition record
is emitted only with at least 56 bytes of caller capacity. A complete
DetectNone record is emitted only with at least 112 bytes. A smaller optional
tail is cleared unavailable padding; it never holds a truncated identity or
BIOS parameter payload. Every byte after the reported prefix retains its
prior value, including oversized outputs beyond 112.

For capacity 32 there is no optional tail. For capacities 33 through 55, only
cleared padding follows the base. When at least 36 bytes fit, the complete
partition size field is zero, which is the observed unavailable convention;
for 33 through 35 even this size field is incomplete and must not be read.
For capacities 56 through 111, a complete partition record is followed by
cleared unavailable detection padding. From 60 bytes onward its complete
size field is zero; below 60 there is no complete detection size field.
No cleared prefix of a missing optional record is advertised as a valid
public record. The only emitted meaningful record sizes are 24 and 56.

The published partition interface requires its size field to equal the
structure size. Thus a zero size is an observed compatibility convention
for unavailable padding, not a documented valid DISK_PARTITION_INFO.
Consumers still must honor the returned extent and record size before
reading a payload. This inconsistency is retained explicitly to match the
observed prefix counts without exposing partial metadata.

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

The initial approved observation established BUFFER_TOO_SMALL at 0/8/24
and SUCCESS/Information 32 at 32 and SUCCESS/Information 40 at 40. The first
candidate deliberately reported 32 at 40; that earlier mismatch is superseded
by this revision rather than being presented as measured parity.

The new parent-supplied whole-HDD GEOMETRY_EX observations from both rigs are:

| Caller output bytes | Reported initialized bytes | Observed optional partition header |
| --- | --- | --- |
| 32 | 32 | No tail |
| 40 | 40 | Size 0/style 0 |
| 56 | 56 | Size 24/style 0 |
| 64 | 64 | Size 24/style 0 |
| 112 | 112 | Size 24/style 0 |
| 128 | 112 | Size 24/style 0 |
| 256 | 112 | Size 24/style 0 |

Only these returned counts and partition-header facts were admitted. Native
raw files were not opened. Full detection bytes and all identities remain
unqualified. The candidate keeps owner-provided style and metadata rather
than assuming that native observed style 0 settles the BRFR owner mapping.
The declared policy at 33/39/41/55/63/111 is independently tested but has not
been natively observed. Tests preserve lower-status/count/geometry rejection,
aliasing, union clearing, and independently stable snapshot concurrency.
