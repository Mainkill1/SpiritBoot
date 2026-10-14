# SpiritBoot credits and project acknowledgements

The SpiritBoot setup menu exposes a three-page summary of the major open projects involved in its development. This document records the licenses of incorporated components separately from development and research acknowledgements. The on-screen v1.0.0 summary predates this audit and omits license identifiers.

**v1.0.0 audit status:** license compatibility is unresolved. The kernel statically incorporates MS-PL storage drivers alongside GPLv2 code. [Issue #245](https://github.com/Mainkill1/SpiritBoot/issues/245) tracks resolution; adding attribution does not resolve that combination. See the [audit writeup](provenance/license-audit-20261013/README.md) and [full notices supplement](provenance/license-audit-20261013/THIRD-PARTY-NOTICES.txt).

## Firmware and incorporated foundations

| Project / component | Contribution | License in the released source |
| --- | --- | --- |
| [SpiritBoot](https://github.com/Mainkill1/SpiritBoot) | Firmware integration, Xbox-compatible kernel work, setup, build/release and qualification tooling. | GPL-2.0 umbrella; upstream per-file notices remain in force. |
| [Roswell (nxkrnl)](https://github.com/mborgerson/roswell) | Pinned Xbox kernel and loader foundation, modified by the ordered SpiritBoot patches. | GPLv2 combined-work declaration; mixed per-file licenses. The MS-PL combination remains unresolved. |
| [ReactOS](https://reactos.org/) | NT kernel, HAL, filesystem, boot-video and runtime foundations. | GPL-2.0 / GPL-2.0-or-later, LGPL-2.1-or-later, MIT, BSD-2-Clause and BSD-3-Clause portions; individual headers govern. |
| [Cromwell](https://github.com/XboxDev/cromwell) | Loader startup/Xcodes and adapted PCI, SMBus and video initialization through Roswell. | GPLv2 / GPL-2.0-or-later portions; preserve original headers. |
| [xbox-linux](https://github.com/XboxDev/xbox-linux) | Conexant, Focus and Xcalibur TV-encoder drivers incorporated through Cromwell/Roswell. | GPL-2.0-only portions. This prevents blanket relicensing of the kernel to GPLv3. |
| [XZ Embedded](https://tukaani.org/xz/embedded.html) | Loader decompression in `boot/nxldr/xz/`. | 0BSD, as specified by the bundled SPDX headers and `COPYING`. |
| [Wine](https://www.winehq.org/) | RTL/CRT and SHA-1/RC4 code incorporated through ReactOS. | LGPL-2.1-or-later portions; preserve individual copyright and public-domain-origin notices. |
| [GNU C Library](https://www.gnu.org/software/libc/) | CRT `math/i386/pow_asm.s` supplied through ReactOS. | LGPL-2.1-or-later. Listed conservatively as a linked-library input; LTO may eliminate unused code. |
| Microsoft [Windows driver samples](https://github.com/microsoft/Windows-driver-samples) | `classpnp` storage library and `disk` class driver supplied through ReactOS/Roswell and statically linked into the kernel. | **MS-PL; compatibility blocker tracked in #245.** Microsoft's publicly licensed source remains copyrighted. |
| Other runtime contributors | ReactOS Portable Systems Group, Michael Ringgaard and University of California runtime/kernel portions, and other authors named in the source headers. | Individual MIT/BSD notices and disclaimers are reproduced in the full notices supplement. |
| [GCC runtime](https://gcc.gnu.org/) | The kernel link uses `libgcc`; the toolchain itself runs on the build host. | GPL-3.0-or-later WITH GCC-exception-3.1 according to the toolchain package notices, included in the supplement. The exact retained-member/eligible-compilation review remains open. |
| [LLVM](https://llvm.org/) | Recorded `sdk/include/vcruntime/emmintrin.h` compiler intrinsics header. | Apache-2.0 WITH LLVM-exception; the supplement includes the exception and full text. Compilation input does not by itself prove retained object code. |
| Boot font | ReactOS `fontdata.c` attributes an 8x13 Plan 9 font to Markus Kuhn; SpiritBoot uses an ASCII subset. | The C wrapper declares GPL-2.0-or-later. Original glyph permissions/provenance still require verification in #245. |

## Emulation, development and test partners

| Project | Role |
| --- | --- |
| [xemu](https://github.com/xemu-project/xemu) and the [SpiritBoot xemu fork](https://github.com/Mainkill1/xemu) | Primary emulator and hardware behavior qualification environment. |
| [QEMU](https://www.qemu.org/) | Underlying machine emulation framework used by xemu. |
| [nxdk](https://github.com/XboxDev/nxdk) | Open Xbox SDK, executable tests, API declarations and developer tooling. |
| [xemu-dashboard](https://github.com/xemu-project/xemu-dashboard) | Development/test hard-drive/dashboard image referenced by reproducible qualification fixtures. |

## Additional documented research references

| Project | Role |
| --- | --- |
| [Cxbx-Reloaded](https://github.com/Cxbx-Reloaded/Cxbx-Reloaded) | Xbox executable loading, API and compatibility research. |
| [xdvdfs](https://github.com/antangelo/xdvdfs) | Xbox optical disc filesystem research and reference. |
| [XboxDevWiki](https://xboxdevwiki.net/) | Xbox hardware and platform documentation. |
| [xboxpy](https://github.com/XboxDev/xboxpy) | Original Xbox hardware/software investigation utilities. |
| [xbox-linux](https://github.com/XboxDev/xbox-linux) | Historical Xbox platform research, in addition to the incorporated encoder code listed above. |

Thank you to the upstream maintainers, translators, testers, reverse-engineering researchers, and contributors who make open Xbox development possible.

**License and attribution notice:** The on-screen summary is not a replacement for copyright notices, full license texts, disclaimers or source availability. See the [SpiritBoot LICENSE](../LICENSE), [source lock](../sources/firmware-lock.json), the Roswell source's `COPYING`, `COPYING.LIB`, `COPYING.ARM`, component license files and individual headers. Preserve these when redistributing. SpiritBoot is supplied without warranty under the applicable license terms. This audit is an engineering inventory, not a legal certification. Development/research acknowledgements above do not assert that those projects' code ships in the BIOS.

**v1.0.0 source access:** The [release](https://github.com/Mainkill1/SpiritBoot/releases/tag/v1.0.0) supplies the exact patched [kernel source](https://github.com/Mainkill1/SpiritBoot/releases/download/v1.0.0/SpiritBoot-v1.0.0-kernel-source.tar.gz). The [product tag archive](https://github.com/Mainkill1/SpiritBoot/archive/refs/tags/v1.0.0.tar.gz) supplies build scripts, patches, source lock, Dockerfile, profile configuration and editable splash PNG. Both are needed for the project's full build inputs.

**Access:** Open SpiritBoot settings using X at cold boot, release the held button, press the controller's **Back** button to view credits, switch pages with D-pad, and press **Back** or **B** to return. No settings are committed by visiting the credits page.
