# Rejected FATX worker admission

This follow-up moved asynchronous noncached FATX mapping and native submission from the title's initial filesystem dispatch into FATX's existing critical worker queue. The worker consumed a one-shot IRP-context flag, retained the allocation-free direct mapping path, and fell back to the established blocking worker path if eligibility changed. The selected-0168 native adapter was unchanged.

The real FATX bodies passed 160 issuer/worker/lifetime checks, five coupled FAT/checkpoint scenarios, 178 mapping checks, and 12,056 extent-cache observations. Native adapter plain and sanitizer tests stayed at 42/42. The exact release64 build used source tree `4cf679222eb993cbc0e3233b605ef96343a9de23` and firmware SHA-256 `4699680c31f768a9f03c8e06a87d479bef70d510dd96a1e88557883becd3747e`.

All four fresh-process ten-second-per-case fixture runs passed their byte, callback, ordering, and completion oracles. The primary 450 us results rejected the design:

| Target pages | Pair 1 cost / rate | Pair 2 cost / rate |
| ---: | ---: | ---: |
| 783 | +2.20% / -3.86% | +7.60% / -7.75% |
| 900 | +9.99% / -4.59% | +23.30% / -12.29% |

The worker wakeup did not provide a cheap public return on this single-CPU guest. It usually added scheduling cost to the measured issue window, including a repeatable direction at both memory targets and a pair-two regression above 20%. The patch is excluded from the firmware lock and no game qualification was attempted. `comparison.json` retains the complete matrix and run identities.
