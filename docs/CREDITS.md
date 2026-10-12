# SpiritBoot credits and project acknowledgements

The SpiritBoot setup menu exposes a three-page summary of the major open projects involved in its development. These credits distinguish components incorporated into the firmware from software used for testing, research, and compatibility comparisons. They do not imply that every reference project's code is linked into SpiritBoot.

## Firmware and incorporated foundations

| Project | Contribution |
| --- | --- |
| [SpiritBoot](https://github.com/Mainkill1/SpiritBoot) | Independent firmware integration, Xbox-compatible kernel work, boot setup, build/release and qualification tooling. |
| [Roswell (nxkrnl)](https://github.com/mborgerson/roswell) | The pinned Xbox kernel and flash/loader foundation modified by SpiritBoot's ordered patches. |
| [ReactOS](https://reactos.org/) | NT kernel and boot-video foundation underlying Roswell. |
| [Cromwell](https://github.com/XboxDev/cromwell) | Original Xbox boot and low-level video/hardware initialization reference; portions are adapted through Roswell with their individual notices. |
| [XZ Embedded](https://tukaani.org/xz/embedded.html) | Decompression routines bundled under Roswell's `boot/nxldr/xz/` for the compressed kernel image. |

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
| [xbox-linux](https://github.com/XboxDev/xbox-linux) | Historical Xbox platform and driver research. |

Thank you to the upstream maintainers, translators, testers, reverse-engineering researchers, and contributors who make open Xbox development possible.

**License and attribution notice:** The on-screen summary is not a replacement for legal notices, authorship records or per-file copyright headers. See the [SpiritBoot LICENSE](../LICENSE), its [source manifest](../sources/firmware-lock.json), [Roswell COPYRIGHT/LICENSE](https://github.com/mborgerson/roswell), and all copied/adapted source headers for authoritative notices. The set of transitive components can change over time; keep this document and the boot credits updated as the implementation evolves.

**Access:** Open SpiritBoot settings using X at cold boot, release the held button, press the controller's **Back** button to view credits, switch pages with D-pad, and press **Back** or **B** to return. No settings are committed by visiting the credits page.
