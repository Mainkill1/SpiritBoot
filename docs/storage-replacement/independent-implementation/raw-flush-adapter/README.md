# Whole-disk flush clean-room boundary

## Result

The 2026-10-15 raw-device diagnostic found that
`NtFlushBuffersFile` on `\Device\Harddisk0\Partition0` returns
`STATUS_INVALID_DEVICE_REQUEST` on SpiritBoot and `STATUS_SUCCESS` on Complex.
Both SpiritBoot runs subsequently read the written bytes exactly after closing
and reopening the handle. That establishes immediate coherence in xemu; it does
not establish reset or power-loss persistence.

A fresh clean-room implementer reviewed only the behavior specification,
approved declaration-only inputs, and independently authored patches `0127`
and `0132`. The implementer did not inspect assembled firmware source, legacy
storage implementation bodies, disassembly, or Git history/diffs. The focused
tests establish that the existing independent request core already:

- holds `NX_FLUSH` behind earlier writes;
- emits a no-data `SYNCHRONIZE CACHE(10)` command for a qualified enabled cache;
- completes only after the lower terminal result;
- propagates a lower failure; and
- rejects an unqualified durability state.

Three request-core scenarios passed under ASan/UBSan. The same production
`request.c` compiled freestanding for i386 with no undefined symbols. A
black-box checker rejects the current SpiritBoot observation with eight named
contract failures and accepts a synthetic complete shape. The synthetic input
tests the checker only; it is not candidate or durability evidence.

## Why there is no production patch yet

The approved inputs do not identify enough of the installed public-to-core seam
to author a safe adapter. The next clean-room packet must provide declarations
or independently authored interfaces for:

1. the installed `IRP_MJ_FLUSH_BUFFERS` dispatch and build registration point;
2. the device context, request-engine association, admission seal and rundown;
3. parent IRP pending/completion access, including inline completion;
4. cancellation, shutdown and removal interaction;
5. the lower no-data SCSI packet submission/completion bridge;
6. a coherent device-owned cache qualification and invalidation source;
7. complete target status mappings; and
8. a disposable-overlay reset or power-loss persistence oracle.

Mapping the current public error directly to success is not an acceptable fix:
it would hide the lower outcome and claim durability without cache
synchronization. The eventual adapter must submit one real synchronization
operation when volatile caching is known enabled, expose its terminal result,
report zero information bytes, and complete the parent exactly once. A known
disabled cache may complete the ordered barrier without a device command; an
unknown or enabled-but-unflushable cache must stay visibly unsupported.

## Performance boundary

The V6 ABBA diagnostic establishes a raw-path SpiritBoot/Complex batch ratio of
`1.5164` and an issue-through-return ratio of `3.2040`. It does not identify a
specific allocation, lock, worker, or packet-reuse change. No performance patch
is justified until instrumentation separates public dispatch, request setup,
lower submission, lower service, completion and caller wakeup. The adapter
contract itself requires no extra worker hop, buffer copy, per-flush allocation
or clock sample.

## Evidence identity

The retained clean-room package is rooted at
`.scratch/raw-flush-cleanroom-impl` in the qualification workspace. Its verified
`SHA256SUMS` file has SHA-256
`b8af9e3fe939d1e045ae756f584725daf3cd9e38f980f264069d277a2b707e74`.
The behavior specification and input manifest used by the implementer have
SHA-256 values
`ebdfe13278aa8de2bbdeb1f3b2884a242ad3ad5848c813e8779572ae144c0e30`
and
`8e71e5994cc3a96cbe74bf243c75585bc9531ad97e321e9c7cfd9dd263c89e73`.
These hashes bind the review record but do not make scratch artifacts part of a
release archive.

The current result closes localization of the existing request core. It does
not close the installed adapter, native restart durability, storage replacement,
performance acceptance or license review.
