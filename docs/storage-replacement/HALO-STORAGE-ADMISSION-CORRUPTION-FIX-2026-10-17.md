# Halo menu corruption: rejected HDD reads at the admission ceiling

## Current finding and repair

Working backward from the missing menu labels established the full failure
chain. Diagnostic run `20261017-220010097-1f13b532d1f7447fbf48ebd9dad8ccb8`
on release64 `f4496a59…` observed 1,647 native adapter submissions and their
1,647 parent completions. Exactly 172 completed with
`STATUS_INSUFFICIENT_RESOURCES` (`0xc000009a`), zero bytes; every rejection was
an attempted 65th outstanding request. Disassembly locates the rejecting
callback in `nx_start`'s empty free-slot branch, not a failed pool allocation.

| Menu entry | HDD byte offset | Guest buffer | Completion | Bytes |
| --- | --- | --- | --- | ---: |
| Campaign | `0x52071e00` | `0x82574000` | Success | 16,384 |
| Multiplayer | `0x52274c00` | `0x827a0000` | Insufficient resources | 0 |
| Settings | `0x52c11e00` | `0x83160000` | Insufficient resources | 0 |
| Game Demos | `0x52c21e00` | `0x83170000` | Insufficient resources | 0 |

The submitted destination buffers match the decoded menu textures below.
Campaign entered at depth 23. The other three entered at attempted depth 65,
received no HDD fill, and were subsequently rendered with old/zero contents.
This proves a failed-load cause for these captured menu defects. It does not
prove that all reported Forza symptoms share this cause.

Patch `0162` had moved the capacity failure from 16 to 64. Patch
`0163-queue-saturated-native-admission.patch` instead separates outstanding
parent requests from the bounded transport window:

- Keep 64 core slots and the 16-envelope reserve; retain burst envelopes only
  while requests are outstanding.
- Enqueue parents in FIFO order when transport capacity is occupied. A single
  admission owner starts them as slots retire, without returning a fabricated
  resource failure to the game.
- Retain the envelope while starting a request, including inline completion
  and cancellation. Queued cancellation removes the parent without touching
  the lower driver. Existing core write/flush barriers still apply.
- Drain queued requests on quarantine and include admission activity in device
  removal rundown. Real nonpaged-pool exhaustion can still fail allocation.

The production adapter regression first failed on request 65 with the old
implementation. With the queue, 256 simultaneous reads complete to distinct
buffers, verified by first/last-word payload signatures and exact byte counts.
The fixture also removes the device with the burst pending, and separately
checks queued cancellation and write/flush ordering. All 36 adapter groups pass
plain and ASan/UBSan; the eight focused product integration/lock tests pass. This is host
contract coverage, not a claim of complete game qualification.

### Memory-pressure follow-up

The queue-only candidate (`6b31d660…`, tree `f3e4160b…`) passed five ordinary
release launches and 20 exact menu-buffer comparisons. Its diagnostic run
`20261017-221507283-60af2ca690324137bfdaec0d27739f68` proves the four menu
reads complete successfully at outstanding depths 25, 74, 189 and 192. However,
it still rejects two other reads at depth 213. Their completion caller is the
native adapter's failed-envelope-allocation branch, not `nx_start`'s slot cap.
The exact failing allocation inside that envelope construction was not captured.

A narrower allocation probe in run
`20261017-221810311-3b22583e613b4b0aa54fecd7a824df6e` observes all 1,646 requests
complete successfully at a peak of 204. It does not reproduce the allocation
failure, but the available-page counter reaches 19 while allocating envelopes.
Do not call the earlier two failures solved based on a clean screenshot.

Patch `0164-compact-data-overflow-envelopes.patch` removes unnecessary control
storage from data-only transient envelopes. The release compiler requests 756
bytes for a data envelope instead of 1,560, moving it from the 2,048-byte pool
bucket to the 1,024-byte bucket. It also avoids the private control MDL (normally
128 pool bytes). Child IRPs and the existing 16 full reserve envelopes remain.
Control requests still allocate the full tail and MDL. Thus each overflow data
request saves 1,152 pool bytes, about 220.5 KiB at 196 overflow requests; this is
an allocation-shape calculation, not a measured whole-game footprint reduction.

The new regression limits overflow pool requests to 1,200 bytes and forces
control-MDL allocation failure. Data reads must still queue/complete without
allocating a control MDL. The old implementation fails this test; the compact
one passes it plus the larger 256-read payload/rundown test and all existing
control/recovery groups under ASan/UBSan.

Patch `0165-cancel-before-native-admission.patch` completes an already-cancelled
parent before queue insertion, even when all transport slots are occupied. The
same lock protects the cancellation latch and insertion. Its regression covers
both pre-cancelled dispatch and cancellation immediately after cancel-routine
installation, with zero extra lower I/O. The original queue implementation fails
that test; the final implementation passes. Independent review confirmed the
correction and found no further concrete important issue in the three patches.

The compact image below (before the cancellation correction) passed five
ordinary release launches, with all four entries visible and all 20 buffers
byte-identical to valid label references. Three diagnostic launches completed
1,646/1,646 requests each, zero resource failures, at peaks of 209, 210 and 213
outstanding. These are repeated retained-HDD results, not independent fresh-cache
runs. Qualification of the final cancellation-corrected binary follows below.

Compact precursor release64 SHA-256:
`7e88501da2969a0e549197f61751c5c3d2779ccdf09b88e6ea046290c23d36f9`.
Assembled source tree: `455e6093bf8b5e04f2e47b2614c7990cea83115a`.
Final cancellation-corrected release64 SHA-256:
`add882b6f50e9c9ae49705bb8374be5646e44ed1b72f0e2eb4b77bdedeeaf296`.
Assembled source tree: `84e1d572b5a3a4ae81c78c28a0855908a909acf1`.
The exact final image completed two request-probe launches, 1,646 successful
requests each, zero resource errors or allocation failures, peak 209 outstanding.
The minimum sampled `MmAvailablePages` during overflow allocation was 69 in
both. This counter is sampled at allocation returns, not continuously across
all game activity. Ordinary-release/reset qualification is recorded below.

### Final exact-binary qualification

The final `add882b6…` image passed five ordinary-release xemu launches. All four
menu entries passed the per-entry image check on every launch; all 20 captured
16 KiB label buffers matched the valid reference hashes. Two further runs
passed the four-entry check both before and after QMP system reset. These runs
used the Windows USER desktop PowerShell pipe, release xemu `f3c528eeec86`,
64 MiB, Vulkan and the same retained HDD/EEPROM. They do not cover fresh-HDD
initialization, a complete campaign, disc replacement, or every memory sector.

The reproducibility directory records each run ID and check result in
`final-release64-five-run-results.json`, `final-reset-results.json`, and
`final-request-summary.json`. Runner completion alone is not the pass criterion.
The two diagnostic runs above add 3,292 successful request completions on this
exact BIOS, with no resource or observed allocation failures.

All 36 production adapter groups pass plain and ASan/UBSan after the final
cancellation correction; the final focused product/coverage suite passes 21
tests. A broader host run passed 555 tests with 26 platform skips, but started
before that last correction; it is not an immutable final-head full-suite result.
Exact-head CI and broader game qualification still gate merge/release. No new
load-speed improvement is claimed. PR251 remains draft.


Reproduction tools, pinned probe bindings, before-result data, and the
four-entry screenshot gate are in
[`tools/halo_menu_backtrace`](../../tools/halo_menu_backtrace/README.md).
The following sections retain the earlier investigation and correct its
claims; their earlier clean-run counts did not close the issue.

## Historical reopening after operator testing

On 2026-10-17 the operator reported missing Settings and Game Demos on a
fresh Halo launch; both returned on the second launch. At that stage the intermittent menu
failure was therefore unresolved. The earlier successful screenshots and host
fixtures do not establish a complete fix. Do not merge or release this candidate
on the strength of the earlier clean-run counts.

Audit of the repeat-run configurations also found that they reused
`halo-dma-compare-20261017/halo-spirit.qcow2`. The scripts did not create a new
overlay for each run. The earlier claim of a fresh private HDD for every boot
was incorrect. A screenshot-exists check was evidence collection, not an
automated check that all four menu entries rendered.

## Failure and boundary trace

The replacement storage stack could render corrupted Halo menu textures and
produce similarly sporadic missing or delayed assets in Forza. The first
boundary comparison established that the disc data itself was correct:

- the current source with the legacy storage backend reached a clean Halo menu
  in 10/10 cold boots;
- the replacement stack corrupted 4/5 matched cold boots;
- clean and corrupt replacement boots issued the same 150 optical commands and
  transferred the same 13,234,176 bytes with matching payload hashes;
- 598 of 603 pages covered by optical DMA were byte-identical in a matched
  clean/corrupt memory capture; and
- a diagnostic xemu build hashed every Vulkan texture source at use time and
  found zero stale texture-cache hits.

The next trace followed the visibly corrupt 256 KiB texture range backward.
In clean boots, later HDD DMA refreshed that range before the GPU consumed it.
In corrupt boots, that HDD read never reached the IDE controller, so the game
rendered the allocation's older contents. This is why an optical-only trace
could show correct bytes while the final frame was still corrupt.

## Earlier finding: 16-slot adapter defect, before the complete game trace

`NX_NATIVE_DISK_SLOTS` preallocated 16 native envelopes, and the request core
also had exactly 16 slots. When a game submitted a seventeenth concurrent HDD
request, `NxNativeAdapterSubmit` completed the game IRP immediately with
`STATUS_INSUFFICIENT_RESOURCES`. That status described SpiritBoot's private
pool limit, not a real machine resource failure. The host fixture proves that
admission defect. The game trace did not establish the entire chain from a
specific failed parent IRP to the missing menu entries; attributing all Halo
and Forza symptoms to this defect was too strong. The later backward trace above establishes that causal link at the remaining
64-slot limit.

A one-variable release experiment increased only the HDD window from 16 to 64.
The previous 16-slot candidate corrupted 3/5 captured boots; the 64-slot
experiment was clean in 5/5. Every clean run contained the HDD refresh that was
absent from the corrupt runs.

Investigation also found a separate child-IRP lifetime violation. An
asynchronous lower completion could re-enter the core pump and reuse its child
IRP before the lower completion callback returned. Patch
`0161-defer-native-child-completion.patch` correctly defers that retirement to
a DPC and retains its regression test. Live testing showed that change alone
still corrupted 3/5 boots, so it is a required contract repair rather than the
cause of this visible failure.

## Repair

Patch `0162-transient-native-envelope-growth.patch` removes the fabricated
16-request failure without permanently preallocating 64 full envelopes:

1. The lightweight request-core window is four times the normal envelope
   reserve, giving the 16-envelope production profiles 64 admission slots.
2. The existing 16 envelopes remain the allocation-free common path.
3. A burst beyond 16 allocates a temporary envelope, child IRP, and control
   MDL from nonpaged pool and submits the request normally.
4. Terminal completion places temporary envelopes on a trim list. An adapter
   DPC frees their IRP, MDL, and envelope after the completion stack has
   unwound.
5. A real allocation failure still returns `STATUS_INSUFFICIENT_RESOURCES`.

The steady-state envelope allocation and fast path are unchanged. Extra memory
exists only while more than 16 requests are active, and overflow objects are
reclaimed after the burst.

## Regression and validation

The production-function host fixture submits 17 simultaneous 4 KiB HDD reads
through a 16-envelope adapter. Before the repair, request 17 completes with the
false resource failure. After the repair, all 17 remain pending at the lower
driver, complete with the correct byte counts, and the fixture verifies that
the temporary pool allocation, IRP, and MDL are freed.

The same fixture now covers overflow cancellation and contention between a
pending control request and data requests. Results:

```text
before: saturated_pool_grows_transiently_instead_of_failing_game_reads:
        NxNativeDispatchReadWrite(...) == STATUS_PENDING
after:  adapter-plain: 32 adapter groups, 0 failures
        adapter-sanitized: 32 adapter groups, 0 failures
```

The focused firmware and storage integration suite passes 71 tests with one
environment skip. The complete host suite passes 554 tests with 26 expected
host-platform skips. The final release 64 MiB candidate comes from assembled
tree `eb48b3dab7214b799300469da208cf9364408644` and has SHA-256
`f4496a595b1116a6b696c1f2c1a856f0a70239de2e99e98cd46f1fd424f4d635`.

Earlier Halo screenshot observations (reused private HDD overlay, not a
fresh overlay for each boot):

- diagnostic xemu with IDE and texture-source hashing: 5/5 clean;
- ordinary release xemu: 5/5 clean; and
- combined repaired candidate: 10/10 clean, compared with 3/5 corrupt for the
  matched 16-slot candidate.

The final rebuild, which also makes removal wait for transient envelopes,
passed a further 2/2 ordinary-release cold boots.

The 64-slot preallocation image was only a causal experiment and is not the
release design.

## Required follow-up evidence

- Check Campaign, Multiplayer, Settings, and Game Demos individually; do not
  treat screenshot presence or process survival as a correctness result.
- Separate fresh overlays, retained caches, and resets with exact input hashes.
- Trace HDD and DVD operations, offsets, lengths, completion status and actual
  byte counts, destination spans, and payloads at completion and use. Account
  for PIO, DMA, cached I/O, scatter/gather, and memory reuse explicitly.
- Compare matching logical assets rather than demanding raw physical addresses
  or unrelated memory pages match between independently allocated runs.
- Report unobserved boundaries as gaps; do not infer full coverage from a
  matching optical-command count or a limited final-memory snapshot.

## Backward trace from the failed menu (2026-10-17)

The Windows lab reproduced the operator's exact missing Settings/Game Demos
case on the unchanged final image in run
`20261017-214732481-777065b88da149ef9f8b7554f6e544d8` at 30 and 60 seconds.
The next run `20261017-214843748-07171724c0a44b6b98ba4e1c9e80f3e5` displayed
all four entries both before and after reset. These were retained-HDD runs.

A following diagnostic release-xemu run,
`20261017-215224375-9c1d90ffabfc45d89bafd69999bccdff`, captured full RAM and
texture-use hashes. Decoding the four 16 KiB menu textures as 256x64 DXT3 ties
visible labels to their physical memory ranges:

| Physical start | Menu entry | Failed capture |
| --- | --- | --- |
| `0x02574000` | Campaign | Correct decoded label |
| `0x027a0000` | Multiplayer | Non-label bytes / noisy decoded image |
| `0x03160000` | Settings | All 16,384 bytes zero |
| `0x03170000` | Game Demos | All 16,384 bytes zero |

An ordinary-release run with memory capture,
`20261017-215548208-c095454ea87842beb7bb49c6edc6971a`, has valid Multiplayer and
Settings textures at those same addresses while Game Demos remains zero.
Another ordinary run `20261017-215626146-552257a381d14a12b75e77cd90d3712b`
has Game Demos present and Settings zero. Decoded alpha planes show the labels;
this links the missing pixels to particular data buffers, rather than merely
comparing unrelated memory pages.

In the failed diagnostic run the GPU first uses the Settings/Game Demos ranges
with the zero-content hash. No HDD DMA completion in that run targets either
16 KiB range. Campaign has a complete 32-sector HDD fill. That initially showed only missing fills. The subsequent pinned request probe
described above establishes why those exact upper requests failed.

The optical readback checks in this diagnostic run all match their source
payloads; the newly traced HDD DMA completions report no backend errors. Those
checks do not validate the upper guest request result or memory lifetime.
