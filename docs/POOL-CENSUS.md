# Pool allocation census

The pool census is an opt-in diagnostic build for SpiritBoot issue [#213](https://github.com/Mainkill1/SpiritBoot/issues/213). It gathers request-size distribution and bucket-page use to identify candidate pool layouts from boot, API, storage, Conker, and PGR2 workloads.

It does not change the allocator's size classes or the normal release image. The diagnostic build uses fixed preallocated counters and adds work to pool allocation/free paths, so do not use it for performance comparisons.

## Build

Build the normal pinned firmware with `--pool-census`:

```sh
python3 scripts/build-firmware.py \
  --source .reference/roswell \
  --output artifacts/pool-census-release \
  --variant release --memory-mib 128 --pool-census
```

The build manifest records `pool_census: true`. The flag is available in `firmware.yml` manual runs as well. It requires the replacement pool and page-window backend (`NXK_MM_POOL` and `NXK_MM_POOLPAGES`). Standard builds leave the census storage and hooks out.

Generate an `nm` listing from the unstripped kernel produced by the diagnostic build:

```sh
build_dir=$(python3 -c 'import json; print(json.load(open("artifacts/pool-census-release/build.json"))["build_directory"])')
i686-w64-mingw32-nm --numeric-sort "$build_dir/ntoskrnl/xboxkrnl.unstripped.exe" \
  > artifacts/pool-census-kernel-symbols.txt
```

## Capture a workload

Run xemu with the diagnostic BIOS and a local GDB port. Keep the emulator open while collecting the workload. The GDB listener binds to `127.0.0.1` only.

```sh
python3 scripts/run-firmware.py \
  --xemu /path/to/xemu \
  --flash artifacts/pool-census-release/flash.bin \
  --hdd /path/to/test-hdd.qcow2 \
  --preserve-hdd \
  --dvd /path/to/test.iso \
  --memory-mib 128 --timeout 86400 --gdb-port 12345 \
  --output artifacts/pool-census-run
```

In another terminal, read and save the current census:

```sh
python3 tools/read_pool_census.py \
  --symbols artifacts/pool-census-kernel-symbols.txt \
  --port 12345 --output artifacts/pool-census-run/census.json
```

The reader briefly stops the guest, verifies that the census update sequence is stable, copies the record, then resumes emulation automatically. `--leave-stopped` is available when an operator wants to inspect the paused state manually.

## Reading the output

- **Bins** count requests in exact 8-byte ranges through the small-allocation limit of 2,040 bytes. Above that, they use 16-byte ranges through 65,536 bytes; larger requests share an overflow bin. The 8-byte small bins align with current and proposed class boundaries, which fall at usable capacities ending in 8.
- **Tags** provide allocation, free, live, peak-live, and sampled lifetime totals by request bin and kernel/title domain.
- **Attached class pages** (`attached_class_pages`) report fresh refills, empty-page reuse, detached pages, active pages, and retained empty pages by class/domain. The class size includes the allocator's 8-byte block header. Each row's peak describes that row's attachment history; adding row peaks does not give a simultaneous global physical peak.
- **Physical bucket backing** (`physical_bucket_backing`) reports the current and global peak number of committed physical pages backing small-object buckets. It updates at the page-window allocation commit and physical return, under the page-window and PFN locks. Reclassifying an empty page does not change this total. During acquire/attach or detach/reuse/free, this count can briefly differ from the attached-class rows, so the reader marks that capture incomplete. Use only complete captures at settled checkpoints.
- **Lifetimes** are sampled at one allocation in 64 and placed in `<1 s`, `1–30 s`, and `>=30 s` buckets. Live samples are right-censored and counted separately.
- **Integrity counters** identify table overflow, missed frees, counter saturation, and page-accounting underflow. Any nonzero integrity counter sets `incomplete: true`; do not use that capture to choose classes.

The record is versioned and contains its byte size and array offsets. Its sequence field is odd only while a census update is in progress. The reader retries if a stop occurs during an update. The opt-in fixed record occupies about 105 KiB of 32-bit static RAM; that diagnostic-only footprint is absent from standard builds and must be accounted for when interpreting memory-availability measurements. Counters are guest diagnostic state, not a stable title ABI.

## Producer and reader qualification

The original draft reader placed the two bucket-page totals at the end of the 30-word header. The compiled schema-3 producer places them before the lifetime fields. As a result, the original reader rejected an initialized production record with a schema-dimension error even though its synthetic reader tests passed. The reader now follows the unchanged production layout.

The firmware workflow runs `tests/host/check_pool_census_abi.py` after the production census fixture. This check compiles the fixture's generated unit, containing the actual maintained kernel header and counter bodies, emits a record through `NxPoolCensusInitialize` and allocation/free/page APIs, and decodes those bytes with the product reader. It verifies page totals, bins, tags and lifetime data in both reservation configurations. Its lock/time/type shims exercise host decoding; an actual xemu stop/read/resume capture is still required before relying on workload measurements.

This fix and its test use only the maintained open kernel source and generated counter data. They do not inspect a reference BIOS, game instructions or a memory dump.

## Physical backing accounting qualification

The draft incremented physical totals only when a newly acquired page was later attached to a class, and decremented them after physical free had returned and released its locks. Those separate pool-list hooks did not serialize physical backing history. A host schedule with another acquire/free between the first acquire and class attachment recorded peak 1 while two backing pages existed. A refill between physical return and the delayed decrement recorded peak 2 while at most one backing page existed. Both schedules settled at current 1 with clean integrity counters, so those counters alone could not reveal the inaccurate peak.

The diagnostic build now records successful backing acquisition and return inside the existing page-window/PFN critical sections. The private run-length word carries a diagnostic bucket flag; public run queries mask it out, and the ordinary allocation/free interfaces and allocator policy are unchanged. No additional ownership table is allocated. Class attach/detach counters remain on their existing pool-list transitions. The census lock is a leaf: these backing helpers update fixed counters without allocating, freeing, acquiring allocator locks or calling the page supply.

`tests/host/pool-census-pages/check.py` compiles the actual maintained pool, page-window and census bodies with a modeled frame supply, lock checks and forced schedules at page-window unlock. It fails against the original bodies on current and peak backing in both interleavings, and passes the repaired bodies in both reservation configurations. It also covers failed acquisition, partial whole-page rollback, page-table failure, same-class reuse, cross-class reclassification, domain separation and query/free byte counts. This demonstrates a real ordering defect through modeled preemption; it is not evidence that a particular native title took either schedule. Native census workload captures remain pending.

## Scope and limitations

This first pass observes `ExAllocatePool*` requests and the replacement pool's small-bucket page lifecycle. It does not count every allocator in the kernel: page-supply, cache, stack, VM, and device-specific allocations that bypass this pool remain separate owners. Compare the census with physical-page and allocation-lifetime probes before deciding that a class change reduces memory use.

The record contains aggregates, not an ordered allocation/free trace or an allocation-to-page occupancy map. A snapshot can bound live padding at that checkpoint, but cannot reproduce another class table's fragmentation, refill churn or peak backing. Ordered replay input or paired workload measurements are required for those decisions. The global peak covers committed small-bucket backing, not every PFN used by the kernel or page tables. Captures during a page-window commit/return must be resumed and retried at a settled checkpoint; census sequence stability alone does not certify that the entire allocator is quiescent.

The census does not record reuse searches, pages examined, scan-length percentiles or lock-held time. Its refill/reuse/detach counters can identify where to add the separate measurement requested by [#218](https://github.com/Mainkill1/SpiritBoot/issues/218), but cannot establish whether the current scan is material.

No size-class change is justified until representative captures have clean integrity counters and candidate workload measurements show fewer settled/peak backing pages without changing allocation contracts.
