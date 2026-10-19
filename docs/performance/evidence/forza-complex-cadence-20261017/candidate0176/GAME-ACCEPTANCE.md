# Candidate 0176 game-acceptance rejection

**Product decision: rejected on 2026-10-18.**

The generated release fixture selected candidate 0176 because its four-run
0168/0176 comparison improved the fixture's primary return-cost and issue-rate
metrics while preserving that fixture's byte and callback oracles. A subsequent
fresh 64 MiB release game run did not produce a visible Forza streaming
improvement, and PGR2 crashed early during separate title testing. Those title
outcomes override the synthetic selection for product use.

The Forza runner process itself remained alive until the owned-desktop runner's
30-minute deadline and was then terminated by the runner. That result is a
performance rejection, not evidence of a Forza host crash. The reported PGR2
failure remains a separate correctness regression that must be reproduced and
isolated by an automated fresh-process title gate.

The GitHub release workflow also failed before runtime qualification because
the committed kernel-coverage inventory was stale. Debug profiles skipped that
release-only gate. The source tree and firmware image were reproducible, but a
candidate with a red release workflow was not eligible for selection.

Patches 0173, 0175 and 0176 are therefore removed from the selected firmware
lock. Their sources and synthetic measurements remain archived as rejected
evidence. No later candidate may be selected from this fixture alone. It must
also pass automated fresh-process PGR2 and Forza title gates on a release64
build, and every release-only CI gate must pass before another human test is
requested.

## Automated title follow-up

The Windows runner was repaired to target the independently attested graphical
`xemu.exe` child instead of its native-launch supervisor. A fresh-process Forza
route now skips the intro, selects the existing Default profile, chooses Arcade
Race, Maple Valley Raceway Short, Class D and the Honda Civic, accepts the
default assists, samples the assist-to-grid transition once per second, starts
the race, and holds the accelerator for 20 seconds. Inputs are sent only to the
runner-attested child. The route uses published release xemu
`5488be40bf3c1c444b507d084c8d964f8f7d73c2a912970495cf85a4f7239564`
with 64 MiB guest memory.

A conservative follow-up candidate removed three state-lock round trips while
keeping the 0168 request order and ownership protocol. It was evaluated, then
discarded because it produced no game-level improvement. In the alternating
four-run sequence below, every run completed, passed its correctness checks,
retained complete evidence, rendered the race scene after the driven interval,
and first displayed the starting grid in sample 4.

| Variant | Firmware SHA256 | Runner run | First grid sample |
| --- | --- | --- | ---: |
| conservative candidate A | `1b5b5829b80d5127d4a67ec9ce853c4ea1eb8252421e0d24a2b741c14f9dc753` | `20261018-094150006-605d8d5cbfba4d1ca8179723e0471d18` | 4 |
| selected 0168 A | `2d43d91ca5a4474a365e308b2117a642a94a2d7c7da6a3004409c267173680e6` | `20261018-094557986-06cede4fad0e4808ae4a2db33575967e` | 4 |
| conservative candidate B | `1b5b5829b80d5127d4a67ec9ce853c4ea1eb8252421e0d24a2b741c14f9dc753` | `20261018-095027183-aa43babd1f70486daf72baaf2ae5fa69` | 4 |
| selected 0168 B | `2d43d91ca5a4474a365e308b2117a642a94a2d7c7da6a3004409c267173680e6` | `20261018-095415439-5ce9044dc9f5435ea778685e19234847` | 4 |

This repeated title gate resolves the follow-up decision: keep 0168 selected.
The candidate reduced internal bookkeeping but did not move the observable map
load boundary. Shipping it would add synchronization risk without a demonstrated
benefit. The runner retains the manifests, screenshots, input-action receipts,
frame/flip logs, host metrics and assessments under the run identifiers above;
game imagery is not copied into this source repository.

The selected 0168 image was then rebuilt from the final lock and reproduced the
same SHA-256. A fresh-process PGR2 route entered a race, completed its 30-second
gameplay segment and exited normally. Execution completed, both screenshot
checks passed, the evidence set was complete and the runner classified the run
as comparison-eligible:

- firmware: `2d43d91ca5a4474a365e308b2117a642a94a2d7c7da6a3004409c267173680e6`
- assembled source: `2716b75a7159254904b4c7a9282f2c51961ee510`
- runner run: `20261018-100317063-6b5d031c1d284d69919a871879db7dc4`

This gate verifies the selected rollback through the tested PGR2 route. It does
not erase or reinterpret the operator-observed early crash on the rejected
candidate, and it is not evidence that the rejected synchronization changes
were safe.
