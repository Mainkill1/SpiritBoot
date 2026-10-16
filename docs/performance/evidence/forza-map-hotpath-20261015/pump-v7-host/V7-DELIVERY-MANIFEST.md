# nxstorage QD12 v7 candidate delivery manifest

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
deliverable/0147-native-storage-qd12-hotpath-v7.patch
SHA-256 50f60210f910d94022df822ca8681ef43fd3495c4828a77ea54d92d5b7adc497
```

The patch changes only:

- `drivers/storage/class/nxstorage/request.c`
- `drivers/storage/class/nxstorage/request.h`
- `drivers/storage/class/nxstorage/native_adapter.c`
- `tests/host/nxstorage/request_test.c`
- `tests/host/nxstorage/native_adapter_test.c`

`patch --dry-run -p1` succeeds against the unmodified assembled 0146 source.
The intended product location is
`patches/roswell/0147-native-storage-qd12-hotpath-v7.patch`, followed by the
normal patch-order/lock and assembled-source identity refresh. Do not include
v1-v5 patches.

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

Candidate source hashes after applying v7 are:

| File | SHA-256 |
|---|---|
| `request.c` | `c01a2ed43def5ec3b5302b731b711720c5f4577938f23243ccc5fd224c101856` |
| `request.h` | `b5f368291012b37fd689d532bbe5f249ac37039a7f09205ab5f6e59bb87292cd` |
| `native_adapter.c` | `89afb6fc60e86d81dc615410bc24559c56e387ccd2363f20f38ba8bf64e2681e` |

`native_adapter.h` and `native_packet.c` are unchanged.

## What v7 changes

The candidate removes two linear admission scans by maintaining O(1) free
lists for core slots and adapter envelopes. It keeps one round-robin pump owner,
starts scans at a targeted cursor, transfers an idle pump directly to the event
caller, and clears only the recycled mutable slot range whose other fields are
overwritten explicitly. v7 removes the v6 notification counter: persistent slot
state is the work record and every external action returns to a bounded scan.

The following lifetime and correctness work remains unchanged:

- Full IRP/SRB/MDL packet preparation and the `submit_active` /
  `result_deferred` lower-call reuse fence.
- Adapter and cancel spin-lock transitions.
- Generation and command-token validation.
- Cancellation after lower ownership commits.
- Queue freeze, release, recovery, and quarantine.
- Write-through durability, flush ordering, and read/write barrier rules.
- Parent completion outside the core lock and optical control-path separation.

Two v7 ownership rules are mandatory:

1. Admission, lower completion, and cancellation retarget the cursor only when
   they acquire an idle pump. Quarantine claims an idle pump at the existing
   round-robin position. An event during an active pump publishes persistent
   state and preserves the owner's cursor.
2. SEND always loops. Only a complete lock-held round-robin scan that finds no
   action may clear `pumping` and return.

The transition-level proof and test mapping are in
`NXSTORAGE-QD12-TRANSITION-SPEC-v7.md` (SHA-256
`993d10bea325cd6cc0de446025f6dd67f505120c97638d9ef1f5d6d1cf81b2c9`).

## Rejected iterations

| Version | Result | Rejection cause |
|---|---|---|
| v1 | 24.90% host CPU gain; native warmup left 6 outstanding | Removed data-path callback deferral, allowing envelope/child reuse before the outer `IofCallDriver` returned. |
| v2 | 17.92% host gain; native warmup left 5 outstanding | Restored lower-call fence, but Boolean wake plus read-completion early exit lost coalesced completion/admission work. Deterministic RED tests reproduce both cases. |
| v3 | Full original pump plus free lists | Correctness-safe isolation step, but 189.93 vs 181.78 ns/I/O was 4.48% slower. |
| v4 | 13.30% host gain | Fixed completion coalescing but retained Boolean wake; deterministic admission coalescing failed before native qualification. |
| v5 | 11.88% host gain; prior suites passed | Completion reentry could retarget the active owner's cursor to a repeatedly reused read slot and starve an older write. SEND could also clear `pumping` without a full scan. |
| v6 | 6.05% host gain; all current host evidence green | Independent audit found `wake` carried no authorization or idle proof once every action looped and only a full scan could idle. Superseded by the smaller v7 state machine. |
| v7 | 5.27% conservative host gain; all current host evidence green | Candidate for integrated native release qualification. |

## RED/GREEN evidence

The new test `completion_reentry_cannot_starve_eligible_write` keeps replacing
completed reads in their just-freed slots while an older write is eligible. It
requires the write to reach transport before the finite read stream ends. It
fails on v5 and passes on v7. `randomized_mixed_reentry_is_fair` adds 1,024
pseudorandom reads/writes at QD4 with randomized lower completion order and a
bounded submit window.

The preserved v5 RED log has 50 tests and exactly one failure:

```text
completion_reentry_cannot_starve_eligible_write:
watched_write_command && watched_write_unissued > 0
```

Artifact: `results/v6-fairness-red.log`, SHA-256
`478c6b6ed614b28f89e0ccf1fffc80e69be472d344bbe934da134a7fb778c07a`.

The v7 core command was:

```sh
CC=clang python3 tests/host/nxstorage/check.py .test-v7-green
```

It passed:

- request engine: 50/50
- pthread ownership/reentry: 8/8
- geometry composer: 13 scenarios, 6,001 checks
- cache query: 20/20
- geometry/owner adapter: 16 scenarios, 61,973 checks
- lower cache publication: 34/34
- i386 freestanding object checks: no unexpected helper

Artifact: `results/v7-green-core.log`, SHA-256
`3469148aa1f3fc0975bcbc6c13fc3ca491bc7a0387111a812eda26cb9392ce10`.

The native-shaped adapter command was:

```sh
CC=clang python3 tests/host/nxstorage/check_adapter.py .test-v7-adapter
```

It passed 28/28 groups in both plain and ASan/UBSan builds. The fixture includes
delayed single-active-lower service, 12 pending reads, 1,024 randomized QD12
completion bursts, synchronous lower completion, completion-triggered parent
reentry, and an explicit assertion that the same child cannot be reused until
`IofCallDriver` returns.

Artifact: `results/v7-green-adapter.log`, SHA-256
`4f2d9a13a72e32cff228db59fbbfa2926c51f065e5bad53642a44efa1b8c9bfc`.

Removing `wake` exposed no hidden dependency, so no new RED implementation was
created. The unchanged coalesced-admission, coalesced-completion, fairness,
pthread, and native-shaped adapter tests are the proof: they remained green
with the field and every read/write removed.

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
  -o deliverable/qd12-candidate-v7-long
```

Each process reports the median of five 1,000,000-batch QD12 samples, or 60
million I/O operations per process. Three independent process medians were
compared against the unmodified 0146 build of the same fixture:

| Variant | Process medians (ns/I/O) | Median |
|---|---|---|
| assembled 0146 | 181.78, 180.93, 184.31 | 181.78 |
| v7 | 173.48, 170.53, 172.21 | 172.21 |

The conservative host CPU-path improvement is **5.27%**. A second interleaved
v7/baseline/baseline/v7 comparison measured 170.35/183.82/195.22/180.44 ns/I/O,
or 7.33% and 7.57% paired improvements. An interleaved v7/v6/v6/v7 comparison
measured 170.94/170.23/170.46/170.80 ns/I/O; v7 was 0.31% slower than v6 in
that pairing, within host-run variance, while deleting unnecessary shared-state
writes and branches. These are CPU overhead measurements, not claims about
native media latency or game frame rate.

Artifacts:

- `qd12_adapter_bench_long.c`, SHA-256 `499cb98f30e2aacd65510c3d7132de88f039dbcfa260322463ff161eb0fad7d4`
- `qd12-candidate-v7-long`, SHA-256 `41d98333e00424d066f30e970b61d646e4de916a6f2cd01a99852d768917c890`
- `results/v7-long.txt`, SHA-256 `f5e28ecafb2bff05004d86d390ac2f02d81d779c67fc0ca65303b22b4e3b1304`
- `results/v7-v6-interleaved.txt`, SHA-256 `7787b2173a9dd37fb4d1c7aeefa0ea1de7a1cd03f7f69a320659d66d2e25225f`
- `results/v7-baseline-interleaved.txt`, SHA-256 `d804da258e06fa343c00919aa0deec058395e7f1d8dd4af62bf28f89393fa233`
- `results/v7-summary.json`, SHA-256 `f91df6dd073131561472f314baae38b6a3b610211a7ad979e80a9a0326368bb9`

## Release-i386 code-shape audit

Candidate and baseline request/adapter/packet objects were compiled with the
actual release command extracted from `ninja -t commands`, including
`-march=pentium -mtune=generic -Os -DNDEBUG= -ffunction-sections -flto
-ffat-lto-objects -fno-omit-frame-pointer -DNX_NATIVE_TARGET=1
-DXBOX_RAM_MIB=64 -DXB_EMULATOR_FILE_MEDIA=1`.

The main request-engine changes are:

| Function | Baseline bytes/instructions/conditional branches | v7 | Finding |
|---|---:|---:|---|
| pump (`run_pump`) | 2084 / 565 / 90 | 2164 / 586 / 91 | SEND has no unscanned idle exit; removal of counter bookkeeping removes 12 bytes and one conditional branch versus v6. |
| `nx_device_init` | 372 / 111 / 25 | 440 / 129 / 27 | Builds core free list once at initialization. |
| `nx_start` | 1172 / 357 / 55 | 1144 / 348 / 52 | Removes slot scan and active-owner counter write; free-head pop and reduced clear remain. |
| `nx_lower_done` | 204 / 61 / 10 | 232 / 71 / 12 | Retargets only on idle-owner acquisition; active owner discovers `done` by scan. |
| `nx_cancel` | 116 / 39 / 5 | 148 / 51 / 7 | Idle owner acquisition remains; active owner discovers `cancelled` by scan. |
| `nx_quarantine` | 44 / 18 / 1 | 64 / 26 / 3 | Idle acquisition remains; active pump sees persistent quarantine state. |

Adapter functions executed by the read fixture are either unchanged or have
the following measured changes:

| Function | Baseline bytes/instructions/conditional branches | v7 | Finding |
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
  increment, and loop; v7 loads `free_envelopes` then `next_free`.
- Baseline core admission has a loop with `index * 0xf8` plus
  active/generation tests; v7 loads `free_head` directly.
- v7 clears 172 command/state bytes versus the baseline 248-byte slot clear,
  reducing every admission clear by 76 bytes.
- v7 SEND returns directly to scan; it has no notification bookkeeping and no
  `pumping=0` branch.
- Cursor stores in start/completion/cancel appear only in idle-owner branches.

The request object has no undefined helper. Adapter undefined symbols are
expected kernel/public dependencies. `__udivdi3` appears only in geometry
control output and is outside the QD12 read route. GCC already emits `rep stosl`
for the aligned clears. The small pump/submit frame changes do not provide
evidence for a safe handwritten assembly replacement. No assembly or intrinsic
change is proposed.

Detailed v6/v7 request-engine counts are in
`disasm/function-metrics-v7-request.json`; the v6 full-call-path counts remain
in `disasm/function-metrics-v6.csv` and `.json` because adapter and packet code
did not change in v7.
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

The prior isolated full release build compiled all v6 nxstorage sources but
stopped at the project source-identity link gate because this clean-room scratch
tree has its Git reference deliberately disabled. The error was `storage link
evidence failed: cannot validate assembled Git source identity`; it was not a
compiler or code failure. v7's changed request object was then rebuilt with the
same exact release-i386 command. The object audit is pre-final-LTO, and native
interrupt/DPC timing remains unqualified until the integrated gate above.
