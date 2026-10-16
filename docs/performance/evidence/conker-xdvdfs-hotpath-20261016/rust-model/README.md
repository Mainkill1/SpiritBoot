# Optical forwarding behavior model

This dependency-free Rust crate evaluates one proposed Conker load-path
optimization: forwarding a proved, sector-aligned XDVDFS file read on the
caller's existing IRP and MDL. It never reads guest memory and cannot modify a
firmware image. `SPEC.md` is the frozen behavior contract and
`CAPTURE-SPEC.md` freezes the guest-memory decoder rules, and `PROVENANCE.md`
records the clean-room boundary used for this investigation.

## Reproduce

The recorded environment used `rustc 1.85.0` and `cargo 1.85.0`:

```sh
cargo test
RUSTFLAGS='-D warnings' cargo test --release
cargo run --release --bin analyze-trace -- request-facts.tsv
```

`rustfmt` and `clippy` were not installed in the recording environment. The
release test with warnings denied is therefore the compiler cleanliness gate.
The crate has no registry dependencies.

## Trace schema

The analyzer accepts one tab-separated request per line. All 16 fields are
mandatory; unknown values and malformed records stop the analysis instead of
being guessed eligible.

| Field | Meaning | Encoding |
| ---: | --- | --- |
| 1 | purpose | `file` or `metadata` |
| 2 | signed file offset | decimal `i64` |
| 3 | requested bytes | decimal `u64` |
| 4 | file bytes | decimal `u64` |
| 5 | file start sector | decimal `u64` |
| 6 | paging request | `0` or `1` |
| 7 | associated request | `0` or `1` |
| 8 | noncached request | `0` or `1` |
| 9 | caller data address | decimal `u64` |
| 10 | target alignment mask | decimal `u64` |
| 11 | spare lower stack location | `0` or `1` |
| 12 | MDL present | `0` or `1` |
| 13 | MDL chained | `0` or `1` |
| 14 | MDL locked or nonpaged | `0` or `1` |
| 15 | MDL PFN span valid | `0` or `1` |
| 16 | MDL byte count | decimal `u64` |

Example:

```text
file\t0\t4096\t8192\t32\t0\t0\t0\t4096\t3\t1\t1\t0\t1\t1\t4096
```

The JSON report conservatively counts one removable child-request build, one
removable second MDL lock/unlock pair, and one removable internal wait for each
proved-forwardable read. It keeps every refusal reason separately. These are
operation counts rather than elapsed-time predictions.

## Product gate

No firmware change is justified by the model alone. A release Conker trace
must first populate every scalar field and establish the eligible share and
queue overlap. The native candidate must then pass completion, cancellation,
EOF, unaligned-read, media-change, and release game tests before any load-time
claim is accepted.
