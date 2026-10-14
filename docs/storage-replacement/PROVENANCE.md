# Storage replacement source provenance and permission protocol

**Execution:** one PR, [#248](https://github.com/Mainkill1/SpiritBoot/pull/248), from implementation through final compiled firmware review. See [single-PR checklist](IMPLEMENTATION-CHECKLIST.md). Do not open independent implementation PRs or treat completed design documents as firmware license clearance.


**Purpose:** document a reproducible technical separation between observed behavior and protected implementation expression. This does not supply legal certification.

## 1. Known rights problem

The v1.0.0 release-audit (product `b65a3f77d9887c9285e936996eb4d286a66f540c`, Roswell `1569e2e89fb47cc72b9c704a8884f98200432bd4`, assembled source `3c23ea01cf43c2979c4c3ef247236e03d079f465`) identifies *actual compiled* Microsoft ClassPnP/Disk sample/private-header implementation under MS-PL, statically combined with GPLv2 material. It identifies 139 distinct source function bodies that have native/inline representation, not merely unused inputs. The FSF treats MS-PL as GPL-incompatible. ReactOS's published *runtime-linking* exception has not been shown to cover this static firmware. Credits/source release alone do not cure conflicting license conditions. Issue: [#245](https://github.com/Mainkill1/SpiritBoot/issues/245).

The report separately identifies 19 `srbhelper.h` and three `classpnp.h` helper names with surviving inline code where SDK/DDK-origin grants need evidence. Interface layouts/constants must be distinguished from substantial copied implementation. It also notes compiler runtime exceptions and component notices requiring separate review. Do not call every Microsoft-owned interface MS-PL; check the *actual grant*.

## 2. Clean-room process: two separate access levels

**Spec/verification team** can perform a read-only review of the old released implementation and source/binary audit, but should communicate only implementation-neutral requirements, public API behavior, environmental constraints, independently generated tests, and source/rights classifications. Keep proprietary or MS-PL expression out of implementer-facing requirements. This team's evidence should be archived with hashes and dates.

**Independent implementation team** receives approved requirements, open hardware/SCSI/ATA documentation, independently authored test cases, and source files whose compatible provenance has been established. Do not grant it access to `drivers/storage/class/classpnp/*`, `drivers/storage/class/disk/*` or MS-PL private headers as a coding reference. In particular, do not provide a reworded line-by-line conversion of `SubmitTransferPacket`, `DiskReadWriteVerification` or any original helper.

Many existing SpiritBoot reviews, including this planning effort, have already inspected implementation portions. Do **not** assert that such reviewers/authors are unexposed, or that access separation alone proves independent authorship. If implementing personnel have been exposed to original code, record it and obtain a separate provenance review; choose a different independent implementer where practical.

No prohibited material is to be copied into public tickets, specifications, prompts, generated code, or tests. A similarity tool can suggest research but **cannot establish** source independence on its own. Keep change-by-change design explanations and independent evidence.

## 3. Approved information categories and records

| Category | Can implementation reuse it? | Evidence |
| --- | --- | --- |
| Device names, IOCTL numbers, documented public structures, register and SCSI/ATA command descriptions | Generally usable as functional interface facts; verify any associated grant | Standard/public docs, black-box observation, own source |
| Independently written native/XBE host tests and observed return values | Yes, subject to their licenses and provenance | Exact test hash, source URL, seed/overlay, trace |
| Existing SpiritBoot-owned code and compatible ReactOS/Roswell GPL/MIT/BSD portions | Only with each applicable license and grant preserved | Per-file grant/copyright; exact reused lines/body |
| Microsoft ClassPnP/Disk implementation and private helper bodies | **No**, not as GPL replacement code without a separate compatible permission | MS-PL provenance audit, proof of non-incorporation |
| SDK/WDK headers or macros with uncertain terms | Hold nontrivial bodies pending review; independently write necessary helpers | Import revision, original notice/license, surviving code evidence |
| Compiler-generated templates/library routines | Use subject to compiler/runtime exception terms | Selected archive member, exception, eligible compilation proof |
| xemu, games, build/benchmark tools used as external references | Not firmware components unless actually linked/embedded | Build graph, source map, resource inventory |

**Candidate provenance ledger** (one record per material unit/function, not one blanket repository statement):
- Candidate file and commit/patch SHA, author and creation date.
- Upstream original file and exact grant, if any; line-level copied/adapted content only from permitted sources.
- Specification item + independent public reference/test ID.
- Whether implementer had access to Microsoft implementation; disclosure of uncertain origin.
- Code/layout ownership proof, compiled object/library and link command.
- Native, inlined and data attribution results for each released profile, including unresolved labels.

## 4. Build graph / firmware proof is not a source-tree search

A replacement release must satisfy all of these independent claims:

1. Build uses pinned input revision and ordered SHA256-validated patches. Source tree and final flash are reproducible and recorded.
2. Actual **final link command** contains no `libclasspnp.a` or `libdisk.a`, including response files and indirectly linked objects. Other archive transitive dependencies checked.
3. Linked unstripped PE/native symbols contain no old known Microsoft function identities; stripped names alone cannot establish this.
4. All surviving inlines/merged functions, generated code, linked headers/macros, data, resource and literal contributions have source attribution or explicit unresolved classification; no surviving MS-PL implementation. Recompare against original Microsoft import revisions when necessary using a separate audit team.
5. Separately clear the 22 SDK/DDK helper identities, and any other uncertain code. Retained compatible source keeps its original copyright notices and license terms.
6. GCC runtime exception applicability must be checked against compiler invocation pipeline; compiled helper bytes alone are not enough.
7. Distribute complete corresponding source/scripts/patches/artifacts under the governing terms, with full relevant notices. The source archive may still contain unused third-party files retaining their notices: distinguish archive contents from firmware incorporation.

The `tools/storage_migration_gate.py` sentinel catches *some* obvious errors (old archives, known symbol names, direct header references); it reports **PRECHECK_ONLY**, not “license compatible.” The full source-range analysis is separate and cannot be replaced with a count of archived source directories or search matches.

## 5. Review/publish hold

- New source files must declare their own actual license/copyright grant; do not retroactively declare another author's MS-PL code GPL.
- Be explicit about original files or fragments with uncertain rights; do not “clean up” away original notices.
- Preserve publication of existing historical sources/patches as required, but ship no old incompatible bodies inside candidate `flash.bin`.
- Every meaningful implementation change goes through a readable patch and a reproducible profile-qualified build; avoid a single large unexplained binary.
- Independent source provenance/legal review must sign off before changing issue #245 to resolved or claiming a “100% GPL” product. Any third-party permission request is separate.


## 6. Required restricted-source implementation package

Before implementation, construct a separately hashed, rights-reviewed package with `approved-inputs.json` listing per-file origin, author/grant/notice, allowed function (interface declaration, test, driver source), approved public hardware/ATA/SCSI specification and behavioral observation. Only approved GPL-compatible code/independently written tests and implementation-neutral requirements may be made available to the implementer. **Do not include** Microsoft `classpnp`/`disk` implementation bodies, private-header helper bodies, object archives, disassembly, a clone carrying hidden historical source, or source-generating tests that embed an old function.

Specifically, the existing `patches/roswell/0108-xbox-inactive-completion-clock.patch` created a host `storage-completion` fixture that extracts the complete original `TransferPktComplete` body from `classpnp/xferpkt.c`. That fixture **can remain in the exposed baseline audit environment**, but it must be removed from the independent implementation team's inputs and must not be counted as candidate validation. Independently produce/approve a behavioral test using **the actual new candidate functions** with provenance evidence. Document already-exposed personnel honestly; switching AI conversations does not prove clean-room independence.

## 7. Static source proof and preflight limitations

The current preflight in `tools/storage_migration_gate.py` has known false accepts for `-Wl,-lclasspnp`, `-l:libdisk.a`, comma-grouped `@response` references and fake nm text; tests also need clone suffix and stale-manifest scenarios. The tool must be repaired and bound to actual resolved linker inputs, binary/source-tree/flash hashes before it can be a release precheck. Even a repaired pass cannot identify all inlined/merged code or certify independence. Source function/inline/data attribution and the 22 unresolved SDK/DDK helper rights are a **separate final review**, not a regex check.

The product must retain original license grants and notices for compatible source and its full corresponding-source distribution. Do not promise that the firmware becomes a single-license project or that a performance success validates license compliance. Any final conclusion requires actual code/grant evidence and appropriate independent review.
