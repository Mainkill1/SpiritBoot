# ATA/PATA completion hot-path investigation

## Disposition

Patch `0151-ata-cache-capture-hotpath.patch` removes cache-publication
bookkeeping from ordinary ATA reads while preserving the existing IDENTIFY
publication protocol. It applies cleanly after the assembled 0149 stack and
after product patch 0150. The patches are structurally independent: 0150
changes `native_packet.c` and its existing host test, while 0151 changes
`native_capture.inc`, `scsi.c`, and adds a separate oracle. Their file overlap
is empty. Patch 0151 does not change PATA controller programming,
interrupt/poll transitions, request ordering, SG ownership, or queue state.

This work used only SpiritBoot-owned/current source, public contracts, exact
release-i386 objects, and measurements. No prohibited legacy ClassPnP, Disk,
or nxcdrom implementation body was inspected.

## Finding

The Forza census recorded 1,024 calls each to `AtaReqStartRequest`,
`PataStartIo`, and `AtaReqCompleteRequest` in the measured load interval. Every
ordinary READ10 request was paying cache-publication costs intended for the two
IDENTIFY commands:

1. Start reset the per-request cache writer by calling the general
   `nx_lcq_define` classifier with an invalid destination.
2. Start called `nx_lcq_define` again after translation even when the final ATA
   command was neither IDENTIFY DEVICE (`0xec`) nor IDENTIFY PACKET (`0xa1`).
3. Completion always constructed and copied an `nx_lcq_result`, although an
   ordinary request has no callback or internal cache worker that can consume
   it.

The cache protocol only admits a writer for the two IDENTIFY commands. These
operations were therefore redundant on the game-read route.

## Change

- Reset the 12-byte writer with three direct zero dword stores instead of a
  general classifier call and a copy through stack storage.
- Return before classification when the translated command is not `0xec` or
  `0xa1`.
- Capture a completion result only if a translation callback or internal worker
  can consume it.
- For a real consumer, always store a current result, including `Started=0`.
  This prevents stale request storage from making a changed or failed command
  look publishable.

Actual-start generation invalidation remains immediately before controller
submission. Internal IDENTIFY still copies its result to worker-owned storage
before request reuse. Runtime IDENTIFY still presents the current result to its
callback before any successor starts.

## Release-i386 evidence

The exact `-Os` i386 object comparison shows:

| Route | 0149 baseline | Candidate | Difference |
|---|---:|---:|---:|
| `AtaReqStartRequest` total text | 284 bytes | 264 bytes | -20 bytes |
| Ordinary start caller route | 89 instructions, 5 calls | 63 instructions, 3 calls | -26 instructions, -2 calls |
| Skipped invalid `nx_lcq_define` callees | 2 × 15 instructions | 0 | -30 instructions |
| Ordinary completion cache prefix | 41 instructions, 1 call | 12 instructions, 0 calls | -29 instructions, -1 call |
| Skipped `nx_lcq_result_copy` callee | 14 instructions | 0 | -14 instructions |
| Total ordinary-I/O bookkeeping route | — | — | **-99 dynamic instructions** |

`AtaReqCompleteRequest` grows from 892 to 904 bytes because it retains the cold
consumer path and adds the consumer guard. The ordinary route jumps directly
to common completion processing. No division, compiler helper, assembly, or
intrinsic was introduced.

`PataStartIo` and `port_leave` have byte-identical function disassemblies before
and after the patch stack. `PataStartIo` consists of hardware-visible device
selection, mandatory status waits, DMA/taskfile programming, and the existing
IRQ/poll transition. `port_leave` is one saved-IRQL load and the required
`KfReleaseSpinLock` call under the portable callback ABI. Exact disassembly did
not expose compiler waste that could be removed without changing hardware or
locking semantics, so both receive a rigorous no-change disposition.

## Isolated benchmark

The benchmark uses the exact baseline/candidate inline adapters plus the
production cache property/query implementation, compiled with `-Os`. Six
interleaved pairs each execute 200,000,000 ordinary-I/O bookkeeping iterations
on one pinned CPU:

| Arm | Median | Mean |
|---|---:|---:|
| 0149 baseline | 11.122367 ns/I/O | 11.122799 ns/I/O |
| Candidate | 1.009794 ns/I/O | 1.011831 ns/I/O |

The median delta is **-90.921%**. Both arms produced the same 200,000,000 sink
count in every run. This result measures only the isolated cache bookkeeping
slice; it is not an end-to-end disk, map-load, or game-performance claim.

## Verification

- New poison-storage oracle: plain and ASan/UBSan passes.
- Native adapter: 28 groups plain and 28 groups sanitized, zero failures.
- Owned nxstorage: 50 request-engine cases, 8 pthread ownership cases, 13
  geometry scenarios, 20 cache-query cases, 16 adapter scenarios, and 34
  lower-cache cases all pass.
- Retained SG selection, lifecycle, and DMA-operation checks pass.
- DMA lifetime: 116 production scatter/paging cases pass with exact payload and
  restored protection.
- Full 64 MiB release firmware build succeeds.

The new oracle poisons writer/result storage and verifies ordinary, cached and
local IDENTIFY, invalid-length, started, unstarted, consumer, and no-consumer
paths. The explicit unstarted-consumer case guards against the stale-result bug
that a simpler `Started`-only condition would introduce.

## Build provenance

- Patch 0151 SHA-256:
  `80dd78a0f3ee6d4b54a5677d174cb7e20f83c844d4398e57dc53aecd9179756d`
- Expected assembled source tree through 0149:
  `a8f3fc46e27bc8e0f51f23708a02a73237565b2e`
- Verified 0150-only source tree:
  `92c25b513752b18f45fa4c0cc1c8619de82238f9`
- Baseline 0149 release BIOS SHA-256:
  `07c52600c710adb5a7ca7748904603a13174e261ce2ce24923dafb0df4b2277a`
- Candidate 0149 + ATA patch release BIOS SHA-256:
  `10613e4f583ccbebf25c8091dc5b0f69d06c098bf616baeb55a49f2e11b15576`
- Candidate assembled source tree:
  `f20fc4b2da9067416c2787b5c69ad655daeb277a`
- Candidate source worktree SHA-256:
  `43eec4bc83ced7a7526598b412ce029211f67382349d6ba15db10e10a9f10576`
- Candidate firmware lock SHA-256:
  `2f92789c607547829c0413eb15a8f5424200a9dde2ae9edd494bc7d2fe162146`

The candidate BIOS is an isolated qualification artifact. Final native
two-boot/game qualification belongs to the parent integration batch after 0150
and 0151 are assembled in product order.

## Reproduction

From an assembled source tree with patches through 0149:

```sh
git apply --check --whitespace=error-all 0151-ata-cache-capture-hotpath.patch
git apply 0151-ata-cache-capture-hotpath.patch
python3 tests/host/atapi-cache-hotpath/check.py "$PWD" /tmp/ata-cache-hotpath
python3 tests/host/nxstorage/check.py "$PWD" /tmp/nxstorage
python3 tests/host/nxstorage/check_adapter.py "$PWD" /tmp/nxstorage-adapter
python3 tests/host/atapi-retained-sg/check.py "$PWD" /tmp/retained-sg
python3 tests/host/atapi-retained-sg/check-lifecycle.py "$PWD" /tmp/retained-sg-lifecycle
python3 tests/host/atapi-retained-sg/check-dma-ops.py "$PWD" /tmp/retained-sg-dma
python3 tests/host/dma-lifetime/check.py "$PWD" /tmp/dma-lifetime
```

The delivery manifest hashes every patch, specification, measurement, source,
disassembly, build summary, and test log used for review.
