# Test Layout

Run the implemented host suite with:

```sh
python3 -m unittest discover -s tests/host -v
```

The current emulator baseline builds Roswell's open API-regression XBE from the
pinned reference checkout. [BUILD_AND_RUN.md](../docs/BUILD_AND_RUN.md) gives the
commands; [baseline evidence](../docs/provenance/OPEN_FIRMWARE_BASELINE.md) records
the separate release/checked results and known TODOs. The Open firmware workflow
also runs this integration path. No retail game data is part of the test fixtures.

Planned test groups:

## host

Tests that run without an Xbox or emulator. First candidates:
- XBE parser validation;
- export table generation/lookups;
- image/layout tooling;
- FATX parsing once added;
- trace/event serialization.

## xbe

Small open XBEs used to probe one behavior at a time. Prefer nxdk-built payloads with explicit expected results.

Examples:
- entry/stack validation;
- memory allocation/protection;
- thread creation and synchronization;
- timer behavior;
- file/device I/O;
- exception behavior;
- input/video/storage probes.

## integration

Full SpiritBoot runs in xemu and later physical hardware.

Integration tests should assert trace milestones rather than relying only on screenshots or timeouts.
