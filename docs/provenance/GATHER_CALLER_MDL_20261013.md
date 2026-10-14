# Large synchronous gather writes: caller-page MDLs

Baseline SpiritBoot creates a Length + 4096-byte nonpaged bounce allocation and
copies every synchronous gather-write byte before dispatch. The accepted route
borrows already validated/pinned WB source PFNs, constructs one MDL and establishes
its CPU mapping before dispatch. If cache eligibility, MDL construction or
mapping fails, the request selects the original bounce path before dispatch.
There is no retry after dispatch. Completion retires the map before the MDL and
then the caller pins. Reads, async snapshots and requests below 64 KiB retain the
bounce route. The flag uses existing request-header padding.

The 64 KiB cutoff is a conservative measured policy, not a proven optimal
crossover. An initial all-size candidate slowed the 8 KiB gather median by
24.46% in six of seven pairs (overlapping ranges). After retaining the small
bounce path, two independent seven-pair cohorts show the 2 MiB gather median
about 14% lower in every pair, with disjoint observed ranges: 5.796→4.977 ms and
5.988→5.146 ms. All 28 native runs pass all72 byte/status/count/EOF/source-canary
checks. Intermediate-size and small-request ranges overlap; no speed claim is
made for those sizes. Flat controls retain slower observations: final 2 MiB flat
median +4.81% (six slower pairs, overlapping ranges), and 512 KiB +18.16% (five
slower pairs, overlapping ranges). Those controls follow the different gather
path in the same run and are not independent causal attribution. The final
all-leaf campaign separately checks ordinary file and streaming operations.

Production-source tests cover115 completion/pending/error/cancellation,
allocation/map/header/cache fallback, partial-page and snapshot cases. Independent
review verified actual MmMap/MmUnmap/IoFreeMdl and native completion ordering.
Host mocks are device/mapping boundary models; no physical Xbox qualification,
Forza/title speedup or net native peak-RAM measurement is claimed. Avoiding the
2 MiB-plus-page temporary bounce is structural, while mapped-VA/PT/MDL overhead
still exists. Diagnostic builds are excluded from performance comparisons.

CI exposed a host-fixture address dependency: the fake cache map initialized
only an allocation's first PDE, and the uncached case relied on a later request
allocation sharing the source PDE. The fixture now initializes every covering
PDE and explicitly sets the source cache attributes. This fixes the model;
firmware bytes remain unchanged. Exact logs, analyzers and every cohort are
retained in the remaining-memory qualification evidence.

The complete seven-pair API removal control now validates all 14 runs. Every
634 enabled assertion passes in both ROMs. Removing only this patch does not
consistently eliminate the earlier four slow signals, and all four control
ranges overlap. The full table still retains flush and reopen trends; this
acceptance is limited to correct lifetime/fallback behavior and the repeated
large-transfer gain, not a universal I/O improvement.
