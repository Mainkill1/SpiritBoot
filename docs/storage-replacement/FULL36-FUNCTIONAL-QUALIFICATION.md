# Complete 36-case functional qualification

The Steam Deck completed all 36 predeclared V32 cases with the published
64 MB reference BIOS, SHA-256
`c630d22f2353d3898024d510f0b402b64bccdb331781fe7885389f73d6200853`.
Every case used a fresh process and private HDD/EEPROM state. All attempts exited
successfully, retained complete evidence, and confirmed target shutdown and
runtime-disk cleanup. This tests the reference firmware and the benchmark method;
the complete replacement storage driver is not implemented.

The [machine-readable receipt](full36-functional-native-receipt.json) lists every
case and native run, actual prepared-disk hash, source-seed lineage, operation
counts and raw evidence hashes. The sequence ran from 2026-10-14 20:37 UTC to
20:50 UTC. No failed attempts were replaced or excluded from this cohort.

| Family | Passed cases | Coverage |
| --- | ---: | --- |
| Small HDD reads | 2 | Depth 1, warm and cold-ish |
| FATX replay | 24 | Two request sequences, depths 1/4/12, normal and 900-page pressure, warm and cold-ish |
| Write/flush API | 2 | Write, API flush, reopen and verified readback, warm and cold-ish |
| Transfer boundaries and scatter/gather | 4 | Split and fragmented requests, warm and cold-ish |
| DVD | 4 | Both released payloads in fixed wrappers, warm and cold-ish |

The cohort completed 36,864 operations and 795,975,680 reported completed bytes.
All 188,416 fixture assertions passed. The frozen generation-2 fixtures poison
output buffers before reads and verify returned bytes, status and IOSB counts;
the collector additionally checks the scheduled APC, queue-depth and pressure
contracts. File readback checks are distinct from physical durability.

The full36 plan is
`9de45a8d7a3aee5bbae92ce13e2a2378f38d31c13ae91e5ee487ded6cf0765f4`.
Its collector is
`8463a75f7a9138c49730adbf8d116db407265cf063e3eac4bdeb35ba706c7483`;
the 328-file outer freeze is
`8b6338df9926540242f1d89bf7d471b7eaa98c91d1f0aa851d4d846a6470aafd`.
The 32 non-optical cases use the unchanged V2 suite. The four DVD cases use the
[qualified fixed-media method](DVD-METHOD-QUALIFICATION.md): the wrapper boots
the recorder and retains the entire original payload as `target.xbe`. The
wrapper is not relabeled as the original released ISO.

This is a functional qualification, not an A/A noise report or a performance
comparison. The DVD initial guard can overlap measurement, and retained timing
values still use the historical metadata conversion. All 36 rows remain
performance-ineligible. Real device-cache synchronization, physical power-loss
durability, private structural counters, original optical media-change parity,
Windows full36 coverage and P1 acceptance remain open. The earlier failed
media-change methods are retained in the linked DVD writeup.
