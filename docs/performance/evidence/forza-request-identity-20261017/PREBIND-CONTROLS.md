# Pre-bind comparisons with observed state controls

The aggregate 89.9 us direct versus 36.55 us queued/start-later pre-bind medians
mix very different inter-call spacing and completion states. Restricting both
groups to the same 512-byte size and confirmed extent hits does not by itself
remove the difference. Adding spacing and prior-completion controls exposes the
mix: most direct calls follow a long gap, while all queued/start-later calls in
this size/hit cohort closely follow the previous selected native return.

Here, **direct** means no observed queue-helper return and this request's own
PataStartIo entry before native return. **Queued later** means a pending
queue-helper return followed by this request's PataStartIo entry after native
return. All values below are measured virtual-time microseconds from the same
instrumented replay. The gap is from the previous selected same-thread native
return to current entry; it is not a pump or frame label.

| 512-byte extent-hit cohort | n | Gap range | Previous child completion | Median entry→bind |
|---|---:|---|---|---:|
| Direct, long gap | 145 | >=10 ms | Before current entry | 90.4 us |
| Direct, nearby, already completed | 5 | 100 us–1 ms | Before current entry | 38.3 us |
| Direct, nearby, completes after bind | 2 | <100 us | During current API after bind | 36.2 us |
| Direct, nearby, crosses pre-bind | 7 | <100 us | During current API before bind | 135.6 us |
| Direct, nearby, crosses pre-bind | 3 | 100 us–1 ms | During current API before bind | 149.9 us |
| Queued, starts before return | 13 | <100 us | During current API after bind | 37.2 us |
| Queued later | 52 | <100 us | After current return | 36.45 us |
| Queued later | 2 | 100 us–1 ms | After current return | 38.05 us |

These rows account for all 229 selected 512-byte extent-hit calls (162 direct,
13 queued/start-before-return, 54 queued/start-after-return). None has a measured
mapper walk. There is no queued-later long-gap comparator and no queued-later
comparator whose previous selected read completed before entry. Queue category
is an outcome correlated with request state, not a randomized intervention.
The five nearby/already-completed direct calls are a small observational group.

For the 145 long-gap direct calls, the median entry→mapping-ready interval is
36.5 us and mapping-ready→lower-bind is 53.7 us. For the 54 queued-later calls,
those medians are 15.85 and 20.7 us. For the five nearby/already-completed direct
calls, they are 15.4 and 21.6 us. Thus the difference appears on both sides of
the confirmed extent-hit mapping-ready boundary; mapper misses cannot explain
this particular comparison. Population medians of components are not additive.

For the seven direct calls with gaps <100 us and previous-child completion
during pre-bind, the median mapping-ready→bind interval is 108.7 us. Six cross
the prior child-completion entry in that interval; one crosses it before
mapping-ready. The completion entry locates concurrent completion activity, but
does not measure the completion routine's exclusive duration or prove that it
accounts for the entire excess. The three comparable calls with 100 us–1 ms
gaps include two prior completions before mapping-ready and one after it.

The broader extent-hit population shows the same spacing association: 227
long-gap direct reads have a median pre-bind time of 89.9 us, while 46 direct
reads with 100 us–1 ms gaps have a median of 34.95 us. These broader cohorts mix
sizes and are corroborating context, not the primary size-controlled result.

The observations establish a long-gap/completion-state mixture before the lower
queue decision. They do not establish why the long-gap calls execute more
slowly. Host or guest cache warmth, scheduling, interrupt activity, and other
unobserved work remain possible explanations. No hardware cache counters,
complete instruction/work counts, or DPC timing boundaries were collected in
this identity trace. The gap cannot prove that a call is first after a frame
wait, and matching child-completion entry is not hardware-tag release. An
unconditional claim that immediate hardware-start policy itself causes the
whole aggregate pre-bind difference is unsupported by these records.

Reproduce the complete controlled tables and per-request values with:

```sh
python3 analyze_prebind.py spirit-identity.log replay-receipts.jsonl --output spirit-prebind.json
python3 -m unittest discover -p 'test_*.py'
python3 verify_manifest.py
```

The analyzer reuses strict identity/timeline validation, then requires one
matching mapping-ready event and one lower binding per selected request. It
checks event order and nonnegative disjoint timing boundaries. Four added tests
cover gap boundaries, same-IOSB matching, previous-completion placement, missing
or duplicate ready events, invalid ordering and first-call handling. The entire
package now has 30 passing tests. This follow-up performed no host operation,
new capture, emulator build, or firmware modification.

## Selecting cases for instruction-path attribution

Use the per-request rows in `spirit-prebind.json`, rather than the aggregate
queue categories, to select these four cohorts. All require `bytes == 512` and
`extent_hit == true`:

| Cohort | Additional predicate | Existing representative API | Pre-bind | Gap |
|---|---|---:|---:|---:|
| Long-gap direct | Direct; gap >=10 ms; previous child complete before entry | 259 | 90.4 us | 32,658.8 us |
| Nearby direct | Direct; gap 100 us–1 ms; previous child complete before entry | 17 | 38.3 us | 259.3 us |
| Nearby queued later | Queued/start-after-return | 238 | 36.4 us | 81.2 us |
| Completion-crossing direct | Direct; gap <100 us; previous child completes during pre-bind | 154 | 135.6 us | 78.5 us |

Each representative is the call nearest its cohort's pre-bind median, with ties
within floating-point rounding resolved by lower API number. Reproduce selection
by filtering the JSON rows with the stated predicates, calculating the median
of `entry_to_bind_us`, and sorting by
`(round(abs(row['entry_to_bind_us'] - median), 9), row['api'])`.
The original raw events join by `api`; lower lifetime joins and sequence
boundaries are retained in `spirit-timeline.json`. API numbers identify this
capture only and must not be treated as stable markers in another replay.

The strongest initial comparison is long-gap direct versus nearby direct:
same size, same confirmed hit, same lower-start outcome, and previous selected
child completion before entry. Compare entry→mapping-ready separately from
mapping-ready→lower-bind. A future independently reviewed owned-kernel
instruction/branch attribution can ask whether those cohorts traverse different
owned paths or execute different amounts of work, while keeping interrupt and
thread-switch intervals separately identified. Equal path counts with different
elapsed time would still leave execution-rate/scheduling causes unresolved;
different path counts would identify extra observed work without establishing
exclusive CPU cost. These instruction counts are not present in this archive.

Use nearby direct versus nearby queued-later as a secondary comparison, and
keep the completion-crossing cohort separate so that observed prior-completion
activity is not silently folded into an ordinary submission path. The complete
cohort tables, including small groups and ranges, should remain beside any
representative examples. On a future replay, reclassify requests from the
observed state and boundaries rather than assuming the same API IDs, timing,
request order, or queue outcomes. This is an attribution proposal, not a new
capture performed by this follow-up.

Independent review reproduced `spirit-prebind.json` exactly, ran all 30 tests,
and confirmed the size/hit/gap/completion counts and medians without a blocking
finding.
