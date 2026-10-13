# Title-aware handle reference: one native lookup

Issue [#215](https://github.com/Mainkill1/SpiritBoot/issues/215) is qualified by a local patch that removes the duplicate native handle lookup after a title type registers. The existing object manager supports an untyped reference for ordinary, kernel and current-process/thread handles. The adapter holds that reference while it classifies the object, then transfers or releases exactly one native reference. A separate regression fixes native-object misclassification between first title creation and first title insertion.

The repeated ordinary-export workload used 33.9% less guest-clock time in seven matched cold-boot pairs. This is a synthetic export result in xemu, not a retail-title phase or a game speedup. No-title and shim changes were unresolved at this experiment's precision. All baseline-equivalence vectors pass; the broken create-before-insert interval is explicitly excluded from that claim.

The machine-readable [measurement record](object-handle-single-lookup-measurements.json) contains all 294 native timing samples, paired analysis, output/checksum records, source and binary identities, operation-count examples, build tool versions, focused guest results and PE footprint. Nothing was published or merged during qualification.

For current-main integration, the measured source diff is byte-identical and is
renumbered as [patch 103](../../../patches/roswell/0103-object-handle-single-lookup.patch),
with the same SHA-256
`518eb15c271c8e2ec9cd6d35a0c61de11bd69790f0cb5c84bf8a8a6a6587a209`.
It applies cleanly after the interrupt and ROM-backed-kernel changes in
SpiritBoot `ebd0b06f29431d9bacc488851c5698b532f53156`. The combined baseline tree
is `eee7de60ad3d2047efab3161491edb17768b5482`; the resulting kernel commit is
`f852bb55d26b75008e5bcedae27ef798cf2dffcc`, tree
`d5e5c40cb66deb63d31030668ee04e61877e3b64`. The historical measurements below
remain bound to their original isolated baseline. The current combined release64
build reconstructs that tree, produces a 512 KiB ROM with SHA-256
`484ea01114ecee7c134f0327101218e1c376769880b5a069a0322c41bd8e552e`,
and passes all 560 production-body cases. The full profile and native guest CI
matrix must still pass before merge.

## Exact source and linked behavior

The product starts from main commit `b684738dd502a9172470ca7681f6147f9d16c72b`. Its Roswell pin is `1569e2e89fb47cc72b9c704a8884f98200432bd4`. Applying the existing 100 ordered patches produces baseline tree `22a477eb82ed0111f2b7ad0d94c7a33a67ab8a94`. The new patch is [0103-object-handle-single-lookup.patch](../../../patches/roswell/0103-object-handle-single-lookup.patch), SHA-256 `518eb15c271c8e2ec9cd6d35a0c61de11bd69790f0cb5c84bf8a8a6a6587a209`; it produces tree `9c3a5cd5f226c11d917ee71abf57ce4399054c36`. The isolated implementation commit is `961eebde5497c8a41712bfa035be4abe93ad145d`.

These are public source bodies and public-API test guests. No proprietary implementation or disassembly was used. The original source22a release and reference trees remain independent of this patch.

The actual native `ObReferenceObjectByHandle` in `ntoskrnl/ob/obref.c:494` accepts a null requested type in both pseudo-handle branches. Those branches reference the current process/thread directly and do not visit a handle table. Other negative handles in KernelMode select the kernel table after removing the kernel bit. Ordinary handles select the process table. The ordinary and kernel paths enter a critical region, map and lock the entry, validate type/access, increment the native object's pointer count, then unlock. The adapter requests DesiredAccess zero and KernelMode. Classification therefore reads an immutable type field while a live native reference protects the body.

The linked entry operations are `ExpLookupHandleTableEntry` (`ntoskrnl/ex/handle.c:43`), `ExpLockHandleTableEntry` (`:887`), `ExUnlockHandleTableEntry` (`:926`) and `ExMapHandleToPointer` (`:1049`). The host checker executes these production bodies, as well as the native reference/dereference bodies. Release disassembly of the actual adapter confirms calls to the native reference and dereference exports; it does not substitute a copied table implementation.

`XobIsShim` in `ntoskrnl/xb/obcreate.c:491` reads the already referenced object's header and requires a non-null shim type. It performs no native lookup or reference. `XobUnwrapShim` (`:504`) already consumes one native shim reference on every path. Success adds a title-body reference before releasing the shim and returns the title body. Mismatch releases the shim, clears output and adds no title reference. The internal header now states this ownership contract explicitly; the helper's implementation is unchanged.

## Adapter behavior and the separate lazy-shim correction

Only the title-aware branch of `XeObReferenceObjectByHandle` (`ntoskrnl/xb/xbe.c:1937`) changes. It clears output, calls the native helper once with a null requested type, then calls `XobIsShim` on that live pointer. Shims use the existing unwrap helper. Ordinary objects use the existing Xbox-decoy-to-native mapping and an explicit header type comparison. A successful ordinary call transfers its native reference to the caller. A mismatch releases it once.

For an invalid handle, a registered title type still takes precedence and returns `STATUS_OBJECT_TYPE_MISMATCH`, with null output; native requests retain `STATUS_INVALID_HANDLE`. Null requests, mapped Xbox decoy types, actual internal types, wrong types, kernel handles and pseudo handles retain their baseline status/output results. The no-title source branch still delegates directly to the typed native helper. No new null-output-pointer contract is introduced.

The new untyped classification necessarily acquires a temporary native reference for valid ordinary/pseudo handles requested with a wrong or registered title type. Previously the typed native lookup rejected such requests before reference acquisition. The temporary reference is released once before returning mismatch: observable status/output and final ownership match, while the internal reference transaction counts intentionally differ. Success reference counts, shim ownership, and invalid-handle reference counts are unchanged. The held reference also makes type inspection safe during concurrent close.

There is an independent baseline defect before the first shim exists. `XeObCreateObject` registers a title type before the first `XeObInsertObject` initializes `XobShimType`. During that interval the legacy shim-typed lookup passes a null type to the native manager, accepts an ordinary body, and sends it to `XobUnwrapShim` as an `XB_OBJECT_SHIM`. Interpreting the native body's first field as a title-object pointer is invalid. The new `XobIsShim` classification requires the actual initialized shim type.

The actual-production-body host regression faults with SIGSEGV on baseline and passes with balanced ownership on candidate. Separately, the same full public XBE on baseline source22a reports exactly `not ok 3 - builtins-after-create-before-shim`; its other eleven checks pass. It exits normally with an end-FAIL marker. Candidate reports twelve passes on all four firmware variants and on the upper-RAM-reserved release128 profile. The guest failure and host fault are distinct observations of this causal defect. This interval is an intentional correction, not a baseline status/byte-equivalence case, and it is omitted from the frozen timing control. The concise compatibility record is [TITLE_HANDLE_CLASSIFICATION.md](../../provenance/TITLE_HANDLE_CLASSIFICATION.md).

## Correctness and operation counts

The 32-bit host checker in `tests/host/object-handle-fastpath/check.py` extracts the production adapter, mapper, title registry/reference/unwrap routines, native reference/dereference and actual table operations. It verifies 4-byte pointers, 8-byte table entries and the native header's 24-byte body offset. OS scheduling/APC/spinlock/pool and final-deletion boundaries use host fixtures; native status decisions, table selection/walk/locking, type checks and shim ownership do not. The counted host translation unit alone receives counters. Production firmware and the native timing guests have no lookup counters.

Tests were written and observed failing before implementation. The legacy ordinary path failed the one-lookup assertion with two native calls and two table maps/walks. The separate lazy-shim test failed with the invalid-body cast. The final checker passes 560 independent literal status/output/ownership cases and compares their semantic records with the exact baseline bodies. Cases include ten mapped native object types, four handle tag-bit forms, no-title and registered-title phases, null/internal/decoy/wrong/title type requests, invalid/closed/null/out-of-range handles, process/thread pseudo handles, kernel handles, shim null/matching/wrong requests, and actual level-one and level-two grown table walks. Failure outputs start at a non-null sentinel.

| After title registration | Native calls before → after | Table maps/walks before → after | Native refs/releases before → after |
|---|---:|---:|---:|
| Ordinary success, null or matching type | 2 → 1 | 2 → 1 | 1/1 → 1/1 |
| Ordinary wrong native type | 2 → 1 | 2 → 1 | 0/0 → 1/1 |
| Ordinary requested as registered title type | 1 → 1 | 1 → 1 | 0/0 → 1/1 |
| Invalid handle, native request | 2 → 1 | 2 → 1 | 0/0 → 0/0 |
| Invalid handle, title request | 1 → 1 | 1 → 1 | 0/0 → 0/0 |
| Pseudo success | 2 → 1 | 0 → 0 | 1/1 → 1/1 |
| Shim success or mismatch | 1 → 1 | 1 → 1 | 1/1 → 1/1 |
| No-title ordinary success | 1 → 1 | 1 → 1 | 1/1 → 1/1 |

Two readers run through 10,000 close/reuse cycles. A separate 100-cycle test holds two references through final close and releases them concurrently; each object deletes exactly once. A title close with a live reference leaves the body alive until its final reference, with exactly one shim delete and one title delete/free. Concurrent schedules are not compared for identical intermediate results; both arms must produce only permitted outcomes and balanced final ownership.

All release64, release128, debug64 and debug128 firmware builds reconstruct the candidate tree from the actual 101-patch lock. The focused public XBE passes 12/12 on every variant, covering ordinary/pseudo/kernel/shim behavior, lazy-shim classification, table growth and concurrent close. The release64 broad API XBE runs all 639 planned cases: 633 ordinary passes, six existing TODO cases, zero failures or skips. Those TODOs cover VFAT EOF beyond free space, readonly volume flush, x87/SSE exceptions under TCG, and two process-priority/thread-list cases. Product host tests pass (129 tests, three existing environment skips: root ownership and unavailable plugin headers). All workflow kernel host checks pass against the reconstructed release64 source/build. `git diff --check` passes.

The upper-RAM reservation release128 profile also reconstructs the exact candidate tree and passes the focused guest 12/12. An independent clean release64 rebuild produces byte-identical flash output to the frozen timing candidate. The broad API guest has only been run on release64; the focused guest supplies the four-variant and upper-reserved-profile checks. CI now gates the actual candidate tree, executes the production-body checker and enumerates the twelve-check guest through `sources/native-regressions.json`, retaining its native artifacts. The workflow also repeats the clean build at release128; that additional repeat was not run locally.

## Matched native experiment and footprint

The final experiment consists of seven sequential cold-boot pairs, alternating baseline/candidate order. Both arms use the frozen `LEGACY_CONTROL=1` ISO, SHA-256 `c2f2dbfed8156bb373ff38bc17ce8847b4c9a0101ddb1273818d03607053f056`. It contains eleven checks and omits only the separately tested broken lazy-shim interval. All fourteen runs exit zero, have identical literal TAP rows, and all 294 samples have checksum 50000. Each workload warms up for 1000 calls, then runs seven 50,000-call samples per boot through the actual exported wrapper.

The firmware pair is release64, compiled with the same GCC13 MinGW toolchain, CMake3.28.3, Ninja1.11.1, settings and `SOURCE_DATE_EPOCH=1788155396`. Baseline flash SHA-256 is `3dc3010a237fcf50bef2ecbe59c81115eabf9684e7a3ceb9caec19a16cb49611`; candidate is `7e42f9a2f9da1548e2afd55dc4278139c2c1c2e122c6ec8c80079b526278c8c5`. The public guest was built with the pinned nxdk image. The root-approved Linux xemu measurement build is source `63f53af93c2d84f5ce1a11e277138cbaf5cca7aa`, binary SHA-256 `2db2f3fd0f3e18e2850d792847be3b1b213e71900716cf7a2cbffa2e2919f9c9`; this differs from the product xemu lock revision. Each boot uses independent copies of the same HDD/EEPROM and read-only boot ROM, with identities in the record, 64 MiB, the same Xvfb/SDL environment, and no tracing or debugger ports. Other task agents avoided heavy builds during the serialized slot. This controls cooperating task workloads, not all host scheduling.

Every sample is normalized by its own guest counter frequency. The analysis uses the median of seven samples per boot, then the candidate/baseline percentage change for each adjacent pair. The interval is a Student t 95% interval over seven boot-pair changes (six degrees of freedom), not 49 independent inner samples. Time includes the exported reference, status/output checksum work and final dereference.

| Workload | Baseline median boot ns/call | Candidate median boot ns/call | Mean paired change | Paired change SD | 95% interval for mean change |
|---|---:|---:|---:|---:|---:|
| Ordinary event after title registration | 806.001 | 530.759 | −33.919% | 1.657% | [−35.452%, −32.386%] |
| Event before any title registers | 345.925 | 347.999 | +0.103% | 3.315% | [−2.963%, +3.169%] |
| Title shim, matching title type | 470.003 | 466.583 | −0.517% | 1.884% | [−2.260%, +1.225%] |

The ordinary gain is resolved beyond this observed variation. The controls do not establish exact-zero overhead: a small no-title or shim regression remains within their intervals. The no-title source branch is unchanged, but the compiled wrapper is not byte-identical: its branch displacement grows and the shared return adds register moves. These limitations must remain part of the merge decision. Exploratory 32-bit host timing obtained during concurrent builds is retained locally and is not acceptance data or xemu throughput.

The actual release64 PE `.text` virtual size increases by 72 bytes, from 338580 to 338652. Kernel file size remains 500736 bytes and `SizeOfImage` remains 561152 bytes. All section virtual addresses and raw sizes are unchanged. `.data` remains 2056 bytes and `.bss` 44208 bytes; there is no new metadata allocation or resident image page. The adapter itself grows from 186 to 260 code bytes; overall section alignment accounts for the 72-byte total delta.

An independent review by the #216 agent checked the actual native bodies, ownership/status paths, use of the existing shim classifier, matched ISO and raw timings, and found no blocking defect. Its precision limits are retained above. This patch is ready for product review with the stated precision and coverage limits; source22a remains the independently released baseline.
