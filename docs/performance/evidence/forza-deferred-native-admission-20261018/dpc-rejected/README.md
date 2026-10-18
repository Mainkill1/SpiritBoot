# Rejected adapter-DPC read admission

This experiment tested whether returning the FATX direct asynchronous read before starting native transport would reproduce the observed reference cadence. FATX marked only its eligible direct noncached reads. The native adapter queued those reads to its existing FIFO admission DPC after publishing `STATUS_PENDING`; other reads, writes, flushes, controls, and optical traffic retained selected-0168 behavior.

The change passed 45 adapter groups in plain and ASan/UBSan builds. Added groups cover return before lower submission, cancellation before admission, immediate lower completion, a four-read FIFO with a cancelled middle request, a DPC already queued, and removal after the caller returned but before admission. The real FATX fast path passed 134 allocation/lifetime checks, five coupled FAT/checkpoint scenarios, and 178 mapping checks. The exact release64 build used source tree `34bcbc1ba645fec88469adc3cedf4ce0ec6a7366` and produced firmware SHA-256 `b43e250a9daba70517ab6d429836c96033c9d165a7160aaa0fccd209aafe5f53`.

The fresh-process A/B/A/B fixture ran every case for ten seconds and all byte, callback, ordering, and completion oracles passed. The primary 450 us results rejected the design:

| Target pages | Pair 1 cost / rate | Pair 2 cost / rate |
| ---: | ---: | ---: |
| 783 | +1.49% / -0.60% | +10.02% / -5.10% |
| 900 | +8.79% / -6.96% | +0.35% / +0.43% |

Most of the complete matrix also regressed. The adapter DPC can run before the issuing system call returns, so it did not create the intended caller/transport separation and added a scheduling boundary. The patch is excluded from the firmware lock and no game qualification was attempted. `comparison.json` retains all eight cases and four runner identities. The next design must hand off at the FATX worker boundary, which runs after the filesystem dispatch returns, while preserving the selected native adapter state machine.
