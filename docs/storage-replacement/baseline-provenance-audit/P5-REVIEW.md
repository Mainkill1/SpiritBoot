# P5 retained-source and measurement review

Read-only investigator review, 2026-10-14. No product/source/Git, VM or remote state was changed. Evidence belongs to the investigator; fresh authors must not receive the private names, original-body boundaries, history, binaries or audit packet. This report records engineering provenance and measurement limits, not legal certification.

## Decision scope

The baseline has confirmed retained Microsoft sample/private-header implementation under MS-PL. The exact prior function audit identifies 139 distinct source functions with retained representation: 65 distinct native identities represented by 66 symbols, plus 79 inline identities, with five shared between those sets. The original ClassPnP import is `88541f70c4273ecd30c8c7c72135bc038a00fd88`; Disk is `3428c5feaac7c1a5e2a09db0ed93392f7568f9e6`. Their original component/root MS-PL license blob is `6ef3ee38d1ce61958787dda3b8c669627b248080`. The prior audit's original comparisons are 89 exact bodies, three with identical C tokens, and 47 adapted bodies. These are source identities, not exclusive byte totals or a decision that every small accessor is independently copyrightable.

The separate 22 SDK/DDK helper identities also have positive nonzero inline evidence. Their original grant remains unestablished. They must not be called MS-PL merely because Microsoft originated the interfaces, nor GPL merely because ReactOS imported them. The old sample/private helpers and the unknown SDK bodies are independent closure questions. A complete candidate must eliminate old retained expression or establish an applicable compatible grant for each retained contribution.

Only baseline/partial laboratory builds exist in the inspected artifact directory. The release64 laboratory baseline and partial prototype both reproduce flash `c630d22f2353d3898024d510f0b402b64bccdb331781fe7885389f73d6200853`; that proves no firmware replacement in those artifacts. Archive/symbol preflight passes remain prechecks. A final complete candidate requires its own resolved-input, native/inline/generated/data/assembly provenance review and corresponding-source/notice receipt.

`P5-BASELINE-SOURCE-BINDING.json` compares the focused source-file hashes between the prior audit, composed source and exact completed release64 build. The completed build tree includes build-plumbing changes; it must not be silently called the prior composed Git tree. Its focused storage source bytes and reproduced flash bind the old retained-byte finding to this completed baseline. Debug configurations and a complete future candidate require their own retained-range analysis.

## All 22 SDK/DDK helper identities

`P5-HELPER-IDENTITIES.json` supplies every identity, source file SHA256, source-definition boundaries/hashes from the existing audit, all three profiles' nonzero ranges/call sites, engineering size label, grant status and source-comparison limitations. No bodies are included. Both actual composed header files match the audited SHA256:

- `sdk/include/ddk/srbhelper.h`: `962e4174486c480d6f7b52ed14a832a0ad6b8e8181094bd9fea14094963f3ffa`.
- `sdk/include/ddk/classpnp.h`: `003a4e8614e795ae63c33607f5bee05e8c65bf487f59612004de397f42ba62bd`.

Neither inspected opening notice supplies an original grant. `srbhelper.h` was imported by ReactOS `f0ffda34da65b9f805fdb50d97e329cc00622df2`, described as WDK 10.0.19041.0 synchronization. `classpnp.h` first appears in `d732208205c5309e97aa128167b0907a737f406e`, with newer storage declarations in `3da77f91732177cfffe927d6be086416f1d9c67d`. No alternate original permission was established here.

The 19 SRB helper definitions are legacy-field accessors in their actual retained subsets. Two class helpers are conditional size/flag predicates; the third handles sense-buffer ownership and includes deallocation. The numeric list is not grounds to claim 22 substantial queue implementations; actual body scope and grant still matter. None is a mere unused prototype: every listed identity has positive retained code evidence. A standard declaration, structure layout or constant need not import a helper body.

<!-- The complete table below is generated only from audit identity metadata. -->

| Header | Identity | Declaration line in focused audit | Nonzero occurrences per release profile | Retained subset |
| --- | --- | ---: | ---: | --- |
| `classpnp.h` | `FREE_PORT_ALLOCATED_SENSE_BUFFER` | 1475 | 1 | sense-buffer ownership helper; small retained subset |
| `classpnp.h` | `GET_FDO_EXTENSON_SENSE_DATA_LENGTH` | 1437 | 2 | conditional getter/flag predicate; small retained subset |
| `classpnp.h` | `PORT_ALLOCATED_SENSE` | 1464 | 1 | conditional getter/flag predicate; small retained subset |
| `srbhelper.h` | `SrbAssignSrbFlags` | 956 | 5 | inline legacy SRB field accessor; small retained subset |
| `srbhelper.h` | `SrbClearSrbFlags` | 992 | 3 | inline legacy SRB field accessor; small retained subset |
| `srbhelper.h` | `SrbGetDataTransferLength` | 775 | 2 | inline legacy SRB field accessor; small retained subset |
| `srbhelper.h` | `SrbGetScsiStatus` | 1047 | 1 | inline legacy SRB field accessor; small retained subset |
| `srbhelper.h` | `SrbGetSenseInfoBuffer` | 629 | 5 | inline legacy SRB field accessor; small retained subset |
| `srbhelper.h` | `SrbGetSenseInfoBufferLength` | 648 | 4 | inline legacy SRB field accessor; small retained subset |
| `srbhelper.h` | `SrbSetCdbLength` | 1103 | 4 | inline legacy SRB field accessor; small retained subset |
| `srbhelper.h` | `SrbSetDataBuffer` | 757 | 5 | inline legacy SRB field accessor; small retained subset |
| `srbhelper.h` | `SrbSetDataTransferLength` | 794 | 5 | inline legacy SRB field accessor; small retained subset |
| `srbhelper.h` | `SrbSetNextSrb` | 919 | 1 | inline legacy SRB field accessor; small retained subset |
| `srbhelper.h` | `SrbSetOriginalRequest` | 720 | 7 | inline legacy SRB field accessor; small retained subset |
| `srbhelper.h` | `SrbSetQueueSortKey` | 849 | 2 | inline legacy SRB field accessor; small retained subset |
| `srbhelper.h` | `SrbSetQueueTag` | 863 | 1 | inline legacy SRB field accessor; small retained subset |
| `srbhelper.h` | `SrbSetRequestAttribute` | 1141 | 4 | inline legacy SRB field accessor; small retained subset |
| `srbhelper.h` | `SrbSetScsiStatus` | 1066 | 1 | inline legacy SRB field accessor; small retained subset |
| `srbhelper.h` | `SrbSetSenseInfoBuffer` | 667 | 7 | inline legacy SRB field accessor; small retained subset |
| `srbhelper.h` | `SrbSetSenseInfoBufferLength` | 685 | 13 | inline legacy SRB field accessor; small retained subset |
| `srbhelper.h` | `SrbSetSrbFlags` | 974 | 8 | inline legacy SRB field accessor; small retained subset |
| `srbhelper.h` | `SrbSetTimeOutValue` | 831 | 4 | inline legacy SRB field accessor; small retained subset |


The focused inventory contains 86 occurrence records per release profile: 82 from 19 SRB names and four from three class names. The broad CSV resolves 85 records/21 names because its source-definition matcher misses one alias call. The focused record identifies `SrbSetQueueTag` through call token `SrbSetRequestTag`, at `retry.c:531`, release64 `0x8403e8ad–0x8403e8b1`, DIE `0x126787`. This is narrow macro/call-site evidence, not a count added from inclusion alone. Boundaries in the focused report and the later generic parser differ by two declaration lines; hashes and positive native ranges are authoritative, and both coordinate systems are retained in the JSON.

## Additional code and interface closure

| Contributor / input | Retention and grant facts | Minimal remaining action |
| --- | --- | --- |
| Sample class sources and private `classp.h` | Confirmed MS-PL retained bodies; private header has 24 nonzero inline occurrences in the narrow audit | Independent replacement must include private implementation, not just remove disk/class archives or rename calls; re-review all actual inline/data/merged ranges |
| Sample `debug.h`, `disk.h` | Include dependencies established; release gates many diagnostics; narrow audit finds no retained disk.h inline body | Exclude from fresh inputs; do not turn inclusion into an extra retained-body claim; inspect exact candidate closure |
| `scsi.h` utility portion | Five distinct utility identities / 17 nonzero inline records per release profile; actual file SHA256 `574e1cdaecc9688fc3693d480a885a2bbf0af38aed1f2bc143e2198ee8bb62b5` | Unknown newer helper-body origin remains open despite old w32api public-domain notice; eliminate these bodies with the class code or independently write required protocol behavior |
| `scsi.h` interface prefix and `srb.h` | Old Casper Hornstrup public-domain w32api opening grants; newer material import requires scoped review; no srb.h nonzero inline body attributed by the broad audit | Fresh inputs use scoped public declarations/numeric facts; no blanket new-helper authorization; ordinary field access can be independently expressed |
| `storduid.h` / `storswtr.h` | 14/18 compilation dependencies in the old focused closure; same WDK import, no original grant notice; no retained nontrivial body identified by that narrow audit | Do not copy whole headers. Export only necessary public interoperability declarations after exact dependency review; absence of recognized bodies is not a broad rights conclusion |
| Generated WDM/header helpers | Broad audit positively records two lookaside helpers and preserves generic/generated inline uncertainty; generated location alone does not establish original authorship | Fresh target packet supplies callable prototypes and numeric ABI facts; necessary header-only operations require independently authored helpers, not wholesale generated-header approval |
| `ntstrsafe.h` | 15 nonzero inline records in the broad release64 audit; public-domain opening notice recorded, with scope check explicit | Retain original notice if grant covers actual used bodies; do not infer its licensing from excluded class callers or expand author input approval incidentally |
| CSQ and SPTI support | CSQ source GPL/interface public domain, explicitly described as independent Vizzini clone; SPTI MIT by Dmitry Borisov, introduction `b558596409030b3d1a42f8474c7292f938611c1f` | Retain actual notices/grants for survivors; absence of original MS sample expression is not assumed solely from similar API names |
| Microsoft CRT and annotations | Official CRTSource 10.0.22621.3 MIT import `04e0dc4a7a18bb1ab69f7ae9720259786025c530`; annotation headers identify ChakraCore MIT | Preserve scoped Microsoft MIT notices. These are compatible grants separate from sample/WDK origin questions |
| Geometry response wrapper | Conservative single-wrapper replacement appropriate; prior attribution did not establish copied substantive whole body; public sizes alone are interface facts | Use independent composer/adapter packet and measured initialized-prefix behavior. Do not accuse or rewrite all partmgr without evidence; retained unknown `utils.c` grant remains separate |

The extra five SCSI utility identities and all their exact records are in the helper JSON, outside the author package. All observed old calls are inside sample class/disk ancestry, so independently removing that ancestry can remove the old inlines. The final candidate must prove that it did: names/includes alone are insufficient.

The focused supporting-header dependency review confines the four private WDK helper headers to class/disk/old optical compilation units; it found none in the nonclass compilation targets. That is baseline evidence, not permission to expose hidden dependencies to a fresh author. All unlisted fresh inputs remain excluded.

`P5-REMAINING-GRANT-SCOPE.json` retains release64 source groups with MS-PL, unspecified/unknown per-file grants, or generated-origin classifications, including source hashes and exact native/inline records. A project-level GPL declaration and missing individual notice are recorded separately. Unknown origin is an unresolved evidence question, not proof of incompatible rights. The original full inventories retain generic inline rows without enough attribution; the final candidate cannot silently count them as independent or removed.

## Compatible components, source and notices

The minimum externally compatible notice/source closure is the actual surviving kernel/HAL/runtime/filesystem/driver graph and generated inputs, with each existing GPL-2.0-only/GPL-2.0-or-later, BSD, MIT and public-domain notice preserved. Do not relabel all code under one new license. The exact native/inline/data/assembly inventories and final build dependency graph must bound this scope; a repository directory list cannot.

The retained RTL resource/error and cryptographic SHA1/RC4 sources declare LGPL-2.1-or-later. Preserve their original Wine/other notices and source, and document the chosen applicable combination route. Xbox encoder and PCI code incorporates xbox-linux/Cromwell GPL source, including GPLv2-only encoder material; a blanket GPLv3 relabel cannot resolve an unrelated incompatible contributor. Per-file-unknown CRT assembly and Roswell loader files remain marked project-grant/individual-origin uncertainty, with no invented author names.

For the loader, preserve original full Cromwell startup/Xcode GPL-2.0-or-later notices naming Andy, Michael, Paul, Steve and Lehner Franz, along with modifications. The XZ Embedded decoder has 0BSD source/grant text and Collin/Pavlov/upstream authors; a generated CRC table is runtime BSS, not a compiled 1KiB ROM asset. Preserve public-domain misc-fixed font base plus Roy Tam's GPL-2.0-or-later glyph edits; the edited font cannot be credited as an unchanged public-domain import. The existing exact fox asset provenance records the user's ownership and authorized project use. Development tools such as xemu/nxdk do not become firmware contributors just because they were used in testing; their separately distributed artifacts have their own scope.

Unused files still present in a distributed source archive keep their original licenses/notices even when no firmware code survives. A narrower candidate source release must still provide the exact corresponding source, configuration, generated input definitions, patches and build/install machinery required by the actual chosen distribution terms. This report does not decide a new legal distribution method.

## GCC runtime exception checkpoint

Five retained division/remainder helpers derive from `libgcc2.c`; the actual stack probe is `libgcc.a(_chkstk_ms.o)`. The prior stack-probe review matched all 44 retained machine bytes in every release profile against the actual archive member and an original GCC13.3 `cygwin.S` recompilation. Its original source and `i386-asm.h` declare GPL-3.0-or-later WITH GCC-exception-3.1, with FSF/Steve Chamberlain and FSF/Daniel Santos notices respectively. Preserve the runtime notices plus GPLv3 and Runtime Exception3.1 texts in source/notice evidence; compiler package identity alone is insufficient.

The exact release64 completed link receipt selects `/usr/lib/gcc/i686-w64-mingw32/13-win32/libgcc.a`, SHA256 `af096e7591413be61256c91cfb6f7e69053e80b80f7aa33015ec9c39323c96ed`. The prior executed-build review counted 739 graph commands/537 GCC commands. This checkpoint's read-only refreshed Ninja graph contains 739 commands/538 commands mentioning GCC or G++, with zero plugin/alternate-optimizer strings; the predicate and command hash differ, so these are distinct count receipts. Actual successful link/postprocess/pack receipts bind the graph to the exact final PE and flash. The postprocessing operates on target PE bytes, not an identified non-GPL optimizer of GCC intermediate representation.

The published [GCC Runtime Library Exception3.1](https://raw.githubusercontent.com/gcc-mirror/gcc/releases/gcc-13.3.0/COPYING.RUNTIME) grants a specific target-code combination permission under its independent-module and eligible-compilation conditions. The graph and byte-origin evidence support this ordinary GCC path; they do not certify every condition, authorize unknown SDK source or cure MS-PL/GPL combination problems. Recheck the actual selected members and complete candidate pipeline before declaring final closure. GNU web pages timed out during this checkpoint; the exact primary GCC13.3 runtime exception text was successfully browsed and prior primary grant evidence remains pinned locally.

## Exact baseline storage-cost measurements

`analyze-p5-artifacts.py` reads existing artifacts only, verifies each recorded flash hash, decodes the loader ELF's payload offset, reads the 12-byte payload header, validates XZ decompressed size against PE image extent, and validates ROM-table span CRCs and zero-filled replaced RAM spans. `P5-ARTIFACT-ACCOUNTING.json` contains paths, source/worktree identities, PE section/page facts, compressed hashes, raw ROM spans and exact build/link/postprocess/pack references.

The six selected comparator builds have successful, hash-verified link/postprocess/pack execution receipts. Deliberate preflight configuration fixtures are outside this comparison set; their existence is not an additional performance-qualified candidate.

| Existing artifact | Flash envelope | XZ prepared image | Raw immutable ROM | Header + XZ + raw ROM | Static whole-image RAM model after discard/ROM |
| --- | ---: | ---: | ---: | ---: | ---: |
| release64 baseline | 524288 | 46816 | 380928 | 427756 | 57344 |
| release128 baseline | 262144 | 218988 | 0 | 219000 | 438272 |
| upper-reserve128 baseline | 262144 | 219004 | 0 | 219016 | 438272 |
| debug64 baseline | 524288 | 279872 | 0 | 279884 | 684032 |
| debug128 baseline | 524288 | 279884 | 0 | 279896 | 684032 |
| partial laboratory release64 | 524288 | 46816 | 380928 | 427756 | 57344 |

All values are bytes. The RAM column is arithmetic for the entire mapped kernel image minus exact immutable ROM spans and complete discardable-owned pages. It assumes the qualified loader/kernel mapping and discard contracts; it is not a new native PTE/pool measurement, exclusive storage RAM or peak. The release64 image extent is 573440 bytes; 380928 bytes are replaced by raw ROM pages and 135168 belong to complete discardable pages. Its resulting model is 14 RAM pages. Release128 has no ROM replacement and leaves 107 pages; debug leaves 167 pages. Decompression touches the prepared image before donation/replacement; steady-state arithmetic must not be reported as boot peak.

Storage-attributed code can be counted as a union of positive native/inline machine intervals, with section/ROM mapping classification, using the pinned source-prefix scope. The script includes that engineering union and named data locations. It must not sum nested inline/native ranges, assign merged code exclusive ownership, equate code bytes with RAM, or turn neighboring COFF labels into data sizes. The existing attributed-data CSV lacks allocation extents, so it cannot establish an exact storage-static-data total. A final static-data count needs DWARF variable types/sizes or exact linker input/section records with alias overlap resolved.

For a complete candidate, use the same exact build/profile, compression flags, image preparation and packer; compare header + XZ + raw-ROM payload, not padded flash capacity or separately compressed source/function fragments. Compression interactions prevent an exclusive per-function compressed-byte sum. Total payload delta is a reproducible firmware comparison, not exclusive storage authorship.

**Native peak storage RAM remains unmeasured.** Every inspected build records `pool_audit=false`, and there is no matched storage allocation high-water trace here. Exact static/ROM counts cannot recover per-device extension, cached IRP/MDL/SRB, sense/bounce buffer, queue, retry/timer or dynamically allocated request lifetimes. The bounded measurement needs a matched baseline/candidate accounting stream at allocation/free and device/request lifetime boundaries, covering storage-owned pools and borrowed/shared allocation policy, with actual concurrent high-water values and all retained cached objects included. Report resident retained allocations separately from peak transient allocations; cross-device simultaneous peaks must use one time-consistent stream. Do not sum independent category maxima or substitute emulator process RSS/whole-kernel free pages for storage peak. Stack usage needs a separate measured bound if included in the claimed metric.

## Exposure and open evidence

Investigator exposure includes previous inspected caller/lower/kernel bodies, prior audit metadata, partmgr wrapper and status-only utility bodies, and one public Microsoft Disk geometry function during the earlier attribution task. No ClassPnP/disk body was newly inspected for this P5 checkpoint. Opening notices of four unknown WDK headers were observed, including an incidental SRB-fold macro in the opening of one header; no expression from that helper was exported. The declaration probes preprocess target headers, which can contain excluded inline helpers; their emitted objects have zero executable text, and full headers/dependencies remain investigator-only. No personnel-independence certification is claimed for this investigator. Fresh authors must stay limited to their approved package and record their own exposure.

Remaining evidence: complete independently linked candidate, native P1 verdict, actual storage-memory high-water traces, final private-body elimination check including the 22 and five extra SCSI bodies, unknown/generator source grant resolution, runtime selected-member/eligible-compilation recheck, and exact corresponding-source/notice package. No current design document, host-test result, hash equality, or regex precheck closes those items by itself.
