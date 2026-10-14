# PR #248 implementation evidence and open gates

Status: **draft; bounded independent primitives exist; full storage replacement is not implemented or qualified.** The old storage classes remain in the reference BIOS. This document is part of the one implementation PR, not a separate release or compliance claim.

## Product and native reference

The baseline is SpiritBoot v1.0.0, commit `b65a3f77d9887c9285e936996eb4d286a66f540c`, Roswell `1569e2e89fb47cc72b9c704a8884f98200432bd4`, original assembled tree `3c23ea01cf43c2979c4c3ef247236e03d079f465`. The first successful recorded-link reference build assembled tree `ce9753a1cc7f7d505c4e59ea6f3c7197d84b99d8` and reproduced the released 64 MB ROM exactly: `c630d22f2353d3898024d510f0b402b64bccdb331781fe7885389f73d6200853` (524,288 bytes). Its source check verified 28,893 tracked files and 228 resolved link inputs. The composed tree changes because build evidence is now explicit; reference driver code remains unchanged. The later owned primitive tree `f587be12d98af88541e137391e27ced142ea5b74` also reproduced the published reserved128 release SHA256 `2632d513d84bf165d3a916b135cc387af6ee414b9f4bfbef334163752f022836`. Reference128 on the first primitive tree `9fb0951a3cfc10d49c456406dcb6382bfcff2cf2` reproduced `dc9de407a5440ff4f0331947661540a2137cbc27f25bb1b3c89f085ee4d04ec4`.

The recorded [reference build matrix](reference-build-matrix.json) also includes successful debug64/debug128 builds on source tree `09c33a8e198446e428e16854eaa0bfc0b89c942c`; these are reference-driver builds, not candidate qualification. The latest product host run passes 224 tests with three skips.

Two failed build attempts remain recorded: the initial source verifier incorrectly rejected Git's intentional CRLF checkout of `.mc` files, then GNU ld's synthetic PE `dll stuff` input was incorrectly treated as a missing file. Regressions now cover both. A diagnostic relink without the pinned epoch differed only at the kernel timestamp and PE checksum (five bytes); all loaded sections and all 5,582 defined symbol/address identities matched. The successful clean builder uses the pinned epoch and matches the complete ROM.

Operator-approved rigs (2026-10-14): Steam Deck `10.0.0.42` primary; Windows `10.0.7.1` secondary, actual Ryzen 9 6900HX rather than the originally named i9. No machine averaging. Windows graphical launch/control must use the PowerShell pipe in the logged-in Codex desktop; service/session-0 runs do not qualify. The owned bridge proof verified protected current-user pipe access, Codex/session1 server and client, and actual `WinSta0/Default`. It intentionally launched no guest and is a bridge proof, not a performance pass.

## Internal split

`0126-storage-backend-evidence.patch` introduces required explicit states from CLI through CMake, actual link evidence, and `build.json`:

| State | Current meaning |
| --- | --- |
| `legacy-reference` | Existing classpnp/disk/nxcdrom; baseline only |
| `partial-lab-prototype` | Bounded owned nxstorage library plus the legacy driver stack; no independent FDO adapter yet; not publishable |
| `complete-candidate` | Requires implemented independent kernel adapter and rejects old linked classes through actual preflight; currently unavailable and rejected |

The partial64 build compiled the actual nxstorage archive, whose unused primitives are then removed by the linker; its ROM remains byte-identical to released64. This proves the build separation, not that native I/O executes the new core. One kernel and one `flash.bin` remain the product format. Different backends require separate output directories; absent/unknown backend and requested/configured mismatch fail. CI explicitly builds the legacy reference; passing that matrix does not qualify replacement behavior.

The existing two-pass INIT placement is preserved. Recording occurs around the compiler invocations that actually execute, including their original argv, expanded/hashes of response files, inputs, map and original linked snapshot. The existing relocation removal/export fixups and flash packer also record consumed input/output hashes. Postprocessing preserves actual linked COFF identity; the final kernel is bound to packaging and published ROM bytes. GCC response escapes are tested against a real compiler, including escapes inside both quote modes. Git canonical tree identity and exact checkout bytes are separately checked. Wrappers invalidate old successful receipts before argument validation, so a rejected standalone attempt cannot retain an earlier pass. Transient LTO inputs and GNU ld synthetic inputs are explicitly recorded; missing ordinary inputs fail.

These unsigned records establish consistency, not authenticated execution or legal certification. Generated/untracked compile inputs and optimized inlines still need the final compiled-source review. The checker remains `PRECHECK_ONLY_NOT_LICENSE_CERTIFICATION`.

## Independent implementation

The [approved inputs](clean-room-inputs/approved-inputs.json), [caller matrix](clean-room-inputs/CALLER-MATRIX.md), [behavior contract](clean-room-inputs/CONTRACT.md) and [geometry contract](clean-room-inputs/GEOMETRY-WRAPPER-CONTRACT.md) were supplied to fresh implementation roles without old class source, old source-extract tests, private helpers, Git history or disassembly. Prior investigator exposure and author access are recorded separately. This is scoped input separation, not a claim of personnel-level or final legal certification.

`0127-independent-storage-primitives.patch` carries byte-identical independently authored production request engine and geometry composer plus their own tests. It does not replace the native adapter or nxcdrom yet. The request core uses fixed slots, iterative segmented commands, actual completion bytes, explicit write/flush barriers, real cache-sync, generation/duplicate guards, bounded queue recovery, and ownership-preserving cancellation. No heap/worker/clock/bounce dependency exists in the core. Sector shifts replace a generic 64-bit division helper. Write-through retains one parent through data and real synchronization. Its error/Information policy is explicit candidate behavior, not claimed observed parity.

The geometry composer emits initialized complete prefixes and MBR/GPT/RAW/BRFR metadata from a caller-provided stable snapshot. Its first policy returned only complete records and failed the observed40-byte return-count contract. A tested policy revision now returns all initialized available bytes up to112, clears unavailable tails, and emits meaningful optional records only when complete fitting. It matches the seven observed counts32/40/56/64/112/112/112; size-zero unavailable markers are an explicit legacy compatibility convention, not a claim of valid standard records. Full native adapter parity and retained-owner synchronization remain unqualified. The ambiguous retained partmgr wrapper has not been replaced yet; substantive whole-body copying was not established by the narrow investigation.

Latest imported primitive tests: 42 deterministic plus 8 real-thread request scenarios under ASan/UBSan; 13 geometry scenarios and 6,001 checks; i386 objects with no undefined helpers. The same source bytes compile in the assembled source host checker. Independent review found a stronger-than-implemented cancellation promise and missing threaded ownership evidence. The core now defines the locked submission commit point and tests both sides of it, checks caller slot-storage byte capacity before clearing, and exercises real mutex/callback interleavings. Actual adapter admission seal and complete callback-source rundown remain mandatory; zero active slots alone is insufficient.

## Native measurements and remaining work

The full native P1 experiment remains **INCONCLUSIVE**. Initial read/replay/query/write/flush/DVD/SG probes found no detected corrupt bytes. Raw failures, launch-method limitations, a long serial-record truncation and a queued A/B order mismatch remain in the ledger. Timings showed substantial variability; five exploratory pairs are not confirmatory acceptance. No timing speedup or all-workloads performance PASS is claimed.

The stdlib comparison harness freezes counts from a complete pilot ledger, re-derives calibration planning instead of trusting a mutable count, rejects future/error captures, and reports PASS/REGRESSION/INCONCLUSIVE using run pairs and simultaneous bounds. The native recorder must still complete fresh-process-per-case cache-controlled A/A and frozen confirmatory schedules. Actual lower commands/IRQs/allocations cannot be invented from public API counts; missing diagnostic structural evidence stays missing.

The declaration-only target probes verified 63 cache and 250 native ABI facts with zero executable `.text`, including the measured 28-byte cache descriptor and 12-byte query. Xbox IRP/device/driver layouts differ materially from desktop assumptions. See the [cache ABI facts](clean-room-inputs/CACHE-ABI-FACTS.md), [native inventory](clean-room-inputs/NATIVE-ABI-INVENTORY.md) and probe receipt; these approve numeric/declaration facts, not unchecked transitive SDK helper bodies.

Open P2/P3: independently implement IRP/MDL/SRB/cancel/rundown/device attachment adapter, disk controls and cache capability, remove nxcdrom/ClassPnP dependence, integrate boot registry/order/namespaces, preserve existing FATX leases and real durability, independently replace the narrowly scoped geometry wrapper if needed.

Open P4/P5: native correctness/fault/API/XISO/save/game/streaming matrix against the exact complete candidate, both approved rigs, all firmware profiles and RAM/ROM footprints, optimized-inline/helper source grants, exact corresponding source/notices, independent final review, and supported/unverified physical Xbox scope. PR #248 stays draft and issue #245 remains open until those gates pass.

Cache qualification gap: the retained Xbox lower stack excludes ATA caching MODE SENSE, ATA passthrough and the standard write-cache property. Its SYNCHRONIZE CACHE implementation can return success without any ATA command for cache-unrecognized/disabled state or absent selected flush opcode. The approved read-only cache-query proposal exposes these facts without altering ATA execution; enabled/unknown cache without a verified flush path cannot be treated as durable. Native callback-time child reuse must preserve older dispatch/channel frames and device references as documented in the approved completion packet.
