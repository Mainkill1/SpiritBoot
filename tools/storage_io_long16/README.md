# Long public storage-I/O fixture

This XBE runs 16 complete passes of the generation 6 public-API raw-device recorder during one boot. Each pass issues 1,024 reads, verifies every returned byte and surrounding canary, checks callback status and pointer identity, and releases all owned resources before the next pass. The longer in-guest interval prevents sub-second samples from being treated as performance evidence.

The only accepted raw leaf is `raw-d0-q1-p0-synthetic.warm`. It replays the checked-in public request metadata through `\\Device\\Harddisk0\\Partition0` at byte offset 7,937,024,000. The 51,625,984-byte seed window must be inside a disposable private disk copy. Never run this leaf against a shared or valuable HDD image.

The recorder reports `STORAGE-IO-V6-CASE` for every measured pass and `STORAGE-IO-V6-END` after every cleanup. A qualifying boot has exactly 16 of each record, 16,384 completed operations, 173,940,736 verified bytes, zero failures, and cleanup complete for every pass.

Build with a prepared NXDK installation:

```sh
eval "\$(/path/to/nxdk/bin/activate -s)"
make -C tools/storage_io_long16 all NXDK_DIR=/path/to/nxdk
python3 tools/storage_io_long16/test_recorder.py
```

The build emits `bin/default.xbe` and `pr248-io-recorder-v7-long-raw-control.iso`. The qualified artifact in `docs/performance/evidence/native-storage-hotpath-long16-20261015` has SHA-256 `bb49ed380728a25f389055ab254f1fc7867b8e3eb5c5632001bc828f0fb8db1f` and was built with NXDK commit `29638d0b` and clang 19.1.7 using the default unoptimized target profile plus `-Wall -Wextra`.

The runner must prepare the selected leaf through its isolated FATX workflow with private HDD and EEPROM state. An ordinary unprepared HDD fails selection. The four exact Windows runner requests, ABBA order, firmware hashes, run IDs, per-pass results, and analysis are checked in beside the performance evidence.
