# Rejected inline FATX completion deferral, 2026-10-18

## Decision

Patch 0187 is rejected and absent from the firmware lock. It started lower
transport through the selected 0168 engine, then delayed only a marked FATX
read whose lower driver completed synchronously inside `IofCallDriver`.

The first controlled release pair passed every correctness oracle but failed
the performance gate:

| Metric | Selected 0168 control A | 0187 candidate A | Change |
| --- | ---: | ---: | ---: |
| Weighted public read-call cost | 73.267 us | 75.853 us | +3.53% |
| Aggregate reads/second | 155.343 | 155.456 | +0.07% |
| Aggregate bytes/second | baseline | +0.09% | +0.09% |

All eight cases ran for at least ten seconds and passed their data oracles.
The candidate screenshot proved only `FATX async completion` changed from Off
to On; contiguous allocation and optical controls stayed Off, ATA stayed Safe,
and the aggregate switch changed from Off to Mixed. Candidate B and real-title
runs were stopped after this result.

Run identities:

- control A: `20261018-164733599-97b72614fc0540908ef2f0c1fedc95f1`
- candidate A: `20261018-164955697-46bc20e5caf54f8aa6c39d9a09cfdc4f`
- excluded control B: `20261018-165214582-f147a4928e244eb3a9f06de02ba8e34e`

Control B had already started when the stop decision arrived. The runner did
not allow cancellation during an active job, so it completed normally with all
eight cases correct and is explicitly excluded from the comparison. Candidate
B was not run.

## Why it failed

Only 36 of 498 reads in the retained title trace completed before the public
API returned, limiting the theoretical benefit to roughly 2.64% of weighted
call cost. The Xbox one-kilohertz clock also quantizes the relative `-5000`
timer to the next tick, approximately zero to one millisecond, which can move
completion work into the title's 456.8-microsecond issue pump. The measured
result confirms that the added timer/DPC path cost more than it saved.

Independent lifetime review found no concrete double-completion, cancellation,
quarantine or removal defect. That result establishes only the tested contract;
it does not override the measured performance rejection.

## Exact rejected build

| Field | Value |
| --- | --- |
| Assembled source tree | `196ef4e0c17e796896f502f01bffaf7424336d1a` |
| Patch SHA-256 | `a58604a1e61b9d9e0a7c0d5af24623d384c42670ddc93879b80802241dfbdf1c` |
| Release64 firmware SHA-256 | `ee4cf66b98da41041c06f118edb7737282cf6ba84f9ebcca70c68a38375c6ed6` |
| Firmware size | 524,288 bytes |
| Kernel SHA-256 | `2fe1d5946611e00fb25bb8854ebc62d4ba5f2f9307825c0f1e2768feecfe44ff` |
| Linker map SHA-256 | `31d639ab275f89c06de97b4db906db007533e6289341b9459fad5987c9a64906` |
| Experiment firmware-lock SHA-256 | `e3cd129e445387df468ae0e74035aefde5f5ec6af4571012096c81c6bf5b69f9` |

The exact tree passed 50 native-adapter groups in plain and ASan/UBSan builds,
134 FATX checks, five producer/adapter coupling checks, and the boot-menu test.
The full pre-result host run executed 564 tests with 26 environment-dependent
skips; its only two failures were the expected coverage pins that still named
the prior experiment. Those pins are refreshed only after a candidate is
selected.

The patch is retained beside this report for reproduction. It is not part of
the selected patch directory.
