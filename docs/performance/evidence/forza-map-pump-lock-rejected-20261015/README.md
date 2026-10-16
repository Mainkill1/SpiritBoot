# Rejected native storage pump-lock optimization

The candidate retained the core scheduler spin lock across adjacent internal
phases while keeping all port callbacks unlocked. Host TDD reduced the pending
submit lock-entry count from seven to five, and stable one-million-cycle QD12
host samples improved about 10.2%. The earlier frequency-shifted samples are
treated as directional only. Core, adapter, sanitizer, cancellation, recovery
and reentry tests passed.

Two controlled Windows runs used a 64 MiB release BIOS, no debugger or firmware
tracing, and the exact Forza map-stream fixture/configuration from the queue-depth
candidate. Both completed 16,384 reads correctly. Against the two queue-depth
candidate runs, mean APC batch time changed -0.96% while mean submit-sum time
changed +1.99%. This is noise-level overall and worse in the intended submit
metric, so the patch is rejected and is not present in the firmware patch stack.

The request JSON files pin the runner configuration. Raw serial logs remain in
the private runner workspace and are identified by byte length and SHA-256 in
`summary.json`; derived analyzer outputs and comparisons are retained here.
`rejected-pump-lock-candidate.patch` is included to make the failed experiment
reviewable and to prevent it from being repeated as an assumed optimization.
