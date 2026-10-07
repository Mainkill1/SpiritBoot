# Building and running the open firmware

SpiritBoot integrates Roswell's open `nxldr` loader and Xbox kernel. The build
produces an xemu flash image: 256 KiB release or 512 KiB checked. It does not
require Microsoft BIOS or MCPX files. The first runtime target is xemu with
128 MiB RAM. Conker: Live & Reloaded is the retail compatibility target; its
gameplay has not yet been verified with this firmware.

Use Linux, Python 3.11+, Git, and Docker, or install the cross compiler and
tools listed in [Dockerfile.firmware](../tools/Dockerfile.firmware) on your host.
The exact source revisions and public fixture identities are in
[firmware-lock.json](../sources/firmware-lock.json).

## Build

From the SpiritBoot checkout:

```sh
git clone https://github.com/mborgerson/roswell.git .reference/roswell
git -C .reference/roswell checkout 1569e2e89fb47cc72b9c704a8884f98200432bd4
docker build -f tools/Dockerfile.firmware -t spiritboot-toolchain .
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/work" \
  spiritboot-toolchain python3 scripts/build-firmware.py \
  --source .reference/roswell --output artifacts/firmware-release
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/work" \
  spiritboot-toolchain python3 scripts/build-firmware.py \
  --source .reference/roswell --output artifacts/firmware-debug --variant debug
```

If the reference checkout already exists, use it and check out the pinned commit
without overwriting local changes. The driver rejects dirty or unpinned sources.
For intentional kernel changes, commit them in your own GPL-compatible Roswell
fork and update the source URL and full revision in the lock file.

On an installed host toolchain, run the same Python command without Docker.
If a managed network requires a CA bundle, add
`--secret id=proxy_ca,src=/path/to/combined-ca-bundle.pem` to `docker build`.
Keep the configured proxy and TLS verification enabled.

Each output directory contains `flash.bin`, `build.json`, `build.log`, and
`work/` (upstream kernel/loader build products). The manifest records revisions,
compiler versions, command arguments, image size, SHA-256, and the source commit
epoch. That epoch is exported as `SOURCE_DATE_EPOCH` to avoid wall-clock PE linker
timestamps. Each build cleans cached linker products so a previous timestamp
cannot leak into a newly attributed image. Failed builds invalidate the published
image and preserve diagnostics.
Use new output directories for a clean reproducibility comparison.

## Prepare the pinned emulator and open fixtures

```sh
mkdir -p artifacts
curl -fL https://github.com/Mainkill1/xemu/releases/download/v0.8.136-0-g458730bf5373/xemu-0.8.136-0-g458730bf5373-x86_64.AppImage \
  -o artifacts/xemu.AppImage
printf '%s  %s\n' \
  e10b192a0402c7624525651ac7631dd7764e6a1b26d67fbb85ef8a4fdd563301 \
  artifacts/xemu.AppImage | sha256sum --check
chmod +x artifacts/xemu.AppImage
curl -fL https://github.com/xemu-project/xemu-dashboard/releases/download/v20260516-0955/xbox_hdd.qcow2 \
  -o artifacts/xbox_hdd.qcow2
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/work" \
  -w /work/artifacts spiritboot-toolchain ./xemu.AppImage --appimage-extract
```

The extracted binary is `artifacts/squashfs-root/usr/bin/xemu`. The container
supplies its runtime dependencies, including host `libusb`. A native launch
needs an X display, those runtime libraries, and the appropriate audio backend.
For a desktop run, the AppImage can also run normally through FUSE.

Build Roswell's open API-regression payload using the recorded nxdk container:

```sh
docker run --rm -v "$PWD:/work" \
  -w /work/.reference/roswell/tests/xbe/api-regression \
  ghcr.io/xboxdev/nxdk@sha256:bab707b7ed2544e9956d51e7b411a4575ab66120bd608b3237698495203d15f7 \
  make NXDK_DIR=/usr/src/nxdk
```

## Verify boot and kernel execution

This starts a software-rendered X display in the container and launches the
open test image. The short startup delay lets Xvfb bind its socket; the launch
driver independently enforces the emulator deadline.

```sh
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/work" \
  -e SDL_AUDIO_DRIVER=dummy spiritboot-toolchain sh -c '
  Xvfb :99 -screen 0 1280x720x24 -nolisten tcp >/tmp/xvfb.log 2>&1 &
  python3 -c "import time; time.sleep(1)"
  DISPLAY=:99 exec python3 scripts/run-firmware.py \
    --xemu artifacts/squashfs-root/usr/bin/xemu \
    --flash artifacts/firmware-release/flash.bin \
    --hdd artifacts/xbox_hdd.qcow2 \
    --dvd .reference/roswell/tests/xbe/api-regression/nxkrnl-api-regression.iso \
    --output artifacts/open-xbe-release --timeout 240 --expect-tap'
```

Use `firmware-debug/flash.bin` and a new output directory for the checked build.
`--expect-tap` requires one complete TAP v13/v14 stream, a matching numbered
plan, no unexpected failures, and a clean emulator exit. TODO and SKIP cases are
reported separately. A timeout or reset is a failure even if part of the suite
has passed. An ordinary capture without `--expect-tap` does not certify a boot.

Each run retains `xemu.toml`, `serial.log`, `emulator.log`, and `run.json`, including
SHA-256 identities for the emulator and input images. Output directories are
exclusive: previous captures are never overwritten. The HDD is opened with
`-snapshot`, so guest writes do not change the supplied image.

## Run Conker on a desktop

Use your local Xbox XISO, not a raw retail disc dump or the Nintendo 64 game.
Run with the checked flash first to retain kernel diagnostics:

```sh
python3 scripts/run-firmware.py \
  --xemu /path/to/xemu \
  --flash artifacts/firmware-debug/flash.bin \
  --hdd /path/to/xbox_hdd.qcow2 \
  --dvd /path/to/conker-live-and-reloaded.iso \
  --output artifacts/conker-first-boot --timeout 600
```

Start from a cold boot; do not load a saved state created with another kernel.
The capture ends at the deadline and reports `timeout`, which is expected for
an interactive game session and does not imply success or failure of gameplay.
Record the menu, playable scene, controller input, audio, visual defects, and
stability alongside the logs. The deadline is measured from process start, not
from the first playable frame; a ten-minute stability result needs observation
after gameplay starts. Kernel/loader failures should be reduced to focused
regressions before changing compatibility behavior.

## Host tests

```sh
python3 -m unittest discover -s tests/host -v
```

See [baseline evidence](provenance/OPEN_FIRMWARE_BASELINE.md) for reproduced
results and known gaps. No game, EEPROM, or proprietary firmware data is tracked.
