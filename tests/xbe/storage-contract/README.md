# Storage boundary contract

Boot on a fresh disposable HDD overlay with populated FATX Partition1 and
Partition3 volumes and a COM1 serial capture. The fixture creates only
`SpiritBootStorageContract.tmp` on those partitions, prints TAP, and shuts down.
Partition1 must have more than 4 GiB free; Partition3 must have less than 4 GiB
free. All test files contain a synthetic 512-byte pattern. Each size case is
reopened and reseeded independently.

The 48 assertions check read-only volume and regular-file flushes, a writable
flush control, positive size-cap and free-space failures, negative size rejection,
and preserved EOF, payload bytes and free clusters after each failed resize.
Queries use `FileNetworkOpenInformation`, the reference-supported class; the
reference rejects `FileStandardInformation`, which made the first investigative
fixture unsuitable for checking EOF. No expectations were relaxed to fix that
fixture error.

The exact 4 GiB and 4 GiB + 512 requests isolate the FATX representability limit
on the large partition. The request beyond Partition1 free space crosses both
limits. Partition3 independently exercises actual allocation failure below the
file-size cap. That last case can take longer because it extends and rolls back
clusters. The negative request has LowPart 512, preventing a baseline signedness
bug from attempting a huge allocation. The expected statuses are DISK_FULL for
positive capacity failures and INVALID_PARAMETER for negative EOF.

Build:

```sh
NXDK_DIR=/home/codex/src/nxdk PATH=/home/codex/src/nxdk/bin:$PATH make
```

Run the same ISO on the baseline, reference and candidate BIOSes. Require all
48 checks and zero failures for qualification. The baseline is expected to fail
six status checks while retaining its data and free-space invariants.

The complementary patched-source host test executes the real resize/rollback
function with a bounded cluster-device double, including empty/existing chains,
allocation-only requests, maximum representable size, normal grow/shrink, and
unchanged generic FAT cap semantics:

```sh
python3 tests/host/fatx/check-size-boundaries.py /tmp/storage-size-check
```
