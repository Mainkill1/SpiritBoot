# 0174 prepare-time submit arming

0174 arms inline-completion deferral while packet preparation publishes the
request handle. It reduces the common retained pending-read route from 14 to
10 adapter lock/IRQL transitions without changing lower submission or result
handling.

Host correctness passed, but the repeated release comparison did not satisfy
the predeclared all-primary improvement gate. The experiment is rejected and
its patch is excluded from the selected firmware lock. The later 0176
experiment used a narrower lock-transfer contract that explicitly separated
no-inline-result submission from the original inline-result fallback; title
acceptance also rejected that experiment.

Patch: `0174-arm-inline-completion-during-prepare.patch`.

