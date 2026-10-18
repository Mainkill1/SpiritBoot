# Exact vectors and separate REP work observations

`summarize_work.py` first qualifies the bounded v2 capture with `qualify.py`,
then reuses the identity/timeline/prebind and prefix join tools. It checks its
selected instruction-start and REP totals against the independently joined
totals. It writes only numeric/symbol metadata and summaries; it does not
publish instruction bytes, operand text, or disassembly listings.

Required CLI inputs are `--prefix`, `--identity`, `--receipts`,
`--identity-tools`, `--symbol-map`, and `--output`. An optional `--owned-image`
must hash-match the symbol map. Its private objdump output is reduced to exact
REP PCs, enclosing linked symbols, mnemonic names, and element widths.
`--interrupt-entry-symbol NAME` can be repeated to label explicit entry-symbol
deltas. These labels do not assign all additional work to interrupts.

For each existing cohort, the tool groups exact prebind **phase × linked-symbol**
instruction-start vectors. The smallest observed total is a descriptive
minimum. If different vectors tie at that minimum, it reports them without
choosing a unique baseline. If the minimum vector is unique, every call gets
a signed vector difference and a componentwise-additive flag. A smaller
symbol count is retained as a negative delta, never hidden by a larger total.
Empty cohorts remain empty rather than becoming hypothetical controls.

REP body iterations are separate from instruction starts. A row with one
marked REP PC can be attributed to that PC's enclosing linked function and
phase. Multiple marked PCs retain unsplit ambiguous iterations. Excluded TB
entries are never promoted into per-instruction attribution. Unknown iteration
counts and out-of-selection counts remain explicit. Where the exact owned
image establishes an element width, iterations × width is reported as byte
operations, not unique bytes, memory latency, architectural retirement, or
CPU time.

The current qualified capture produces these observations:

- The 18 long-gap direct 512-byte extent-hit calls have a unique minimum vector
  of 3524 prebind instruction starts, identical in 12 calls.
- The other six calls have componentwise nonnegative additions: API 4 +991,
  6 +295, 29 +292, 31 +1633, 59 +292, and 61 +295. Explicit interrupt-entry
  symbol additions coexist with these differences; the tool retains every
  additional symbol and does not claim that all additions are interrupt work.
- All three other configured cohorts are empty. There is no nearby direct
  control in this capture.
- REP totals are 52724 known iterations: 52700 attributed unambiguously to
  owned PCs and 24 excluded. There are no ambiguous or unknown REP totals.
- In all 12 minimum-vector calls, `_IoInitializeIrp@12` at PC `840150be`
  contributes 416 REP iterations before mapping-ready and 164 after
  mapping-ready but before binding. The exact owned-image scalar is `rep stos`
  with one-byte elements, so the respective byte-operation counts are 416 and
  164. The report preserves phase/function observations; identifying parent
  and child request roles also relies on the owned implementation's call path.

`native-work-summary.json` binds the input files, exact owned image, and tools
by SHA256. No native replay or firmware change was performed by this tool.
The result supports work attribution in an instrumented capture, not a
performance improvement or a Forza fix.

Tests use generic synthetic vectors and instructions, without hardcoding
native API IDs or counts. `summarize-red.log` and `summarize-scope-red.log`
preserve failing tests before implementation. Full discovery in
`summarize-full-green.log` passes 104 tests, including 10 work-summary tests.
