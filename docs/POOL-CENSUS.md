# Pool allocation census

The pool census is an opt-in diagnostic build for SpiritBoot issue [#213](https://github.com/Mainkill1/SpiritBoot/issues/213). It gathers request-size distribution and physical bucket-page use so candidate pool layouts can be replayed against actual boot, API, storage, Conker, and PGR2 allocation traces.

It does not change the allocator's size classes or the normal release image. The diagnostic build uses fixed preallocated counters and adds work to pool allocation/free paths, so do not use it for performance comparisons.

## Build

Build the normal pinned firmware with `--pool-census`:

```sh
python3 scripts/build-firmware.py \
  --source .reference/roswell \
  --output artifacts/pool-census-release \
  --variant release --memory-mib 128 --pool-census
```

The build manifest records `pool_census: true`. The flag is available in `firmware.yml` manual runs as well. Standard builds leave the census storage and hooks out.

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
- **Pages** report fresh refills, empty-page reuse, detached pages, active pages, and retained empty pages by class/domain. The class size includes the allocator's 8-byte block header.
- **Bucket page totals** report the current and global peak number of physical pages backing small-object buckets. Reclassifying an empty page does not change the physical total; a page leaves the total only after the page allocator returns it. During detach/reuse or detach/free, the global count can briefly differ from the per-class/domain rows, so the reader marks that capture incomplete. Use only complete captures at settled checkpoints.
- **Lifetimes** are sampled at one allocation in 64 and placed in `<1 s`, `1–30 s`, and `>=30 s` buckets. Live samples are right-censored and counted separately.
- **Integrity counters** identify table overflow, missed frees, counter saturation, and page-accounting underflow. Any nonzero integrity counter sets `incomplete: true`; do not use that capture to choose classes.

The record is versioned and contains its byte size and array offsets. Its sequence field is odd only while a census update is in progress. The reader retries if a stop occurs during an update. The opt-in fixed record occupies about 103 KiB of 32-bit static RAM; that diagnostic-only footprint is absent from standard builds and must be accounted for when interpreting memory-availability measurements. Counters are guest diagnostic state, not a stable title ABI.

## Scope and limitations

This first pass observes `ExAllocatePool*` requests and the replacement pool's small-bucket page lifecycle. It does not count every allocator in the kernel: page-supply, cache, stack, VM, and device-specific allocations that bypass this pool remain separate owners. Compare the census with physical-page and allocation-lifetime probes before deciding that a class change reduces memory use.

No size-class change is justified until representative captures have complete integrity counters, and replaying those captures shows fewer settled/peak backing pages without changing allocation contracts.
