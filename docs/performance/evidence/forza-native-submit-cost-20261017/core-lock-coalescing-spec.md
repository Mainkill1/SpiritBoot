# Isolated 0170 core lock handoff experiment

Base: selected 0168 source tree `2716b75a7159254904b4c7a9282f2c51961ee510`.
0169 is excluded. This is a re-evaluation of the owned historical design, not a
selected product patch or a demonstrated native improvement.

The state lock is also a native IRQL boundary. Reduce acquisitions by carrying
an already-held lock across adjacent internal bookkeeping, never across a
transport callback that previously ran unlocked. This can change DPC opportunity
timing at removed handoffs; native elapsed-budget qualification is required.
No hardware delay/check, cancellation check or lower ownership gate is removed.

Proposed windows:

1. In each of `nx_start`, `nx_lower_done`, `nx_cancel`, `nx_quarantine`, a caller
   that sets `pumping=1` transfers its held lock to the first `run_pump` scan.
   A caller that does not claim pumping releases its own lock once and returns
   normally. `run_pump` consumes the held lock and always returns unlocked.
2. After lower submit returns, keep the lock from checking terminal/pending state
   into the next scan. Never retain it across the submit itself.
3. After retire returns, keep the lock from `record_result` and `cursor=index`
   into the next scan. Preserve that cursor reset exactly.
4. Keep the lock across purely internal retries after command-build failure or
   failed preparation, and from post-retire cancellation/quarantine terminal
   bookkeeping into the next scan. Retire itself stays unlocked.

Required invariants:

- Slot/token/generation checks, dispatch-result stack-pointer lifetime, bitmap
  updates, fairness cursor and barrier rules are unchanged.
- Prepare, submit, retire, cancel and complete callbacks run unlocked. The
  historical `mark_pending` callback still runs locked. Reentrant callbacks
  can publish work but cannot create a second pump owner.
- Submit commitment remains the locked `inflight=prepared=1` update after
  cancellation/quarantine checks. Post-commit cancellation must cancel/drain
  transport; a return code alone never proves that lower ownership ended.
- `NONE` detection and `pumping=0` remain under the same lock, followed by one
  release. A racing producer either becomes owner after that release or is
  seen by the existing owner. No new notification or deferred worker is added.
- Preserve the existing parent-completion gates and child-unwind protection.
  Start/cancel/dispatch leases can outlive parent completion: they must continue
  to prevent envelope reuse or reclamation until their owners release them.
  Removal still drains those leases. Adapter logic is unchanged.

Host evidence must include baseline-red deterministic acquisition checks for
all four owner entry routes, not only startup. A pending core submission should
fall from six to four acquisitions (the older engine was seven to five), and
the native adapter's retained pending route from fourteen to twelve. The count
is a work invariant, not a timing assertion. Existing callback lock assertions,
inline/duplicate completion, prepare/commit cancellation, quarantine/recovery,
split requests, fairness, reentry, lower-unwind and threaded removal gates must
pass. Mutations must demonstrate rejection of a locked transport callback and
an incorrect idle-owner handoff. Compile the exact candidate source with
ASan/UBSan and the existing freestanding checks; run adapter, packet, owner and
sense gates as well. Keep selected firmware lock and product test pins unchanged.

Only after independent review and host qualification may one isolated release64
build proceed. Native tests must compare the current frozen initial-poll fixture
against 0168 with repetitions; no host microbenchmark or reduced acquisition
count qualifies this experiment as a game fix.

## Qualification reached

The isolated patch is archived as
[core-lock-0170-coalesce-core-lock-handoffs.patch](core-lock-0170-coalesce-core-lock-handoffs.patch),
SHA-256 `38329a159a3d1c628f7bb6a0899c0d04684ae68b3f3c69f0b175ccfea195753f`.
Exact assembled tree: `a6f7d46982fca95e85e7b865323302ac217d656b`.
The [host receipt](core-lock-host-validation.json) binds the retained logs.

All four owner acquisition assertions failed on the baseline. The candidate
passes 55 core tests, the active-scan differential checks, eight pthread
scenarios, 42 adapter groups in plain and ASan/UBSan modes, packet checks in
plain/ASan+UBSan/MSan modes, and owner/sense checks. The observed pending adapter
route is fourteen acquisitions on 0168 and twelve on this candidate.
Mutations that reverse final idle publication and unlock, or call prepare while
locked, are rejected. The independent reviewer separately reproduced the
idle-order rejection and adapter gates.

The first adapter run failed because an existing test assumed cancellation at
release thirteen of fourteen. With twelve releases its hook never fired, and
the failed test left that global hook armed. The corrected test first measures
a completed retained pending call, injects at its penultimate release, checks
the intended parent and actual firing, and disarms before any assertion can
exit. The last two adapter releases are mechanically unchanged: admission-owner
exit after handle/start-lease bookkeeping, then dispatch-lease cleanup. Both
baseline and candidate pass this adapted test. The initial failed-run log is
retained; its abort is not omitted from the qualification history.

One isolated release64 build completed at
`artifacts/forza-core-lock-release64/flash.bin`, SHA-256
`6f672d7450e43c9b0aff7779b31a7ff993cc823e86fc62b859909a248d641f79`.
Assembled source is `artifacts/forza-core-lock-release64/work-96qqypvr/source`.
The build uses a temporary lock under `.scratch/forza-core-lock-0170/`; the
selected product lock and test pins remain at 0168. The repeated native comparison did not establish a consistent gain, so this
experiment remains unselected. See the [four-run qualification and decision](../forza-complex-cadence-20261017/candidate0170/README.md). At the primary
450 us budget, both memory conditions reverse improvement direction between
pairs. One 64 KiB read-cost result at 783 pages / 1 ms regresses by 28.03%; its
cause remains under investigation. All 32 native cases pass the data/lifetime
oracle, which does not establish a performance improvement.

## Reproduce the isolated experiment

From the product repository root, use a new host-output directory:

```sh
python3 docs/performance/evidence/forza-native-submit-cost-20261017/check_core_lock_candidate.py --output /tmp/forza-core-lock-check
```

This verifies every patch hash in the archived lock, assembles the owned sources,
runs all five host gate scripts and both mutations, and reruns the adapted
late-cancellation test against the original 0168 core before restoring candidate
source. It checks the observed adapter acquisition counts of fourteen and twelve.
The [reproduction log](core-lock-reproduction.log) records a successful run of
this durable tool. `check_core_lock_mutations.py` also accepts explicit
`--source` and `--output` arguments for independent mutation replay.

The archived [build lock](core-lock-build-lock.json) changes only the candidate
patch path from its original `.scratch` location to this durable evidence
directory. Patch bytes/hash and assembled tree are identical. The
[build receipt](core-lock-build-receipt.json) records both lock hashes and the
original build-receipt hash, rather than claiming the normalized lock was the
one used for the completed build. No second firmware build was performed.

To reproduce a build with the established local `spiritboot-toolchain` image,
mount the product repository at `/work` and a pristine Roswell checkout at
the revision pinned in the archived lock read-only at `/source`, then run:

```sh
python3 /work/scripts/build-firmware.py \
  --source /source --output /work/artifacts/forza-core-lock-reproduction \
  --storage-backend complete-candidate --variant release --memory-mib 64 \
  --lock /work/docs/performance/evidence/forza-native-submit-cost-20261017/core-lock-build-lock.json
```

The build uses a new isolated checkout and retains source/build diagnostics.
The lock override does not change the selected product configuration. Firmware
runtime qualification is a separate operation; neither reproducer uses a live
host or flashes firmware.
