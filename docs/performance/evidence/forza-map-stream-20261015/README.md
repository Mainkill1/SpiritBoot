# Forza map-stream release BIOS ABBA evidence — 2026-10-15

This release-only Windows run replays the public request shape captured from Forza world streaming: 1,024 asynchronous FATX reads per pass, queue depth 12, 900 available pages, warm cache, and 16 measured passes. Every attempt used the same xemu executable, config, EEPROM, and fresh private HDD template. The runner launched xemu through the protected PowerShell user-desktop pipeline. No debugger or operator input was used.

The sequence was A/B/B/A. A is the prior known-good IRQ BIOS (`913293b4…`); B is the current PR #248 BIOS (`d1404fe3…`). Both A controls qualified: 16 passes, 16,384 completed operations, queue high-water 12, and no failures. Their median APC batch times were 40,559,969.5 and 39,122,563.5 ticks; A2 differed from A1 by -3.54%, within the fixture's 10% stability threshold.

Both B attempts failed during the first warm-up before any measured pass. Async reads completed with `STATUS_INSUFFICIENT_RESOURCES` (`0xC000009A`): 339 failures in B1 and 371 in B2. The fixture cleaned up correctly and emitted `not ok`. A B-versus-A timing comparison is therefore invalid; correctness fails first.

`summary.json` is the machine-readable result. Each `*-request.json` is the exact runner request manifest. Each `*-analysis.json` is the output of `tools/forza_map_stream.py`. `irq-control-a1-a2-comparison.json` records control stability. Raw serial logs remain in the local run archive because each successful control log is about 6.7 MiB; `summary.json` pins every raw log by byte count and SHA-256.
