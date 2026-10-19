# Rejected FATX direct native read stack, 2026-10-18

## Decision

Patches 0180 through 0184 are rejected and absent from the firmware lock.
They introduced and repeatedly repaired a second nxstorage request lifecycle,
but the operator reproduced an early PGR2 crash and no material improvement in
Forza. No binary in this directory is a current test candidate.

The direct route remains useful negative evidence. It showed that reducing
nxstorage bookkeeping can reduce synthetic submission cost, but it did not
show that lower-I/O bandwidth causes Forza's missing-world delay. The title
trace instead shows fast lower completion followed by frame-scale request/APC
cadence. The replacement experiment is documented in
[`../forza-fatx-timer-batch-20261018/README.md`](../forza-fatx-timer-batch-20261018/README.md).

## Rejection sequence

- **0180:** created a qualified one-command FATX read bypass. Independent
  transaction tests found four cancel, quarantine, and child-lifetime defects.
- **0181:** fixed those four defects. Final review then found an unlocked
  quarantine-publication handoff and a collision between its private marker
  and `IRP_XB_SG_COMPLETION`.
- **0182:** fixed the handoff and marker collision.
- **0183:** added shared teardown, quarantine, and cancellation lifetimes that
  the bypass still lacked.
- **0184:** removed duplicate planning from the bypass.

Each correction was locally justified, but together they exposed the design
error: the optimization had to reproduce the stable engine's whole ownership
model. The result grew to roughly 1,100 lines while leaving two decisive facts
unchanged: PGR2 crashed in operator testing, and Forza did not materially
improve. The stack is rejected as a unit rather than carrying a safer version
of an unproductive architecture.

[0180-REJECTION.md](0180-REJECTION.md) and
[0181-REJECTION.md](0181-REJECTION.md) retain the deterministic failures found
during review. The rejection records retain the reproduced failures and correction
requirements. The later rejected payloads are not selected or distributed as
current firmware inputs.

## Historical synthetic result

The archived release workload ran selected-0168 / candidate-0181 /
selected-0168 / candidate-0181. Each cell ran for at least ten seconds and
checked payloads, callbacks, pending status, byte counts, canaries, and
lifetimes.

| Pages | Budget | Mean submission cost | Mean verified rate |
| ---: | ---: | ---: | ---: |
| 783 | 250 us | -9.13% | +11.72% |
| 783 | 450 us | -1.02% | +1.81% |
| 783 | 1,000 us | -5.99% | -0.90% |
| 783 | uncapped | -7.08% | -0.69% |
| 900 | 250 us | -4.93% | +6.01% |
| 900 | 450 us | -0.57% | -0.40% |
| 900 | 1,000 us | -2.63% | -0.36% |
| 900 | uncapped | -1.45% | -0.78% |

The narrow 250 us cells improved, while saturated throughput stayed near the
control and some individual cells regressed. This supports only the statement
that bypassing bookkeeping made some submission bursts cheaper. It does not
qualify the rejected route or establish a Forza fix.

## Historical automated title result

Automated 0181 release runs completed two Forza control/candidate pairs and
three PGR2 candidate routes. The retained screenshots looked intact and PGR2
held about 30 FPS in those three processes. These runs did not reproduce the
operator's later early PGR2 crash and did not measure the reported Forza
streaming scene. They therefore cannot override the title failure.

The raw synthetic plans, logs, summaries, run receipts, title run IDs, and
hashes are retained here for audit. They are historical observations from a
rejected image, not acceptance evidence for 0185 or any release.

## Reproduction

From the repository root:

```sh
python3 docs/performance/evidence/forza-direct-native-read-20261018/reproduce.py
```

The reproducer verifies retained archive hashes and classifications. Original
title screenshots remain on the private runner and are represented here by
their recorded hashes and run IDs. No game image, HDD, EEPROM, save, guest RAM,
or firmware binary is committed.
