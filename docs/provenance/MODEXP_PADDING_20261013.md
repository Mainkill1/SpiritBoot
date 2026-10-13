# Bounded modular arithmetic for zero-padded operands

Issue #240 reports a roughly 349 ms `modexp-512-e1-odd` workload and a roughly
14 ms `xc/rsa/modexp_even_modulus` leaf. Both pass correctness in the frozen
campaign, but their small numerical operands are padded to 512 and 64 words.
The implementation uses that caller width for reduction, Montgomery setup,
products and scratch allocation. These costs belong to leading zero words,
not the exponent's mathematical size.

Patch `0125` normalizes internal arithmetic to the modulus' highest nonzero
word, while retaining the caller word count for all exponent bits and output
width. Leading zero value words do not contribute reduction bits. The odd
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
16,384 to four, reduction bits from 18,432 to 160, and scratch bytes from 1,288
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
workflow; final reference/baseline/candidate contract and unchanged timing
receipts are required before acceptance.

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
