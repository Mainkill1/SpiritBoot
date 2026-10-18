# Candidate 0176 paired native qualification

**Generated-fixture qualification only; whole-game Forza validation remains
required.**

**Decision: select 0176.** Every 450 µs target improves in both consecutive
pairs and at both memory-pressure levels. Weighted `NtReadFile` entry-to-return
cost falls **8.99–15.92%**, while verified throughput rises **2.54–13.17%**.
Weighted return cost improves in all sixteen paired case observations. All four
runs pass the full generated-byte, canary, callback status/count/identity,
non-alertable phase and buffer-lifetime oracle.

The order is **0168 control 1 → 0176 candidate 1 → 0168 control 2 → 0176
candidate 2**, with no intervening runner job. Every case runs for at least ten
seconds in a fresh emulator process without a RAM snapshot. Each oracle verdict
was required before the next run could start.

## Change under test

0176 removes repeated state-lock transitions from the ordinary retained read
path while retaining one admission owner and one request-core pump owner:

1. A newly admitted read builds and submits its known first command without a
   general active-slot rediscovery scan. A private rescan handoff catches
   reentrant start, completion, cancellation and quarantine events before the
   fast owner can return.
2. Queue publication hands its held adapter lock into admission ownership, and
   the admission owner's final lock is handed back to the originating dispatch
   epilogue. FIFO and capacity decisions remain under the same lock.
3. Packet preparation arms inline-completion deferral while it already holds
   the adapter lock to publish the request handle. When lower submission has no
   inline result, `NX_SUBMIT_LOCK_HELD` transfers the final held lock to the
   core's post-submit update. Inline completion releases the lock, reports the
   deferred result through the original path, and returns without the flag.

The host-observed retained pending read falls from **14 to 7 adapter lock/IRQL
entries**. Slots, generation tokens, MDLs, packet preparation, lower submission,
cancellation, completion, split reads, queue-frozen recovery, quarantine and
removal rundown remain on the existing paths. Writes and flushes do not use the
first-read fast start.

The exact built source passes 50 request-core tests, 1,528,352 active-scan
differential observations at eight capacities, eight pthread ownership cases,
42 native-adapter groups, ten packet groups, nine owner groups, optical and
sense tests, plus ASan, UBSan and MSan variants. These include completion
reentry, cancellation before and during preparation, completion during lower
submission, depth-12 randomized bursts, saturated admission, FIFO flush
barriers, queue-frozen recovery and removal.

## Primary 450 µs results

Negative return-cost change is faster. Positive throughput change is faster.

| Pair | Free pages | Control µs/read | 0176 µs/read | Cost change | Control reads/s | 0176 reads/s | Rate change |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 783 | 78.406 | 70.547 | -10.02% | 146.638 | 152.571 | +4.05% |
| 1 | 900 | 79.930 | 67.387 | -15.69% | 142.394 | 161.145 | +13.17% |
| 2 | 783 | 81.466 | 68.500 | -15.92% | 138.471 | 155.822 | +12.53% |
| 2 | 900 | 77.651 | 70.667 | -8.99% | 149.839 | 153.650 | +2.54% |

## All weighted cases

Weighted cost divides the sum of all read-call durations by the number of
reads, using each run's own request frequency. It excludes alertable polls,
outside-pump preparation/oracle work and 33 ms blocking intervals.

| Pair | Free pages | Budget µs | Control → 0176 µs/read | Cost change | Control → 0176 reads/s | Rate change |
| ---: | ---: | --- | ---: | ---: | ---: | ---: |
| 1 | 783 | 250 | 113.505 → 104.712 | -7.75% | 71.721 → 76.484 | +6.64% |
| 1 | 783 | 450 | 78.406 → 70.547 | -10.02% | 146.638 → 152.571 | +4.05% |
| 1 | 783 | 1000 | 68.397 → 62.332 | -8.87% | 201.443 → 199.500 | -0.96% |
| 1 | 783 | uncapped | 64.798 → 61.912 | -4.45% | 202.354 → 199.768 | -1.28% |
| 1 | 900 | 250 | 112.670 → 87.271 | -22.54% | 74.785 → 89.863 | +20.16% |
| 1 | 900 | 450 | 79.930 → 67.387 | -15.69% | 142.394 → 161.145 | +13.17% |
| 1 | 900 | 1000 | 66.306 → 63.394 | -4.39% | 201.665 → 199.230 | -1.21% |
| 1 | 900 | uncapped | 66.664 → 62.384 | -6.42% | 202.169 → 199.904 | -1.12% |
| 2 | 783 | 250 | 127.746 → 108.309 | -15.22% | 66.424 → 72.235 | +8.75% |
| 2 | 783 | 450 | 81.466 → 68.500 | -15.92% | 138.471 → 155.822 | +12.53% |
| 2 | 783 | 1000 | 69.807 → 61.023 | -12.58% | 201.380 → 199.472 | -0.95% |
| 2 | 783 | uncapped | 69.636 → 63.053 | -9.45% | 202.067 → 200.006 | -1.02% |
| 2 | 900 | 250 | 107.654 → 97.890 | -9.07% | 73.121 → 82.858 | +13.32% |
| 2 | 900 | 450 | 77.651 → 70.667 | -8.99% | 149.839 → 153.650 | +2.54% |
| 2 | 900 | 1000 | 69.974 → 63.824 | -8.79% | 201.468 → 198.812 | -1.32% |
| 2 | 900 | uncapped | 65.534 → 63.079 | -3.75% | 202.283 → 199.566 | -1.34% |

The 1000 µs and uncapped cases sit at the fixture's approximately 200 reads/s
ceiling. Their throughput varies by at most 1.34% while all eight weighted call
costs improve by 3.75–12.58%. No weighted cost or throughput regression exceeds
20%.

## Required over-20% investigation

One per-size mean crosses the 20% review threshold: pair 1 at 900 pages and
1000 µs reports the 512-byte mean **31.25% higher**. The request-position
populations differ materially. All 254 nonempty control frames begin with a
64 KiB read, so every measured 512-byte request occupies the second position.
The candidate has 88 frames beginning with 512 bytes. In pair 2, control and
candidate both have mixed first positions (128 and 88 512-byte-first frames),
and candidate 512-byte cost improves **16.02%**. Whole-case weighted cost
improves **4.39%** and **8.79%** in the two pairs. The raw regression and all
four position counts remain in [decision.json](decision.json); no repeatable
unresolved regression over 20% remains.

Four individual per-size maxima rise by more than 20%. They are retained in the
decision record as outliers, separate from means and throughput. No claim is
made that the change improves every observed maximum.

## Identity and reproduction

0176 release64 BIOS SHA-256:
`5be85ddc85f462a0a6ef28ed2ba5fb4ba3e1688c75cab4e2ebcbad556a33c1a2`.
Assembled source tree: `c30e8e2e9cab57d122040f1cd6a17bb44928ae0a`.

0168 control SHA-256:
`2d43d91ca5a4474a365e308b2117a642a94a2d7c7da6a3004409c267173680e6`.
All runs use XISO
`8d94b0c6fa4699de29959e0bdc5ddd63b6b518ea7c65fcf22cf4da9e1f9b4630`
and release xemu
`5488be40bf3c1c444b507d084c8d964f8f7d73c2a912970495cf85a4f7239564`.
Launcher, configuration, arguments and 64 MiB memory are identical; only the
firmware differs.

[capture-manifest.json](capture-manifest.json) binds source request hashes,
input hashes, run IDs, completion times and prior-job identities. The sanitized
build receipt binds the release artifact and exact source tree. Private paths,
endpoints, workstation telemetry and firmware/emulator/EEPROM/HDD/game/RAM/
snapshot payloads are excluded.

```sh
python3 docs/performance/evidence/forza-complex-cadence-20261017/candidate0176/reproduce.py
```

Reproduction verifies the frozen analyzer, plan, build/input/run hashes,
consecutive order, raw serial logs, saved summaries, comparison and decision.
This synthetic blocking-cadence fixture is a controlled storage-path test. It
does not establish whole-game Forza performance, cold-cache behavior or
statistical significance from only two observations per variant.
