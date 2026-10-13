# Halo 64 MiB memory compatibility evidence

This directory contains independently authored public probes and derived receipts used by `HALO_64MIB_MEMORY_COMPATIBILITY.md`.

- `memory-inventory-probe/` is an nxdk XBE source and its frozen build. It calls public memory APIs and emits aggregate statistics; it reads no firmware or title instructions.
- `memory-inventory.json` records the first stable sample from each matched native arm and binds the original local serial logs by SHA256.
- `failure-chain.json` retains only public exception metadata and the owned-kernel/public I/O outcome from bounded traces. `instruction_bytes_read` is false for both collectors.
- `release64-build.json` binds the reproducible firmware to its ordered patches and exact reconstructed kernel tree.
- `threshold-control.json` records the prior controlled 22-page title threshold and binds its open-kernel source note.
- `profile-builds.json` records all supported profile outputs and the byte-identical clean 64 MiB release rebuild.
- `host-tests.json` and `source-gates.json` bind the product and reconstructed-source regression runs to their retained local logs.
- `native-api.json` and `native-warm-reset.json` bind the exact public probes and native results.
- `game-observations.json` records the 15, 30 and 45-second liveness samples and the locally reviewed outcome labels. Game images and screenshots are intentionally absent.

No proprietary firmware, game payload, instruction bytes, disassembly or secret material is stored here.
