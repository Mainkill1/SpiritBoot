# Audit of QD12 transition specification v6

Reviewed input:

`/home/codex/xemu-shader-workbench-handoff/.scratch/forza-storage-redesign-v1/deliverable/NXSTORAGE-QD12-TRANSITION-SPEC-v6.md`

SHA-256: `f4de6551416f8660e67ee88c8ffe1e784e1410ba8a0089547a62e0d1889da8ea`

This is a one-way audit against the frozen independent Rust model and its
fairness/lost-wake rules. No implementation body was inspected.

## Findings on the requested properties

### Active-pump events preserve the round-robin cursor: confirmed

Admission step 6, lower-completion step 5, cancellation step 3, and the COMPLETE
reentry paragraph all preserve the current owner's cursor when `pumping=1`.
Only an idle-to-owned transition targets the newly admitted, completed, or
canceled slot. Queue selection advances the cursor after every inspected slot.

This closes the v5 starvation trace. A continuously replenished hot slot can
add notifications, but it cannot move an active owner's sweep position back to
itself and indefinitely hide an older eligible slot.

### Only a complete lock-held no-action scan enters idle: confirmed

Queue-selection step 6 explicitly names the full bounded no-action scan as the
only transition to `PUMP_IDLE`. The scan and `wake=0; pumping=0` handoff occur
under the same core lock. An admission or completion waiting on that lock has
not yet published state; after release it observes `pumping=0`, claims ownership,
and chooses its starting slot. This satisfies the model's atomic final-event
rule.

### SEND always returns to selection: confirmed

SEND steps 7-8 continue scanning regardless of pending/nonpending return,
terminal state, or wake count. v6 explicitly removes the pending-SEND idle exit.
A SEND return therefore makes no device-wide quiescence claim.

### RETIRE same-slot revisit is finite: confirmed with stated invariants

RETIRE points the cursor back to its slot once so the immediately enabled phase
is not delayed. Result interpretation can enable one of a finite set of next
actions: complete the parent, send the next data segment, send write-through
sync, or send queue release. When selection inspects that same slot for the next
action, queue-selection step 3 advances the cursor past it before the external
action executes.

An inline/reentrant completion during the following SEND preserves that already
advanced active cursor. The next selection therefore visits intervening slots
before wrapping back. The proof depends on the stated one-terminal-report and
one-retirement rules; under those rules, RETIRE cannot create an unbounded
same-slot action loop or starve another eligible slot.

### Counter saturation cannot affect liveness: confirmed

Persistent slot/device state decides whether selection finds an action. The
counter neither chooses the scan cursor during active pumping nor authorizes an
idle transition. Saturation may lose notification cardinality, and stale counts
may overstate activity, but the owner still scans and only a lock-held complete
no-action scan clears the counter and exits. No persistent runnable state can be
hidden by saturation under the written rules.

## Documentation mismatch: count cardinality is not a liveness requirement

The workload section says the counter prevents concurrent notifications from
collapsing, and the coalesced-admission section says its test fails if those
notifications collapse to a Boolean. That result does not follow from the v6
transition rules.

With active-event cursor preservation, unconditional post-SEND scanning, and
full-scan-only idle, a Boolean dirty bit—or no count after state publication—is
liveness-equivalent to a saturating count. Multiple admissions remain persistent
in their slots, and the bounded scan finds each one before idle. Multiple lower
completions remain persistent as terminal slot states and are likewise found.

If replacing the count with a Boolean still fails the named test, then either:

1. the tested Boolean variant also changes an exit/scan rule; or
2. a counter-dependent transition is missing from v6 prose.

This does not invalidate the counter or the five requested properties. It means
the document should describe the counter as diagnostic/accounting or add the
missing dependency; it should not claim notification cardinality is necessary
for liveness under the transitions currently written.

## Conclusion

No fairness or lost-wake mismatch remains in the five audited transition rules.
The v5 hot-slot starvation and pending-SEND exit are both closed. The sole v6
mismatch is the evidence claim that a counted wake is required to avoid
coalescing: persistent-state full scanning makes cardinality unnecessary for
liveness.

