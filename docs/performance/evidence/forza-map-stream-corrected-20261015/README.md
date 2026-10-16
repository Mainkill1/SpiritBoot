# Corrected Forza map-stream candidate — 2026-10-15

This release-only Windows qualification uses the same standalone fixture, xemu, config, EEPROM, fresh private HDD template, and protected PowerShell user-desktop launch path as the A/B/B/A regression run. No debugger, firmware tracing, or operator input was used.

The corrected BIOS (`aed336c4…`, source tree `da043f7…`) qualifies twice. C1 and C2 each complete 16 passes, 16,384 asynchronous FATX operations, queue high-water 12, and the 900-page pressure point with zero failures. Candidate medians differ by only 0.77%.

Correctness is restored, but performance remains behind both known-good controls. Candidate APC/caller batch medians are 27.7–33.5% slower in the four pairwise comparisons. Averaging the two run medians per arm gives +30.54% APC batch time and +37.81% submit-sum time. Post-return-to-APC sum improves by 14.14%, which localizes the remaining regression to submit-side work rather than delayed completion.

`summary.json` records exact BIOS, fixture, runner, job/run, controlled-input, raw-serial, and analysis identities. Request manifests and hardened analyzer outputs are included. The large raw serial logs stay in the local runner archive and are pinned by byte count and SHA-256 in `summary.json`.
