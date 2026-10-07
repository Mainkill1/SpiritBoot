# Test Layout

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
