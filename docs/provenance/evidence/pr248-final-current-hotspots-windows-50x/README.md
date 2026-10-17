# PR #248 exact-candidate Windows 50x hotspot comparison

This package records and reproduces the 2026-10-15 targeted comparison of the exact PR #248 SpiritBoot release64 candidate against Complex 4627. It lengthens the original one-second diagnostic by applying a `50` measurement multiplier and three warmups to each selected leaf. Each xemu process ran for 63.379 to 64.526 seconds.

The fresh confirmatory campaign used an A1/B1/B2/A2 order, where A is SpiritBoot and B is Complex. Every arm completed all six selected leaves, passed the frozen correctness contract, produced complete evidence, and was marked comparison-eligible by Xemu-Test-Runner.

## Frozen inputs

| Input | Identity |
| --- | --- |
| SpiritBoot source head | `7182e22c43b3a411bcf177946f05bf963b8248a7` |
| SpiritBoot release64 BIOS | `cff12e2cd1b1af1faf0060b676d8ffc37f8256400b12edfe5ad3b2a191943db9` |
| Complex 4627 BIOS | `1de4c87effe40d44f95581d204f9fa0600fbd5fe2171692316dcf97af0f4113f` |
| xemu executable | `14777b55740706608cdfde97349eefa3d5115ece4c889679c9c8b96641a85f2d` |
| XISO fixture | `10ca07f227ae4e1d03510fcc1d3237304ff4291741d4c552ab33991e71de1738` |
| XISO catalog | `sha256:c5059152ee5e253a7ab66156f50ae7218e821b021f76203185cda30e2e8a94f7` |
| Private HDD seed | `f048c5cb4f408da9bd750e93980b59de4b6ae10abcd70e0663b73d9023a640d8` |
| EEPROM seed | `d8ad01ff8c028aca874c82940b6cb54b4f81b53204fe42716729c549fb3728f5` |
| Windows 50x reference | `eeb1132f12ae6b432081525901d19d001d0f15dddf40ab47533356bf8aedf2dc` |
| Xemu-Test-Runner client | commit `0ba533ed89c8bb3cf530c4bfff8dbb190b3f08be` |

The host was Windows 10.0.19045 on an AMD Ryzen 9 6900HX with 16 GiB RAM, AC power, the High performance power plan, a live unlocked `WinSta0\\Default` desktop, Vulkan, 64 MiB guest RAM, vsync disabled, and shader caching disabled. The runner launched xemu through the logged-in user's PowerShell named-pipe transport.

## Reference provenance

The first 50x diagnostic correctly lengthened the work but used the historical 1x Steam Deck/OpenGL reference. The runner rejected every leaf because fixed-work fields and host-dependent framebuffer hashes differed. Both BIOS arms nevertheless produced the same framebuffer hashes and passed the guest's built-in Vulkan-memory oracle.

Complex run `20261015-222634002-762fd437855341b7b7cd57d27d31932a` supplied the Windows 50x fixed-work records and framebuffer hashes in `reference-results-windows-50x-v1.json`. That file was frozen before the fresh campaign below. The fresh A1/B1/B2/A2 campaign then passed it without modification. Timings from the preliminary campaign are excluded from the confirmatory result.

## Confirmatory runs

| Order | BIOS | Run ID | Process duration | Contract |
| ---: | --- | --- | ---: | --- |
| A1 | SpiritBoot | `20261015-223140930-343b327ba1bd43dcac1a74623f00f27e` | 64.263 s | passed / eligible |
| B1 | Complex | `20261015-223247827-e99e4f7db65042c0be77763098d776ca` | 63.619 s | passed / eligible |
| B2 | Complex | `20261015-223354067-4a4ee733c6734c0a90b376d21332d06b` | 63.379 s | passed / eligible |
| A2 | SpiritBoot | `20261015-223500070-e11bf194e9cc4c6dbf472a1fdb212595` | 64.526 s | passed / eligible |

Lower times are better. The delta is `(SpiritBoot / Complex - 1) * 100`.

| Leaf | SpiritBoot mean | Complex mean | Delta |
| --- | ---: | ---: | ---: |
| `busy_pfifo.pfifo_saturation` | 89,045.874 us | 90,874.586 us | **2.012% faster** |
| `surface.vulkan_memory_pressure.representative.growth` | 11,063.245 us | 11,201.483 us | **1.234% faster** |
| `surface.vulkan_memory_pressure.representative.plateau` | 12,247.175 us | 12,591.728 us | **2.736% faster** |
| `surface.vulkan_memory_pressure.representative.alias_resize` | 13,528.233 us | 13,805.385 us | **2.008% faster** |
| `surface.vulkan_memory_pressure.representative.reuse` | 14,777.673 us | 15,172.217 us | **2.600% faster** |
| `surface.vulkan_memory_pressure.representative.idle_retention` | 678.493 us | 576.420 us | **17.708% slower** |

The combined fixed work across the five memory-pressure leaves was 10,458,963.5 us for SpiritBoot and 10,669,446.5 us for Complex, making SpiritBoot **1.973% faster** for that group. No selected leaf crossed the requested 20% regression-investigation threshold. `idle_retention` remains the largest observed loss and should be retained in future broad sweeps.

These are targeted xemu graphics-path measurements. They do not replace paired storage, physical-Xbox, title-loading, or full-catalog qualification.

Cross-host confirmation and future regressions are tracked in [issue #249](https://github.com/Mainkill1/SpiritBoot/issues/249).

## Package contents and reproduction

- `campaign.json` freezes BIOS identities, settings, order, tests, reusable payload sources, and request hashes.
- `requests/*.json` are the exact four submitted job definitions.
- `reference-results-windows-50x-v1.json` freezes the fixed-work and framebuffer correctness records.
- `execution-receipt.json` records the four original runner outcomes and run IDs.
- `analysis.json` contains the full per-run inputs and calculations.
- `execute_campaign.py` submits the same jobs and collects evidence.
- `analyze.py` recomputes ratios from a collected evidence directory.

The runner must already contain the read-only MCPX and Complex assets, the private XISO HDD seed, and the two payload-reuse source jobs named in `campaign.json`. Proprietary or bulky binaries are represented by hashes and are not committed here.

Example:

```bash
python3 execute_campaign.py \
  --runner-tools /path/to/Xemu-Test-Runner/scripts \
  --candidate-bios /path/to/flash.bin \
  --fixture /path/to/suite.iso \
  --output /path/to/new-evidence \
  --job-suffix repeat-1

python3 analyze.py /path/to/new-evidence --output /path/to/new-analysis.json
```

Use Xemu-Test-Runner commit `0ba533ed89c8bb3cf530c4bfff8dbb190b3f08be`. `--job-suffix` keeps reruns from colliding with the original immutable runner job IDs.
