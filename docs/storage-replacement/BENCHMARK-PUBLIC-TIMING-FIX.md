# Public timing without invented physical durability

The generation2 write fixture completes write, public API flush, close/open,
read and full data comparison. Its actual public timing is useful for baseline
noise/count planning, but the earlier comparator required physical cache-sync
and persistence evidence before accepting any write timing. That excluded the
full36 A/A pilot even when all public operations and integrity checks completed.

The explicit durability policy now qualifies public timing through frozen
fixture/parser/source contracts and complete hashed raw operation evidence.
Positive physical `real_flushes` and all36 cases remain required. This checkpoint
has no physical parser, so every required write durability decision remains
INCONCLUSIVE and combined P1 cannot PASS. Caller-supplied physical true/counts
cannot bypass the gate. Public operation/readback failures remain REGRESSION;
missing public proof remains unknown. Missing raw flush calls are distinct from
observed zero, avoiding the native parser's old absent-field default.

The optional fixed fixture policy also corrects workload labeling. The current
XBE consumes selected case/cache but does not consume a host numeric seed.
Independent pairs use one explicit METADATA_ONLY label and pinned fixture/case/
request identity. The legacy varying seed schedule remains unchanged without
that policy. This makes fixed-workload scope visible without asserting that the
guest executed changing PRNG inputs.

The new invented host fixtures cover complete full36 public A/A planning with
physical evidence unavailable, all required physical gates preserved, combined
unknown despite supplied true/counts, fixed metadata labels versus legacy seeds,
missing and zero raw flush counts, failed reopen integrity, source/raw artifact
loss or tampering, incomplete generation evidence, case/cache/request/policy
bindings, unchanged healthy counters and frozen rules after calibration. Initial
feature tests reproduced rejected calibration and misleading varying labels;
an additional coherent cache mismatch reproduced false qualified timing before
the raw-cache binding was added.
Wrong or missing per-operation case IDs also reject a coherent ledger even when
its summary matches the requested case. Hashes validate consistency; factual
upstream parser/importer and raw capture qualification remain required.

Independent review also reproduced unrelated reported timing surviving coherent
raw tick/frequency changes. The public contract now explicitly freezes the
historical recorded-RDTSC-frequency conversion and verifies the batch and every
operation against positive uint64 raw ticks/frequency. Relative allowance is
exactly eight machine epsilons with zero absolute tolerance; boundary and raw
counter/frequency mutation tests cover rejection. Future fixed-source conversion
remains separate declared importer work, and historical metadata is retained.

No native parser, fixture, driver, BIOS, launcher or old accepted observation was
changed. Host tests qualify analysis behavior only. Actual native clocks,
artifact-set/per-case ISO/prepared-seed mapping, independent method review,
physical durability, structural counters and full P1 acceptance remain open.
The exact schema and CLI are documented in PERFORMANCE-HARNESS.md.
