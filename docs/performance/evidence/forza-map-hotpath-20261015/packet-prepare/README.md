# Packet preparation hot-path delivery

The integration artifact is `0150-native-packet-prepare-hotpath.patch`. Apply it
after SpiritBoot patch 0149. The exact pre-tree is
`a8f3fc46e27bc8e0f51f23708a02a73237565b2e`; applying only this patch produces
post-tree `63ce2832cea9bf6fe9fd7b93bc42a7c4d5a59674`.

This is the reviewed replacement for the rejected initial 0150 draft. The final
patch explicitly makes the zero-length RELEASE_QUEUE CDB path source-inert, uses
native-width page arithmetic, proves native clear size/alignment assumptions,
and adds plain, ASan/UBSan, and MemorySanitizer regressions.

Read `PACKET-PREPARE-HOTPATH-SPEC.md` for the frozen behavior and
`PACKET-PREPARE-HOTPATH-REPORT.md` for implementation, performance, tests, and
limits. `evidence/DECK-ABBA-SUMMARY.json` is the final machine-readable paired
result. Raw phase profiles, runner results, input manifests, cleanup receipts,
and compressed serial captures support every row.

The build used the pinned `spiritboot-toolchain` image and normal release64
command:

```sh
python3 scripts/build-firmware.py \
  --source /path/to/roswell-1569 \
  --output /path/to/output \
  --storage-backend complete-candidate \
  --variant release --memory-mib 64
```

Run qualification from the assembled source:

```sh
python3 tests/host/nxstorage/check_packet.py /tmp/packet
CC=gcc python3 tests/host/nxstorage/check_packet.py /tmp/packet-gcc
python3 tests/host/nxstorage/check_adapter.py /tmp/adapter
python3 tests/host/nxstorage/check.py /tmp/core
```

The packet runner uses `$CC` for plain and ASan/UBSan builds and independently
discovers a MemorySanitizer-capable clang for the no-source-read checks.
`tools/run_deck_final.py` records the release-only A/B/B/A jobs without rebooting
the Deck. Every private runtime HDD was deleted after evidence collection.
