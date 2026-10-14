# Independent bounded extended-geometry composer

The owned production source is geometry_composer.c with neutral public
inputs in geometry_composer.h. It combines a fresh lower geometry/capacity
base with an already consistent owner metadata snapshot. It has no heap,
worker, clock, lower-submission, completion, or lock dependency.

Run the whole independent package:

```sh
python3 run_checks.py
```

The host test compiles the exact production source. It covers 13 scenarios
and 6001 assertions, including 40000 concurrent calls using independently
stable snapshots. Normal execution and ASan/UBSan pass. GCC static analysis
passes. The production source compiles as freestanding i386 C; the ELF32
Intel 80386 object has no undefined symbols. FAIL-FIRST.log records the
required executable red phase before production behavior was implemented.
PREFIX-POLICY-FAIL-FIRST.log records a second executable red phase before
the later initialized-prefix revision: 263 assertions failed against the
unchanged prior composer.

Output capacity 0/31 fails with zero returned bytes. On success the reported
prefix is min(caller capacity, 112), and every byte in it is initialized.
The partition record is emitted only when all 24 bytes fit at capacity 56;
the full detection record is emitted only at capacity 112 and is explicitly
DetectNone. Smaller optional tails are cleared unavailable padding, with a
zero record-size field whenever the complete field fits. No partial identity
or BIOS facts are returned. MBR, GPT, RAW,
and caller-required Xbox BRFR 128 are supported. Every failure leaves the
caller buffer unchanged and returns zero initialized bytes; lower failures
retain their exact status bits. Positive nonzero lower statuses are rejected.

SPECIFICATION.md fixes the revised candidate policy and acceptance boundary;
SPECIFICATION-V1.md preserves the superseded complete-prefix-only choice.
ADAPTER-INPUTS.md identifies future minimal inputs and ABI gates without
providing an adapter implementation. PROVENANCE.md records all inputs,
incidental public-macro exposure, necessary protocol convergence, and limits.
SHA256SUMS pins authored files and evidence logs.

The revised returned counts match the admitted observations from both rigs:
32/40/56/64/112/112/112 for caller capacities 32/40/56/64/112/128/256.
Sizes 33/39/41/55/63/111 are tested as declared policy and have no admitted
native measurement. Zero-size unavailable partition padding differs from
the published size requirement for a valid public record. This convention
is documented explicitly; it does not turn partial padding into a record.

Full historical parity is not established. DetectNone does not preserve any
lower optional detection facts. Identity/checksum availability, BRFR mapping,
full detection bytes, error choices, and native callers remain parity
concerns. Host concurrency tests do not prove retained-owner synchronization.
Native target ABI assertions and the broader A/A freeze must be completed
before integration. The composer remains an unlinked primitive; no native
geometry fix or firmware licensing/personnel certification is claimed.
