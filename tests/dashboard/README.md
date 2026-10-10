# Minimal HDD dashboard and memory observation fixture

This original nxdk XBE provides a `C:\xboxdash.xbe` for dedicated test HDDs.
It contains no firmware, game assets, or reconstructed proprietary code.
It does not change the SpiritBoot firmware build. Use only disposable test
media; do not replace an existing user's dashboard.

## Build

The pinned public nxdk image is
`ghcr.io/xboxdev/nxdk@sha256:bab707b7ed2544e9956d51e7b411a4575ab66120bd608b3237698495203d15f7`.

From the repository root:

```sh
docker run --rm -v "$PWD/tests/dashboard:/work" -w /work \
  ghcr.io/xboxdev/nxdk@sha256:bab707b7ed2544e9956d51e7b411a4575ab66120bd608b3237698495203d15f7 make -j2
```

Install `bin/default.xbe` as `C:\xboxdash.xbe` using a FATX-aware tool on an
**offline copy** of the HDD. Read back the complete file and compare it with
the built XBE. Disconnect the DVD for the dashboard-only route. X3's
Autostart Config Live setting must be disabled in its own separate settings
fixture. Its identification/settings hardware is tracked by xemu #350/#351.

The dashboard's first UART records report its actual kernel launch path,
public MM/PS statistics, and `DASH_EARLY_READY`. There is then a five-second
diagnostic capture interval before framebuffer or marker-buffer allocation.
This interval is not a change to any authored game benchmark.

## Separate DVD handoff build

Clean the local objects before switching build modes; make does not infer a
change in compiler flags from a command-line variable.

```sh
docker run --rm -v "$PWD/tests/dashboard:/work" -w /work \
  ghcr.io/xboxdev/nxdk@sha256:bab707b7ed2544e9956d51e7b411a4575ab66120bd608b3237698495203d15f7 \
  sh -c 'rm -f main.obj main.exe bin/default.xbe; make -j2 DVD_LAUNCH=1'
```

This build opens `\Device\CdRom0\default.xbe` through public kernel APIs,
checks that its first four bytes are the XBE signature, closes the file,
then requests that native optical path through nxdk's public `XLaunchXBE`
API. It avoids a `D:` mapping inherited from the HDD dashboard directory.
An open/read/signature/close failure emits `DASH_LAUNCH_BLOCKED` and keeps
the diagnostic session available without attempting the reboot.
It allocates neither the observation buffers nor a framebuffer before
handoff. It is not a general-purpose file browser. A returned launch is
recorded as `DASH_LAUNCH_RETURN unexpected=1`, then held for diagnosis.

To prove the dashboard route rather than automatic DVD boot, start with an
empty DVD drive, wait for `DASH_EARLY_READY`, pause through QMP, insert the
read-only game DVD, then resume. Require the `DASH_LAUNCH_REQUEST` record
and verify the game's intro/menu separately. A request alone is not proof
of game entry. Published game input procedures remain unchanged; this is a
separate diagnostic launch route.

## Clearing experiment

For cold boot, start the emulator with `-S`. Before the first CPU instruction,
seed ordinary physical RAM with the address-specific `marker_page` pattern
from `tools/dashboard_memory.py`. Verify all written bytes before resuming.
Capture physical RAM at `DASH_EARLY_READY`, before this guest writes its
observation buffers or framebuffer.

The default dashboard allocates three nonpersistent 64 KiB contiguous
buffers through public APIs, reports their physical addresses, and writes
known nonzero words only within its owned allocations. At `DASH_HELD_READY`,
capture the buffers. Request a reset, wait for its completed QMP `RESET`
event, then capture at the next `DASH_EARLY_READY`. Resume afterward.

No out-of-allocation guest memory walk, arbitrary page fault recovery,
firmware patch, or guest-private allocator inspection is used.

Analyze private dumps without publishing their contents:

```sh
python3 tools/dashboard_memory.py cold-early.bin
python3 tools/dashboard_memory.py warm-early.bin --before warm-before.bin \
  --range 0x03bd0000:65536 --range 0x03be0000:65536 --range 0x03bf0000:65536
```

Use the addresses actually reported by that run, not the illustrative ones
above. The analyzer rejects incomplete captures, misaligned/out-of-bounds
ranges and overlaps. Classifications are:

- `retained`: entire page still equals the seed.
- `zero`: entire page is zero.
- `mixed`: at least one marker word remains but the page changed.
- `replaced`: changed page without any surviving marker words.

These are observations, not attribution to a particular clearing function.
A zero page is not proof of ownership or a universal memory-clearing rule.
Overwritten marker data can reflect normal boot reuse. This fixture does
not establish persistent-allocation behavior, 128 MiB behavior, or game FPS.
The early checkpoint includes nxdk entry/runtime work; it is not the first
kernel instruction. A generic whole-RAM clear is not required to pass.

Keep dumps, ROMs, HDD images and native screenshots in private lab storage;
only independently authored sources belong in this repository. Strip any
firmware UART prefix before publishing the fixture's own numeric records.
Public SDK contracts: [XboxDev/nxdk](https://github.com/XboxDev/nxdk).
