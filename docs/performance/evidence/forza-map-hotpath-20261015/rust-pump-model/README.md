# Bounded request pump model

This directory is an isolated, independently authored Rust model of the
SpiritBoot bounded storage request engine. It is an executable design artifact,
not product code and not a kernel adapter.

The model is driven through two boundaries:

1. `Engine::notify` records admission-independent events such as prepare
   completion, submit return, lower completion, cancellation, retirement, and
   parent delivery.
2. `Engine::poll_effect` advances the iterative pump by at most one action and
   returns it outside the modeled lock. The consumer can reenter with `notify`
   before polling again.

That split makes the submit/inline-completion race explicit and prevents a
completion callback from recursively launching more work. A persistent rescan
request plus round-robin cursor ensures that terminal completion cannot lose
the wake-up needed to launch the next waiting request.

Files:

- `SPEC.md`: tagged behavioral rules and neutral transition table suitable for
  a separate C implementer.
- `src/lib.rs`: state machine.
- `tests/model.rs`: deterministic scenarios and randomized property schedules.
- `PROVENANCE.md`: source boundary and input hashes.
- `RESULTS.md`: verification evidence and limits.
- `V5-AUDIT.md`: post-freeze comparison with the separately authored v5 prose
  transition specification.
- `V6-AUDIT.md`: post-freeze verification of the corrected fairness and idle
  rules, plus one notification-cardinality documentation mismatch.

Run:

```sh
cargo test
RUSTFLAGS='-D warnings' cargo test
cargo test --release
```

No file outside `.scratch/pump-rust-translation/` is modified by this model.

