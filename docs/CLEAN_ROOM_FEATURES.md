# Independent kernel compatibility work

SpiritBoot's open kernel previously exposed several Xbox APIs without their
required side effects. A fresh implementation agent received a behavior-only
specification, the pinned public Roswell source, and public nxdk declarations.
It did not receive the supplied community firmware, extracted code, disassembly,
or comparison artifacts. A second fresh agent reviewed the resulting source.
This records separation of inputs and context; the shared filesystem does not
enforce that separation, and this document is not a legal certification.

| Feature | What the missing behavior does | Independent implementation |
| --- | --- | --- |
| Shutdown notifications | Lets drivers and titles finish work before a kernel-initiated reset or shutdown. | A stable priority list invokes callbacks outside its lock; duplicates and removal of pending callbacks are handled. The real HAL reset path drains it. |
| Contiguous-memory persistence | Keeps selected physical pages and their contents through warm reset, including title launch data. | An independently designed, validated one-shot handoff reserves selected pages before boot allocation and restores allocator ownership. Free clears persistence. |
| Page locking | Prevents physical pages from moving while a driver or outstanding request uses them. | Nested pin accounting blocks relocation and delays reclaim of pinned movable pages. A pinned contiguous allocation must be unlocked before free is retried. |
| Scatter/gather I/O | Reads into, or writes from, separate memory pages while preserving one request's completion status, event, and APC. | One owned multi-page IRP uses a bounce buffer. Each request captures its own segments and holds pins until completion. This replaces per-page dispatch. |
| IDE channel object | Gives public callbacks access to the active storage request, interrupt, completion, timer, and reset paths. | Public nxdk-compatible fields and mutable callbacks connect to the existing ATAPI driver and share its native interrupt owner. |
| Debugger prompt | Reads a bounded debugger response and returns safely when no input transport is available. | A bounded wrapper uses the existing configured input transport. The tested KDBG=FALSE builds return an empty response promptly. |

Reducing scatter/gather dispatch to one IRP is a structural improvement. No
throughput or game-frame-rate improvement is claimed without measurements.

## Scope and limitations

- The pinned baseline and these builds require the existing 128-MiB xemu
  configuration. Operation on a 64-MiB console is not validated.
- Persisted partial pages survive as whole pages. Adjacent selected pages
  restore as a maximal contiguous run, rather than preserving their original
  allocation boundaries. Integrity checks detect corruption, not deliberate
  replay; there is no independent hardware cold-reset discriminator.
- Pin-count overflow conservatively retains that page until reboot. The VOID
  lock API cannot report refusal of an extra lock, so allowing the page to
  become movable after overflow would be unsafe.
- Public IDE queue fields reflect lifecycle state; they do not expose every
  private ATAPI queued request or its complete retry scheduler. Chaining the
  saved defaults is supported during the corresponding active callback.
- Attached interactive debugger input is wired to the existing transport but
  remains unverified. Other debugger exports and public-key data are outside
  this implementation; no proprietary key blobs were introduced.
- Emergency resets at raised IRQL or with interrupts disabled require a path
  that avoids callback and allocator locks. Ordinary title resets can run the
  notification sequence; emergency resets cannot safely promise normal I/O
  callbacks.
- Ordinary shutdown suppresses normal kernel APCs until reset. Callbacks may
  use synchronous I/O completed by special APCs, but must not wait for a normal
  kernel APC. A nested firmware return unwinds its initiating callback without
  returning to that callsite; the outer reset continues the remaining list.
  Resources need cleanup before that call or through supported SEH cleanup.
- Ordinary shutdown callbacks must not wait for a normal kernel APC: those
  APCs are suppressed through the reset sequence. Special I/O completion APCs
  remain available for synchronous I/O. A callback's nested firmware return
  unwinds that callback and lets the outer action drain the remaining list;
  code after the non-returning call is unreachable.
- Conker: Live & Reloaded gameplay remains untested because no game image was
  supplied. Guest regression success does not establish retail compatibility.

See the [behavior specification](superpowers/specs/2026-10-07-clean-room-kernel-design.md),
[implementation report](clean-room-kernel-task-report.md), and
[independent review](clean-room-kernel-review.md) for implementation details,
reference revisions, tests, and remaining concerns. The build distributes
hashed source patches against the original pinned upstream rather than copying
community firmware code or publishing an unavailable local upstream revision.
