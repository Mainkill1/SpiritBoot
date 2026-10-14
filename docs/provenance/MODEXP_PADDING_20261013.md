# Bounded modular arithmetic for zero-padded operands

Issue #240 reports a roughly 349 ms `modexp-512-e1-odd` workload and a roughly
14 ms `xc/rsa/modexp_even_modulus` leaf. Both pass correctness in the frozen
campaign, but their small numerical operands are padded to 512 and 64 words.
The implementation uses that caller width for reduction, Montgomery setup,
products and scratch allocation. These costs belong to leading zero words,
not the exponent's mathematical size.

Patch `0125` normalizes internal arithmetic to the modulus' highest nonzero
word, while retaining the caller word count for all exponent bits and output
width. Leading zero base words do not contribute initial reduction bits. The odd
path still computes a Montgomery factor for its chosen width and converts
both input and output accordingly. The even path retains the same multiply
and bit-reduce algorithm. No exponent-one shortcut or new cryptographic
algorithm is introduced. A nonzero modulus keeps the same integer value when
its leading zero words are removed; reduction and exponentiation therefore
produce the same residue, padded with zero high output words.

All public operand reads finish before the first Result write. Whole and
one-word-shifted aliases of Base, Exponent and Modulus remain valid. Zero and
oversized caller widths, zero moduli and forced allocation failures retain
status zero with untouched output. Successful calls retain status one and
write every caller result word. The pool tag, nonpaged allocation lifetime and
size limit remain unchanged; only transient scratch size decreases.

The actual-source test was written before the production change. Its baseline
passes 3,087 independent Python `pow`, complete output canary, operand-lifetime,
status and alias checks. Its padding work budget then fails for two words
already: it should take the same arithmetic work to represent 5^1 mod 17 in
one word or in a wider zero-padded buffer. The final test passes 3,111 checks,
including product, reduction and scratch budgets. The public 364-check vector
fixture also passes after compilation with 32-bit ASan/UBSan. Existing kernel
optimization comparisons pass 30,978/30,978 and preserve complete SHA/DES state
hashes. The product suite runs 134 tests: 131 pass, with its three known environment
skips, named in the evidence receipt.

Actual production work for the unchanged exponent-one numeric inputs:

| Caller words | Products before/after | Reduction bits before/after | Scratch bytes before/after |
|---|---:|---:|---:|
| 1 | 6 / 6 | 32 / 32 | 28 / 28 |
| 64 | 24,576 / 6 | 2,048 / 32 | 1,288 / 28 |
| 512 | 1,572,864 / 6 | 16,384 / 32 | 10,248 / 28 |

For the even-modulus 64-word leaf inputs (7^5 mod 100), products fall from
16,384 to four, reduction bits from 18,432 to 288, and scratch bytes from 1,288
to 28. These are deterministic source counters, not guest timing measurements.
Full-width moduli keep their arithmetic width. This change does not claim a
similar improvement for full-width RSA keys or expensive full-width even
moduli, nor does it alter title-owned crypto vector dispatch.

The release64 ROM layout audit verifies all ROM CRCs and source DES table
bytes. Permanent image RAM remains 14 pages (56 KiB), image/ROM/discard pages
remain 140/93/33, and warm staging remains 178 pages of the 505-page bound. The
DES table keeps its exact virtual/physical addresses and bytes. No permanent
or per-thread fields grow.

The baseline is the actual staged public source tree
`694b0e2461558f6a5f7a774fd34c79bd7cdc111e`, not that checkout's pristine HEAD.
Ordered patches are applied to a pristine pinned source mounted read-only;
builds explicitly pass `--variant release --memory-mib 64`. Public nxdk input
structures and Python arithmetic supply the independent contracts. No third
party implementation was copied and no proprietary firmware source,
disassembly or decompilation was used. Native execution is owned by the root
workflow; final placement timing receipts are required before acceptance. The first
layout is rejected, with its complete native evidence retained below.

Reproduction inside the existing toolchain image:

```sh
python3 tests/host/kernel-performance/modexp.py SOURCE OUTPUT --optimized --sanitized
python3 tests/host/kernel-performance/check.py SOURCE OUTPUT --optimized --compare BASELINE
python3 scripts/build-firmware.py --source /source --output OUTPUT --variant release --memory-mib 64
python3 tools/des_layout_audit.py --baseline BASELINE_BUILD --candidate CANDIDATE_BUILD --output layout.json
python3 -m unittest discover -s tests/host
```

The native contract probe uses pinned nxdk and is separate from timing. The
original portable kernel/API performance fixtures are retained unchanged.
Artifact identities, red/green receipts, work counts and static layout are in
`evidence/modexp-padding-20261013`.

The first native candidate passes 364/364 fixed checks, as does the baseline.
Complex passes 357/364: all seven failures are the same vector across output
placements, with `Words=512`, `Base=2^16383+123`, exponent one and modulus 17.
Complex returns status one and residue four. Both SpiritBoot images return
status one and residue thirteen, matching the independent mathematical oracle.
This reference discrepancy predates the optimization and is retained verbatim;
it is not classified as an unsupported call or hidden as an exclusion. The
other twelve vectors pass on all three kernels, including the frozen padded
performance operands, full-width two-word arithmetic, high-word exponents, and
all whole/shifted aliases.

Seven alternating triplets for the first layout validate all 40 frozen portable
workloads, every expected sample/checksum, exact input/ROM/ISO/executable
identities, 64 MiB configuration and per-run launch-config bytes. The two BIOS
clock frequencies differ (3,374,488/3,375,000 Hz); each counter is normalized
using its own reported frequency. All 118 declared iteration-batch samples
are included in each aggregate. Original timings and failures remain in
`evidence/modexp-padding-20261013/rejected-layout`.

That first layout changes the padded 512-word exponent-one median from
352.082 to 0.191 ms, the padded 64-word exponent-65537 median from 7.537 to
0.078 ms, and the sampled-body aggregate from 1.510 to 0.426 seconds
(-71.77%, all seven lower, disjoint observed trial-median ranges). It is
rejected because DES3-CBC median rises 9.40% (9.849 to 10.774 ms), all seven
higher with disjoint ranges. DES-CBC rises 8.12%, all seven higher with
overlapping ranges. Higher disjoint ranges also occur for SYSVA 1025/4096,
object-warm-64 and SHA-65. All forty rows are retained; the aggregate does
not erase these regressions and is not a game/FPS measurement.

The source addition to the shared `BnReduce` moved several early function
addresses eight bytes. The placement variant restores that source body
byte-for-byte and trims `BaseWords` within `XcpModExp` only. Internal modulus
normalization, the complete exponent scan, deferred output writes and all
alias/status checks remain. Under LTO, DES/SHA/BnReduce addresses are four
bytes before their baseline locations rather than identical; no causal claim
is made from addresses alone. Source 3,111, sanitized 364 and full-source
30,978 checks pass. Permanent RAM remains 14 pages and the ROM DES table
bytes/addresses remain identical. Final seven-triplet timing is retained in `final-layout` below.

The placement variant completes seven alternating native triplets with all
40 workloads and 118 samples per run intact. The strict analyzer checks every
TAP assertion, exact declared samples/iterations/order, success flags, complete
checksums, input seed records, hashed launch-config bytes, ROM/ISO/executable
identities, per-BIOS clock frequency, alternating triplet order and nonoverlap
of reported process intervals. Overlay bytes are not independently reread;
input and fresh per-run paths are verified from the exported records.

Final paired medians (each run's within-workload median, then seven-run median):

| Workload | Baseline ms | Candidate ms | Complex ms | Candidate change | Lower pairs | Observed median ranges |
|---|---:|---:|---:|---:|---:|---|
| modexp-2-e3-even | 0.081086 | 0.061676 | 0.047593 | -23.94% | 7/7 | disjoint lower |
| modexp-32-e3-odd | 1.685293 | 0.062528 | 0.048889 | -96.29% | 7/7 | disjoint lower |
| modexp-64-e65537-odd | 7.509880 | 0.074974 | 0.055407 | -99.00% | 7/7 | disjoint lower |
| modexp-512-e1-odd | 348.046578 | 0.189066 | 0.082667 | -99.946% | 7/7 | disjoint lower |
| DES-CBC 4 KiB | 3.636404 | 3.681744 | 0.423852 | +1.25% | 2/7 | overlapping |
| DES3-CBC 4 KiB | 10.647541 | 10.755113 | 0.998815 | +1.01% | 3/7 | overlapping |

The median sum of every declared workload sample is 71.65% shorter, all seven
pairs lower with disjoint observed ranges. This fixed companion aggregate is
dominated by the padded exponent-one workload and does not estimate game
loading or FPS. All 40 rows, including non-crypto controls, are preserved in
`evidence/modexp-padding-20261013/final-layout/all40.csv` and `native-report.json`.

The earlier DES trend does not recur relative to the final cohort's paired
baseline: both CBC controls and every SHA control overlap. Candidate DES
absolute times are similar across cohorts while the paired baseline also
changes, so this experiment does not prove that instruction placement caused
the earlier trend. It qualifies the final candidate against its contemporaneous
control. Two controls retain higher disjoint ranges: object-warm-1 +8.44% and
object-warm-8 +9.46%, each seven of seven higher. Their paths are unchanged;
the cause is not established, and these observations remain visible for the
combined final sweep. This is an arithmetic padding improvement with measured
limits, not a uniform speedup or universal parity claim against Complex.

The final placement kernel timings refer to ROM
`80c5040023ce1181529e334173ff3abc22138664b4caf382acb00b75725fbb36`. The
364 native contract receipts were obtained on the baseline and first arithmetic
layout; the placement change keeps its math/status/alias contracts and passes
all 3,111 actual-source and 364 sanitized checks again. All seven Complex
high-base discrepancies remain retained in both campaign reports.

Reproduce the final native analysis without contacting the native host:

```sh
python3 docs/provenance/evidence/modexp-padding-20261013/analyze-native.py RESULTS OUTPUT --kernel-prefix probe-crypto-layout --kernel-candidate-hash 80c5040023ce1181529e334173ff3abc22138664b4caf382acb00b75725fbb36
```
