# 0174 prepare-time submit arming

0174 arms inline-completion deferral while packet preparation publishes the
request handle. It reduces the common retained pending-read route from 14 to
10 adapter lock/IRQL transitions without changing lower submission or result
handling.

Host correctness passed, but the repeated release comparison did not satisfy
the predeclared all-primary improvement gate. The experiment is rejected and
its patch is excluded from the selected firmware lock. Selected 0176 uses a
narrower lock-transfer contract that explicitly separates no-inline-result
submission from the original inline-result fallback.

Patch: `0174-arm-inline-completion-during-prepare.patch`.

