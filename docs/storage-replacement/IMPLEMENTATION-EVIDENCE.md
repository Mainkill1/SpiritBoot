# PR #248 implementation evidence and open gates

Status: **the independent complete candidate is implemented, excludes the
identified incompatible storage-class archives from the release link, passes
the complete host suite and has current release64 native streaming evidence;
final operator game acceptance and physical-Xbox smoke testing remain open.**
The old storage classes remain available only in the explicitly selected
reference backend and are excluded from the complete-candidate link. This
document is an engineering and corresponding-source record, not legal advice.

The [native cutover bring-up](NATIVE-CUTOVER-BRINGUP-2026-10-15.md) records the
three runtime divergences found after the aggressive class replacement: missing
`\\Device\\Harddisk0` ownership, rejected PnP start forwarding, and missing
extended disk geometry for PartMgr. The corrected source tree
`abebfef7a717e0379057b5087b8ff71e75279018` passes 639 API checks as
637 pass, zero fail, and two declared xemu floating-point TODOs on release and
debug builds at both 64 MiB and 128 MiB.
The exact second-pass images are release64
`cff12e2cd1b1af1faf0060b676d8ffc37f8256400b12edfe5ad3b2a191943db9`,
release128 `b2de51291b6231e25fd6f1fda7db607595c94673f8312a78f02833825863931a`,
debug64 `5cf32acc210781f7a8337b94f5deff45b73b381d1b9777329a85d171f67d13bb`,
and debug128 `ef99a89e607c52d339196aa491927971fa5c6f98c10c73c9666ecae1815a3185`.
The [second-pass review-fix record](PR248-SECOND-PASS-REVIEW-FIXES-2026-10-15.md)
and its machine-readable receipt bind those images to the focused production
tests, storage preflight, and per-profile API runs.
The [complete-candidate license map](COMPLETE-CANDIDATE-LICENSE-MAP.md)
enumerates the linked replacement units and function groups, their exact source
hashes, directly used interface-header terms, and source-only exclusions.

## Product and native reference

The baseline is SpiritBoot v1.0.0, commit `b65a3f77d9887c9285e936996eb4d286a66f540c`, Roswell `1569e2e89fb47cc72b9c704a8884f98200432bd4`, original assembled tree `3c23ea01cf43c2979c4c3ef247236e03d079f465`. The first successful recorded-link reference build assembled tree `ce9753a1cc7f7d505c4e59ea6f3c7197d84b99d8` and reproduced the released 64 MB ROM exactly: `c630d22f2353d3898024d510f0b402b64bccdb331781fe7885389f73d6200853` (524,288 bytes). Its source check verified 28,893 tracked files and 228 resolved link inputs. The composed tree changes because build evidence is now explicit; reference driver code remains unchanged. The later owned primitive tree `f587be12d98af88541e137391e27ced142ea5b74` also reproduced the published reserved128 release SHA256 `2632d513d84bf165d3a916b135cc387af6ee414b9f4bfbef334163752f022836`. Reference128 on the first primitive tree `9fb0951a3cfc10d49c456406dcb6382bfcff2cf2` reproduced `dc9de407a5440ff4f0331947661540a2137cbc27f25bb1b3c89f085ee4d04ec4`.

The recorded [reference build matrix](reference-build-matrix.json) also includes successful debug64/debug128 builds on source tree `09c33a8e198446e428e16854eaa0bfc0b89c942c`; these are reference-driver builds, not candidate qualification. Its original product host run passed 224 tests with three skips; later scoped implementation checks are recorded below.

The first CI update built all four firmware profiles successfully, but its upper-RAM CMake probe omitted the newly mandatory storage selection and recorder arguments. `0128-storage-aware-config-probe.patch` makes those test inputs explicit and checks the specific memory-contract error. A fresh reference64 build on tree `8c2410156f1dd955afc7199c86dabaa12452282e` reproduces the release hash; all 104 follow-up kernel host-check logs complete locally against that exact assembled source/build. These are reference checks, not native candidate qualification.

Two failed build attempts remain recorded: the initial source verifier incorrectly rejected Git's intentional CRLF checkout of `.mc` files, then GNU ld's synthetic PE `dll stuff` input was incorrectly treated as a missing file. Regressions now cover both. A diagnostic relink without the pinned epoch differed only at the kernel timestamp and PE checksum (five bytes); all loaded sections and all 5,582 defined symbol/address identities matched. The successful clean builder uses the pinned epoch and matches the complete ROM.

Operator-approved rigs (2026-10-14): Steam Deck `10.0.0.42` primary; Windows `10.0.7.1` secondary, actual Ryzen 9 6900HX rather than the originally named i9. No machine averaging. Windows graphical launch/control must use the PowerShell pipe in the logged-in Codex desktop; service/session-0 runs do not qualify. The owned bridge proof verified protected current-user pipe access, Codex/session1 server and client, and actual `WinSta0/Default`. It intentionally launched no guest and is a bridge proof, not a performance pass.

## Internal split

`0126-storage-backend-evidence.patch` introduces required explicit states from CLI through CMake, actual link evidence, and `build.json`:

| State | Current meaning |
| --- | --- |
| `legacy-reference` | Existing classpnp/disk/nxcdrom; baseline only |
| `partial-lab-prototype` | Bounded owned nxstorage library and narrow geometry adapter plus the legacy driver stack; no independent read/write class adapter yet; not publishable |
| `complete-candidate` | Independent disk/optical class adapter and bounded request engine; rejects old linked classes through actual preflight; boot/API qualified in all four firmware profiles, with broader gates still open |

The first partial64 build compiled the actual nxstorage archive, whose unused primitives were then removed by the linker; that ROM remained byte-identical to released64. The later partial geometry build installs the narrow independent geometry route and has a different ROM, as recorded below. Neither build routes ordinary native storage requests through the new request core. One kernel and one `flash.bin` remain the product format. Different backends require separate output directories; absent/unknown backend and requested/configured mismatch fail. CI explicitly builds the legacy reference; passing that matrix does not qualify replacement behavior.

The existing two-pass INIT placement is preserved. Recording occurs around the compiler invocations that actually execute, including their original argv, expanded/hashes of response files, inputs, map and original linked snapshot. The existing relocation removal/export fixups and flash packer also record consumed input/output hashes. Postprocessing preserves actual linked COFF identity; the final kernel is bound to packaging and published ROM bytes. GCC response escapes are tested against a real compiler, including escapes inside both quote modes. Git canonical tree identity and exact checkout bytes are separately checked. Wrappers invalidate old successful receipts before argument validation, so a rejected standalone attempt cannot retain an earlier pass. Transient LTO inputs and GNU ld synthetic inputs are explicitly recorded; missing ordinary inputs fail.

These unsigned records establish consistency, not authenticated execution or legal certification. Generated/untracked compile inputs and optimized inlines still need the final compiled-source review. The checker remains `PRECHECK_ONLY_NOT_LICENSE_CERTIFICATION`.

The legacy `storage-completion/check.py` source extractor is segregated as a baseline check. Immediately before its sole pipeline invocation, CI checks the entire actual CMake backend selection inside a fail-fast shell. Independent review verified that partial, complete, missing and conflicting selections stop before extraction. Owned production tests verify locked patch hashes and apply only the new `nxstorage` production/test paths, without copying legacy bodies. This closes the narrow test-segregation task, not native candidate qualification.

## Independent implementation

The [approved inputs](clean-room-inputs/approved-inputs.json), [caller matrix](clean-room-inputs/CALLER-MATRIX.md), [behavior contract](clean-room-inputs/CONTRACT.md) and [geometry contract](clean-room-inputs/GEOMETRY-WRAPPER-CONTRACT.md) were supplied to fresh implementation roles without old class source, old source-extract tests, private helpers, Git history or disassembly. Prior investigator exposure and author access are recorded separately. This is scoped input separation, not a claim of personnel-level or final legal certification.

`0127-independent-storage-primitives.patch` carries byte-identical independently authored production request engine and geometry composer plus their own tests. It does not replace the native adapter or nxcdrom yet. The request core uses fixed slots, iterative segmented commands, actual completion bytes, explicit write/flush barriers, SYNCHRONIZE CACHE(10) CDB `0x35`, generation/duplicate guards, bounded queue recovery, and ownership-preserving cancellation. No heap/worker/clock/bounce dependency exists in the core. Sector shifts replace a generic 64-bit division helper. Write-through retains one parent through data and the synchronization command. Native hardware execution and durability remain unproved. Its error/Information policy is explicit candidate behavior, not claimed observed parity.

The geometry composer emits initialized complete prefixes and MBR/GPT/RAW/BRFR metadata from a caller-provided stable snapshot. Its first policy returned only complete records and failed the observed40-byte return-count contract. A tested policy revision now returns all initialized available bytes up to112, clears unavailable tails, and emits meaningful optional records only when complete fitting. It matches the seven observed counts32/40/56/64/112/112/112; size-zero unavailable markers are an explicit legacy compatibility convention, not a claim of valid standard records.

`0130-independent-geometry-owner-adapter.patch` installs the independently authored owner adapter for explicitly selected lab/candidate backends, preserving the legacy-reference route. It snapshots the retained owner under its synchronization event, releases that event before the lower query, and keeps child request output/event/status storage live through terminal completion. Sixteen sanitizer scenarios exercise 61,973 checks; target assertions verify the actual Xbox request, event, geometry and nested-record declarations. The [actual target-build receipt](geometry-target-build.json) binds source tree `74650fbf8b165e457381a41ef9c9003f303a1f7b` to partial64 ROM `19ac6e636f7ea1149c70537aea87eacbbd007667be8e8331a0d8a80b60db08dc`. The corrected Deck fixture produced all 210 query rows: status, caller IOSB and returned counts match the reference. Fourteen successful extended-geometry prefixes match the initialized schema; byte differences clear unavailable fields and padding. This is bounded query parity, not full native request, hot-removal, performance or driver-replacement qualification.

Latest imported primitive tests: 42 deterministic plus 8 real-thread request scenarios under ASan/UBSan; 13 geometry scenarios and 6,001 checks; i386 objects with no undefined helpers. The same source bytes compile in the assembled source host checker. Independent review found a stronger-than-implemented cancellation promise and missing threaded ownership evidence. The core now defines the locked submission commit point and tests both sides of it, checks caller slot-storage byte capacity before clearing, and exercises real mutex/callback interleavings. Actual adapter admission seal and complete callback-source rundown remain mandatory; zero active slots alone is insufficient.

`0129-independent-cache-query-primitive.patch` adds an independent normalized encoder, with 20 sanitizer fixture groups and target ABI checks. `0131-independent-cache-publication-primitive.patch` adds the independent publication state and native-shaped capture helpers, with 32 sanitizer groups and independent boundary review. The [publication integration receipt](cache-publication-integration.json) explicitly records that only the pure module was target-compiled: no native handler, producer, device/request fields or worker-result handoff is installed. The [amended integration requirements](independent-implementation/lower-cache-query/amendments/transaction-lifetime-2026-10-14/INTEGRATION.md) distinguish the owning IDENTIFY transaction from independent invalidation and require persistent raw-result handoff before request completion. Native source guards and rundown remain open. The corrected cache-validity facts use WORD84 for enabled-cache/flush capability and WORD83 for LBA48; historical proposal errata remain visible.

CI exposed a checker failure under GCC's default PIE settings after the publication addition. `0132-nxstorage-freestanding-gcc-checks.patch` explicitly disables PIC/PIE for bare-metal i386 probes, links the publication object with its exact owned encoder, and still requires no remaining undefined helpers. GCC and Clang production checks pass. The [checker writeup](GCC-CHECKER-FIX.md) preserves the failed CI artifact and scope: firmware bodies were unchanged. The [exact fix-head CI receipt](freestanding-checker-ci.json) records successful host tests and all four legacy-reference firmware profiles.

## Native measurements and remaining work

The [public-kernel contract differential](KERNEL-PUBLIC-CONTRACT-FIXES.md)
separates three real firmware divergences from three invalid test assumptions.
Complex establishes clock level 28 for public ordinal 130, direct PCI
configuration access and completion of a valid invalid-request IRP. Boundary
diagnostics also establish eight-bit bus/register wrapping, ignored slot
reserved bits and blacklist ordering. Locked patch `0137` corrects those paths.
The final identical 119-check fixture passes 119/119 on SpiritBoot and Complex
with byte-identical serial output; 31 registered native fixtures pass 5,481
assertions on the final release64 image. These pre-extraction kernel corrections
remain separate from storage-replacement completion and candidate qualification.

The exact final pre-extraction release64 image then completed the expanded
Windows matrix through the protected USER desktop pipe: all 36 registered
fixtures passed, with 6,197 successful assertions and the two declared TODOs
out of 6,199 checks. The same inputs on Complex passed 19 fixtures; six more
completed with reference-oracle discrepancies and eleven did not complete on
that reference. The portable [combined comparison](../provenance/evidence/pr248-final-windows-matrix/COMBINED-36-COMPARISON-RECEIPT.portable-v2.json),
[Complex receipt](../provenance/evidence/pr248-final-windows-matrix/COMPLEX36-FINAL-RECEIPT.portable-v3.json)
and its [normalization manifest](../provenance/evidence/pr248-final-windows-matrix/COMPLEX36-FINAL-RECEIPT.portable-v3.manifest.json)
retain the classifications, identities and cleanup evidence. Two additional
performance-fixture executions per BIOS reproduced SpiritBoot's 72/72
scatter/gather and 42/42 kernel-performance results; Complex reproduced 72/72
and 35/42. Their [two-run summary](../provenance/evidence/pr248-final-windows-matrix/PERFORMANCE-TWO-RUN-SUMMARY.portable.json)
retains 102 metric series. Cross-BIOS timing is not comparable because the
Complex support-discovery rows used a shorter completion ceiling. These are
bounded pre-extraction results; they do not qualify the unimplemented storage
replacement or establish the unfinished P1 experiment.

The [final broad XISO comparison](BROAD-XISO-FINAL-COMPARISON.md) then ran all
144 executable leaves twice per BIOS in frozen ABBA order on the primary Linux
host. Every run completed 144/144 leaves and all 149 records passed their
applicable built-in oracle. Both SpiritBoot runs repeat exactly; Complex B1
matches both SpiritBoot runs, while Complex B2 alone changes one eligible
framebuffer hash. The frozen repeatability verdict is therefore FAIL without
proving a SpiritBoot regression. Two-run aggregate timing is descriptive only:
SpiritBoot's sum of leaf means is about 0.299% lower, with 64 lower leaf means
versus 80 for Complex, but cache controls and the functional gate are
insufficient for acceptance.

Latest bounded update: [0133 zero-domain descriptor correction](independent-implementation/zero-domain-mdl/FIX.md) passes 44 request and eight ownership scenarios plus sanitizer/freestanding checks. The reviewed [native seam facts](native-seam-facts/WORKER-HANDOFF-FACTS.md) and [next-task plan](independent-implementation/native-adapter-plan/NEXT-NATIVE-TASKS.md) resolve the requested worker/MDL planning questions. Neither installs the full adapter.

The [2026-10-15 storage diagnostics](IO-PERFORMANCE-DIAGNOSTICS-20261015.md)
now establish six functional V3 leaves and narrow the pre-extraction slowdown.
QD1 reproduces the gap without queue underfill or induced pressure. The
order-aware V5 control rejects forcing the existing worker route, which was
1.6475 times slower than the current direct route. The V6 raw-device ABBA
control passed 4,096 byte-exact reads and measured SpiritBoot at 1.5164 times
the Complex batch mean, with a 3.2040 issue-through-return ratio. It also found
that whole-disk `NtFlushBuffersFile` returns `STATUS_INVALID_DEVICE_REQUEST` on
SpiritBoot and success on Complex. This is pre-extraction diagnostic evidence;
it neither qualifies performance nor installs the replacement.

The [isolated raw-flush follow-up](independent-implementation/raw-flush-adapter/README.md)
passes three sanitizer-backed scenarios and a freestanding i386 check against
the independently authored request core. It localizes the missing behavior to
the unimplemented public-to-core adapter and records the exact declarations,
lifetime rules, lower bridge, status mapping and persistence evidence still
needed. No production patch or durability claim is made.

The unchanged-fixture [post-END collector](STORAGE-POST-END-CONTEXT.md) now qualifies Deck collection without a heavy initial guard overlapping measurement. First scheduled V351 capture passed its workload, but [actual importer replay failed](AA-FIRST-IMPORT-FAILURE.json) on a flat-receipt/case-map interface mismatch. Its timing result remains ineligible and the remaining schedule is stopped pending correction and a fresh predeclared method. Windows cache and full P1 gates remain open.

The [complete 36-case Deck functional sweep](FULL36-FUNCTIONAL-QUALIFICATION.md) passed on the published 64 MB reference BIOS: 36,864 operations and 188,416 assertions, with complete evidence and cleanup for every run. The [Windows clock-context run](WINDOWS-CLOCK-CONTEXT.md) also completed through the protected desktop pipe on PowerShell 5.1. Neither result qualifies performance: the Deck DVD initial guard can overlap measurement, and Windows driver-cache qualification remains unresolved. The [source-fixed counter integration](BENCHMARK-SOURCE-FIXED-COUNTERS.md) now carries exact conversion bounds into comparison decisions and preserves historical reported values. Native evidence import, accepted runtime context and actual per-host A/A remain required.

The full native P1 experiment remains **INCONCLUSIVE**. Initial read/replay/query/write/flush/DVD/SG probes reported zero assertion failures. Independent review found that the V1 write/flush fixture reuses a buffer already containing expected bytes for readback; a no-fill-success read can therefore pass. Its readback integrity and raw `persistence=1` are unsupported, and its inferred-integrity claims are rejected. The frozen V1 source/media/raw results remain retained. The separately pinned V2 fixture now uses per-operation byte-complement poison and distinct write/readback buffers, with fail-first no-fill and partial-fill regressions. Subsequent parser and collector corrections preserve duplicate-field, matrix, execution, cleanup and raw-evidence checks; their superseded freezes and failures remain recorded. Corrected Deck normal reads, geometry queries, an owned timeout and a fresh successful run afterward are bounded qualification evidence. Clock metrology remains open. The [Windows V27 receipt](WINDOWS-NATIVE-QUALIFICATION.md) records protected Codex desktop-pipe normal/query/owned-deadline/post-deadline qualification after recovery and an EOF error-retention correction; its original V23 failed deadline and stopped sequence remain preserved. These are bounded native method checks, with full P1 and full-class qualification still open. Neither API flush success nor verified reopen establishes hardware durability. Raw failures, launch-method limitations, a long serial-record truncation and a queued A/B order mismatch remain in the ledger. Timings showed substantial variability; five exploratory pairs are not confirmatory acceptance. No timing speedup or all-workloads performance PASS is claimed.

The bounded V2.4 Deck clock diagnostic completed all 50 samples with verified executable, rewritten runtime configuration and PID lifetime. Its busy loop compared RDTSC ticks against the QPC frequency, so the requested durations were wrong. The raw observations remain preserved; this exposes a fixture unit error and does not establish emulator slowdown. The separately frozen and independently reviewed V2.5 diagnostic completed all 50 samples with matched QPC deadlines, including all 25 busy spans. This qualifies diagnostic collection only: backend/marker uncertainty and normative clock calibration remain open. The [causal method](CLOCK-MEASUREMENT-PLAN.md) is now implemented as a separate diagnostic: V2.6.3 failed its obsolete single-step-field guard and remains preserved; corrected V2.6.4 completed all50 samples/100 markers with exact read/route/FD/lifetime replay. The [portable receipt](causal-clock-native-receipt.json) qualifies collection only. Its29 finite conditional intervals contain the compiled clock rates, while21 overlapping intervals remain INCONCLUSIVE. Runtime clock/control assumptions, normative calibration and P1 remain open.

The stdlib comparison harness freezes counts from a complete pilot ledger, re-derives calibration planning instead of trusting a mutable count, rejects future/error captures, and reports PASS/REGRESSION/INCONCLUSIVE using run pairs and simultaneous bounds. The native recorder must still complete fresh-process-per-case cache-controlled A/A and frozen confirmatory schedules. Actual lower commands/IRQs/allocations cannot be invented from public API counts; missing diagnostic structural evidence stays missing.

The [public timing correction](BENCHMARK-PUBLIC-TIMING-FIX.md) separates API
flush/reopen timing from physical durability and explicitly labels fixed guest
workloads as metadata-only seeds. Its [independent review](p1-public-timing-independent-review.json)
verified the final raw tick/frequency mapping, malformed-value rejection and
legacy controls. Required physical write gates remain INCONCLUSIVE. The
[exact counter arithmetic](COUNTER-INTERVAL-ARITHMETIC.md) preserves conversion
uncertainty through durations, throughput, quantiles and ratios; its bounds do
not establish host clock resolution or accuracy. Native per-case artifact
bindings, runtime clock qualification and actual A/A still remain open.

The declaration-only target probes verified 63 cache and 250 native ABI facts with zero executable `.text`, including the measured 28-byte cache descriptor and 12-byte query. Xbox IRP/device/driver layouts differ materially from desktop assumptions. See the [cache ABI facts](clean-room-inputs/CACHE-ABI-FACTS.md), [native inventory](clean-room-inputs/NATIVE-ABI-INVENTORY.md) and probe receipt; these approve numeric/declaration facts, not unchecked transitive SDK helper bodies.

The independently reviewed [boot dependency audit](boot-dependency-audit/README.md) binds 25 source files and 62 ranges to current assembled tree `7e891ec86f42b1313e5cd3453347836ac451ba79`. It verifies nine folded entries, Disk/Cdrom object names, NTAPI entry declarations, kernel-owned boot-node interfaces and the post-boot PnP sealing boundary. It also identifies a repeated START caller requirement through partmgr and corrects stale references to excluded Xbox power-management paths. This closes P0's missing boot-file inspection only. The exposed investigation packet is archived for review and has not been added to independent-author inputs; actual P3 entry ABI, initialization outcomes, retained callback lifetime and native memory remain open.

P2/P3 implementation status: the complete candidate now contains the
independent IRP/MDL/SRB adapter, fixed-slot request engine, cancellation and
publication seal, disk and optical controls, folded boot entries, owned disk
namespace, lower-stack attachment, PnP start forwarding, and PartMgr geometry
contract. It links `nxstorage` without `classpnp`, `disk`, or `nxcdrom` and
passes the four-profile API runtime matrix. Native cache-capability and
physical durability claims remain limited by the lower stack and require the
separate evidence gates described above.

The [native adapter review hardening](NATIVE-ADAPTER-REVIEW-HARDENING-2026-10-15.md)
records fail-first production-function coverage for poisoned partial allocation,
every child-IRP/control-MDL slot failure, an already-cancelled data IRP, and
cancellation on both sides of the request core's transport commit. The locked
adapter harness now passes 10 groups under plain and ASan/UBSan builds. This is
deterministic host fault/race coverage; the existing native qualification limits
remain unchanged.

## Current final performance batch

The exact corrected release stack adds the bounded Forza queue and hot-path
patches 0146 through 0151, safe-default Advanced controls in 0152, and opt-in
synchronous XDVDFS direct forwarding in 0153/0156. Patch 0155 rolls back the
unqualified small-SYSVA local-invalidation experiment from 0154.
Patch 0157 adds per-request payload association to the randomized 1,024-read
QD12 adapter stress and corrects the Advanced menu label for the now
synchronous-only direct optical path. Patch 0158 limits allocation persistence
to an armed quick launch, verifies actual optical-media changes without a cold-
mount TEST UNIT READY, and prevents control/data request-envelope double lease.
It assembles tree
`ad8641445795b0701ec73c987f1c771d0ac83654`. Release64 reproduces
SHA-256
`382956e7bfceaf943e37e90a772963ca7d9d6162959b326135ace533a0cba9ec`.
Release128 is
`15159ed9c3ee4c76c2bec8242c3e3cd15d8f8040b3c8b3b468acabf4bf7e4a72`.

The complete product host suite passes 549 tests with 26 expected
host-platform skips. Two independent Windows release64 boots completed 32
Forza-shaped passes and 32,768 asynchronous FATX reads at queue depth 12 and
900-page pressure, with zero request, oracle, warmup or cleanup failures. The
final two-run mean improves end-to-end APC batch time 3.93% and submission time
5.82% against the retained-SG control. Exact packet preparation on Steam Deck
reduces weighted instructions 33.33%; ordinary ATA cache bookkeeping removes
99 i386 instructions. The proposed four-read Xbox ATA settle optimization was
rejected after sporadic Forza menu corruption: xemu gives those reads zero
elapsed guest time. A later automatic QEMU-HDD candidate also froze during
operator testing and is rejected. The replacement keeps
`KeStallExecutionProcessor(1)` for every ordinary boot and permits acceleration
only after an explicit session-only Advanced choice; CI checks this in the
exact assembled source. Full inputs, limits and rejected designs are in
`docs/performance/evidence/forza-map-hotpath-20261015/`.

The exact image also completed two independent release-only Steam Deck runs of
all 144 XISO leaves and five structural groups. Each run passed 149/149
same-host records with no applicable oracle failures or functional-hash
changes. The descriptive sum of two-run leaf means improved 8.09%. The only
initial >20% leaf was rerun with 4,096x work in ABBA order; its 15.4--16.1
second samples narrowed to +1.95%, so no broad-suite leaf remains over the
review threshold. These results are under `final-broad-xiso/` in the evidence
directory above.

The 0154 focused release64 A/B/B/A campaign performs 8,388,608 warm one-page
allocate/write/verify/free operations per arm. Local invalidation reduces the
two-run mean from 10.689900 to 1.584932 seconds (85.1736%) with identical
checksums and all guest correctness markers passing. This closes a measured
firmware-owned bottleneck; it is not a whole-game claim. Reproduction inputs
and raw logs are in
`docs/performance/evidence/sysva-local-invalidation-20261016/`.

Remaining P5 operator gates are current-image Forza scenery streaming, DOA save
reload, PGR2/Conker scene transitions and a physical-Xbox smoke test. These do
not reopen the source/link result: the release candidate links the independent
storage classes and excludes `libclasspnp.a`, `libdisk.a` and `libnxcdrom.a`.

Cache qualification gap: the retained Xbox lower stack excludes ATA caching MODE SENSE, ATA passthrough and the standard write-cache property. Its SYNCHRONIZE CACHE implementation can return success without any ATA command for cache-unrecognized/disabled state or absent selected flush opcode. The approved read-only cache-query proposal exposes these facts without altering ATA execution; enabled/unknown cache without a verified flush path cannot be treated as durable. Native callback-time child reuse must preserve older dispatch/channel frames and device references as documented in the approved completion packet.
