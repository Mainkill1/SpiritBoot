# Open firmware baseline — 2026-10-07

## Reproduced result

SpiritBoot builds an open Roswell flash and cold-boots its open API-regression
XBE in the Mainkill1 xemu fork without Microsoft BIOS or MCPX files. The
reproducible release image completed its entire 631-test TAP plan with **625
passes, 6 TODO gaps, 0 unexpected failures**, followed by clean emulator shutdown.
The checked image independently completed the same 631-test plan with the same
625/6/0 result and clean shutdown.

This establishes firmware execution, XBE loading, and the exercised kernel
behaviors. **Conker: Live & Reloaded has not been tested:** no game image was
available in this workspace. These results establish neither retail gameplay nor
physical Xbox support, audio output, controller behavior, or rendering quality.

## Exact inputs and environment

| Input | Identity |
| --- | --- |
| Roswell kernel/loader | `1569e2e89fb47cc72b9c704a8884f98200432bd4` |
| Mainkill1 xemu release | `458730bf5373f1f0d027450fef7443e3af7a3ae1`, `v0.8.136-0-g458730bf5373` |
| xemu AppImage SHA-256 | `e10b192a0402c7624525651ac7631dd7764e6a1b26d67fbb85ef8a4fdd563301` |
| Extracted xemu ELF SHA-256 | `3790019a2ccab47df1f67982e05856b2a345ec8ce5393967d1ed2187528aada2` |
| nxdk container | `ghcr.io/xboxdev/nxdk@sha256:bab707b7ed2544e9956d51e7b411a4575ab66120bd608b3237698495203d15f7` |
| Open API-regression XISO SHA-256 | `2057592eb3a43d88ff7746c55de7e2d685125c88b88e3a759ff6bab026ff1bec` |
| Open HDD fixture | xemu-dashboard `v20260516-0955` |
| HDD SHA-256 | `00d7df7a2bc235f8801764f00b7f40e194d1e392f7a9619d6b2396c89770f6dd` |

Build environment: pinned Ubuntu 24.04 base image, CMake 3.28.3, Ninja 1.11.1,
i686 MinGW GCC 13-win32, host GCC 13.3.0, Python 3.12.3. Runs used 128 MiB RAM,
Xvfb, Mesa llvmpipe software OpenGL, and dummy host audio. HDD writes were snapshot
overlays. The configured boot-ROM and EEPROM paths were empty.

The initial emulator target was main revision `e3798f995b9cbe1de3095b189a9370044a7db466`.
Its Actions binary download returned Forbidden in this environment. The pinned
public release above was retrieved, verified against the publisher's SHA256SUMS,
and reported the matching full commit in its runtime log. Newer renderer changes
on main are outside this baseline's evidence.

## Firmware and reproducibility

| Variant | Size | SHA-256 |
| --- | ---: | --- |
| Release | 262,144 bytes | `63b6e70fff47b464140bbff65fbe7090c6c4ea648106e12ba552640ae0945963` |
| Checked (`DBG=1`, `KDBG=FALSE`) | 524,288 bytes | `2aeb8cbe690b49b76d265a84e36e8b8531b724b954afdc29c3ba4dfd37c12f5a` |

Two independent clean release builds produced identical flash bytes. Initially
the hashes differed: PE timestamps in `xboxkrnl.exe` used wall-clock time. Exporting
`SOURCE_DATE_EPOCH=1788155396` (the source commit epoch) resolved this. The driver
uses a fresh configure tree on every invocation to avoid retaining old cached
compiler choices, flags, or timestamps.
Checked output includes build-path-dependent diagnostics and changed when the
build-directory layout changed; checked reproducibility is not claimed.

Roswell's README and older design notes describe a 1 MiB flash, but the pinned
`boot/nxldr/nxldr.ld`, CMake definition, and generator produce 256 KiB release and
512 KiB checked images. SpiritBoot validates those actual formats without padding
or modifying the upstream loader.

## Known TODO cases

The strict grader reports these separately from passes:

| Test | Known gap reported by the open suite |
| --- | --- |
| 178 `io/bad-ptr/set_eof_beyond_free_space` | FAT size-cap validation happens before free-space validation |
| 201 `io/storage/flush_volume_readonly` | Read-only volume flush returns access denied |
| 316 `ke/exceptions/x87_divide_by_zero` | xemu TCG does not raise the expected unmasked FP exception |
| 317 `ke/exceptions/sse_divide_by_zero` | xemu TCG does not raise the expected unmasked FP exception |
| 573 `ke/procprio/a_new_thread_starts_at_the_process_priority` | Process-priority propagation does not cover all title threads |
| 577 `ke/procprio/the_process_lists_its_threads` | Process thread-list publication is incomplete |

These are upstream test findings; none has been established as a Conker blocker.
No speculative kernel workaround was added.

## Local retained evidence and public verification

Ignored local evidence is stored in:

- `artifacts/final-release/` and `artifacts/final-repeat/`
- `artifacts/final-debug/`
- `artifacts/open-xbe-release-final/`
- `artifacts/verified-final-debug/`

Each build/capture records raw logs and JSON provenance. These directories are
not reference dependencies or tracked game data. The new Open firmware workflow
rebuilds both variants, compares clean release images, boots the open XBE, and
uploads build/capture evidence. A workflow definition alone is not a passing CI
result; consult the draft PR's checks for remote execution status.

## Provenance and licensing

Kernel, loader, and test implementation remain in an unmodified pinned Roswell
checkout. SpiritBoot adds original orchestration code and host fixtures; no
upstream kernel code or proprietary implementation was copied into this tree.
GPL-2.0 is the umbrella license already selected in foundation PR #2. Preserve
Roswell's GPL/MIT/BSD/LGPL/CC0 per-file notices when distributing its build.
The pinned public source URL and exact revision identify the corresponding source.

Sources: Roswell `README.md`, `docs/building.md`, `boot/nxldr/nxldr.ld`,
`boot/nxldr/CMakeLists.txt`, `gen-flash-bin.py`, and `tests/xbe/api-regression`;
Mainkill1/xemu published release and runtime banner; xemu-dashboard public release.
Follow [BUILD_AND_RUN.md](../BUILD_AND_RUN.md) to reproduce the commands.
