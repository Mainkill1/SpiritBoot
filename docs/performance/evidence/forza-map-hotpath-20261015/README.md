# Forza map-stream hot path

This evidence set qualifies the independently authored SpiritBoot storage path
against a generated release-only workload shaped from public request metadata.
The XBE issues 1,024 asynchronous FATX reads at queue depth 12 under the
900-page pressure point and repeats that pass 16 times. It contains no title
data. No prohibited legacy ClassPnP, disk, CD-ROM, or filesystem implementation
body was inspected.

## Accepted batch

The corrected release64 candidate combines six bounded changes:

1. `0147-retained-pata-sg-workspace.patch` retains the single-active-command
   PATA scatter/gather workspace across requests. It removes 32,768 allocation
   and free pairs, about 27.25 MiB of transient allocator traffic, from one
   complete fixture invocation. The exact-body host route is 83.6% lower cost;
   two prior native boots improved end-to-end APC batch time by 3.18% versus
   the queue-depth-16 control.
2. `0148-native-storage-qd12-hotpath.patch` uses bounded free-slot state and a
   full state scan to decide quiescence. The accepted v7 has no wake counter or
   notification-cardinality dependency. It preserves the lifetime fence,
   round-robin cursor, cancellation, recovery, durability and parent reentry.
   Long host CPU improves 5.27% versus the pre-pump path. Release-i386 size and
   branch counts fall in the pump, submit, completion, cancel and quarantine
   routes.
3. `0149-fatx-hot-read-extent.patch` remembers one generation-checked physical
   extent already proved by the resident FAT validator. It retains the 16
   sparse checkpoints, falls back on every miss or malformed fact, and
   invalidates before allocation-chain mutation. The exact mapping route is
   4.34% faster, with 52.15% fewer `VfatTryMapRead` calls and 51.63% fewer
   `FatResource` acquisitions in the measured replay.
4. `0150-native-packet-prepare-hotpath.patch` replaces repeated byte and
   generic-clear work with target-shaped fixed-size operations after explicit
   object-size, alignment, source-bound and page-range proofs. The final Deck
   A/B/B/A run reduces exact `nx_packet_prepare` weighted instructions 33.33%,
   TB executions 30.65%, and diagnostic attributed CPU 21.17%. The whole
   profiled phase was noisy and is not used as an end-to-end claim.
5. `0151-ata-cache-capture-hotpath.patch` bypasses cache-publication work for
   ordinary ATA reads while retaining IDENTIFY publication, invalidation and
   consumer ordering. It removes 99 dynamic i386 bookkeeping instructions on
   each ordinary-I/O route; the isolated bookkeeping slice improves 90.92%.

Patch `0146-forza-map-queue-depth.patch` supplies the 16-entry HDD envelope
needed to admit the title's observed 12-request burst. Patches 0147 through
0151 optimize work inside that fixed-capacity route.

Patch `0152-ata-400ns-status-reads.patch` was removed after real-game testing
exposed sporadic missing or corrupt Forza menu data. Four Alternate Status
reads consume bus time on physical ATA hardware but zero elapsed guest time in
xemu, so the candidate removed a required optical ATAPI settle interval. The
active release restores `KeStallExecutionProcessor(1)`. The audit, before/after
screenshots, rejected patch, and permanent regression guard are under
`ata-stall/` and `forza-menu-corruption/`.

The replacement `0152-emulator-advanced-controls.patch` keeps the delayed
ATA select path as the default. Y opens a session-only Advanced page whose top
row toggles every current experiment and reports Off, On, or Mixed. Individual
contiguous-cache and ATA rows remain available. QEMU ATA-HDD detection is
retained only as an unconsumed future capability signal; it cannot change ATA
timing. The hidden BACK credits action remains available. See
`ata-stall/EXPLICIT-ADVANCED-ATA.md` for the code and test contract.

The preceding automatic-QEMU release64 image
`08afa8ab25c48765f51390a8bdfb41ccde298dbef23eb4048642f131bf0d215c`
froze during operator testing and is rejected. The safe-default replacement
release64 image is
`b266d2a130c4c3c02cf396aea4af3d294107ccffbf04593e1d156d9a638b51cd`.
Release128 is
`fdfcb2382d3b24a0d4aaa7f8037792b00bd82daf2640bf40d1b9b1f8c036f340`.
Both assemble tree `2f6790bae801075928f1ff556aed1ef2d2938858`.

These identities remain the historical Forza integration evidence. Later
patches 0153 and 0154 do not rewrite those measurements. Patch 0154 closes the
largest separately measured remaining firmware-owned SYSVA gap; its exact
release images, A/B/B/A result and reproduction bundle are in
[`../sysva-local-invalidation-20261016/`](../sysva-local-invalidation-20261016/).

Two independent Windows release64 boots completed 32 passes and 32,768
measured reads at QD12 with zero request, oracle, cleanup or warmup failures.
Compared with the mean of the two retained-SG boots, the combined candidate
improves end-to-end APC batch time by 0.79% and summed submission time by
5.84%. The summed post-return intervals overlap concurrent requests and rise
15.61%; they are diagnostic occupancy, not additive wall time. The end-to-end
result governs. See `pump-v7-fatx-native-summary.json` and the exact request and
analysis files.

The superseded 0146--0152 image completed two more independent
Windows release64 boots: another 32 passes and 32,768 reads, again with zero
request, oracle, cleanup or warmup failures. Against the retained-SG two-run
mean, the final mean improves end-to-end APC batch time 3.93% and submission
time 5.82%. Against the 0147--0149 two-run mean, the final mean improves APC
batch time 3.16% and the overlapping post-return interval 13.13%; submission
time is effectively unchanged (+0.02%). `return_after_apc` rises 14.65% versus
retained-SG but accounts for only about 35.7 thousand ticks versus 48.4 million
end-to-end ticks. It is reported rather than hidden and is not the governing
load-time metric. These performance values are historical evidence only because
0152 failed the subsequent optical game load. See
`final-integration/final-native-summary.json`.

Human-driven Forza remains the final streaming acceptance gate. The synthetic
fixture proves request correctness and a non-regressing measured route; it
cannot prove when the game publishes road/world resources.

The exact release64 image also completed two independent Steam Deck OpenGL
runs of the frozen 144-leaf, five-group XISO suite. All 149 records passed the
same-host policy in both runs, with zero applicable oracle failures and zero
functional-hash differences from the prior candidate. The sum of the 144
two-run leaf means improved 8.09%. This aggregate is descriptive because the
suite includes emulator-heavy routes outside firmware control. The only
initial result above the 20% review threshold was the sub-millisecond
`report_query.dma_target_switch` leaf. A balanced prior/current/current/prior
follow-up used 4,096x fixed work, 64 warmups, 16,384 iterations and 15.4--16.1
seconds of measured work per run. All four records passed, and the current
two-run mean was 1.95% slower, closing the short-sample signal. No leaf remains
above the 20% threshold after sustained review. See `final-broad-xiso/`.
The current image was faster in 119 of 144 leaves (82.64%) and slower in 25;
this is below a 90% leaf-win target and is not represented as such.

## Rejected and superseded pump designs

Early v1 and v2 variants shortened callback deferral and timed out natively due
to child-IRP lifetime/reentry faults. v3 improved host speed but retained an
unsafe scheduling shape. v4 fixed completion coalescing but coalesced Boolean
admission notifications. v5 counted admissions but a separate Rust state model
found cursor starvation. v6 preserved fairness and completed two native boots,
but its wake counter was unnecessary: persistent slot state plus a complete
bounded scan already decides whether work exists. v7 removes that shared state
and is the accepted design.

The Rust model, rejected patches, native failure receipts and v5/v6 summaries
remain in this directory so a fast but incorrect design cannot be mistaken for
qualified work. The transition contract is
`docs/storage-replacement/independent-implementation/request-engine/QD12-TRANSITION-SPEC.md`.

## Function-level census

`deck-function-census/` records the first complete 1,024-read pass on the Steam
Deck: 190 exact function entries plus one range-only interrupt attribution,
13,550,787 weighted guest instructions and no dropped or overflowed counters.
Every executed row has a measured share and an explicit optimization,
hardware/correctness, diagnostic or follow-up disposition. The retained-SG
baseline identifies `_pump` (10.45%), `VfatTryMapRead` (10.29%),
`NxNativeAdapterSubmit` (3.29%) and `nx_packet_prepare` (2.74%) as the main
software-controlled storage costs. The accepted pump and extent changes target
the first three; packet preparation and ATA/stall attribution are separate
focused reviews. Profiler wall/CPU timing is excluded because the plugin
perturbs it.

The 16 rows originally marked as follow-up candidates are now closed by the
pump/native-adapter, FAT mapping/checkpoint, packet-preparation and ATA-cache
patches, or by exact no-change review of `PataStartIo` and `port_leave`. The ATA
settle-delay candidate was rejected after it caused optical menu corruption;
the reviewed outcome retains required hardware and interrupt ordering. The
later SYSVA campaign covers the remaining separately measured firmware-owned
allocation gap.

## Reproduction map

- `retained-sg-native-summary.json`: two retained-SG native controls and their
  queue16 comparisons.
- `pump-v6-native-summary.json`: qualified but superseded v6 native runs.
- `pump-v7-fatx-native-summary.json`: accepted combined native candidate.
- `fatx-hot-extent/`: exact-body mapping benchmark, i386 metrics and checks.
- `packet-prepare/`: corrected packet specification, exact disassembly, host
  sanitizer results and final Steam Deck A/B/B/A captures.
- `ata-cache-capture/`: ordinary-I/O cache-bookkeeping proof, disassembly and
  isolated benchmark.
- `ata-stall/`: rejected ATA settle optimization, test-gap analysis, regression
  policy, and the earlier native measurements retained as negative evidence.
- `forza-menu-corruption/`: exact source audit and failing/restored screenshots.
- `pump-v7-host/`: final pump manifest and locked checksums.
- `rust-pump-model/`: independent language state model and v5/v6 audits.
- `deck-function-census/`: compact raw counters, full disposition ledger,
  analyzer/plugin source, runner request and configuration.
- `final-broad-xiso/`: two exact-release full-suite runs, all 144 leaf means,
  and the sustained ABBA disposition of the only initial >20% result.
- `rejected-*.patch`, `forza-map-stream-pump-v5-*`, and the lock-prototype
  directory: negative evidence only.

The current exact assembled source passes the extent oracle twice (12,056
checks), 20,795 checkpoint checks, five real FAT/async coupling scenarios, 126
allocation-free asynchronous-read checks, and the packet suite in plain,
ASan/UBSan and MSan modes. The complete product host suite passes 535 tests
with 26 expected platform skips. Native execution uses release firmware
without a debugger or firmware tracing.
