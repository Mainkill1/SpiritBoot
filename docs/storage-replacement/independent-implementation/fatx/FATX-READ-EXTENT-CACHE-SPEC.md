# FATX resident read-extent cache contract

## Scope and evidence boundary

This is an independent, repository-native optimization of the existing Xbox
FATX noncached asynchronous read path. It does not change the ordinary worker
path, allocation policy, on-disk format, or storage protocol. The design was
derived from the current SpiritBoot FATX public structures and behavior,
release workload metadata, and current project tests. No prohibited legacy or
reference implementation body was consulted.

The measured Forza replay currently performs about 20,348 FAT link inspections
and 1,024 FAT cache mappings for each 1,024-request measured pass at an assumed
16 KiB cluster size. The existing 16-position seek cache reduces the walk to a
nearby starting point, but every request still reads FAT entries to re-prove a
physical run. This cache may reuse only a run already proved by that same
resident metadata path.

## State

Each eligible FCB may own one optional nonpaged cache. Allocation failure is
benign and leaves all reads on the existing path. The cache is bounded to:

- 16 sparse seek checkpoints, retaining current miss acceleration;
- one hot read extent containing a cluster-aligned file byte offset, first
  physical cluster, positive cluster count, and the cache generation. The
  cache also records the validated power-of-two cluster size and its shift.

An extent states that each file cluster in its half-open file range maps to the
corresponding consecutive physical cluster. Empty entries have a zero count.
No extent describes file contents, EOF, valid-data length, or cache-manager
state.

## Ownership and locking

- `MainResource` shared owns the file allocation chain during lookup, FAT
  validation, and publication. The async path already keeps this lease until
  lower I/O completes.
- Allocation resize and chain-changing operations own `MainResource`
  exclusively. They invalidate before their first possible FAT mutation.
- `LastMutex` owns the cache generation, all checkpoint entries, and the hot
  extent. A lookup requires the extent generation to equal the cache generation, copies
  its result while holding the mutex and uses only the
  copied scalar values after release.
- FCB destruction occurs after file users are gone and releases the optional
  cache once. It does not race a valid `MainResource` owner.
- `FatResource` and cache-manager mapping contexts remain owned solely by the
  existing resident metadata validator. An extent hit acquires neither because
  `MainResource` excludes chain mutation and the mapping fact is already
  validated.

Lock order remains `MainResource` then `LastMutex`. No extent helper acquires
`FatResource`, waits, performs I/O, allocates memory, or calls a lower driver.

## Admission and lookup

The async read admission checks remain authoritative: nonzero bounded length,
aligned destination, adequate stack, no cleanup, range within file size and
valid-data length, no shared cache map, and a fresh nonrecursive shared
`MainResource` lease.

After admission, validate the requested byte range with overflow-checked
32-bit arithmetic and the recorded cluster shift. Non-power-of-two geometry
bypasses this advisory cache. Under `LastMutex`, inspect the one hot entry. A
hit requires its byte range to contain the complete request. Partial overlap is
a miss. On hit:

1. derive the first physical cluster by the file-cluster delta;
2. reject arithmetic overflow or an invalid physical cluster;
3. derive the disk byte offset with widened arithmetic;
4. preserve the original byte offset within the first cluster;
5. proceed through the unchanged MDL, lower-stack, completion, and APC path.

The cache is advisory. Any malformed entry, arithmetic failure, partial match,
or cache absence falls through to checkpoint selection and the existing
resident FAT validator. It must never turn a read that formerly fell back into
an error.

## Publication and replacement

Only a successful `VfatTryMapRead` result may publish. It publishes exactly the
cluster interval that the call proved contiguous, expressed in absolute file
offsets. Publication happens while `MainResource` is still shared and under
`LastMutex`.

If the new interval overlaps or touches the hot interval and both intervals
share the same file-to-physical linear mapping, replace them with their union.
Otherwise replace the hot interval with the newly proved interval. Publication
also retains the current sparse checkpoint behavior. This 28-byte fast lane is
deliberately small: the measured sequence preserves nearly all useful hits,
while the existing 16 sparse checkpoints still accelerate broader random
misses.

No speculative read-ahead, FAT access, blocking map, allocation, or chain walk
may occur solely to enlarge an extent.

## Invalidation

The existing `VfatInvalidateSeekCheckpoints` operation becomes whole-cache
invalidation. Under `LastMutex` it advances a nonzero wrapping generation and
clears checkpoints and the hot extent. It is called before:

- allocation extension or truncation, including failure/rollback paths;
- file deletion before cluster release;
- any other operation that changes the FCB's allocation chain.

An ordinary in-place data write does not invalidate because it does not change
the file-to-cluster mapping. Rename/move does not invalidate when the chain is
preserved. A future chain-mutation entry point must call the same invalidator
before its first mutation.

Concurrent sequence: a reader holding `MainResource` shared may hit or publish;
a mutator cannot acquire exclusive ownership until readers release. Once the
mutator owns the resource, it clears the cache before changing the chain. A
later reader therefore cannot observe a pre-mutation extent.

## Required behavioral checks

1. Exact hits at extent start/end and byte offsets inside clusters.
2. Misses before, after, and crossing an extent boundary.
3. Sequential and nearby random reads eliminate repeated FAT walks after one
   successful validation.
4. Non-power-of-two or changed cluster geometry bypasses the extent cache.
5. Contiguous, fragmented, malformed, end-of-chain, FAT16, and FAT32 mappings
   match an independent chain oracle.
6. Compatible overlap/adjacency coalesces; physically inconsistent adjacency
   stays separate.
7. A disjoint publication deterministically replaces the former hot run.
8. Whole-cache invalidation prevents every stale hit after extend, truncate,
   delete, failed extension rollback, and delete/recreate.
9. Cache allocation failure, cold FAT metadata, lock contention, mapping
   failure, and exceptions retain the ordinary fallback.
10. Concurrent readers cannot publish torn entries; mutation exclusion and
   lock order are asserted by the host model.
11. Release i386 disassembly contains no new compiler helper call on a hit and
    measurements report per-function call counts and time before/after.
12. Native release testing must preserve bytes, status, command, IRQ, APC,
    cancellation, and cleanup counts before this candidate can be accepted.

## Native risks and acceptance boundary

The main risks are a missed chain-mutation invalidation site, 32-bit arithmetic
wrap, a lock-order inversion, and a cache hit computed from an incompletely
validated span. Host tests must make these failures observable, but only two
independent release firmware runs plus the human-driven Forza stream can
qualify the candidate. Until those pass, this is a batch candidate rather than
an accepted optimization.
