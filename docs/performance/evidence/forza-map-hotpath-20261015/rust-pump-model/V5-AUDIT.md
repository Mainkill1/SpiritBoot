# Audit of QD12 transition specification v5

Reviewed input:

`/home/codex/xemu-shader-workbench-handoff/.scratch/forza-storage-redesign-v1/deliverable/NXSTORAGE-QD12-TRANSITION-SPEC-v5.md`

SHA-256: `87eb7e8977c9180992c351f5e1f7f32d5e56fbfddabf7d4c9ccdc17ad7006c8d`

This audit compares authored prose with the frozen independent Rust model. It
does not inspect an implementation.

## Cursor fairness mismatch

The v5 cursor is both the event target and the scan cursor. Admission, lower
completion, retirement, and completion reentry can all point it back to the hot
slot. A full scan only before idle proves quiescence; it does not prove strong
fairness while the pump remains continuously busy.

Exact counterexample:

1. Slot A is runnable and has an outstanding wake notification.
2. Slot B is selected and begins an unlocked submit.
3. B completes inline or reentrantly, increments the saturating wake count, and
   retargets the cursor to B.
4. The SEND return consumes one count. Selection begins at B, so B retires.
5. B either advances to another segment or completes and synchronously admits
   replacement work into its reused slot. Both paths retarget the cursor to B.
6. Repeat steps 2-5. Each B event adds one count and B's SEND consumes one. A's
   older notification can remain represented by a constant residual count, but
   it has no identity and never forces inspection of A.

Lower capacity repeatedly becomes available, yet A can remain runnable forever.
This violates the frozen model rule that an eligible resident request cannot be
skipped forever while capacity repeatedly becomes available. The finite Forza
fixture may still pass because each request has finite segments; the transition
rule itself lacks a fairness proof.

A neutral correction is to keep a monotonic round-robin sweep cursor that only
advances after inspection. An event-target hint may be separate, but targeted
selections need a bounded budget before the next sweep step. Retargeting must
not overwrite the fairness cursor.

## Idle handoff result

The Queue selection step 6 handoff is atomic enough as written. If the core lock
is held across the entire complete no-action scan and the writes `wake=0` and
`pumping=0`, an admission/completion cannot publish between the scan and those
writes. A publisher already waiting for the lock has not published its state;
after release it observes `pumping=0` and claims pump ownership. No extra event
counter check is required inside that single locked transaction.

The v5 document contains a conflicting exception. Its introduction says idle is
reached only through a complete bounded scan, while SEND step 7 clears pump
ownership when the current lower command is pending, not done, and `wake==0`.
That is an idle transition without a full scan.

If the current C candidate has removed the SEND shortcut, the prose should
remove or replace step 7 so the claimed invariant is literal. If the shortcut
remains, a zero count is not equivalent to a state scan. A saturating counter
also cannot be a formal cardinality proof after saturation: at least one
notification is then unrepresented, so consuming the counter to zero can leave
persistent runnable state. The full locked no-action scan is the robust final
condition.

## Conclusion

- Lock-held full-scan idle transition: satisfies the model's atomic final-event
  rule.
- Event-retargeted scan cursor: violates strong fairness under a continuously
  hot slot.
- SEND step 7: contradicts the stated full-scan-only idle invariant and should
  be removed from v5 if the candidate already removed it.

