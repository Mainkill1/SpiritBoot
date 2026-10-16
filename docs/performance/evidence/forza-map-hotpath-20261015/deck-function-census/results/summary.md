# Retained-SG Forza 1,024-read Deck function census

Correctness: **PASS** (1,024/1,024 operations, 10,871,296 bytes, QD12, pressure 900, zero oracle failures).

The marked phase executed 190 supplied kernel entries and 1 additional nearest-symbol ranges. The ledger contains 191 nonzero rows.

## Functions above 1% of weighted guest instructions

| Function | Entry hits | TB executions | Weighted instructions | Share | Diagnostic vCPU CPU share |
|---|---:|---:|---:|---:|---:|
| `_pump` | 2,048 | 374,167 | 1,415,676 | 10.45% | 10.70% |
| `_VfatTryMapRead` | 1,024 | 317,902 | 1,393,946 | 10.29% | 9.46% |
| `@KfLowerIrql@4` | 44,016 | 134,526 | 797,316 | 5.88% | 4.07% |
| `_KeStallExecutionProcessor@4` | 1,024 | 271,360 | 542,720 | 4.01% | 7.19% |
| `_NxNativeAdapterSubmit` | 1,024 | 92,112 | 446,222 | 3.29% | 3.07% |
| `_nx_packet_prepare.constprop.0` | 1,024 | 64,512 | 371,712 | 2.74% | 1.99% |
| `@KeUpdateSystemTime@12` | 2,762 | 47,805 | 354,390 | 2.62% | 1.90% |
| `_VfatDispatchRequest.lto_priv.0` | 1,024 | 56,320 | 337,920 | 2.49% | 2.16% |
| `_KiDeliverApc@12.constprop.0` | 2,778 | 49,321 | 282,501 | 2.08% | 1.55% |
| `@IofCompleteRequest@8` | 2,048 | 48,128 | 244,736 | 1.81% | 1.56% |
| `@ExpFindEntryForThread@16` | 2,357 | 69,223 | 221,388 | 1.63% | 2.00% |
| `_VfatLookupSeekCheckpoint.constprop.0` | 1,024 | 60,172 | 219,840 | 1.62% | 1.69% |
| `@KiEoiHelper@4` | 4,692 | 51,612 | 182,988 | 1.35% | 1.61% |
| `_AtaReqStartRequest` | 1,024 | 31,744 | 163,840 | 1.21% | 1.25% |
| `@IofCallDriver@8` | 5,120 | 20,480 | 163,840 | 1.21% | 0.78% |
| `_port_leave` | 21,885 | 43,770 | 153,195 | 1.13% | 1.31% |
| `_AtaReqCompleteRequest.lto_priv.0` | 1,024 | 30,681 | 149,426 | 1.10% | 1.11% |
| `_NtReadFile@36` | 1,024 | 16,384 | 145,408 | 1.07% | 0.66% |

## Measurement limits

- Plugin callbacks and per-TB thread clocks heavily perturb wall and CPU time; neither is a release timing result.
- Weighted guest instructions are exact for translated blocks executed during the marked phase, but do not weight TCG helper or host I/O cost.
- Entry hits are exact for supplied PE/COFF function/code-entry addresses; aliases at one address are combined.
- Range attribution assigns a TB to the nearest lower supplied entry and can absorb local assembly labels, padding, and omitted private bodies.
- Inlined and LTO-eliminated source functions have no independent entry and cannot be attributed separately.
- vCPU thread CPU excludes xemu storage, render, audio, and other host worker-thread CPU.
