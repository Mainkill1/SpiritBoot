# Optional directory-update counters

This diagnostic answers whether attempted directory-entry updates actually
change bytes. It does not suppress writes or change write-through durability.
No game assets, entry contents, filenames or per-call logs are recorded.

Normal builds default to counters disabled. Request an instrumented firmware
explicitly:

```sh
python3 scripts/build-firmware.py --source .reference/roswell \
  --output artifacts/metadata --metadata-counters
```

The Open firmware workflow also accepts the explicit `metadata_counters`
dispatch input; ordinary push/PR builds keep it disabled. `build.json`
records the effective boolean and the CMake command. Do not publish timing or
FPS claims from enabled firmware: comparisons and atomic increments add work.

## Snapshot contract

Resolve `VfatMetadataCounters` from the exact firmware's unstripped kernel and
loaded image layout, then stop emulation before reading its80 bytes. Do not
reuse an address from another firmware. There is no hot-path snapshot/export
operation. Individual counters are atomic; reading a running guest does not
give a consistent transaction across bins.

All fields are32-bit little-endian words:

|Byte offset|Meaning|
|---:|---|
|0|Magic `0x4d455431`|
|4|Schema1|
|8|Structure size80|
|12|Number of counter wraps|
|16–47|Eight FAT12/16/32 bins|
|48–79|Eight FATX16/32 bins|

Interpret bin values as unsigned32-bit counts. A nonzero wrap count means the
window cannot be treated as complete exact counts. A stopped snapshot may be
subtracted from a later stopped snapshot of the same run/image when neither
wrapped; include all counts since boot if no start snapshot was retained.

The bin index is a change mask:

- `0`: entire32-byte FAT or64-byte FATX entry is byte-identical.
- Bit0 (`1`): size/first-cluster fields changed.
- Bit1 (`2`): date/time fields changed.
- Bit2 (`4`): another field changed.

Every successful pin in `VfatUpdateEntry` increments exactly one bin before
the existing copy/dirty/unpin path. Sum all bins for attempts, bin0 for
identical attempts, and bins1–7 for changed attempts. Masks can combine
categories; sum bins containing a bit to count that category.

FATX storage fields are first cluster and size (bytes44–51), timestamps are
bytes52–63, and other fields are bytes0–43. FAT storage includes first
cluster and size plus the high cluster word on FAT32. That union holds an
extended-attribute index on FAT12/16 and is counted as other there. FAT
timestamps include creation milliseconds/time/date, access date and update
time/date. Compile-time assertions check the actual driver layouts.

Attempts that return early for a root/FAT/volume FCB, cache initialization
failure or pin failure are not counted. Counts do not establish that a write
completed, that a block was evicted, or which physical sector was involved.
A growing file can change size on every call, so it may have no avoidable
entry updates despite frequent writes to the same metadata block.

## Verification

The maintained production-body fixture builds both gate settings:

```sh
python3 "$KERNEL_SOURCE/tests/host/metadata/check.py" artifacts/metadata-check
```

It runs the actual updater, counter, read/write-back and write-through bodies
with counted synchronous adapters and independent byte oracles. It checks
all change masks, FAT16/FAT32 union handling, identical and growing entries,
read failure, failed write/retry, neighboring dirty data, atomic counting and
wrap detection. Disabled binaries contain neither the helper nor storage.
These adapters do not qualify real-device I/O, guest concurrency, or live
cache-eviction attribution.

This is the measurement step for issue#79, not its optimization or a claim
that Doom's repeated entries are identical. Preserve existing write-through
and save/load behavior when selecting any follow-up optimization.
