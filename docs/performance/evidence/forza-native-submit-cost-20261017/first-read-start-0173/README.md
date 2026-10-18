# 0173 first-read fast start

0173 submits the already-known first read command directly from the request
owner. A private `rescan_requested` handoff preserves work raised by reentrant
start, completion, cancellation and quarantine paths before that owner exits.
It keeps the single pump owner, slot/generation checks, split reads, recovery,
cancellation and completion behavior. Writes and flushes retain the general
pump path.

The exact production reconstruction passes the core, active-scan, ownership,
adapter, packet, optical and sense checks. Its corrected release A/B/A/B trial
did not pass the strict all-primary gate: one 783-page/450 µs pair changed
weighted cost by +2.08% and throughput by -0.86%. 0173 was therefore not
selected alone. It is retained as a prerequisite of the later 0176 experiment,
whose full stack passed the generated gate. Title acceptance then rejected the
combined stack, so 0173 is excluded from the selected firmware lock.

Patch: `0173-fast-start-first-read-command.patch`.
Stable copy: `patches/roswell/0173-fast-start-first-read-command.patch`.

