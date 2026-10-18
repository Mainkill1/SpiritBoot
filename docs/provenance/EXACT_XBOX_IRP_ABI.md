# Exact Xbox IRP ABI and lifetime

## Question

Why did the selected SpiritBoot storage candidate crash early in Project Gotham
Racing 2 and fail to improve Forza world streaming, and what must the kernel
preserve when it builds and completes Xbox I/O request packets?

## Rejected candidate

The 64 MiB release candidate assembled through patch 0168 was rejected on
2026-10-18. Human title testing observed an early PGR2 crash and no material
Forza improvement. That result is a compatibility failure and is not accepted
as performance evidence for the replacement below.

The selected source had widened the title-visible Xbox `IRP` from 0x68 to 0x80
bytes so it could retain NT bookkeeping fields. `IoGetNextIrpStackLocation`
therefore placed the first public stack at +0x80 instead of the Xbox ABI's
+0x68. Public FSD builders also exposed SpiritBoot's internal buffered/direct
state rather than the packet shapes returned by the reference kernel. The
storage pipeline then consumed and completed packets whose public layout and
ownership rules differed from what titles and Xbox drivers expect.

Review of the lifetime paths found related defects that had to be corrected as
one port rather than hidden with extra polling or queue delays:

- `STATUS_MORE_PROCESSING_REQUIRED` could discard hidden state that the resumed
  completion still owned.
- The associated-IRP union did not retain which member was active, so a system
  buffer, master IRP, or child count could be interpreted as another member.
- Raw caller-owned packets did not preserve APC environment and packet
  generation across queued completion and rundown.
- Cancellation and thread-loss cleanup could leave pinned pages or privately
  owned buffers behind.
- The per-CPU MDL lookaside was initialized with the small-IRP element size
  instead of the MDL element size.
- Whole-page IRP allocations could not be recovered safely from their public
  interior pointer.

These are demonstrated causes in code and executable fixtures. The title
symptoms alone do not prove which defect fired in a particular frame.

## Reference observation

The behavior probe is an original XBE that observes public results only. It was
run against Complex 4627 with a pinned release xemu. The XISO SHA-256 is
`16ddd9e4995eaa630e28b2a596af1a139c88639249a2d9de7bff7d6cb34d7160`;
the xemu SHA-256 is
`5488be40bf3c1c444b507d084c8d964f8f7d73c2a912970495cf85a4f7239564`.

| Device mode | `UserBuffer` | `SegmentArray` | `LockedBufferLength` | public `Flags` |
|---|---|---:|---:|---:|
| neither | caller buffer | null | 0 | 0 |
| buffered | caller buffer | null | 0x200 | 0x200 |
| direct | caller buffer | null | 0 | 0 |

The three assertions passed in a 636-test TAP run. The result contained 634
ordinary passes and two expected xemu TCG floating-point TODO results. Its
serial SHA-256 is
`2bec41abfe3253f6867e587940e5a8900d90bc8e45167ed9ee7e8ae7bf8e42b1`.
Running old and current probes across old and current xemu binaries produced
byte-identical observations for matching probes, ruling out the emulator
revision as the source of the public-shape difference.

## Implementation

Patch `0177-exact-xbox-irp-abi.patch` restores the public `IRP` to 0x68 bytes
and places the public stack immediately after it. It separates Xbox public
flags from internal NT state. Kernel-allocated packets store private state in
an 80-byte prefix; raw caller-owned packets use a keyed, locked sidecar. The
normal `IofCallDriver` path does not allocate a sidecar.

Public exported builders now reproduce the observed three-mode shapes. The
buffered path pins and lends the caller's buffer without a bounce allocation or
copy. The direct path keeps the title-visible fields exact while storing its MDL
privately. Zero-length direct requests retain that public shape without creating
or probing an invalid zero-length MDL. Completion snapshots and detaches hidden
state before publishing a user event. APC delivery and rundown hold the exact
sidecar generation, and MORE retains the state required for recompletion. FATX,
XDVDFS, nxstorage, and the dormant legacy storage consumers use the private
accessors rather than removed public tail fields.

This removes a buffer allocation and copy from every public buffered transfer.
It also avoids adding an allocation to the ordinary raw-call hot path. Those are
code-path improvements; title-level load-speed claims require the automated
release gates below.

## Regression evidence

The patch carries executable host gates for:

- exact 0x68 ABI, stack offset, fields, flags, and builder route;
- public direct/buffered/neither builders, including zero-length direct I/O and
  five rejected mutants;
- every equal-bit collision between the Xbox public flags and private NT
  bookkeeping flags;
- a byte-exact 257-byte buffered write/media/read completion round trip;
- owned allocation/free provenance for stack counts 0, 1, 2, 3, 4, 8, and 9;
- caller-owned sidecar creation, reuse, MORE, and concurrent lifecycle stress;
- APC completion, delivery, and rundown with exact-once IRP, sidecar, MDL, and
  buffer release;
- special paging, mount, and close completion;
- storage-source access to removed public fields;
- tagged interior-pointer recovery for small, large-lookaside, and whole-page
  allocations.

The source also carries a two-process cold-storage XBE. Its authoring phase
alternates 50 noncached writes across a deterministic 2 MiB payload and spacer,
flushes and closes them, commits a checksummed manifest last, and flushes the
volume. A separate cold process reopens the files, checks exact length and every
byte through synchronous and event-completed reads, and requires at least one
pending completion. Its serial grader refuses either phase in isolation.

The existing FATX asynchronous/EOF, XDVDFS forwarding/completion, nxstorage,
thread-view, and pool tests are also part of the release source gate. CI builds
the attributed assembled tree and runs these tests from that tree. The final
64 MiB image is accepted only after fresh, unattended release-xemu runs pass
PGR2 race continuity, the Forza R-class world-stream score, two Halo 2 menu
boots, and DOA save creation/reload using the exact retained HDD.

## Final release64 qualification

The candidate qualified on 2026-10-18 with firmware SHA-256
`75f0680d7a32e8264c3f496eb48c071bd4a9fe8b7e9285e59461f6e35f194f4e`
from assembled source tree `067841f59e485858a1a00059184f1b29eeec5d7a`.
All runs used release xemu `5488be40bf3c1c444b507d084c8d964f8f7d73c2a912970495cf85a4f7239564`,
64 MiB, a fresh process, private HDD state, and no manual input.

- PGR2 create run `20261018-224154536-f2ff3c2a1a7c4f149043dfb453e9e1a2`
  wrote 421,888 bytes in 28 operations. Its exact retained HDD, SHA-256
  `bfbf46e580a4c05e487e3a255e795532455ad7bb3e22fd5e7cff23e0ec1714aa`,
  cold-reloaded in run `20261018-224414626-937978818dc8414880168a7bef146dd5`.
  OCR proved the existing `Player` profile prompt and the run reached a changing
  25-second race window without profile or I/O errors.
- DOA create run `20261018-224750103-794c4262e4fe4756bc08d8d403448ec5`
  wrote 83,546,112 bytes in 5,100 operations. Its exact retained HDD, SHA-256
  `3299219d120de922087df12125e19c40ca124792f936e7a3e0aab0f2acc9de70`,
  cold-reloaded in run `20261018-225019720-5a138068e6a147b0b9716a0a0a00edd8`
  without damaged-save text.
- Forza run `20261018-222750891-ff3f84f9218d44208b571e43c927058f`
  observed 4,362 reads / 54,033,408 bytes with no invalid read, waited 10.357
  seconds for race readiness, reached 100 mph, and moved 33.81 minimap pixels.
- Halo 2 runs `20261018-223143529-98f9faea71d94f63bb56cac93f6e6d4b`
  and `20261018-223332923-7f93745462aa45e8a3e354fbb4b0e5fe`
  independently showed Campaign and Settings over three stable observations.
- Cold-storage XBE runs `20261018-225211542-d198a34978954edb8c731c8779693d10`
  and `20261018-225222038-747a3ffad17a40aa820af9dca19e6cbe`
  persisted and re-read all 2,097,152 bytes; both runner correctness contracts
  and the serial grader passed.

An earlier PGR2 result with uncertain profile provenance is excluded. The final
route starts from the pinned clean seed, proves every profile-creation screen
and positive HDD writes, imports only that runner-retained image, and binds each
reload input to an observed menu state before the race can begin.

## Limits

The public reference observations specify layout and builder behavior, not the
reference kernel's private implementation. SpiritBoot's prefix and sidecar are
independent mechanisms chosen to preserve those observations and enforce clear
ownership. A caller that frees a packet after MORE without completing,
reinitializing, or reusing it violates the supported packet lifecycle.

Game profiles are also firmware/EEPROM key-domain inputs. A save created under
Complex is not a valid SpiritBoot persistence oracle. PGR2 and DOA gates must
author a fresh private HDD with the exact candidate and EEPROM, terminate xemu,
then cold-reload that same pair and reject damaged/corrupt-profile text before
claiming a pass.
