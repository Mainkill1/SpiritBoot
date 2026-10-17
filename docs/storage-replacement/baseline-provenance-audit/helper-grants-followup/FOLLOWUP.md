# PR248 helper grants follow-up — investigator only

Date: 2026-10-14. This is bounded read-only provenance evidence. No product edits, Git mutations, replacement driver bodies, native runs, remote changes or outside messages were performed. Evidence does not certify legal compatibility, copyrightability, independent authorship or the completed candidate.

All 27 requested identities remain unresolved for an original grant compatible with the planned GPLv2 firmware combination. Their three actual source files and all 27 body hashes match the earlier P5 inventory. Positive baseline code evidence totals 103 inline occurrence records per release profile: 86 SDK/DDK records and 17 SCSI utility records. These are occurrence records with overlapping ranges, not exclusive function or byte totals.

The generated-header follow-up resolves four source-location gaps and locates scoped declared-grant evidence; it does not expand author input approval or certify all fragments of the generated headers.

## Exact per-chunk provenance

- `PORT_ALLOCATED_SENSE` and `FREE_PORT_ALLOCATED_SENSE_BUFFER` are present with exact baseline body hashes in [the 2010 initial header addition](https://github.com/reactos/reactos/commit/d732208205c5309e97aa128167b0907a737f406e). No original per-file grant appears in that inspected header notice. Their earlier appearance must be distinguished from the 2020 import.
- `GET_FDO_EXTENSON_SENSE_DATA_LENGTH` and all five SCSI utilities are absent in the parent `093f377c`, then present with exact baseline body hashes in [the 2020 definitions import](https://github.com/reactos/reactos/commit/3da77f91732177cfffe927d6be086416f1d9c67d). The old public-domain w32api notice on `scsi.h` is evidence for the original portion, not a recovered original grant for these later imported bodies.
- All 19 SRB identities are present at [the WDK 10.0.19041.0 import](https://github.com/reactos/reactos/commit/f0ffda34da65b9f805fdb50d97e329cc00622df2). Their baseline bodies differ from that import at the SRB-versus-extended-SRB discriminator; the remaining accessor code is retained. This adaptation is not evidence of independent rewriting. Their body equality to pinned Roswell remains true.
- All 27 identities are also found in original Microsoft WDK headers at the immutable [WDKmetadata revision](https://github.com/microsoft/wdkmetadata/tree/fbb3a13785073a707c6171bffbd5522438031732/generation/WDK/IdlHeaders). All five SCSI bodies and two class predicates have identical normalized tokens there. Other bodies differ and are recorded individually, rather than treated as exact Microsoft-byte matches. All three inspected Microsoft files name Microsoft and reserve rights in their opening notices.

Neither Microsoft metadata repository supplies an MIT relicensing shortcut for these headers: the [WDKmetadata license](https://github.com/microsoft/wdkmetadata/blob/fbb3a13785073a707c6171bffbd5522438031732/LICENSE) and [Win32metadata license](https://github.com/microsoft/win32metadata/blob/76c04c2021ef4a831a6f1e06d9566002d746139b/LICENSE) explicitly preserve original header licenses. The MIT metadata/tooling grant is separately scoped. Microsoft [published EWDK terms](https://learn.microsoft.com/en-us/legal/windows-sdk/license-terms-ewdk) restrict redistribution by platform and excluded-license conditions; this page was contextual primary evidence, not a recovered agreement binding the exact historical 19041 import. No original alternate compatible grant was found in this bounded review. Missing evidence is not proof that no permission could exist.

`HELPER-GRANT-EVIDENCE.json` records immutable URLs, response hashes, commit authors/dates, parent presence, per-file hashes, per-body/token hashes, and individual retained caller coordinates. Source bodies and token lists are omitted. The two 404 responses are for files absent in API-confirmed addition parents, not denied source access.

## Requested identity disposition

Resolved compatible original grants: none. All entries below require disappearance of the old compiled body or separate compatible original permission before this specific gate can pass.

| Header | Identity | Source body lines | Baseline occurrences/profile | Original compatible grant |
| --- | --- | ---: | ---: | --- |
| `classpnp.h` | `FREE_PORT_ALLOCATED_SENSE_BUFFER` | 1478–1488 | 1 | Unresolved |
| `classpnp.h` | `GET_FDO_EXTENSON_SENSE_DATA_LENGTH` | 1439–1460 | 2 | Unresolved |
| `classpnp.h` | `PORT_ALLOCATED_SENSE` | 1467–1471 | 1 | Unresolved |
| `srbhelper.h` | `SrbAssignSrbFlags` | 959–970 | 5 | Unresolved |
| `srbhelper.h` | `SrbClearSrbFlags` | 995–1006 | 3 | Unresolved |
| `srbhelper.h` | `SrbGetDataTransferLength` | 777–790 | 2 | Unresolved |
| `srbhelper.h` | `SrbGetScsiStatus` | 1049–1062 | 1 | Unresolved |
| `srbhelper.h` | `SrbGetSenseInfoBuffer` | 631–644 | 5 | Unresolved |
| `srbhelper.h` | `SrbGetSenseInfoBufferLength` | 650–663 | 4 | Unresolved |
| `srbhelper.h` | `SrbSetCdbLength` | 1106–1117 | 4 | Unresolved |
| `srbhelper.h` | `SrbSetDataBuffer` | 760–771 | 5 | Unresolved |
| `srbhelper.h` | `SrbSetDataTransferLength` | 797–808 | 5 | Unresolved |
| `srbhelper.h` | `SrbSetNextSrb` | 922–933 | 1 | Unresolved |
| `srbhelper.h` | `SrbSetOriginalRequest` | 723–734 | 7 | Unresolved |
| `srbhelper.h` | `SrbSetQueueSortKey` | 852–859 | 2 | Unresolved |
| `srbhelper.h` | `SrbSetQueueTag` | 866–877 | 1 | Unresolved |
| `srbhelper.h` | `SrbSetRequestAttribute` | 1144–1155 | 4 | Unresolved |
| `srbhelper.h` | `SrbSetScsiStatus` | 1069–1080 | 1 | Unresolved |
| `srbhelper.h` | `SrbSetSenseInfoBuffer` | 670–681 | 7 | Unresolved |
| `srbhelper.h` | `SrbSetSenseInfoBufferLength` | 688–699 | 13 | Unresolved |
| `srbhelper.h` | `SrbSetSrbFlags` | 977–988 | 8 | Unresolved |
| `srbhelper.h` | `SrbSetTimeOutValue` | 834–845 | 4 | Unresolved |
| `scsi.h` | `ScsiConvertToFixedSenseFormat` | 4062–4106 | 1 | Unresolved |
| `scsi.h` | `ScsiGetDescriptorSenseKeyAndCodes` | 3850–3880 | 5 | Unresolved |
| `scsi.h` | `ScsiGetFixedSenseKeyAndCodes` | 3794–3839 | 5 | Unresolved |
| `scsi.h` | `ScsiGetSenseKeyAndCodes` | 3897–3922 | 5 | Unresolved |
| `scsi.h` | `ScsiGetTotalSenseByteCountIndicated` | 3753–3783 | 1 | Unresolved |

Header SHA256 identities:

- `sdk/include/ddk/classpnp.h`: `003a4e8614e795ae63c33607f5bee05e8c65bf487f59612004de397f42ba62bd`.
- `sdk/include/ddk/scsi.h`: `574e1cdaecc9688fc3693d480a885a2bbf0af38aed1f2bc143e2198ee8bb62b5`.
- `sdk/include/ddk/srbhelper.h`: `962e4174486c480d6f7b52ed14a832a0ad6b8e8181094bd9fea14094963f3ffa`.

## Minimum engineering scope if grants remain unresolved

Removing the old disk/ClassPnP implementation, private header bodies and old optical integration eliminates the observed ancestry of these 27 helpers. SDK/DDK helpers have class caller coordinates. Some SCSI call coordinates are nested calls inside `scsi.h`; their recorded native parents remain class ancestry. A final independently linked candidate must re-audit actual native/inlined/merged ranges, macro aliases and generated closure. Removing names or includes alone does not prove body disappearance. The `SrbSetQueueTag` identity is also reached through the public alias `SrbSetRequestTag`; keep that alias in the disappearance check.

An independent author need only express operations actually required by the new legacy-SRB transport contract. The 19 former accessor identities do not require19 similarly shaped replacement functions. The three class helpers need no copied private-extension implementation; new sense-buffer ownership and size facts belong to the new driver. The SCSI conversion used by old class history may disappear with that history. Independently authored sense interpretation still needs the accepted public protocol behavior and error outcomes; a recreation of every old utility is not implied. If any old helper body survives, the unresolved grant remains live for that exact survivor. Distributed unused source retains its original notice obligations.

## Concrete generated helper gaps

The baseline broad audit had attributed two retained helpers only to generated `wdm.h`. The exact generated body hashes now equal `sdk/include/xdk/exfuncs.h`, and the CMake generator recipe binds`wdm.template.h` to that generated output. Both lookaside helper token bodies already match current source at [the 2010 XDK change](https://github.com/reactos/reactos/commit/0fb515fa5b6ca9d965457f65c1ea5d5f2f841066), whose WDM template already carries the named ReactOS public-domain notice. `exfuncs.h` itself supplies no separate per-chunk opening grant. This is concrete declared template-grant evidence with a historical body binding, rather than a grant inferred merely from a generated path. Original expression origin beyond this bounded history is not independently certified.

| Identity | Positive release64 records | Body SHA256 | Origin finding |
| --- | ---: | --- | --- |
| `ExAllocateFromNPagedLookasideList` | 1 | `24e909d1de1f5a58de5c6bf280cab532d9763de7b0581c40dd087e01881e5325` | Current tokens present at 2010 XDK change; template public-domain notice located |
| `ExFreeToNPagedLookasideList` | 1 | `ca99dadae5b396fe301695e98ff47d338cc50b6aa181ff0098a80296d17bc7ea` | Current tokens present at 2010 XDK change; template public-domain notice located |
| `ExAllocatePoolZero` | 6 | `7b1f7653bd5202d558d86871b9cad4e402815eaa2cb18dc2b36fc2fd9eba0629` | Exact body at 2020 ReactOS allocator introduction; independent-implementation assertion and template notice located |
| `ExAllocatePoolUninitialized` | 8 | `c0350f2c6a6539c549cdde97d68dd9e4b85c29a2b40eefdfc209ad03795319fa` | Exact body at 2020 ReactOS allocator introduction; independent-implementation assertion and template notice located |

The two allocators were generically unresolved in the broad CSV and are concrete survivors outside class ancestry: five storage `ExAllocatePoolZero` records, plus one kernel record, and eight lower-driver `ExAllocatePoolUninitialized` records. Their generated bodies exactly match current XDK source and the [2020 ReactOS introduction](https://github.com/reactos/reactos/commit/380cd27cf3dc2286d994d905556e15f2884b9746). That commit expressly describes a ReactOS implementation with a platform-specific zeroing policy; it does not establish a grant for the imported storage headers. The WDM template carries the declared public-domain grant at that point as well. The evidence therefore supports a narrower review of these bodies and notices rather than automatic removal of all generated headers. If that scoped declared grant is insufficient for the release policy, independently authored necessary operations or an explicit original grant remain the fallback.

These four mapping/grant-evidence findings are recorded separately from the 27 unresolved original-compatible-grant findings. The whole generated header remains excluded from independent author inputs because it includes unrelated imported pieces. Generator sources, notices and exact candidate-selected bodies need to be part of final source/notice closure.

## Filtered implementer-packet proposal

This paragraph is a proposal only; no approved author package was edited. Public legacy SRB field definitions and semantics can be supplied from the [official request-block documentation](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/srb/ns-srb-_scsi_request_block) and the already approved target ABI facts. Needed observable requirements are request fields round-trip without changing unrelated fields; response processing uses the actual returned transfer and sense lengths; owned sense buffers are released once after the last user; borrowed buffers remain with their owner; truncated or unrecognized sense data cannot trigger an out-of-bounds read; actual required status/retry outcomes follow the accepted contract. These are independently worded acceptance outcomes, not a source-shaped helper plan. Exact unknown baseline error policy must remain labelled unknown until measured or adopted explicitly. No helper bodies, private-extension layout, old token ordering or old internal decomposition should enter that packet.

## Exposure and verification limits

Investigator-only: read inherited P5 metadata and opening notices; loaded unfiltered baseline and upstream versions of 3 SDK/DDK files and 4 XDK/generated inputs in memory for hash/provenance analysis. Public search results incidentally exposed Microsoft classp.h/retry.c excerpts and an unrelated third-party driver excerpt; that unrelated source was not relied upon. Microsoft allocator commit diff was inspected as provenance. No replacement driver authored; no personnel independence or legal certification claimed. Output contains hashes/identity metadata and original prose, without source bodies or token lists.

No applicable local AGENTS.md was found in the inspected root, scratch parent or target trees. The OSS clean-room skill strict investigator profile was applied. The cloud-runtime skill was read; environment-status tool and executor policy snapshot were unavailable. Public primary-source browsing and read-only HTTPS retrieval succeeded. No credentials were inspected.

The existing P5 inventory and release64 CSV provide compiled-retention evidence. This follow-up neither builds nor executes a candidate, performs a fresh DWARF attribution, nor establishes storage high-water RAM. It checks the current selected source bytes against the prior inventory and upstream history. Scope excludes the 139 known sample/private-header identities; their required independent removal remains unchanged. No independent personnel-level clean-room claim is made.

Machine-readable records and collection scripts remain investigator-only scratch evidence, outside the product and approved author input package.
