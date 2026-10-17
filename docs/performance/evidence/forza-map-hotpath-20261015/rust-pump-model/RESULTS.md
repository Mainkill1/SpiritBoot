# Verification results

Toolchain:

- `rustc 1.85.0 (4d91de4e 2025-02-17)`
- `cargo 1.85.0 (d73d2caf9 2024-12-31)`

## Test-first evidence

The first compile failed because the test-selected public model API did not yet
exist. A minimal API scaffold was then added and the behavioral run failed eight
scenarios on the deliberate `Busy` admission stub. The randomized scenario was
strengthened to require at least one real admission and then failed as intended.

Two later review findings each received a failing regression before correction:

- zero-byte reads incorrectly prepared a lower command;
- read-first selection could indefinitely starve an eligible write under a
  replenished read stream.

The fairness correction uses one round-robin scan over every eligible request.
The barrier test explicitly holds an earlier write lower-owned and proves a read
can occupy the second lower position while the intervening flush remains
blocked.

## Passing gates

`RUSTFLAGS='-D warnings' cargo test`:

- 11 integration tests passed;
- 0 failed, ignored, or filtered;
- 64 deterministic randomized schedules are exercised inside the property test;
- the 1,024-operation queue-depth-12 test completes every parent at lower depth
  one and checks at least sixteen cumulative admissions;
- no compiler warning is accepted.

`cargo test --release` also passed all 11 integration tests and doc tests.

Covered behavior includes delayed single-active lower completion, completion
before submit returns, completion callback reentry, precommit and postcommit
cancellation, one-shot lower cancellation, stale and duplicate reports, slot
generation reuse, zero-byte completion, round-robin fairness, write/flush/
write-through barriers, recovery failure, quarantine drain, 1,024 reads, and
random fair schedules.

`cargo fmt` and `cargo clippy` components are not installed in this environment,
so those two commands could not run. Compilation with warnings denied and both
debug/release test profiles passed.

## Qualification limits

This host model does not prove native IRQL or cancel-spin-lock behavior, real
IRP/MDL/SRB reuse, DMA lifetime, cache durability, device teardown, or parity
with an excluded implementation. Its liveness result assumes a fair environment
that eventually acknowledges every prepare, submit-return, terminal lower
completion, retirement, and parent-delivery effect.

