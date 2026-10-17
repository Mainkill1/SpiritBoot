# FATX hot read-extent candidate: implementation and evidence

## Result and acceptance state

The isolated candidate adds one generation-checked hot physical extent ahead of
the existing 16 sparse seek checkpoints. It reduces the exact 1,024-request
Forza replay's release-host mapping-route time from 1,935,081 ns to 1,851,099
ns, a 4.34% improvement. It also removes 52.15% of calls to the resident FAT
validator, 50.68% of FAT cache mappings, and 51.63% of `FatResource`
acquisitions. Seven alternating AB/BA pairs produced the aggregate medians;
each observation is the median of 101 samples of 32 replay passes.

This is an isolated candidate, not an accepted firmware change. Native release
i386 firmware, QD12/cancellation stress, and human-driven Forza testing remain
required. The earlier 8-entry design is rejected: despite similar structural
savings, it was 5-6% slower on the release host. No larger fallback cache is in
this patch.

## Evidence boundary

This is a repository-native implementation derived from the current SpiritBoot
FATX public structures and behavior, current project tests, the public Forza
request fixture, and the clean-room contract in this deliverable. No prohibited
legacy or reference implementation body was inspected.

The benchmark and tests extract the production C bodies from `fat.c` and
`rw.c`; they do not use a rewritten model of the cache or FAT mapper. The host
kernel primitives are controlled stubs, which makes avoiding `CcMapData` and
resource acquisition cheaper than on target hardware. The measured CPU win is
therefore conservative for those avoided calls, but it is not a substitute for
native release testing.

## State, ownership, and invalidation

The existing optional seek cache grows from 128 to 156 bytes: one 16-byte
`VFAT_READ_EXTENT` plus a 12-byte generation/geometry record. Allocation remains
limited to files larger than 1 MiB; failure keeps the existing uncached path.
There is one hot range, so lookup has no loop and publication has no search.

`MainResource` shared owns allocation-chain stability from lookup through lower
I/O completion. Resize/delete own it exclusively and invalidate before changing
or releasing a cluster. `LastMutex` owns the generation, geometry, extent, and
sparse checkpoints. Lock order remains `MainResource` then `LastMutex`; the new
helpers do not allocate, wait, map metadata, perform I/O, or take `FatResource`.

Whole-cache invalidation advances a nonzero wrapping generation, clears all
state, and restores the new generation. The audited mutation sites are
`VfatSetAllocationSizeInformation` before extension/truncation and its rollback,
and both FAT/FATX delete paths before cluster release. New-object allocation has
no pre-existing FCB cache, directory extension uses the allocation-size path,
and in-place data writes do not change the chain. Any future chain-mutating
entry point must invalidate before its first mutation.

A successful `VfatTryMapRead` is the only publication source. Compatible
physical overlap/adjacency coalesces; disjoint or fragmented evidence replaces
the single hot entry. A hit requires matching generation and exact stored
power-of-two geometry, complete byte-range containment, and checked arithmetic.
Malformed, stale, partial, changed-geometry, or absent state falls through to
the existing checkpoint plus resident FAT validation path.

## Target-route function inventory

Counts below are per 32-pass sample, 32,768 requests. “Unchanged” means the
function body or mandatory call count was deliberately retained for the stated
hardware/correctness reason.

| Function / primitive | Baseline calls | Candidate calls | Evidence or reason |
|---|---:|---:|---|
| `VfatPrepareSeekCache` | 32,768 | 32,768 | Unchanged admission/allocation gate; allocation failure must remain benign. Release i386: 68 instructions, 5 branches in both. |
| `ExAcquireFastMutex` / release | 98,304 each | 98,304 each | Unchanged lock count. Three already-existing critical sections own allocation, lookup, and publication without creating a new lock transition. |
| `VfatLookupReadExtent` | 0 | 32,768 | New single-entry fast lane. Release i386: 115 instructions, 12 branches, no division/compiler helper; only `ClusterToSector` is called on hit. |
| `VfatLookupSeekCheckpoint` | 32,768 | 15,680 | Down 52.15%; needed on misses to accelerate nonlocal/fragmented reads. Release i386 unchanged at 54 instructions, 8 branches. |
| `VfatTryMapRead` | 32,768 | 15,680 | Down 52.15%; remains authoritative on misses for resident metadata, malformed links, fragmentation, and cache-cold fallback. Production body unchanged. |
| `ExAcquireResourceSharedLite(FatResource)` | 33,158 | 16,039 | Down 51.63%; required around resident FAT metadata on misses. |
| `CcMapData` / `CcUnpinData` | 33,776 | 16,657 | Down 50.68%; required to validate resident FAT entries on misses. |
| FAT entry inspections / `FAT32IsEndOfChain` | 890,630 | 846,536 | Down 4.95%. Hits preferentially remove short validations; long miss walks remain authoritative. |
| `ClusterToSector` | 32,768 | 32,768 | Unchanged: every forwarded request needs one physical byte translation, either in the extent hit or mapper. |
| `VfatRememberReadExtent` | 0 | 15,680 | New miss-only publication/coalescing. Release i386: 213 instructions, 26 branches, no call, division, or compiler helper. |
| `VfatRememberSeekCheckpoint` | 32,768 | 32,768 | Unchanged to preserve broad random/worker-path acceleration. Release i386 unchanged at 64 instructions, 7 branches; its existing variable divide remains. |
| `VfatLockUserBuffer` | 32,768 | 32,768 | Unchanged memory-safety gate before lower I/O. |
| `ExSetResourceOwnerPointer` | 32,768 | 32,768 | Unchanged lease transfer required until async completion. |
| `IoCopyCurrentIrpStackLocationToNext`, `IoSetCompletionRoutine`, `IoMarkIrpPending`, `IoCallDriver` | 32,768 each | 32,768 each | Unchanged lower-driver protocol and completion/cancellation ownership. |
| `VfatAsyncReadComplete` / `ExReleaseResourceForThreadLite` | 32,768 | 32,768 | Unchanged completion accounting and chain-stability lease release. |

The measured mapping subroute does not time MDL construction or lower-driver
latency because the patch does not alter them. The async integration tests
exercise their status, completion, and resource-ownership behavior.

## Per-function diagnostic profile

A separate three-run `-O3 -pg -fno-inline` diagnostic profile expanded the
same production bodies to 33,554,432 requests so sampling could attribute self
CPU. Its median wall time improved from 10.594 s to 9.894 s (6.61%). These
numbers locate cost; the uninstrumented release-host result above is the
acceptance measurement.

| Function | Baseline median self CPU | Candidate median self CPU | Interpretation |
|---|---:|---:|---|
| `VfatTryMapRead` | 1.28 s | 1.15 s | Total falls with 52.15% fewer calls; remaining calls are the longer/harder walks. |
| `FAT32IsEndOfChain` | 0.31 s | 0.30 s | Essentially unchanged total because most FAT-link work is in retained long misses. |
| `CcMapData` | 0.11 s | 0.12 s | 10 ms sampler noise; calls fall 50.68%, host stub cost is intentionally tiny. |
| `VfatLookupSeekCheckpoint` | 0.08 s | 0.02 s | Falls with miss-only invocation. |
| `VfatPrepareSeekCache` | 0.02 s | 0.01 s | Same calls/body; difference is sampling noise. |
| `VfatLookupReadExtent` | — | 0.07 s | New fast-lane lookup cost. |
| `VfatRememberReadExtent` | — | 0.05 s | New miss-only publication cost. |
| `VfatRememberSeekCheckpoint` | 0.04 s | 0.05 s | Same calls/body; difference is sampling noise. |
| fast-mutex acquire | 0.04 s | 0.03 s | Same call count; no added transition. |
| route body outside callees | 0.08 s | 0.06 s | Branch/bookkeeping total remains bounded. |

The 10 ms sampling quantum cannot resolve zero/10 ms differences. The raw
three-run samples and call graph are retained in
`per-function-profile-final.json` and `tests/profile-final/`.

## Release i386 code shape

Exact production helper bodies were compiled for `i386-unknown-none-elf` with
`-O2 -ffreestanding -fno-stack-protector -fno-builtin` and disassembled.
Neither new extent helper contains a divide instruction or compiler helper
call. The lookup has a 12-byte local stack frame and four `%esp` references;
the publisher has a 40-byte local frame and three `%esp` references. Geometry
uses the cached shift; only the existing checkpoint publisher retains one
hardware `div`. Allocation clearing grows from 128 to 156 bytes, and whole-cache
invalidation clears the same bounded 156 bytes. There are no unbounded clears,
loops, or publications on a hit.

The standalone i386 helper compilation may differ from final whole-program
inlining and register allocation. Native release disassembly must confirm the
final call sites before acceptance.

## Test evidence

The final exact-body host run reports:

- extent helper oracle: 6,028 checks, zero failures, under plain and ASan/UBSan;
- seek checkpoints: 20,795 checks, 566,733 traversed links, zero failures;
- resident FAT mapper: 178 checks, zero failures;
- integrated real async/checkpoint/FAT scenarios: 5 passed;
- allocation-free async entry/completion: 126 checks, zero failures;
- source-level publication and mutation gates: passed.

The extent oracle covers allocation failure, exact byte boundaries, within-
cluster offsets, partial spans, compatible coalescing, fragmented adjacency,
disjoint replacement, invalid and overflowing publication, generation
invalidation, changed and non-power-of-two geometry, and 2,000 randomized
comparisons to an independent linear mapping oracle.

## Native risks and required gate

1. A chain mutation outside the audited sites could retain stale physical state.
2. Final i386 inlining/register allocation could differ from the isolated
   helper disassembly.
3. Host cache/resource stubs understate the benefit and do not model native
   interrupt timing.
4. Native QD12, cancellation, cleanup, and cold-metadata fallback must preserve
   byte counts, status, command, IRQ, APC, and resource-release counts.
5. Human-driven Forza must show equal correctness and improved world/map
   delivery in two release runs; aggregate CPU must not regress.

Until all five gates pass, keep this patch out of release firmware.
