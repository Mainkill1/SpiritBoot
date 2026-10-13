# Modular exponentiation public contract

364 public nxdk checks over 13 fixed independent vectors. It covers the frozen
512-word exponent-one and 64-word even-modulus workloads, full-width two-word
odd/even arithmetic, a high-word exponent and a full-width base. Seven output
placements cover unaliased results and whole/one-word-shifted aliases of each
operand. Each verifies status, every result word, canaries and untouched other
operands. Expected residues were generated with Python integer `pow`.

Build with the pinned nxdk image from `sources/firmware-lock.json`:

```sh
make NXDK_DIR=/usr/src/nxdk -j2
```

This is a focused correctness probe. The frozen kernel/API performance fixtures
must be used unchanged for timing. Zero-size, oversized and allocation failure
contracts are retained in the source harness; this native probe uses valid
nonzero moduli and the established word-count bound.
