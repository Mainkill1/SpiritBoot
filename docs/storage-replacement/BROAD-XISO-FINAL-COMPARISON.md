# Final pre-extraction broad XISO comparison

Status: **the four-run campaign completed, but the frozen repeatability gate
failed on one Complex framebuffer observation.** The result does not establish
a SpiritBoot regression: both SpiritBoot runs repeat exactly, and the first
Complex run matches both SpiritBoot runs across all 149 eligible records. This
is pre-extraction evidence for the exact final release64 image, not
qualification of the unimplemented storage replacement.

## Frozen inputs and method

The campaign used the frozen 144-leaf suite plus five structural groups. The
suite ISO has SHA-256
`10ca07f227ae4e1d03510fcc1d3237304ff4291741d4c552ab33991e71de1738`.
The SpiritBoot BIOS was
`0f6e4f48269e0ef65bb27758e221b4bcdb707ef0cbf57c211d7e969866334d5e`;
the Complex BIOS was
`1de4c87effe40d44f95581d204f9fa0600fbd5fe2171692316dcf97af0f4113f`.
Both ran at 64 MiB on the same primary Linux host, xemu and OpenGL renderer.

The same-host policy was frozen before the first Complex result. It requires
both runs of each BIOS to repeat every eligible observation, as well as
cross-BIOS equality. Two observations explicitly marked
`oracle_applicable=false` remain excluded. Framebuffer hashes pinned on a
different Windows/backend context are informational in this same-host run. The
execution order was candidate A1, Complex B1, Complex B2, candidate A2; no run
was retried or substituted.

All four runs completed exactly 144 of 144 leaves and all 149 records reported
PASS with zero built-in applicable-oracle failures. Every run shut down and
cleaned its private state successfully.

## Frozen-policy result

The candidate repeats have no eligible differences. Complex B1 and B2 differ
only at
`vertex_buffer_allocation.disjoint_same_page.framebuffer_fnv1a64`:

| Run | Framebuffer FNV-1a 64 |
| --- | --- |
| Candidate A1 | `fdcd25a37910bb25` |
| Complex B1 | `fdcd25a37910bb25` |
| Complex B2 | `ffce5ac91d0966b5` |
| Candidate A2 | `fdcd25a37910bb25` |

Accordingly, A1 equals B1 and A2 equals B1 across all eligible records; both
candidate runs differ from B2 only at this observation. The `fdcd...` value
also matches the pinned reference and retained OpenGL/Vulkan evidence, while
`ffce...` appears only in B2. The most likely explanation is a transient
fixture, renderer or scheduling race in that one reference run. Firmware-sensitive
scheduling cannot be excluded. The frozen campaign verdict remains **FAIL**
because the reference arm did not repeat; the discrepancy is not waived after
observing the result.

The first candidate run also disagreed with 55 framebuffer values pinned from
the Windows reference context. Those values are retained as informational.
They do not fail the final policy because the host/backend changed and the
same-host comparison was frozen before Complex executed.

## Descriptive timing

Timing is descriptive because the functional repeatability gate failed and
there are only two runs per BIOS. Host page cache and in-memory driver cache
were not controlled. These values cannot support a release performance claim
or replace the P1 experiment.

The sum of the 144 two-run leaf means was 31,544,807.3725 microseconds for
SpiritBoot and 31,639,398.06 microseconds for Complex, a candidate/Complex
ratio of `0.9970103512` (about 0.299% lower for SpiritBoot). SpiritBoot had the
lower mean in 64 leaves and Complex in 80. The per-suite ratios show why the
aggregate must not hide individual slow paths:

| Suite | Leaves | Candidate / Complex | Descriptive direction |
| --- | ---: | ---: | --- |
| `game_load` | 52 | 1.007874 | Complex lower |
| `busy_pfifo` | 2 | 0.999058 | SpiritBoot lower |
| `vertex_buffer_allocation` | 9 | 0.943616 | SpiritBoot lower |
| `cpu_floating_point` | 2 | 0.991067 | SpiritBoot lower |
| `cpu_translation_blocks` | 3 | 1.010275 | Complex lower |
| `tiny_draw` | 8 | 0.998581 | SpiritBoot lower |
| `high_vertex_count` | 4 | 0.956686 | SpiritBoot lower |
| `surface` | 26 | 1.037572 | Complex lower |
| `pipeline_texture_switch` | 4 | 1.014795 | Complex lower |
| `primitive_type` | 20 | 0.872795 | SpiritBoot lower |
| `report_query` | 8 | 0.930372 | SpiritBoot lower |
| `fill_rate` | 2 | 0.945391 | SpiritBoot lower |
| `uniform_thrash` | 1 | 1.137488 | Complex lower |
| `pfifo_array_elements` | 3 | 0.738341 | SpiritBoot lower |

The largest visible candidate regressions include `busy_pfifo.pfifo_saturation`
at `1.884283` and the `surface.vulkan_memory_pressure.representative` group at
`1.209379`. These remain investigation targets even though the aggregate is
slightly lower. The complete 144-row table is the portable
[leaf CSV](../provenance/evidence/pr248-final-broad-xiso/leaf-averages.csv).

## Evidence

The portable [final comparison](../provenance/evidence/pr248-final-broad-xiso/final-comparison.json)
has SHA-256
`bb5ee1fe898cb3fe660c26991896aa8c7e8365edecc2a22841452fc41e326096`.
The [frozen policy](../provenance/evidence/pr248-final-broad-xiso/policy.json)
has SHA-256
`b371713f23996f3844b964c7907999d85cefb652a9de1eb1ce6377b8e6f74a85`;
the [execution receipt](../provenance/evidence/pr248-final-broad-xiso/execution-receipt.json)
has SHA-256
`2dfac4bdac09e1edb84f757ece5720c2821fb0a1aebdd161d17c9e2721c59893`.
The repository-normalized leaf CSV has SHA-256
`94a6d0ca72d3b7e3a3df010dc02d490b345963b01c804aeba6526436ec6e4346`.
The [manifest](../provenance/evidence/pr248-final-broad-xiso/manifest.json)
binds these portable files to the retained original receipts and records path,
endpoint, host-label and CSV line-ending normalization.
