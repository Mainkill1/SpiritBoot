# Bounded packet primitive during baseline collection

Root scope decision, 2026-10-14: the fresh predeclared reference A/A schedule is
running. Its first actual import passed independent review. P1 still gates
major driver work and candidate comparison; no performance gate is closed.

A small unlinked packet preparation/result-capture primitive and its production
function tests may proceed in parallel, like the existing bounded request and
geometry primitives. This narrows the earlier planning document’s conservative
blanket wait for T1. It does not authorize the installed native adapter.

Allowed: independently authored idle-packet field preparation and copied terminal
result extraction, using only approved declarations, exact reviewed 0133 core
inputs and the frozen behavioral packet. Include RED-first tests, native layout
assertions, exposure records and independent review.

Excluded: lower submission, cancellation, rundown, parent completion, driver
installation, boot/device dispatch, cache publication wiring, candidate benchmarks
or tuning. If the primitive requires those lifecycle components, leave them
unimplemented until P1 rather than expanding this assignment. No source-body or
rights grant changes. All native and release qualification gates remain open.
