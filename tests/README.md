# Test Layout

Planned test groups:

## host

Tests that run without an Xbox or emulator. First candidates:
- XBE parser validation;
- export table generation/lookups;
- image/layout tooling;
- FATX parsing once added;
- trace/event serialization;
- kernel-test log normalization (`scripts/test-kernel-tools.ps1`).

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

### Current host fixture

`tests/host/kernel-test-log-sample.txt` exercises PASS, FAIL, SKIPPED, duration, environment, build metadata and source-hash handling in the hardware-log importer. Run `./scripts/test-kernel-tools.ps1` from the repository root on a system with PowerShell.
