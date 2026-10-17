# Narrow retained-owner geometry adapter specification

Frozen before production adapter behavior, 2026-10-14. Composer source/header
remain pinned at 9aa37527ca497180337a58216e11d3b458fe2cec06c484618c62ce756876cfc9
and f5de15599fbeaf91310347502a31a7eb769a5507ad0db04764cc0ded68ab4b52.

The new ordinary C entrypoint returns NTSTATUS and accepts PFDO_EXTENSION
and PIRP. Approved platform declarations precede the adapter translation
unit. No unfiltered target header or unknown inline helper is included.
The enclosing dispatch alone writes the upper final status and completes it.
The adapter starts Information at zero, writes it only after successful
composition, and never completes or frees an upper or synchronous child IRP.

It rejects missing owner/stack/buffer arguments and outputs below 32 before
submitting a query. Under the owner's synchronization event it copies the
lower device, exact capacity, sector size, style, and applicable identity.
It requires LayoutValid and a nonnull LayoutCache, but never dereferences or
retains the cache pointer. MBR/GPT/RAW and the frozen composer's explicit
custom BRFR policy are preserved without relabeling. The owner checksum is
unavailable and is explicitly zero. The actual FATX owner is MBR 0 with
signature 0x584f4258; it is not inferred to be BRFR from a header enum.

One owner event wait acquires the scalar snapshot and one set releases it.
No layout ownership spans lower building, dispatch, or completion waiting.
The copied snapshot can therefore survive an owner cache replacement or
style/identity mutation during the lower operation. Exact capacity is copied
under the same ownership as style and identity; it is never a CHS product.
The supported caller keeps the owner and attached lower device alive for the
call on the boot-fixed HDD. There is no new hot-remove/reference guarantee.

The lower operation is a no-input public basic geometry query with an exact
24-byte fresh system-memory output, an initialized event, and a fresh IOSB
initialized to pending/count 0. The basic output starts cleared, so a claimed
successful no-write response cannot reuse old valid geometry. Builder failure
returns INSUFFICIENT_RESOURCES. Pending submission waits nonalertably in
KernelMode without a timeout. A transient unsuccessful wait cannot release
the child's stack-resident output/IOSB: waiting continues until the completion
event is acquired. Supported kernel waits with these parameters complete
normally; perpetual kernel/lower failure has no invented timeout guarantee.

Only a terminal lower success with Information exactly 24 can supply geometry.
Terminal failure is preserved. A failing immediate dispatch cannot become
success merely because an inconsistent IOSB says success. Remaining pending
or positive nonzero terminal statuses are malformed and fail explicitly.
The adapter never reads a child IRP after submission; the I/O manager owns
the synchronous child's completion and disposal, including inline completion.

Copied owner capacity/sector must be positive, signed-capacity representable,
sector-aligned, and within the frozen composer sector policy. Invalid owner
snapshot is INVALID_DEVICE_REQUEST. Successful short/overreported basic data
is INFO_LENGTH_MISMATCH. Invalid lower geometry or a lower sector size that
differs from the owner snapshot is UNRECOGNIZED_MEDIA. Missing arguments are
INVALID_PARAMETER. A failed owner wait is returned if negative, otherwise
INVALID_DEVICE_REQUEST. These error choices are explicit candidate policy,
not measured historical error parity.

The adapter independently initializes a 32-byte base from the fresh validated
geometry and copied exact capacity, then calls the unchanged composer. It
retains the observed compatible prefix policy and the zero-size unavailable
padding convention. Full initialized DetectNone does not assert BIOS facts.
The composer remains the only response serialization implementation.

Tests first compile the actual adapter and composer with original host API
doubles. The host types model relevant public fields semantically; they are
not invented target owner offsets. Tests exercise immediate/pending success
and failure, terminal-vs-dispatch disagreement, count faults, no-write/poison
geometry, invalid snapshots/arguments, every 0-through-256 output capacity,
owner mutation/cache replacement, output aliasing, one enclosing completion,
no layout lock during lower wait, builder allocation failure, synchronous
child disposal, and a retry after a transient wait fault. Freestanding i386
compilation uses the same semantic preamble and checks calling convention;
it does not qualify the native owner ABI. Actual-build assertions and final
native link/behavior qualification belong to the parent integration phase.
