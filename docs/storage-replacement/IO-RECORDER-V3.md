# Resident-buffer I/O recorder: six-leaf native qualification

The [maintained generation 3 fixture](../../tests/xbe/storage-io-recorder-v3/README.md) first passed `fatx-d0-q12-p900-synthetic.warm` on 2026-10-15, then completed five additional warm dataset-0 leaves in the queue-depth/pressure diagnostic: QD1 and QD4 at pressure 0 and 900, plus QD12 at pressure 0. Across those six distinct leaves, the verified result is **6,144 complete operations, 65,227,776 exact payload bytes, zero failures and complete guest/host cleanup**. This establishes their allocation, setup, callback and full-oracle behavior on the stated 64 MiB configuration. It is not an all-case qualification or P1 pass.

V2 regenerated/poisoned request buffers on the issuer and verified full payloads in APC callbacks. V3 allocates all 1,024 unique slices before seeding, poisons every payload before a pass, and retains all slices until its complete post-batch byte/canary oracle finishes. The callback records IOSB identity/status/count and buffer availability. Warmup and its oracle finish before re-poisoning and pressure restoration. All data checks remain required; their phase changes. The measured metric is issue-to-APC availability, so old and new timings cannot be directly compared.

## Exact native scope and result

Run `20261015-024337394-24ab598cc42146a5b1628ed922f9e13c`, job `pr248-io-v3-fatx-d0-q12-p900-warm-20261015-v1`, ran on the approved Windows Ryzen secondary through the Codex USER desktop's protected PowerShell named pipe, session 1, `WinSta0/Default`. It used the local 64 MiB semaphore-fix BIOS `42ad0c392b97d195f6aacaa47b1c168f1f74038ddf3258257b21cfde99bcb647` and PR356 xemu `14777b55740706608cdfde97349eefa3d5115ece4c889679c9c8b96641a85f2d`, with Vulkan 1280×720 and vsync=false. This was not the published c630 reference/Deck configuration.

The exact fixture ISO is `f2aa311c157f5f4055a89e7d1e21209cd919d9069f6a398adac2588295ee7d73` (720,896 bytes). Its `default.xbe` is `7158fdb09ae2fe14cd97855301eaf7fd49e47a3d8ac1aaea08eb0db97f8b9a84` (147,456 bytes). Source/ISO/request review found no Critical or Important issue before launch. The [portable receipt](io-recorder-v3-native-receipt.json) binds these identities, reviewed source closure and raw artifacts.

| Verified observation | Value |
|---|---:|
| Scheduled/completed operations | 1,024 / 1,024 |
| Exact payload bytes verified | 10,871,296 |
| Resident slab / static records | 14,823,424 / 81,920 bytes |
| Warmup oracle failures / measured failures | 0 / 0 |
| Free pages before measured META | 900 |
| Requested / maximum active caller slots | 12 / 12 |
| First issue / last APC-ready tick | 5,234,696,644 / 5,276,246,430 |
| Batch / sum of caller-lifetime ticks | 41,549,786 / 244,589,318 |
| Average outstanding caller lifetimes | 5.8866565 |

Every operation retained its exact vector, disjoint page-rounded slice, alignment and timestamp bounds. Every submission returned `STATUS_PENDING`; every completion had status 0, its full byte count, one APC, matching IOSB pointer and a successful post-batch oracle. All guards and complete payloads were checked. The 900-page value is a setup snapshot, not a continuously observed invariant. Average caller lifetimes and maximum bookkeeping slots do not identify private device concurrency.

The owned HDD was prepared from seed `78af83a6c8a1f84cefd37b811a4197419ace68e09ad197376ca9bb2cca05e56b`; prepared bytes have their own recorded hash. Guest cleanup reported complete, the actual child and pipe server exited, the owned job had zero active descendants, and the private HDD was deleted after evidence finalized. The post-END query observed shutdown, followed by owned quit/cleanup. The runner's generic correctness field remained `notEvaluated`; the explicit native TAP/operation/oracle verifier establishes the functional verdict here. Its recorded one post-END diagnostic makes `Intervened=true`; manual inputs and pauses were zero.

## Two-pair descriptive comparison

The same fixed case was also run twice per BIOS in opposite orders: SpiritBoot then Complex, followed by Complex then SpiritBoot. Every run completed the same 1,024 operations and 10,871,296-byte full oracle with depth 12 reached, 900 pages observed before META, zero failures and complete cleanup. Complex batch ticks were 24,632,153 and 25,685,440; SpiritBoot batch ticks were 41,549,786 and 40,584,574. Their arithmetic means are 25,158,796.5 and 41,067,180 ticks, a 1.6323189 SpiritBoot/Complex ratio. The individual order-pair ratios are 1.6868110 and 1.5800615. Pooled caller-lifetime occupancy was 10.7195991 for Complex and 6.1378077 for SpiritBoot.

The [descriptive receipt](io-recorder-v3-two-pair-descriptive.json) binds all four run IDs, BIOS/fixture/xemu identities, strict-verification hashes and exact arithmetic. Both orderings therefore identify a repeatable investigation target in this case: SpiritBoot takes longer while sustaining fewer outstanding caller lifetimes. They do not identify the responsible kernel component or prove a general performance regression. Two observations per BIOS, uncontrolled OS/driver caches, a nominal counter rate and a single synthetic case are insufficient for confidence intervals or acceptance. These diagnostic observations cannot be reused as samples in a future frozen confirmatory experiment.

## Limits and maintained coverage

Both actual-C host profiles (`-O0`, `-O2`) pass nine fault-test methods/51 fixture invocations each and are discoverable in one ordinary host-suite run. The checked-in C/metadata/mock source bytes match the reviewed source closure. Native build instructions are in the fixture README; compiler defaults and rebuilt artifact identities remain explicit.

Six warm dataset-0 leaves are now functionally qualified: QD1 and QD4 at pressure 0 and 900, QD12 at pressure 0, and the earlier QD12/pressure900 case. The remaining 18 supported FATX leaves and 12 other matrix families remain open. See [the diagnostic update](IO-PERFORMANCE-DIAGNOSTICS-20261015.md) for the strict ten-run queue-depth evidence and its performance limits. OS page cache and GPU driver cache were uncontrolled (`DriverNamespaceVerified=false`), and nominal 733333333 Hz is a recorder label, not a frequency measurement. No timing calibration, absolute clock accuracy, physical flush/durability, private structural counters or statistical power is established. Raw ticks are retained as diagnostic observations.

The simple native-regression CI loop does not construct the required private single-case FATX configuration and therefore does not run this fixture. Adding it requires safe pinned preparation/isolation and an appropriate memory scope first. Its host fault tests run through normal discovery now. No driver code or existing V2 evidence is replaced by this fixture.
