# Current-main performance and compatibility integration

## Question

Which open SpiritBoot changes are safe to compose into the 64 MiB firmware used
for title and save testing, and which experiments must remain outside that
baseline?

## Baseline and scope

The integration starts from `cb0a42b493a328e5df26d19a928e7deacc57ce45`,
which includes the VM-query fast path from PR 235. It replays the independently
developed changes from PRs 228–234, 236, and 237 onto that exact mainline:

- apply the published title scheduling quantum;
- report and persist complete contiguous-allocation extents;
- use the public thread owner in critical sections;
- submit eligible contiguous FATX reads directly and preserve their resource
  lifetime;
- preserve Xbox immediate-delay semantics and remove inactive async-completion
  clock work;
- expose the complete public thread identity, terminal state, wait blocks, and
  IRP thread boundaries;
- keep the Xbox interrupt entry on static kernel storage; and
- release the completed Phase1 initialization thread.

The component writeups and retained evidence describe the guest-visible
contracts and the limits of each performance result. This integration makes no
new claim that composing the changes creates an additional speedup.

## Excluded drafts

PR 222 is not part of this baseline. Its direct scatter/gather route changes
synchronous write submission, has no matched throughput or title result, and is
too close to the save path to introduce while a save problem is being isolated.
Its corrected asynchronous snapshot behavior and source tests do not establish
that the synchronous route is beneficial or suitable for release.

PR 223 is also excluded. It is an opt-in pool census whose standard firmware is
intended to remain byte-identical. It still needs a complete stop/read/resume
capture before its measurements can support allocator work. It is a diagnostic
tool rather than part of the firmware under title test.

## Composition result

The ordered patch set reconstructs Roswell source tree
`319a9709b8958b2eb3d0e948e6e3b3eb6afc829c`. The release 64 MiB profile was
built twice from the pristine pinned source. Both 512 KiB images have SHA-256
`b9052178571a1855c5cefa4919aec095cfb9854665dc38a39765a47ee7e88971`.

The repository host suite passed 129 tests with three existing environment
skips. The actual patched source and compiled release kernel passed every
source-level workflow command, producing 93 nonempty check logs. Those checks
cover the composed scheduler, allocation, FATX, completion, VM-query, thread,
IRP, interrupt, Phase1 lifetime, memory, cache, object, and ABI contracts.

The full GitHub debug/release and 64/128 MiB firmware matrix remains the final
merge gate. Title testing remains necessary because the host and owned native
fixtures cannot reproduce a title's complete workload.

## Save-troubleshooting constraint

Save investigation must use the exact integrated release 64 MiB image above.
Changing the write path, enabling allocation diagnostics, or mixing another
firmware build would change the baseline and invalidate a side-by-side result.
Once a save failure is reproduced, tracing should begin before the title issues
the save operation and must record the first observable divergence rather than
assuming a disk, cache, memory-pressure, or game-logic cause.
