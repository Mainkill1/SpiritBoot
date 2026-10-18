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
