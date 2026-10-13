# Native handles between title creation and first insertion

Current-main integration applies the exact measured diff as
`0103-object-handle-single-lookup.patch` after SpiritBoot v0.99.4. Its SHA-256 is
`518eb15c271c8e2ec9cd6d35a0c61de11bd69790f0cb5c84bf8a8a6a6587a209`;
combined source tree `d5e5c40cb66deb63d31030668ee04e61877e3b64` differs from the
v0.99.4 tree only by this patch. The observations below retain the original
isolated measurement identities; current combined-tree regression results are
recorded separately rather than relabeling those measurements.

After a title creates its first custom object, ordinary native handles must still
return their native body for a null or matching type. Process/thread pseudo
handles and kernel handles must retain their usual status, output and ownership.

## Observation and demonstrated cause

Baseline Roswell tree `22a477eb82ed0111f2b7ad0d94c7a33a67ab8a94` registers the
title's type in `XeObCreateObject` before the first `XeObInsertObject` initializes
the native shim type. The legacy handle adapter tries a lookup constrained to
that still-null shim type. The actual native object manager interprets null as
untyped, succeeds for an ordinary body, and the adapter incorrectly passes that
body to `XobUnwrapShim`. Reading its first field as a title-object pointer is an
invalid cast. This was established from public production source, without
proprietary instructions or disassembly.

The production-body host regression faults with SIGSEGV on the baseline. The
same full public XBE on source22a, using Linux xemu source
`63f53af93c2d84f5ce1a11e277138cbaf5cca7aa`, reports exactly one failure:
`builtins-after-create-before-shim`. Its other eleven checks pass and the emulator
exits normally. These are distinct failure manifestations, not a claim that the
native guest crashes. Candidate passes all twelve checks on release/debug at
64/128 MiB.

## Resulting change and ownership

The candidate obtains one untyped native reference, then uses the existing
`XobIsShim` to classify its already referenced body. That helper requires a
non-null actual shim type and performs no additional native lookup or reference.
An ordinary body is validated against the requested mapped native type and its
reference transfers to the caller; mismatch releases it once. Actual shims use
the existing unwrap helper, which consumes one native shim reference on every
path and adds a title-body reference only on success.

This intentionally corrects the create-before-insert interval. It is excluded
from the baseline-equivalence matrix and from the frozen timing control. The
remaining 560 legacy status/output/final-ownership vectors match. Wrong-type
ordinary requests now acquire and release a temporary reference for safe
classification; their final ownership and observable failure remain the same.

## Regression evidence and limits

The v0.99.4-composed candidate passes exact-head Open firmware run
[`38330646937`](https://github.com/Mainkill1/SpiritBoot/actions/runs/38330646937)
and hotpath run
[`38330646927`](https://github.com/Mainkill1/SpiritBoot/actions/runs/38330646927).
Downloaded artifacts reconstruct tree
`d5e5c40cb66deb63d31030668ee04e61877e3b64`; all four release/debug and
64/128 MiB profiles pass the focused public guest 12/12 and the 560-case host
matrix. Across those bundles, all 93 retained runtime guest runs pass. The broad
API guest reports 633 passes and the same six TODOs in each profile, with zero
failures or skips.

The original isolated patch, then numbered
`0101-object-handle-single-lookup.patch`, produces source tree
`9c3a5cd5f226c11d917ee71abf57ce4399054c36`. The maintained host regression compiles
the actual adapter, native reference, shim ownership and handle-table bodies;
the maintained XBE includes the first-create/first-insert interval. Both catch
reintroduction of the unsafe classification. No hardware or retail-title
validation is claimed for this correction.

See the [complete source, correctness and measurement report](../optimization/2026-10-12/object-handle-single-lookup-report.md)
and its [raw measurement record](../optimization/2026-10-12/object-handle-single-lookup-measurements.json)
for exact identities, status/reference matrices, race tests, artifact hashes,
matched native timing and remaining precision limits.
