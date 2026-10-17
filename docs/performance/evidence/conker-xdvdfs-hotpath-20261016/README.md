# Conker XDVDFS load-path investigation

This evidence set follows the release Conker function census. It targets the
largest proved duplicate filesystem work without changing optical or ATA
timing.

## Observed route

For an XDVDFS file read, the current release path maps the caller's MDL, builds
a synchronous child read over the same destination, causes that child to
construct and pin a second MDL, submits it to the optical stack, waits for the
child, and only then completes the caller request. The 60-second census saw:

| Boundary | Hits |
| --- | ---: |
| XDVDFS file dispatch | 1,729 |
| optical target read | 2,380 |
| filesystem request build | 2,393 |
| page lock/unlock pairs | 5,456 |
| directory-table reads | 594 |
| path resolutions | 272 |

The aligned file-data route is the first candidate because it can potentially
reuse an already described caller transfer. Directory caching is deferred
until media-generation and invalidation behavior are explicitly owned.

## Investigation stages

1. Freeze behavior and ownership rules before an implementation.
2. Implement the decision and completion semantics in dependency-free Rust.
3. Capture all required scalar facts from a release Conker run.
4. Use the Rust analyzer to measure eligibility and refusal reasons.
5. Build a native candidate only if the measured eligible share is material.
6. Qualify exact release images with host contracts and repeated real-game
   load timing.

Stages 1 through 5 are complete. The accepted diagnostic counter found 89.98%
of Conker file reads eligible for direct forwarding, and the native candidate
is patch `0153-xdvdfs-direct-forwarding.patch`. Stage 6 uses repeated,
uninstrumented release64 runs and remains a qualification gate; counter runs
are never used as timing evidence.

## Safety boundary

The candidate does not remove hardware delays, change ATA selection, alter the
lower optical segment size, cache directory data, or infer that a guest buffer
is resident. Requests lacking complete ownership proof retain the existing
path. See `rust-model/SPEC.md` for the frozen rules and
`rust-model/PROVENANCE.md` for the separation record. The product setting is
session-only, defaults off, and is also covered by **All advanced settings**.

## Observation-method outcome

The two QEMU plugin attempts are rejected. One prevented QMP initialization;
the other used register discovery in an unsupported callback context and then
stalled. The accepted firmware-side counter records only aggregate admission
decisions and is removed from timing builds. See `collector/RESULTS.md` and
`diagnostic-counter/RESULTS.md`.
