# FATX extent-hit lock coalescing experiment, 2026-10-18

This experiment followed the selected 0168 firmware and did not enter the
selected patch stack. It combines extent lookup and advisory checkpoint
publication under one `LastMutex` section. Executable host cases prove one
mutex acquisition for an established extent hit and two for an extent miss,
while the real FAT-chain/async-read coupling scenarios preserve mapping,
completion, cancellation, and buffer lifetime behavior.

The exact release64 build used assembled source tree
`45143dd675460aaaf79c18daddb000c1c7a137ce`; its 512 KiB BIOS SHA-256 was
`4e31ab8220f1c86dee8d91d971db65efede44c3642810a12fd3db7033ed0afdc`.
The complete host suite passed 565 tests in 452.719 seconds with 26 expected
environment skips.

Two fresh-process automated Forza runs completed their map-load and driven
world-stream routes without a correctness failure:

- `20261018-102318186-28fb0c70b8834a13af3fe0ee07193ab8`
- `20261018-102716401-24763b52579048eda285f0045b910eb8`

Both candidate runs and both selected-0168 controls first showed the starting
grid in the `load-04` one-second sample. All four subsequently entered and
drove a rendered race. The route therefore found no map-load improvement, so
the patch was rejected despite its narrower host work reduction. This avoids
shipping an unmeasured optimization after the earlier title regression.

The runner's generic comparison field is ineligible because the attested input
helper is represented as diagnostic tooling. The game-specific conclusion uses
the complete screenshot sequence and successful correctness checks; it does
not claim a framework performance qualification.
