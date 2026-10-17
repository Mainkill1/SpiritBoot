# Halo menu backtrace reproduction

This fixture follows missing menu labels backward through GPU texture bytes,
HDD destinations, adapter submission, and parent completion. It diagnoses a
specific Halo CE v1.09 retained-HDD workload; it is not an all-games, all-memory,
or all-storage-path qualification.

## Inputs and execution

The job manifests contain exact payload lengths/SHA-256s, launch arguments,
diagnostics, and the Windows **user-desktop PowerShell pipe** wrapper environment.
`retained-hdd-xemu.toml` records the lab ISO, HDD, EEPROM and MCPX paths. They are
private operator inputs, not bundled. All recorded launches reuse that HDD.
A new process is not a new disk image. Preserve the seed or restore a pinned
copy before attempting a matched cold-cache comparison; do not label these
runs as fresh-overlay tests.

`release64-job.json` uses the ordinary release xemu. The `*-probe-job.json`
files use release-optimized diagnostic xemu with `XEMU_SPIRIT_MENU_TRACE=1`.
The capture shim source is included; it wraps `xemu-real.exe` as `xemu.exe` and
captures the user desktop at 12, 30 and 60 seconds. Keep the window unobscured.
Use the lab's recorded `native-launch.exe` pipe bridge (hash in each manifest),
not a service-session launch. It must supply the real child QMP endpoint to the
runner for the 31-second pause/full-64-MiB RAM capture/quit plan.

With the payloads matching a recorded manifest in `PACKAGE`, and a checkout of
Mainkill1/xemu-test-runner providing `scripts/runner_transport.py` and
`scripts/runner_workflows.py`:

```sh
python3 tools/halo_menu_backtrace/replay.py \
  --runner-scripts RUNNER/scripts --url http://10.0.7.1:9368 \
  --request tools/halo_menu_backtrace/final-release64-job.json \
  --package PACKAGE --job-id halo-menu-UNIQUE-ID --output RESULTS
```

Reusing an executed package can fail hash verification because xemu writes its
configuration on exit. Restore original inputs rather than disabling the hash
check. The runner's completed status only proves collection, not menu health.

## Probe build and binding

Apply the matching `xemu-*-probe.patch` to xemu commit
`f3c528eeec86db32c9f96a932267105e83f77375`. Build with the release Windows
configuration and the gcc toolchain image
`ghcr.io/xemu-project/xemu-win64-toolchain-gcc:sha-2881edd`.
The IDE probes record HDD DMA sector payload hashes at submission/completion,
PIO buffers, and optical source/readback hashes; the Vulkan probe records
texture source hashes at use. The guest probes only read memory/registers.

The binding JSON pins BIOS SHA-256, exact function entry addresses, optimized
calling conventions, and IRP/MDL offsets. The kernel is ROM-backed at
`0x84000000`; its absence from a physical 0..64 MiB RAM capture is expected.
**Do not use a binding on another BIOS.** Re-derive entry addresses and calling
conventions from that build's `xboxkrnl.unstripped.exe`. LTO makes the adapter
entry `regparm(3)` despite its source declaration; assuming cdecl loses the
parent IRP. Request probes change scheduling, so confirm appearance separately
on the ordinary release emulator.

```sh
python3 tools/halo_menu_backtrace/analyze_requests.py \
  --trace RESULTS/ide-trace.log \
  --binding tools/halo_menu_backtrace/f4496a59-binding.json \
  --bios REJECTED/flash.bin --output before.json
```

`rejected-menu-chain.json` joins all 1,647 submissions and completions: 172
resource failures, all at attempted depth 65, including the missing menu
buffers. The queue-only candidate's `candidate-menu-chain.json` proves those
four menu reads succeed beyond the old cap, but still records **two allocation
failures** elsewhere at depth 213. Do not describe it as zero-error qualification.

## Check the visible entries and their data

`check_menu.py` requires Pillow and the 1296x759 Windows capture layout, Campaign
selected. Supply a known-good reference screenshot; the recorded reference SHA
is `e7dd5725e7526cde668c28d022ff286ca8a3b304a32f9c9ef08b01d777d376cf`.
It checks Campaign, Multiplayer, Settings and Game Demos separately. Its actual
missing-entry regression rejected Settings/Demos while passing the other two;
known-good before/after-reset screenshots passed. No game artwork is bundled.

```sh
python3 tools/halo_menu_backtrace/check_menu.py \
  --reference GOOD.png --candidate RESULTS/shim-capture-30s.png --output menu.json
python3 tools/halo_menu_backtrace/check_buffers.py RESULTS/menu-memory.bin \
  --output buffers.json
```

The buffer check covers four 16 KiB, 256x64 DXT3 labels at fixture-specific
physical addresses. Expected hashes were obtained from decoded valid labels in
ordinary-release captures; Settings from run `20261017-215548208-…` and Demos
from `20261017-215626146-…`. If allocation addresses change, trace the actual
textures and rebind; never classify unrelated bytes as corruption.
`release64-five-run-results.json` records five successful queue-only runs and
20 exact buffer matches. These results do not erase the two diagnostic failures.

The firmware patch carries production-function host tests for a 256-read burst,
payload association, queued cancellation, write/flush ordering, device removal,
compact data-only overflow allocation, and cancellation before admission. Run product integration with:

```sh
python3 -m unittest tests.host.test_nxstorage_production \
  tests.host.test_forza_corruption_regressions
```

## Compact-envelope follow-up

`compact-release64-five-run-results.json` records five ordinary-release launches
of `7e88501d…` with all 20 menu buffers matching valid labels. The three
`compact-menu-chain-*.json` files each join 1,646 successful requests, zero
resource failures, including a peak of 213 outstanding. Reproduce these using
`7e88501d-binding.json` and `xemu-7e88501d-probe.patch`; this patch also traces
envelope/child/control-MDL allocation returns and `MmAvailablePages`. The exact
allocation that failed twice in the prior `6b31d660…` run was not identified by
this later probe; the recorded request errors remain part of the evidence.

The final source also corrects cancellation that arrives before queue insertion.
The compact precursor results above are not a substitute for qualification of
that final binary.

## Final cancellation-corrected image

Use `final-release64-job.json`, `final-reset-job.json`, and
`final-probe-job.json` for BIOS
`add882b6f50e9c9ae49705bb8374be5646e44ed1b72f0e2eb4b77bdedeeaf296`.
The latter requires `xemu-add882b6-probe.patch` and `add882b6-binding.json`.
`final-request-summary.json` and `final-menu-chain-*.json` record two runs with
3,292/3,292 successful requests, no allocation failures, and 69 minimum observed
available pages at allocation returns. This is not continuous memory profiling.
The assembled source tree is `84e1d572b5a3a4ae81c78c28a0855908a909acf1`.

`final-release64-five-run-results.json` records five ordinary-release launches,
all four menu entries present and all 20 texture-buffer hashes matching.
`final-reset-results.json` records two further runs with all four entries present
before and after reset. All reuse the retained test HDD/EEPROM. These checks do
not qualify fresh-HDD initialization, a campaign, other games, or disc changes.
