# Retained packet preparation hot-path specification

Date: 2026-10-16

## Boundary and evidence

This work studies only SpiritBoot's independently authored `nxstorage` packet
contract, its owned tests, exact release-i386 output, and marker-bounded Steam
Deck profile. No legacy ClassPnP, Disk, or nxcdrom implementation body is an
input. The baseline executed packet preparation 1,024 times in the measured
pass and attributed 371,712 weighted guest instructions to its function range.

## Required behavior

Preparation rejects every malformed resource, command, address extent, page
extent, timeout, alignment, stack, and ownership condition before mutation. A
successful call must:

1. reset the retained child IRP to pending;
2. erase all previous SRB, supplied sense, and next-stack bytes;
3. install the current MDL only for a data command;
4. publish the SCSI dispatch and completion tuple;
5. populate every required SRB field;
6. copy exactly the declared 6, 10, 12, or 16 CDB bytes and leave the rest zero;
7. perform no CDB source read for zero-length RELEASE_QUEUE; and
8. publish a complete immutable completion ticket only after readiness.

Source CDB bytes beyond the declared length are outside the command and must not
be read. SRB and stack objects are native objects whose size and alignment must
be proven compatible with word clearing at compile time. Sense storage remains
byte-aligned and can be separate from the SRB.

## Optimization constraints

Page-count expressions use `uintptr_t`. This preserves the admitted 64-bit host
contract while compiling to 32-bit arithmetic on release i386. The page count
for a nonempty interval is `((offset + bytes - 1) / 4096) + 1` after containment
checks.

Release-target clearing may issue direct word stores for statically proven SRB
and stack layouts. The generic byte clear remains for arbitrary sense storage
and host tests. CDB transfer may select a fixed-size copy only after validation;
it must copy no byte outside that selected extent. The measured common 10-byte
path may receive a branch hint only when exact release disassembly proves the
resulting instruction shape.

## Acceptance checks

- Plain, ASan/UBSan, and MemorySanitizer packet builds pass.
- The zero-length test poisons all 16 source bytes and proves no source-dependent
  destination byte is produced.
- Reuse tests poison every SRB, sense, and stack byte for 1,024 preparations;
  under MemorySanitizer they also poison the source suffix for 6/10/12-byte CDBs.
- A wide oracle covers 4,096 randomized ranges and the exact host edge
  `ByteOffset=4095, ByteCount=UINT32_MAX`, accepting 1,048,577 pages and rejecting
  capacity 1,048,576 without mutation.
- Compile-time native checks prove SRB and stack sizes are multiples of four and
  alignments are at least four.
- Exact release-i386 output contains no division/helper call in the page proof,
  reduces the common 10-byte CDB path, and keeps that path at 11 instructions.
- A repeated host benchmark reports medians and dispersion; paired release-only
  Deck A/B/B/A runs verify exact marker and function-entry integrity.
