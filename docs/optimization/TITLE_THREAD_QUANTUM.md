# Apply the title's published thread quantum to its scheduler state

A title thread was given a public quantum of 60 while its native scheduler state retained the system process's 36-unit quantum. With three quantum units charged per millisecond, equal-priority CPU contention gave title threads approximately 12 ms per turn rather than the approximately 20 ms observed on Complex 4627.

The new `thread-quantum` XBE reproduces the difference through public APIs. It runs an equal-priority CPU-bound contender, warms up scheduling, and measures sixteen 1 ms alertable waits using both guest ticks and the public performance counter. Its behavioral check requires at least fourteen samples in the measured reference interval of 18–100 ms. The broad upper bound tolerates incidental interference; the lower bound distinguishes the demonstrated 12 ms and 20 ms behavior. The test also verifies that every wait succeeds and that the contender terminates. This is a scheduling regression, not an FPS benchmark or a general timer conformance suite.

`NxkPublishThreadProcess` now initializes the current registered title thread's native `QuantumReset` and remaining `Quantum` to the same 60-unit value used in its public view. This occurs during title registration before entering title code. The dispatcher IRQL protects the initialization against a context switch. The process-wide quantum is left alone because the process also contains kernel workers. No disk, resource-loader, GPU or memory-allocation policy changes are included.

## Validation

All firmware tests below used 64 MiB firmware and a 64 MiB Windows xemu guest, fresh HDD overlays and an identical initial EEPROM. The build source tree for the locally rebuilt baseline matches merged main `e250e992`; its binary differs from the earlier release build, so a baseline/candidate pair was built with the same local toolchain. The source patch is the only kernel change between that pair.

| Check | Complex 4627 | Current SpiritBoot | Rebuilt baseline | Candidate |
| --- | ---: | ---: | ---: | ---: |
| Scheduling XBE, diagnostic xemu | 6/6 | 5/6, expected mismatch | 5/6, expected mismatch | 6/6 |
| Scheduling XBE, original xemu | — | — | 5/6, expected mismatch | 6/6 |
| Ordinary/scatter/APC I/O, diagnostic xemu | 333/333 | 333/333 | 333/333 | 333/333 |
| Ordinary/scatter/APC I/O, original xemu | — | — | 333/333 | 333/333 |
| Zero-initialized IOSB and delay observations | 338/338 | 338/338 | 338/338 | 338/338 |

The original executable is `gdcc536830deb.exe`, source `dcc536830deba245eec36cd009db5860ca04884c`, SHA-256 `cd4cfd696aa9c196cf44fd35765e16cf662afc16a689e1af4584fa79398784db`. The separate same-source plugin-enabled diagnostic executable has SHA-256 `75a2abdd708ed761b8ba5d95cb5f37b259567d5434e7d499dad3952d5d8505f6`. The original-executable runs have neither a debugger nor a plugin attached. The instrumented runs matched public call/return pairs without recorder errors and correctly attributed all 32 exercised I/O APC callbacks.

Baseline firmware SHA-256: `569bcbd0ffc69ed92ad8cecc33a4fc064820c8e5646ca6b7d690159a25719104`.

Candidate firmware SHA-256: `a0ac9cbe7c389bf513123ee955a1deac24a93c09a979f194f0ecbfc82f983bc9`.

Both 64 MiB builds complete the kernel INIT-reference checks and boot-menu placement check. The existing firmware host suite passes 54 tests with one existing skip. Receipt hashes are recorded in the accompanying provenance JSON; proprietary ROMs and game data are not included.

## Forza status and remaining scope

Entry threads and the `PsCreateSystemThreadEx` wrapper register through `XeRegisterThread` and receive this initialization. The existing non-Ex `PsCreateSystemThread` wrapper bypasses registration and retains the process-default quantum. That separate path needs its own qualification before claiming the corrected quantum for every public thread-creation API.

This scheduler mismatch was found while investigating delayed Forza scenery. A native recording from boot reproduces missing road at a stopped Civic, but **the candidate has not yet been evaluated at that Forza checkpoint**. The scheduling regression is fixed; causation for the world-loading symptom remains unproven. A matched human-driven Complex/candidate comparison is required before treating this as the Forza fix or publishing it as such.

The frequently observed 2 ms-delay worker reads audio; the main title thread requests the world resources. The initial Forza recorder also misclassified unchanged, initially-zero I/O status blocks as completed reads. Those completion labels are excluded. A revised recorder separately tracks public completion-APC dispatch and has been qualified against a zero-initialized-IOSB XBE.

Delay rounding also differs independently: without contention, a requested 1 ms delay is about 2 ms on Complex and 1 ms on SpiritBoot. At a 20 ms request under contention, the candidate can return after one 20 ms turn while Complex returns after approximately 40 ms. This patch corrects the observed CPU-turn length; it does not change relative-deadline rounding or claim complete scheduling/timer equivalence. Physical hardware, 128 MiB firmware and game-level acceptance are not covered by these receipts.
