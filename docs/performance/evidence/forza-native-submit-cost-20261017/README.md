# Native submission-cost candidates, 2026-10-17

The [causal findings](CAUSAL-FINDINGS.md) connect the title's deadline to the
owned submission path and separate demonstrated causes from remaining work.

Five narrow owned-code experiments investigate avoidable work in the native
storage adapter. The selected stack ends at 0168; 0169 and 0170 remain
unselected after native tests failed to establish a repeatable gain. These are not an established
Forza fix. Ordinary generated burst tests
found no consistent gain from 0166. The repeated 0167 synthetic comparison is mixed; see
[its full eight-case archive](../forza-complex-cadence-20261017/candidate0167/).
0168 has passed host, release64 build and one generated native burst run;
[that single observation](../forza-complex-cadence-20261017/candidate0168/)
does not establish a stable speedup or title repair.
The public read/callback comparison and fixture limitations are recorded in
[the cadence evidence](../forza-complex-cadence-20261017/) and
[the live-latency evidence](../forza-live-latency-20261017/).

The [buffered caller-budget investigation](../forza-budget-attribution-20261017/)
identifies the exact title exit condition: a roughly 457 microsecond elapsed
budget, beginning before its initial alertable poll. Higher inclusive read-call
cost leaves room for fewer submissions; the observed outstanding count remains
far below its limit. The [owned control-flow audit](owned-submit-path.md) follows
lock release through IRQL lowering, DPC retirement and synchronous pump work,
and identifies the specific bookkeeping removed by these patches.
The [deeper phase capture](../forza-budget-attribution-20261017/OWNED-PHASES.md)
localizes broad adapter/pump cost and rules out packet preparation as its main
component. Added observation hooks perturb timings, so these scopes establish
localization rather than exclusive CPU costs or release-speed predictions.

The source used for the diagnostic baseline was left unchanged. Candidate work
used independent copies of owned source. None uses proprietary
implementation code, title instructions, title-derived constants, or a title
specific branch. All retain the ATA settle delay, cancellation path, lower
completion unwind, admission queue, and existing transport callback boundaries.

## 0166: signal rundown only after sealing

[0166-sealed-rundown-notifications.patch](../../../../patches/roswell/0166-sealed-rundown-notifications.patch)
adds a `sealed` check at the two existing rundown-event signals:
`release_envelope_locked` and the idle exit of `admit_waiting_requests` in
`native_adapter.c`. The only waiter, `unbind_cache_publication`, runs after
`NxNativeAdapterSeal`. Normal admission and retirement previously called
`KeSetEvent` despite having no possible teardown waiter. The event is a
synchronization event, so the kernel's already-signaled notification-event
shortcut does not apply.

The same adapter lock serializes sealing, the waiter's idle check, and both
signal decisions. Completion before sealing needs no remembered notification:
the subsequent idle check sees that completion. Completion after sealing still
signals, including completion between the idle check and the actual wait.
The event remains an auto-reset synchronization event; no waiting or ownership
protocol changes.

The new steady-state host test first failed on the unchanged implementation,
then passed with the two guards. A second test completes the final read exactly
between removal's idle check and its event wait. A separate mutation that
removed the final-release wake was rejected immediately. Existing threaded
removal, transient-envelope, cancellation, and lower-unwind tests also pass.
See [the baseline failure](rundown-baseline-red.log) and
[the missing-wake mutation result](rundown-missing-wake-mutation.log).

These calls already run at `DISPATCH_LEVEL` under the adapter lock. Removing
their dispatcher bookkeeping does not eliminate the surrounding IRQL release
or move completion work out of submission. Ordinary native burst results were
mixed rather than an improvement; 0166 is therefore a cleanup candidate, not
a demonstrated performance repair.

## 0167: skip inactive slots without changing pump order

[0167-skip-inactive-native-slots.patch](../../../../patches/roswell/0167-skip-inactive-native-slots.patch)
adds two 32-bit active-slot masks to the private core state. The production
adapter has 16 retained envelopes and a core capacity of 64. Before this patch,
`run_pump` visits all 64 slots on an unsuccessful pass even with only one request
active. The candidate visits only active slots for capacities up to 64. Larger
capacities retain the original linear scan.

This is an algorithmic work reduction, not a measured latency gain. A pending
single-request idle pass examines one active slot instead of 64 slot records.
The candidate still evaluates every active slot using the original scheduling
logic; inflight, blocked, cancelled, terminal, and recovery slots are not
excluded by the bitmap.

The invariant is that a bit is set exactly while its slot is active. Both
updates occur under the existing core lock, next to the original `active=1`
and `active=0` transitions. Initialization clears the masks. Completion clears
the bit before making the slot available for reuse, including exhausted
slot-generation cases. Cancellation and lower completion do not remove active
slots; they update the same persistent slot state used by the original pump.

`nx_active_scan_next` preserves the original circular scan's cursor and
remaining-distance values after each returned active index. If no active slot
remains in the pass, it accounts for the inactive suffix and ends at the
original scan's final cursor. The pump still returns to the same lock-held idle
handoff. A command-construction failure retains its selected slot so the
existing terminal-slot retry remains effective. Transport callbacks stay
outside the lock. No lock acquisition or release is coalesced.

This differs from the previously
[rejected pump-lock candidate](../forza-map-pump-lock-rejected-20261015/), whose
host improvement did not translate into a native submission improvement.
That rejected change has not been reintroduced.

## 0168: combine two empty adapter bookkeeping windows

[The owned submission audit](owned-submit-path.md) traces the exact nested
DPC/completion path and enumerates the ordinary pending-read lock entries.
[0168-coalesce-native-adapter-bookkeeping.patch](../../../../patches/roswell/0168-coalesce-native-adapter-bookkeeping.patch)
combines retained-envelope reservation/publication and the admission tail when
no cancellation is needed. Dynamic allocation and cancellation retain their
unlocked callbacks and lifetime checks. This reduces 16 lock entries to 14;
a stable native latency gain is not established.

The final new tests run against unchanged 0167 fail only the count ceiling;
see [the baseline failure](adapter-locks-baseline-red.log). The candidate
passes all 42 adapter groups plain and ASan/UBSan, with deterministic sealing,
removal and late-cancellation guards. [The count log](adapter-locks-count.log)
records 14 entries. [Exact locked production checks](adapter-locks-locked-production.log)
pass both Python gates, including the full owned core and adapter runners.
The [62 firmware/identity checks](adapter-locks-identity.log) pass with one skip;
[six corrective checks](adapter-locks-corrective.log) also pass.

Release64 complete-candidate firmware built from source tree
`2716b75a7159254904b4c7a9282f2c51961ee510`; flash SHA-256 is
`2d43d91ca5a4474a365e308b2117a642a94a2d7c7da6a3004409c267173680e6`.
The image is in `artifacts/forza-bookkeeping-release64`. This is build identity,
not a title correctness or performance acceptance. The single generated native
run is archived separately above. The earlier full-host
suite history below remains scoped to its original stack; no new full-suite
pass is asserted.

## 0169: bind native port calls at compile time

[The binding specification](static-port-binding.md) records the linked runtime
dispatch cost and the unchanged callback/IRQL boundaries. The experimental request
engine supports a native direct binding, while its runtime interface remains
available for portable tests. All 44 adapter groups pass in runtime and bound
modes, plain and sanitized, with identical observations. Freestanding i386
checks show zero indirect engine calls and no lock forwarding wrappers in the
bound mode. The release 0169/0168/0169 sequence passes all 24 native correctness
cases but does not establish a repeatable return-cost gain. The patch remains
archived and is excluded from the selected firmware lock; see
[the complete comparison](../forza-complex-cadence-20261017/candidate0169/).

## 0170: carry the core lock across internal bookkeeping

The [isolated specification and reproduction tools](core-lock-coalescing-spec.md)
reduce pending adapter lock acquisitions from fourteen to twelve while keeping
transport callbacks unlocked and idle ownership publication atomic. Host tests,
mutation checks and an independent replay pass. The [four-run release comparison](../forza-complex-cadence-20261017/candidate0170/)
passes all 32 correctness cases, but primary 450 us cost/rate changes reverse
sign between pairs at both memory targets. A per-size regression also exceeds
20%. This experiment remains unselected; lower operation counts alone do not
qualify a performance improvement.

## Host validation and reproducibility

[host-validation.json](host-validation.json) records patch hashes and assembled
source-tree identities. The exact patch stack is reconstructed by:

```sh
python3 -m unittest discover -s tests/host -p test_nxstorage_production.py -v
python3 -m unittest discover -s tests/host -p test_forza_corruption_regressions.py -v
python3 -m unittest discover -s tests/host -v
```

The owned core test runner now compiles `active_scan_test.c` against the actual
production core and selector. Its independent reference visits every slot in
circular order. Exhaustive small masks, randomized active/runnable sets, every
single-bit boundary, and wraparound positions produce 1,528,352 matching
observations. Repeated saturation, random completion, stale-completion replay,
and reuse pass at capacities 1, 31, 32, 33, 63, 64, 65, and 129.

The [core check log](active-scan-core-checks.log) also records all 50 existing
request-contract tests and 8 pthread ownership scenarios passing, including
coalesced admissions/completions, fairness, cancellation, split requests, cache
ordering, and generation exhaustion. Freestanding i386 checks report no new
undefined helpers. Native adapter checks pass all 38 groups both plain and
with AddressSanitizer/UndefinedBehaviorSanitizer. Exact locked reconstruction
also passes packet, sense, owner, cache, and geometry checks; see
[the production check log](locked-production-checks.log).

The first full host run completed 562 tests in 446.993 seconds, with 26 skipped
and two checksum-pin failures. Both were stale product pins for the updated
firmware lock and production test assembler, rather than runtime failures.
The [original log](host-suite-before-pin-refresh.log) is retained. Those pins
were refreshed in `sources/kernel-coverage-inputs.json`. The corrected
[identity/firmware checks](corrected-identity-checks.log) pass all 62 tests, with
one skip, in 6.263 seconds. The full run began with 0166 integrated; 0167 is
separately covered by the final exact locked-production reconstruction above.
A redundant full rerun was stopped after the hash-only correction; no second
full-suite pass is claimed.

Native acceptance requires correct generated bytes and callback ownership,
ordinary submission/burst measurements, and the relevant title scenario.
The generated burst fixture includes immediate alertable polls inside its
synthetic issue budget, but starts that budget after its initial retirement
polls. It does not reproduce all title work or establish a title budget.

The [full IRP reset specification](irp-full-reset-spec.md) and exact-function
host checker prepare a separately measured follow-up; they introduce no
production change.
