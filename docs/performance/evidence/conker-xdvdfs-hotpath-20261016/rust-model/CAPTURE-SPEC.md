# Frozen scalar-capture specification

This behavior specification was frozen before adding the Rust guest-memory
decoder. It describes how a diagnostic stop at the selected release
`XdvdDispatchRead` entry becomes one `RequestFacts` record.

## Binding

- The capture binds an exact final kernel SHA-256, entry address, entry bytes,
  and named structure offsets derived from the same assembled source and
  release disassembly.
- Live entry bytes must match the binding before any record is accepted.
- The decoder reads through a bounded guest-memory interface. An unreadable,
  null, unaligned, wrapped, or non-kernel structure pointer rejects the sample.
- The decoder performs no guest writes and does not infer a missing fact.

## Request extraction

- The second dispatch argument identifies the caller IRP.
- The current stack pointer identifies read length, signed byte offset, flags,
  and file object. The file object identifies an XDVDFS FCB; the FCB supplies
  file start sector and file byte count.
- IRP flags supply paging, associated, and noncached facts.
- A spare lower stack location exists only when `CurrentLocation > 1` and the
  current location is within the declared stack count.
- The MDL must be present. `Next != NULL` marks it chained. Locked or nonpaged
  flags supply the residency fact.
- MDL byte count is copied exactly. The PFN-span fact is true only when the MDL
  header size can contain every PFN required by `ByteOffset + ByteCount` and
  the arithmetic is checked.
- The data address is `MappedSystemVa` when the MDL is mapped or describes
  nonpaged pool; otherwise it is checked `StartVa + ByteOffset`.
- The target device supplies the alignment mask. The dispatch stop is a file
  request; metadata reads require a separate capture boundary and are not
  synthesized by this decoder.

## Failure and output

- One invalid pointer, range, structure relation, or integer conversion fails
  the record with a deterministic reason. A partial record is never emitted.
- Capture tooling retains rejected-sample counts separately from classified
  eligibility. Rejected samples make the trace incomplete and prohibit a
  native optimization decision.
