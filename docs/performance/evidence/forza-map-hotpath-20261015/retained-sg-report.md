# Forza async FATX non-nxstorage profile

Scope: current independently assembled release source only. No legacy
ClassPnP, Disk, or nxcdrom implementation body was inspected.

## Workload normalization

The dedicated fixture submits 1,024 asynchronous, noncached FATX reads at
queue depth 12 with a 900-page pressure target. The 1,024 requests transfer
10,871,296 bytes and describe 3,619 pages (3.534 pages/request mean, 17-page
maximum). Every request is at most 64 KiB and maps to one ATA READ command.

The fixture reports 16 measured passes. `recorder_execute(..., warm=true)`
runs a warmup batch before each measured batch, so a complete invocation
actually drives 32,768 reads/ATA commands. The result contains 16,384 timed
reads.

## Dynamic ranking

| Rank | Route | Per measured pass | 16 measured | Full fixture including warmups | Assessment |
|---:|---|---:|---:|---:|---|
| 1 | Generic HAL SG allocation/free | 1,024 pairs | 16,384 pairs | 32,768 pairs | Fixed 872-byte target buffer despite normally one SG element; implemented retained-buffer candidate eliminates hot allocation/free. |
| 2 | FATX direct-map cluster lookup, likely 16 KiB clusters | 20,348 FAT link inspections, 1,024 cache maps | 325,568 links, 16,384 maps | 651,136 links, 32,768 maps | Potentially large, but prior coarse extent attempt did not improve the game. Instrument direct-map hits and link counts before another rewrite. |
| 3 | Default IDE callback bridge | about 4,095 start/ISR/finish/start-next bridge traversals | about 65,520 | about 131,040 | Exact-pointer fast paths can preserve public hooks while bypassing default global-state trampolines. |
| 4 | Ineligible lower-cache publication tracking | 1,024 tracking sequences; about four LCQ calls/read | 16,384 sequences | 32,768 sequences | Ordinary READ can never publish the IDENTIFY cache. Gate on a tracked-identify flag. |
| 5 | Large-page MDL PFN fill | 3,619 PFN iterations | 57,904 | 115,808 | Validate one 4 MiB PDE and span-fill sequential PFNs until its boundary. |
| 6 | FAT seek-checkpoint locking | 3,072 LastMutex transactions | 49,152 | 98,304 | Remove the separate hot prepare transaction while retaining lookup/update locking. Expected smaller gain. |
| 7 | ATA device/port queue layers | one enqueue/dequeue chain per command | 16,384 chains | 32,768 chains | High-risk collapse; retain until lock/queue counters prove dominance. |

The FAT model uses the current 16-checkpoint algorithm and a likely 16 KiB
FATX cluster size. Its steady-pass distribution is 19.87 link inspections per
read mean, 1 median, 106 p95, and 211 maximum, with exactly 1,024 cache map
batches. Cluster-size sensitivity: 4 KiB 78,374 links/pass; 8 KiB 39,705;
16 KiB 20,348; 32 KiB 10,762; 64 KiB 5,710.

## Retained SG candidate

PATA sets `Controller->QueueDepth = 1`. The candidate allocates one HAL-sized
872-byte nonpaged SG workspace when the channel starts, only when queue depth
is one and the DMA calculate/build operations exist. Each command passes that
workspace to `BuildScatterGatherList`. Completion still calls
`PutScatterGatherList`, so buffer flushing and map-register release are
unchanged. The active request owns the sole port slot until resource release;
the next request cannot overwrite the workspace. Final removal drains queues
before freeing it. Multi-slot ports retain the original allocated path.

This removes 872 KiB of transient allocation traffic per measured pass,
13.625 MiB across the reported 16 passes, and 27.25 MiB across the actual
warmup-plus-measured fixture. It also removes 1,024 allocator lock paths on
submit and 1,024 frees on completion per pass.

An `-O3` host benchmark compiled the exact production HAL calculate, build,
get, put, adapter callback, and SG construction bodies against immediate
adapter/MDL boundaries. In 101 alternating samples of 1,024 lifecycles:

* allocated median: 15.540 microseconds/1,024
* retained median: 2.550 microseconds/1,024
* isolated SG-lifecycle speedup: 6.09x (83.6% less time)
* observed hot allocations/frees: 103,424/103,424 on allocated samples and
  zero on retained samples

This microbenchmark proves the structural cost disappears. It does not prove
a 20% end-to-end read improvement. The dedicated release XBE and live Forza
load still need AB/BA measurement.

The final release link exposes the previously unreachable HAL calculate/build
operations. Relevant symbol sizes are: Calculate 0x28, Build 0x258, Get 0x54,
Put 0x5c, `AtaReqSendRequest` 0x2a4. The raw kernel grew from 502,784 to
503,296 bytes; the final compressed kernel payload is 46,892 bytes.

## Verification and artifacts

* Exact patch: `retained-sg.patch`, SHA-256
  `7fc90c71f590c14ccf1f927b1cc9d0927f8682ddb5b6e5b398279ed6c0a208a7`
* Release 64 MiB flash: `sg-build3/flash.bin`, SHA-256
  `3f6011f15282b44c0c7dac74e9e81b42fe99ebe58a9b9e9d718a498f18a24f69`
* Benchmark result: `sg-benchmark/result.json`
* Focused TDD: retained selection/fallback, one-time allocation and queue-depth
  guard, Xbox DMA operations exposure
* Existing regression checks: 116 DMA lifetime cases, DMA channel cases, PCIIDE
  PnP lifetime cases
* Full Release 64 MiB firmware build and init-reference audit pass
* `git diff --check` and patch apply check pass

## Measurement gate

For each candidate, run two 16-pass release fixture captures in AB/BA order.
Record submit-sum, corrected APC batch, command/byte/IRQ/APC counts, direct-map
hits/fallbacks, FAT links/cache maps, PFN pages, TAG_DMA allocations and bytes,
SG elements, PRD elements, LCQ tracked/untracked calls, IDE default/hooked
bridges, and device/port queue transitions. Accept only identical command,
byte, IRQ, and APC totals with a repeatable timing gain beyond run noise.
