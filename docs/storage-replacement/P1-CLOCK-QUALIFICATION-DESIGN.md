# Proposed P1 counter qualification after V2.6.4

Status: design for independent review; no normative qualification and no new
native operation is authorized by this document. The actual V2.6.4 capture
completed only its declared collection scope. All 29 finite QPC/RDTSC intervals
contain the compiled rates; 21 short/overlapping intervals stay INCONCLUSIVE.
The 81,378,105 ns maximum read-start gap is not a backend bound.

## Minimal method

Use raw per-operation and batch RDTSC differences from the untraced generation2
fixture. Bind their conversion rate to the exact per-host compiled clock
function/branch packet. For Deck that fixed rate is 733,333,333 ticks/s. Do not
require a submillisecond serial observer to establish a constant short rate: the
reviewed compiled affine function supplies a difference quantization error below
one tick under its explicit runtime conditions. All measured sample brackets
remain recorded as diagnostic consistency observations rather than empirical
proof of short-interval precision.

The BIOS QPC getter reports 3,374,488 while the compiled raw PM timer advances
3,375,000 ticks/s. Paired-QPC-derived RDTSC metadata therefore has approximately
151.704 ppm fixed low bias, plus its recorded anchor/bracketing uncertainty. Keep
that original metadata and the actual min/median/max aggregates of five estimates;
the original fixtures do not retain the five individual raw anchors, which remain
unknown. Do not silently change old milliseconds or qualify older rows. A future bridge can separately derive
fixed-source seconds under the exact reviewed plan/proof while retaining raw
ticks and origin. Alternatively a predeclared paired raw-tick ratio can cancel
the constant rate/bias within the same host and pinned emulator. It still needs
the same running-clock and actual-order gates; ratios cannot hide pauses,
restarts, clock changes or missing/failed operations.

The separately retained Windows PE packet now binds its own startup and counter
functions. Its integer-scale branch has conversion error below1/R seconds; the
fallback has error below1ns+1/R (about2.364ns), where R=733333333. That fallback
requires actual positive QPF F<=UINT32_MAX. Qualified actual F and the accepted
compiled startup can derive the initialized scale. This is independent Windows
evidence, not application of Deck proof by filename or source resemblance.
Actual F is not yet observed by this draft. Hosts remain separate; no absolute
timing claim follows from an unqualified host clock provider.

## Actual evidence proposed for the runtime branch inference

CLOCK_MONOTONIC, seccomp, libc and vDSO checks below are Deck-specific. Windows
uses the separately pinned PE/QPC/QPF startup packet and actual qualified host
frequency/clock-provider context; it does not inherit Linux constructor checks.

Capture these read-only facts from the exact owned process, outside acceptance
measurement. An additional diagnostic companion may establish availability,
while untraced acceptance processes retain only declared launch/control and
process identity receipts. Do not run a traced observer during acceptance.

| Gate | Actual evidence | Failure/unknown handling |
| --- | --- | --- |
| Compiled function | Exact executable SHA/BuildID and reviewed byte ranges for `cpu_get_tsc`, virtual clock, initialization and enable/disable paths; packet pins | Mismatch rejects; embedded source commit alone insufficient |
| Kernel monotonic availability | Owned observer successful CLOCK_MONOTONIC calls, target/observer boot ID and time-namespace identity, actual kernel version | Different namespace/boot or failed availability is INCONCLUSIVE |
| Constructor context | Target status `Seccomp=0`, actual executable start/lifetime, declared no sandbox/clock override | A filter/unknown startup context is INCONCLUSIVE; no claim of seeing the constructor return |
| Clock symbol context | Record presence of clock-interposition environment names without dumping secrets; reject LD_PRELOAD/LD_AUDIT. Retain actual mapped executable/libc/vDSO identities and reviewed clock-resolution assumptions | Unpinned/preloaded/unknown clock implementation is INCONCLUSIVE; no whole-process source equivalence |
| Time mode | Exact frozen argv/config/env; no `-icount`, replay, clock override or TSC-rate override; actual instantiated xemu matched | Mismatch rejects. The runtime monotonic branch remains an explicitly reviewed construction inference, not an observed variable value |
| Running/ticks | Fresh start, `startPaused=false`, initial/final supported `query-status` running:true/status:running, no declared pause/input/reset diagnostics, retained operations/intervention receipts | Any actual pause/reset/intervention/failure/restart stops the cohort. Continuous VM event exclusion is unobserved under current short-lived managed QMP clients |
| Firmware/counter provenance | Exact published/candidate flash/source/PE pins, unchanged public counter implementation, same fixture/C/XBE; counters monotonic and records complete | Mismatch, duplicate framing, rollback, missing or contradictory results reject |
| Duration quantization | Preserve raw integer deltas; platform-specific exact rational conversion bounds below; no overhead subtraction | A measurement too short for the frozen precision budget remains INCONCLUSIVE |

The constructor argument is conditional: compiled initialization selects
CLOCK_MONOTONIC only if its availability probe succeeds. Same-kernel/time-
namespace availability, no seccomp/interposition and trusted libc mapping can
support that inference under a predeclared host method; they do not measure the
internal flag. Independent review must decide whether this condition is adequate
for the relative/absolute acceptance scope before the method is frozen. If that
condition is unacceptable, a separate authorized companion must observe the
actual flag/lifecycle boundary; do not assert it from a boolean supplied by the
caller.

Continuous exclusion must not be invented from sparse snapshots. A viable
controlled-lab method can predeclare no operator intervention and runner-denied
input/pause/reset controls, retain all available operation receipts and fail on
observed violations. Its unobserved-event limitation belongs in the acceptance
contract. If that assumption is not acceptable, extend supported event capture
or use a separately reviewed companion; polling delay does not solve it.

## Numerical conversion budget to freeze before A/A

Proposed numerical policy, still requiring independent review: each paired
reported metric permits at most0.1% relative uncertainty from counter conversion
arithmetic. This budget does not assert that caller instrumentation, the host
clock provider or environmental noise have this precision. Those are separate
construction/runtime/control conditions and empirical A/A observations.

Use exact rational T=raw_ticks/733333333. The conditional absolute bound e is
1/733333333 seconds for Deck and the Windows divisible-QPF integer branch;
Windows fallback uses1/1000000000+1/733333333 seconds. Retain raw values and
strict bounds; do not round the bound downward. Measured latency has interval
[max(0,T-e),T+e]. Rank per-operation lower/upper endpoints for p95/p99; use the
batch interval for throughput inversion and batch latency. No observation is
dropped because its interval is short or overlaps zero.

For a positive baseline metric A and candidate B with bounds [a0,a1] and
[b0,b1], the possible ratio is[b0/a1,b1/a0] if a0>0. Require both endpoint
relative deviations from the reported central ratio to be<=0.001 for the
conversion-budget qualification. A zero lower endpoint or exceeded budget makes
that entire paired metric INCONCLUSIVE, with original data retained; it is not
a favorable filter. Statistical bounds must also include these deterministic
uncertainty endpoints rather than compare a rounded center alone. All methods,
platform conditions and the numerical budget are fixed before A/A/candidate data.

The future importer must separately preserve historical frequency-derived
milliseconds and aggregates while labeling the new source-informed conversion.
This policy does not authorize rewriting older qualification rows or add a
native measurement by itself.

## Before any P1 baseline calibration

Independent review approves the narrowed clock/provenance/control assumptions
and exact precision budget; the new plan freezes every host's conversion or
raw-tick comparison policy before candidate values. A/A pilots then determine
actual environmental noise and count planning, with actual submit/start order,
matched fresh processes/cache policies and failures retained. Full36 functional
qualification can proceed separately with raw ticks and no accepted timing
conversion. Physical flush/durability and private structural counters remain
missing until actual diagnostic companion evidence exists; timing agreement
cannot fill them.
