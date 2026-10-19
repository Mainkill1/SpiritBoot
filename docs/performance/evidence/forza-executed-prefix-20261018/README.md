# Executed submission work in the preserved Forza scene

This is a qualified **diagnostic capture of the preserved baseline kernel**, not
validation of a new BIOS or a release performance measurement. Restoring the
scene restores its RAM and kernel. New firmware qualification uses the separate
[fresh-boot XBE protocol](../../../../tests/xbe/forza-poll-budget/VALIDATION.md).

## Result

All 64 selected reads returned and received successful, length-matching
callbacks inside the replay interval. Selected lifetimes drain at identity
sequence 666; 269 later callbacks are explicitly unassigned because new API
admission had stopped. Both recorders report zero overflow, read failures,
invalid observations, thread mismatch and open admitted calls. The prefix
histogram's maximum probe length is 10, below its fail-closed bound of 128.

There are 18 long-gap, direct-start, 512-byte extent hits whose preceding selected
child had completed before entry. Twelve have the **same exact phase-by-symbol
instruction-start vector**: 1,123 starts before mapping-ready and 2,401 between
mapping-ready and lower-child binding, totaling 3,524. The other six vectors
contain additive work, including identified timer/interrupt entry paths. The
summary preserves every added symbol; it does not label all added work as owned
by the selected request or by an interrupt.

The capture has **no nearby direct or queued-later control cohort**. Its
instrumentation changes timing and queue behavior. Consequently it cannot
explain the earlier 90.4 versus 38.3 microsecond long-gap association or establish
an uninstrumented speed ratio. All 18 long-gap calls have zero owned translation
allocations during their API interval; that does not rule out TLB/cache effects
or prove translation-cache residency costs.

REP body observations are separate from instruction starts. In each of the
12 repeated vectors, `IoInitializeIrp` executes 416 byte-store bodies before
mapping-ready and 164 afterward. The exact owned image binds their REP PC to a
one-byte store instruction. This proves that the common route clears those
580 bytes one at a time. The current selected 0168 initializer has the same
code. A candidate using equivalent aligned four-byte clearing therefore has a
concrete execution target, but 145 wider iterations are **not a measured latency
gain**. Every byte, tail, field assignment and surrounding guard must still
match; see [the full-reset contract](../forza-native-submit-cost-20261017/irp-full-reset-spec.md).

The older baseline's inactive-slot scan is observed after binding/start in the
representative call. It must not be used to explain this pre-bind floor or
proposed again as a new fix: selected 0167 already removes that inactive scan.

## Contents and reproduction

* `capture/`: compressed scalar logs, exact replay receipts, qualified cohort and
  joined phase analysis. There are no guest payloads or memory dumps.
* `analysis-tools/`: strict parsers, lifetime qualification, phase/cohort join,
  instruction/REP accounting, synthetic tests and independent reviews.
* `native-work-summary.json`, `rep-metadata.json`, `WORK-SUMMARY.md`: exact vectors,
  distinct REP counts and owned-image instruction-width metadata.
* `recorder-v2/`: reviewed observer, patch, native build receipt, actual staged
  identity test, C tests, guard mutations and portable test wrapper.
* `code-identity/`: scalar proof binding the saved mappings to the owned image.
  The sole code-byte difference is the expected startup prefetch enable patch;
  instruction boundaries are preserved. Read-only flash mapping alone does not
  establish slow MMIO reads.
* `capture-v1-rejected/`: the earlier recorder rejection and bounded diagnosis.
  That overflowed capture supplies no qualified instruction attribution.

The observation source is reconstructed from public xemu fork commit
`f3c528eeec86db32c9f96a932267105e83f77375`, first applying the sibling
identity archive's cumulative patch, then this archive's prefix patch. The
verifier checks every intermediate/final source hash against the build receipt.
With an existing checkout containing that Git commit:

```sh
python3 verify_source.py /path/to/xemu
python3 recorder-v2/run_tests.py /path/to/xemu
python3 -m unittest discover -s analysis-tools -p 'test*.py'
```

All generated C fragments, binaries and mutation outputs are temporary. This
checks exact source reconstruction and tests, not bit-identical executable
reproduction. The captured emulator retains the dirty-worktree limitations
recorded in the sibling [source provenance](../forza-request-identity-20261017/SOURCE-REPRODUCTION.md).
The firmware itself is release64; the diagnostic emulator is not the release
performance runner.

To reproduce the scalar qualification and joined analysis, decompress the three
`.gz` files into a temporary directory without changing their bytes, then run:

```sh
python3 analysis-tools/qualify.py --prefix /tmp/forza-prefix.log \
  --identity /tmp/forza-identity.log --receipts capture/replay-receipts.jsonl \
  --identity-tools ../forza-request-identity-20261017 --output /tmp/qualification.json
python3 analysis-tools/join_prefix.py --prefix /tmp/forza-prefix.log \
  --identity /tmp/forza-identity.log --receipts capture/replay-receipts.jsonl \
  --identity-tools ../forza-request-identity-20261017 \
  --symbol-map /tmp/baseline-symbol-map.json --output /tmp/analysis.json
```

The complete work-summary CLI additionally accepts the pinned owned PE via
`--owned-image`; `WORK-SUMMARY.md` describes the required inputs and limits.
Its published REP metadata contains symbol names, PCs, mnemonics and widths,
not code bytes or operands. Runtime code identity is a separate checked proof.
All instruction starts, completed REP bodies, byte operations and elapsed
instrumented intervals remain distinct quantities; none is exclusive CPU time.
