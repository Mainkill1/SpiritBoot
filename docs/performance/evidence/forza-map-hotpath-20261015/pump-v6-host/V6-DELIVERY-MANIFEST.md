# nxstorage QD12 v6 candidate delivery manifest

## Status and boundary

This is a **candidate**, not a release-qualified change. It has full host,
sanitizer, fairness, and release-i386 object evidence. It still requires an
integrated release BIOS build and native xemu A/B before acceptance.

The work used only SpiritBoot's independently authored `nxstorage`, its public
behavior contracts and host tests, and original-prose measurement notes. No
legacy ClassPnP, Disk, or nxcdrom implementation body was inspected. The
candidate was developed in this isolated scratch tree and did not modify the
product repository.

## Integration unit

Apply this as the next numbered patch after the assembled 0146 source:

```text
deliverable/0147-native-storage-qd12-hotpath-v6.patch
SHA-256 b0d64b130d630a81d0cf4fb3b51a8e8992bd1debb2998b24d04ad6c4e320c59e
```

The patch changes only:

- `drivers/storage/class/nxstorage/request.c`
- `drivers/storage/class/nxstorage/request.h`
- `drivers/storage/class/nxstorage/native_adapter.c`
- `tests/host/nxstorage/request_test.c`
- `tests/host/nxstorage/native_adapter_test.c`

`patch --dry-run -p1` succeeds against the unmodified assembled 0146 source.
The integrated product location is
`patches/roswell/0148-native-storage-qd12-hotpath.patch`, after the accepted
`0147-retained-pata-sg-workspace.patch`. The patch bytes and SHA-256 are
unchanged. Do not include v1-v5 patches.

## Pinned source inputs

The patch was generated against these exact assembled inputs:

| File | SHA-256 |
|---|---|
| `request.c` | `3236fb633bb2bc13ba7dce401dd5efc0672b93958132342e783522402b6c39d4` |
| `request.h` | `4f791f7647270b46feadff138af54ad92f74800b1d863568c80933fd1d00447a` |
| `native_adapter.c` | `9a50d64d7996db63bc326d2fc895d9190c0ce67f657d6dd3cb459df12d2bc3c9` |
| `native_adapter.h` | `9c40be9f1413b5384bb9c92f6e9c41b4190cc467079575b7a149d4a97c321b67` |
| `native_packet.c` | `22e20350e6d0323b6bebdbe471ac8bdab72b5bcedd6a6a0740d9e9cca9222c00` |

The independently supplied assembled-source pin was
`da043f...`; integration must replace the abbreviated provenance note with the
repository's complete generated source identity rather than copying this
abbreviation into a lock file.

Candidate source hashes after applying v6 are:

| File | SHA-256 |
|---|---|
| `request.c` | `def88c55c14c1baa3b3ec1f55534f58f762d3dc7e974e3417851d1a1e060a0ab` |
| `request.h` | `bbba2955a0bc1c71f854fc515786d9bdb4348abcba49078f72e9fd897a46d377` |
| `native_adapter.c` | `89afb6fc60e86d81dc615410bc24559c56e387ccd2363f20f38ba8bf64e2681e` |

`native_adapter.h` and `native_packet.c` are unchanged.

## What v6 changes

The candidate removes two linear admission scans by maintaining O(1) free
lists for core slots and adapter envelopes. It keeps one round-robin pump owner,
uses a saturating notification counter, starts scans at a targeted cursor,
transfers an idle pump directly to the event caller, and clears only the
recycled mutable slot range whose other fields are overwritten explicitly.

The following lifetime and correctness work remains unchanged:

- Full IRP/SRB/MDL packet preparation and the `submit_active` /
  `result_deferred` lower-call reuse fence.
- Adapter and cancel spin-lock transitions.
- Generation and command-token validation.
- Cancellation after lower ownership commits.
- Queue freeze, release, recovery, and quarantine.
- Write-through durability, flush ordering, and read/write barrier rules.
- Parent completion outside the core lock and optical control-path separation.

Two v6 fairness rules are mandatory:

1. Admission, lower completion, and cancellation retarget the cursor only when
   they acquire an idle pump. A notification during an active pump increments
   `wake` and preserves the owner's cursor.
2. SEND never releases pump ownership. It consumes at most one notification
   and loops. Only a complete lock-held round-robin scan that finds no action
   may reset `wake`, clear `pumping`, and return.

The transition-level proof and test mapping are in
`NXSTORAGE-QD12-TRANSITION-SPEC-v6.md` (SHA-256
`f4de6551416f8660e67ee88c8ffe1e784e1410ba8a0089547a62e0d1889da8ea`).

## Rejected iterations

| Version | Result | Rejection cause |
|---|---|---|
| v1 | 24.90% host CPU gain; native warmup left 6 outstanding | Removed data-path callback deferral, allowing envelope/child reuse before the outer `IofCallDriver` returned. |
| v2 | 17.92% host gain; native warmup left 5 outstanding | Restored lower-call fence, but Boolean wake plus read-completion early exit lost coalesced completion/admission work. Deterministic RED tests reproduce both cases. |
| v3 | Full original pump plus free lists | Correctness-safe isolation step, but 189.93 vs 181.78 ns/I/O was 4.48% slower. |
| v4 | 13.30% host gain | Fixed completion coalescing but retained Boolean wake; deterministic admission coalescing failed before native qualification. |
| v5 | 11.88% host gain; prior suites passed | Completion reentry could retarget the active owner's cursor to a repeatedly reused read slot and starve an older write. SEND could also clear `pumping` without a full scan. |
| v6 | 6.05% host gain; all current host evidence green | Candidate for integrated native release qualification. |

## RED/GREEN evidence

The new test `completion_reentry_cannot_starve_eligible_write` keeps replacing
completed reads in their just-freed slots while an older write is eligible. It
requires the write to reach transport before the finite read stream ends. It
fails on v5 and passes on v6. `randomized_mixed_reentry_is_fair` adds 1,024
pseudorandom reads/writes at QD4 with randomized lower completion order and a
bounded submit window.

The preserved v5 RED log has 50 tests and exactly one failure:

```text
completion_reentry_cannot_starve_eligible_write:
watched_write_command && watched_write_unissued > 0
```

Artifact: `results/v6-fairness-red.log`, SHA-256
`478c6b6ed614b28f89e0ccf1fffc80e69be472d344bbe934da134a7fb778c07a`.

The v6 core command was:

```sh
CC=clang python3 tests/host/nxstorage/check.py .test-v6-green
```

It passed:

- request engine: 50/50
- pthread ownership/reentry: 8/8
- geometry composer: 13 scenarios, 6,001 checks
- cache query: 20/20
- geometry/owner adapter: 16 scenarios, 61,973 checks
- lower cache publication: 34/34
- i386 freestanding object checks: no unexpected helper

Artifact: `results/v6-green-core.log`, SHA-256
`3469148aa1f3fc0975bcbc6c13fc3ca491bc7a0387111a812eda26cb9392ce10`.

The native-shaped adapter command was:

```sh
CC=clang python3 tests/host/nxstorage/check_adapter.py .test-v6-adapter
```

It passed 28/28 groups in both plain and ASan/UBSan builds. The fixture includes
delayed single-active-lower service, 12 pending reads, 1,024 randomized QD12
completion bursts, synchronous lower completion, completion-triggered parent
reentry, and an explicit assertion that the same child cannot be reused until
`IofCallDriver` returns.

Artifact: `results/v6-green-adapter.log`, SHA-256
`4f2d9a13a72e32cff228db59fbbfa2926c51f065e5bad53642a44efa1b8c9bfc`.

## Long host benchmark

The benchmark compiles the production request engine, packet builder, native
adapter, cache query/property, disk owner, optical profile, and driver against
the host platform shim:

```sh
clang -std=c11 -O3 -DNDEBUG -DNX_NATIVE_ADAPTER_HOST -pthread \
  -I drivers/storage/class/nxstorage -I tests/host/nxstorage \
  -include tests/host/nxstorage/native_adapter_host_platform.h \
  drivers/storage/class/nxstorage/request.c \
  drivers/storage/class/nxstorage/native_packet.c \
  drivers/storage/class/nxstorage/native_adapter.c \
  drivers/storage/class/nxstorage/cache_query.c \
  drivers/storage/class/nxstorage/cache_property.c \
  drivers/storage/class/nxstorage/nxdisk_owner.c \
  drivers/storage/class/nxstorage/nxcdrom_profile.c \
  drivers/storage/class/nxstorage/driver.c \
  deliverable/qd12_adapter_bench_long.c \
  -o deliverable/qd12-candidate-v6-long
```

Each process reports the median of five 1,000,000-batch QD12 samples, or 60
million I/O operations per process. Three independent process medians were
compared against the unmodified 0146 build of the same fixture:

| Variant | Process medians (ns/I/O) | Median |
|---|---|---|
| assembled 0146 | 181.78, 180.93, 184.31 | 181.78 |
| v6 | 171.63, 170.59, 170.79 | 170.79 |

The measured host CPU-path improvement is **6.05%**. This is CPU overhead per
I/O in the fixture, not a claim about native media latency or game frame rate.

Artifacts:

- `qd12_adapter_bench_long.c`, SHA-256 `499cb98f30e2aacd65510c3d7132de88f039dbcfa260322463ff161eb0fad7d4`
- `qd12-candidate-v6-long`, SHA-256 `61e4b9d2a6d2c4a11a3fb484a397684d977a8b05cf5c2822126d607b2217553c`
- `results/v6-long.txt`, SHA-256 `6d7625af15354fa539b099fc6d0a958dfd01c38f23881b558be093de1c387a09`
- `results/v6-summary.json`, SHA-256 `32a7783f407981bd455b83d7f8211c5f74265f064ec51d408685191224c5cd80`

## Release-i386 code-shape audit

Candidate and baseline request/adapter/packet objects were compiled with the
actual release command extracted from `ninja -t commands`, including
`-march=pentium -mtune=generic -Os -DNDEBUG= -ffunction-sections -flto
-ffat-lto-objects -fno-omit-frame-pointer -DNX_NATIVE_TARGET=1
-DXBOX_RAM_MIB=64 -DXB_EMULATOR_FILE_MEDIA=1`.

The main request-engine changes are:

| Function | Baseline bytes/instructions/conditional branches | v6 | Finding |
|---|---:|---:|---|
| pump (`run_pump`) | 2084 / 565 / 90 | 2176 / 582 / 92 | Fair scan/wake state adds 17 instructions; SEND has no unscanned idle exit. |
| `nx_device_init` | 372 / 111 / 25 | 440 / 129 / 27 | Builds core free list once at initialization. |
| `nx_start` | 1172 / 357 / 55 | 1164 / 357 / 53 | Removes the slot scan; free-head pop and reduced clear offset added. |
| `nx_lower_done` | 204 / 61 / 10 | 244 / 75 / 13 | Counts notification and retargets only on idle-owner acquisition. |
| `nx_cancel` | 116 / 39 / 5 | 160 / 56 / 8 | Same ownership/fairness rule. |
| `nx_quarantine` | 44 / 18 / 1 | 76 / 30 / 4 | Counts notification while preserving active cursor. |

Adapter functions executed by the read fixture are either unchanged or have
the following measured changes:

| Function | Baseline bytes/instructions/conditional branches | v6 | Finding |
|---|---:|---:|---|
| `release_envelope_locked` | 88 / 27 / 3 | 116 / 31 / 4 | Pushes the envelope to the O(1) free list. |
| `NxNativeAdapterInitialize` | 820 / 219 / 22 | 860 / 228 / 22 | Builds the envelope free list once. |
| `NxNativeAdapterSubmit` | 1356 / 341 / 30 | 1364 / 336 / 29 | Removes admission scan: five fewer instructions and one fewer conditional branch. |

`command_envelope`, `port_prepare`, `port_submit`, `port_retire`,
`port_complete`, `finish_parent`, `NxNativeAdapterChildComplete`,
`NxNativeCreateClassDevice`, and `NxNativeDispatchReadWrite` are unchanged.
They retain packet layout, lower-call deferral, cancellation, and completion
contracts. `native_packet.c` machine-code disassembly is identical; its large
`nx_packet_prepare` body remains because it rebuilds IRP/SRB/MDL state.

Exact disassembly confirms:

- Baseline adapter admission has a count compare, `slot * 0x598`, active test,
  increment, and loop; v6 loads `free_envelopes` then `next_free`.
- Baseline core admission has a loop with `index * 0xf8` plus
  active/generation tests; v6 loads `free_head` directly.
- v6 clears 172 command/state bytes versus the baseline 248-byte slot clear,
  reducing every admission clear by 76 bytes.
- v6 SEND returns to scan after consuming zero or one wake; it has no
  `pumping=0` branch.
- Cursor stores in start/completion/cancel appear only in idle-owner branches.

The request object has no undefined helper. Adapter undefined symbols are
expected kernel/public dependencies. `__udivdi3` appears only in geometry
control output and is outside the QD12 read route. GCC already emits `rep stosl`
for the aligned clears. The small pump/submit frame changes do not provide
evidence for a safe handwritten assembly replacement. No assembly or intrinsic
change is proposed.

Detailed machine counts are in `disasm/function-metrics-v6.csv` and `.json`.
The `.asm`, symbol, and undefined-symbol files in `deliverable/disasm` provide
the instruction-level evidence.

## Integration pins and required native gate

Integration must update every identity that covers the assembled storage
source: patch order/lock data, firmware assembled-source hash, workflow source
pin, host production coverage input list, and any release map/report receipt.
The existing nxstorage, adapter, packet, owner, optical, sense, completion, and
XBE API tests must remain enabled.

Before merging or releasing, run an integrated **release 64 MB** build and:

1. Confirm the source/patch identity gate and final LTO link pass in the real
   Git worktree.
2. Run the full host and adapter commands above on the integrated tree.
3. Run the native QD12 XBE warmup/steady fixture and require zero stranded
   requests, exact completion count, no child reuse before lower return, and no
   timeout.
4. A/B Forza map streaming on the same release xemu/ISO/HDD/config, recording
   issue-to-APC latency, outstanding depth, throughput, and map-load wall time.
5. Exercise cancellation, reset, save, optical boot/control, and queue recovery
   before treating the candidate as release-ready.

An isolated full release build compiled all v6 nxstorage sources but stopped at
the project source-identity link gate because this clean-room scratch tree has
its Git reference deliberately disabled. The error was `storage link evidence
failed: cannot validate assembled Git source identity`; it was not a compiler
or code failure. The exact object audit is therefore pre-final-LTO, and native
interrupt/DPC timing remains unqualified until the integrated gate above.
