# SpiritBoot v1.0.0 license and release audit

Audit date: 2026-10-13. **Result: unresolved release compatibility blocker**, tracked in [#245](https://github.com/Mainkill1/SpiritBoot/issues/245). This is an evidence-based engineering audit, not legal certification. The documentation changes do not change or requalify the published BIOS.

## What the release contains

The 64 MB BIOS is SHA256 `c630d22f2353d3898024d510f0b402b64bccdb331781fe7885389f73d6200853`. Its product revision is `b65a3f77d9887c9285e936996eb4d286a66f540c`, Roswell base is `1569e2e89fb47cc72b9c704a8884f98200432bd4`, and assembled kernel source tree is `3c23ea01cf43c2979c4c3ef247236e03d079f465`.

The project uses copyrighted open-source code under its authors' licenses. Roswell incorporates ReactOS, Cromwell/xbox-linux, Wine and other components. Microsoft publishes storage driver samples as open source under MS-PL; ReactOS imported that implementation and Roswell carries it. Copyrighted open-source code and a proprietary Xbox BIOS dump are distinct provenance questions. The finding below concerns the former.

The bundled `media/doc/3rd Party Files.txt` identifies Microsoft's driver-sample repository and import versions: ClassPnP `88541f7`, Disk `3428c5f`. Microsoft's [storage sample documentation](https://learn.microsoft.com/en-us/windows-hardware/drivers/samples/storage-driver-samples) describes those two components. Their copyright and MS-PL notices already exist in the pinned Roswell base; SpiritBoot inherits them through that dependency.

The release currently provides GPLv2 `LICENSE`, all 28,893 tracked files of the assembled Roswell source, a source/build manifest, checksums and a fix writeup. The kernel source includes CMake/interface files, loader/flash assembly scripts and its upstream license files. The product tag archive contains the build wrapper, ordered patches, source lock, toolchain Dockerfile, profile options and editable splash PNG. The credits now link both source sets directly.

## Static storage link: unresolved

Both of these files in the shipped source contain MS-PL, including its source-redistribution clause:

- `drivers/storage/class/classpnp/license.txt`
- `drivers/storage/class/disk/license.txt`

The actual kernel link line includes `drivers/storage/class/classpnp/libclasspnp.a` and `drivers/storage/class/disk/libdisk.a`. Their CMake targets are static libraries linked into `xboxkrnl.exe`. The qualified release kernel's symbol table retains:

```text
8400c400 T _ClassInitialize@12
8400c45c T _ClassInitialize@12.part.0
8400d270 t _ClassReadWrite@8
84078a40 T _DiskDriverEntry@8
8400fe58 t _DiskReadWriteVerification@8
```

This establishes actual compiled storage code in the BIOS, beyond an unused source directory. The source's Roswell README declares the combined kernel GPLv2 and identifies GPLv2-only xbox-linux encoder code. Changing the umbrella license to GPLv3 is not a general solution.

The [FSF classifies MS-PL as GPL-incompatible](https://www.gnu.org/licenses/license-list.html#ms-pl). [Microsoft's license text](https://learn.microsoft.com/en-us/previous-versions/msp-n-p/ff649456(v=pandp.10)) requires preservation of notices and source redistribution under MS-PL. Microsoft's [Windows-driver-samples repository](https://github.com/microsoft/Windows-driver-samples/blob/main/LICENSE) still declares MS-PL when checked during this audit.

[ReactOS's published linking exception](https://reactos.org/intellectual-property-guideline/) describes runtime linking of modules. It does not establish permission for this static Roswell/SpiritBoot combination. ReactOS also [documented the MS-PL/GPL linking concern](https://reactos.org/project-news/september-2015-meeting-minutes/). This audit has not established an applicable exception or alternative license grant; do not claim the combined release is license-compliant until that is resolved.

The engineering remedies are documented applicable permission, or compatible replacement storage code followed by game/save/API/performance qualification. Relabeling the source, removing headers, or adding MS-PL to credits does not resolve compatibility.

## Attribution and packaging changes

The original credits named projects without license identifiers and classified xbox-linux only as research, even though its encoder code is incorporated. [CREDITS.md](../../CREDITS.md) now identifies component licenses, actual incorporation, full-notice/source access and unresolved findings. Development/test tools remain acknowledgements rather than firmware component claims.

[THIRD-PARTY-NOTICES.txt](THIRD-PARTY-NOTICES.txt) supplies the actual GPLv2, LGPLv2.1, ReactOS BSD, XZ 0BSD and Microsoft MS-PL license texts, MIT terms, and original copyright/license comments from 739 source/header inputs. It preserves names, conditions and disclaimers rather than only listing SPDX identifiers. It does not authorize an incompatible combination.

The supplement also includes [LLVM's Apache 2.0 license with LLVM Exceptions](https://llvm.org/LICENSE.txt) for the recorded `emmintrin.h` input, and the toolchain's GCC runtime package copyright/exception plus GPLv3 text. The LLVM exception includes a GPLv2 combination waiver and embedded-object provisions; do not classify this input as plain Apache-2.0 without its exception. Package-wide compiler notices are included for clarity and do not assert all listed compiler components ship in the BIOS.

[build-inputs.json](build-inputs.json) records 540 source/resource link inputs, 26 archive dependencies and the retained storage symbols. The notice collection also considers source headers recorded in the qualified build. These are conservative compilation inputs, not proof every function survives LTO. Host tools, test programs and other unbuilt directories present in the large Roswell source archive are not all firmware components. The original per-file notices remain authoritative.

The audit checks the 64 MB build directly. The same source/link configuration is used for the 128 MB builds, but profile-specific retained-code inventories remain part of the closing audit.

## Remaining release gates

- Resolve static MS-PL/GPL compatibility and audit the replacement/permission's full dependency closure, including supporting headers and Microsoft sample-derived code.
- Preserve copyright, license and disclaimer notices with binary distributions. Keep full notices separate from the short on-screen credits.
- Verify compiler runtime members and the applicability of the GCC Runtime Library Exception; record exact toolchain/runtime license material.
- Add explicit dated modification notices where GPLv2 section 2(a) requires them. For example, SpiritBoot modifies `ntoskrnl/xb/crypto.c`, but its released header does not identify those changes or their date. Repository patch history is available but is not itself a notice carried by each modified file.
- Verify the original boot-font glyph permissions and provenance. `fontdata.c`'s GPL header and attribution do not by themselves establish the original glyph license.
- Update future on-screen credits with license identifiers, no-warranty information and notice/source pointers; preserve the currently approved v1.0.0 ROM bytes.
- Make patched kernel source and product build/asset source directly available together, with hashes and clear rebuilding instructions. Do not describe GitHub's product-only automatic source archive as the assembled kernel source.
- Check all released profiles and enforce these gates before declaring a replacement release compliant.

GPLv2 [sections 1–3](https://opensource.org/license/gpl-2-0) cover notices, modified-file notices and complete corresponding source, including scripts controlling compilation/installation. Adding a license column is useful, but it cannot replace those obligations or solve incompatible licenses.

## Validation and limits

The source package was previously checked against all 28,893 Git-tree blobs. This audit independently read the actual build graph, bundled license files, source headers and unstripped release symbols. The JSON records the firmware hash and exact license-file hashes. Documentation and added release supplements do not modify the three published BIOS assets or the original source archive.

No legal certification, exhaustive provenance validation of every transitive file, physical-console qualification or resolution of #245 is claimed. The source and functionality checks remain valid evidence of their respective claims; they do not substitute for license compatibility.
