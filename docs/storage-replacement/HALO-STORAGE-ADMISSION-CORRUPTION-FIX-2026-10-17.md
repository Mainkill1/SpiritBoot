# Halo and Forza storage admission corruption fix

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

## Root cause

`NX_NATIVE_DISK_SLOTS` preallocated 16 native envelopes, and the request core
also had exactly 16 slots. When a game submitted a seventeenth concurrent HDD
request, `NxNativeAdapterSubmit` completed the game IRP immediately with
`STATUS_INSUFFICIENT_RESOURCES`. That status described SpiritBoot's private
pool limit, not a real machine resource failure. Halo abandoned the affected
cache/resource load. Forza could similarly omit or defer world assets under a
storage burst.

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

The repository integration suite passes 70 tests with one environment skip.
The final release 64 MiB candidate has SHA-256
`f4496a595b1116a6b696c1f2c1a856f0a70239de2e99e98cd46f1fd424f4d635`.

Live Halo validation used fresh private HDD overlays for every boot:

- diagnostic xemu with IDE and texture-source hashing: 5/5 clean;
- ordinary release xemu: 5/5 clean; and
- combined repaired candidate: 10/10 clean, compared with 3/5 corrupt for the
  matched 16-slot candidate.

The final rebuild, which also makes removal wait for transient envelopes,
passed a further 2/2 ordinary-release cold boots.

The 64-slot preallocation image was only a causal experiment and is not the
release design.
