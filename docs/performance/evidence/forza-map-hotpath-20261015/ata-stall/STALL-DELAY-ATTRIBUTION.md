# KeStallExecutionProcessor attribution and ATA 400 ns candidate

## Decision

**Recommend integration as Roswell patch `0152-ata-400ns-status-reads.patch`, after packet patch 0150 and ATA cache-capture patch 0151.** The measured 1,024-entry hotspot is the mandatory ATA device-selection settle interval. The interval must remain, but the calibrated 1 us guest CPU loop is not the protocol's required implementation. On Xbox, four serialized reads of Alternate Status provide the ATA settle interval, preserve the pending IRQ, and leave the first ordinary Status read in the same place. Release/native testing shows a temporally adjacent end-to-end gain and no request, queue-depth, oracle, or completion failure.

This work inspected owned PATA source, exact final-release binaries, the current Steam Deck census, public xemu IDE behavior, and newly collected release/native traces. It did not inspect legacy ClassPnP, Disk, or nxcdrom implementation bodies.

## Exact inputs

| Item | Identity |
|---|---|
| Final release64 BIOS under review | SHA-256 `07c52600c710adb5a7ca7748904603a13174e261ce2ce24923dafb0df4b2277a` |
| Final release source tree | `a8f3fc46e27bc8e0f51f23708a02a73237565b2e` |
| Final unstripped kernel | SHA-256 `4ee1e203c08499a2c32e8aca42edc41465cecfe2ecd62bd9d2e6608bc478f664` |
| Deck executed-function ledger | SHA-256 `a07e4048aba161a4444ef2de5a86f5ef7c85a5cad80ce15555e7eaabf99686f5` |
| xemu source used for emulator semantics | commit `51f8761f7c7ce144cbdb70d5a6181554f1d9aeec`; `hw/ide/core.c` SHA-256 `37063499faf9307f766ab08f7c8896609bfa0242cbdeb6fe14712dc6ce08fc7f` |
| Candidate-only release64 BIOS | SHA-256 `f27038c3639670b2242c4fa809374e4af9a267930f3a1db5ca6abbb1a2d4c956` |
| Candidate-only source tree | `3f154d6c9d27ea3625e55501b26f6a600df529a4` |
| Candidate-only unstripped kernel | SHA-256 `5a9f14f0fd17985b547f85e2876311bc87353c0eadfc340506e4bd54461ea0bb` |
| Integrated 0150/0151/0152 release64 BIOS | SHA-256 `615f7b9b28ba5a1ead8c83c22564e3d55e94c5720f0ce0af590670947c54dd05` |
| Integrated source tree | `035b13670b3caf36d784b9ef6aec0ef916cbb0be` |
| Integrated unstripped kernel | SHA-256 `c3f1db26450c0c1e1f5e08241a3925772e7d39a96f3e9f6d4a31dde177722bd0` |

## Dynamic attribution

The Deck census reports:

| Symbol | Entries | TB executions | Weighted instructions | Weighted share | Diagnostic thread CPU share |
|---|---:|---:|---:|---:|---:|
| `_KeStallExecutionProcessor@4` | 1,024 | 271,360 | 542,720 | 4.005081% | 7.194504% |
| `_PataStartIo` | 1,024 | 19,456 | 76,800 | 0.566757% | 1.973146% |
| `_PataReadStatus` | 2,048 | 4,096 | 8,192 | 0.060454% | 0.415612% |

Exact release disassembly proves that every `PataStartIo` invocation unconditionally:

1. writes the Device/Head register;
2. calls `KeStallExecutionProcessor(1)` through `ATA_IO_WAIT`;
3. reads Status.

There are exactly 1,024 `PataStartIo` entries and exactly 1,024 total stall entries. The unconditional one-per-request site therefore accounts for the entire measured stall population. No conditional 10 us poll, reset path, SMBus, PHY, USB, or video stall ran in the marked phase. The 2,048 `PataReadStatus` entries are consistent with two status observations per request and do not introduce another stall.

The generic stall implementation is already handwritten assembly: it multiplies the calibrated PCR stall scale by the requested microseconds and runs an aligned decrement loop. There is no compiler-generated helper or missed intrinsic to repair. The census plugin observes translation blocks and reads clocks around callbacks, so the reported 4.005% guest-instruction and 7.195% diagnostic CPU shares magnify the loop. The release/native replay below confirms that replacing the realization still improves uninstrumented execution.

## Complete static caller/delay inventory

The final linked release has 30 direct calls. The address-level list is in `evidence/static-direct-callers.tsv`; the grouped inventory below accounts for all of them.

| Linked caller | Delay (us) | Static sites | Disposition |
|---|---:|---:|---|
| `HalpXboxSmBusTransfer` | 1 | 1 | Retain hardware poll delay |
| `NxPhyInitialize` | 100 | 2 | Retain PHY reset/autoneg polling |
| `NxpPhyClearLock` | 50 | 1 | Retain MII transfer polling |
| `NxpPhyReadReg` | 50 | 1 | Retain MII transfer polling |
| `NxpPhyWaitForLinkUp` | 100 | 1 | Retain link-state polling |
| `NxpPhyWriteReg` | 50 | 1 | Retain MII transfer polling |
| `PataIdentifyDevice` | 10 | 1 | Retain bounded status poll |
| `PataIsDevicePresent` | 1 | 1 | Replace ATA settle realization |
| `PataIssueSoftwareReset` | 20 | 2 | Retain reset pulse/recovery timing |
| `PataPollingTimerDpc` | 1 | 1 | Replace ATA control-settle realization |
| `PataPollingTimerDpc` | 10 | 1 | Retain bounded status poll |
| `PataProcessRequest` | 10 | 3 | Retain bounded DRQ/status polling |
| `PataResetChannel` | 1 | 2 | Replace ATA device-select settle realization |
| `PataStartIo` | 1 | 4 | Replace ATA device/control-select settle realization; first site is all 1,024 measured entries |
| `PataStartIo` | 10 | 3 | Retain bounded status polling |
| `BsOhciStop` | 100 | 1 | Retain OHCI state transition poll |
| `BsControl` | 100 | 1 | Retain USB control state poll |
| `BootVgaInitializationKernelNG` | 500 | 3 | Retain encoder/SMBus initialization delay |

The patch replaces four owned-source `ATA_IO_WAIT` sites. Inlining expands these to eight release call instructions: one in `PataIsDevicePresent`, one in `PataPollingTimerDpc`, two in `PataResetChannel`, and four in `PataStartIo`. All 10, 20, 50, 100, and 500 us calls remain. Total direct calls fall from 30 to 22; PATA calls fall from 18 to 10; `PataStartIo` calls fall from seven to three.

## Protocol, IRQ, and emulator proof

The required property is a settle interval after Device/Head or Device Control state changes. Four serialized Alternate Status reads are the ATA bus-level way to consume that interval. They observe status without acknowledging the device interrupt. The candidate sequence is:

```text
out Device/Head
in  Alternate Status
in  Alternate Status
in  Alternate Status
in  Alternate Status
read ordinary Status
```

The old sequence was `out`, a calibrated 1 us CPU loop, then ordinary Status. The candidate keeps the write/status ordering and retains a longer-than-or-equal-to-400 ns protocol interval on ATA hardware. It does not replace the interval with a guessed shorter CPU loop.

In the pinned xemu source, a Device/Head write updates `bus->unit` immediately. `ide_status_read`, used for Alternate Status, returns the selected device's current status without `qemu_irq_lower`. The ordinary Status path returns the same status and then lowers the IRQ. Thus the four reads neither alter selection nor consume the pending interrupt, and the existing ordinary read remains the first IRQ-acknowledging operation. The host model test independently checks `W A A A A S` ordering, identical status, IRQ retained through all alternate reads, and IRQ cleared only by the final ordinary read.

The Xbox release compiler emits exactly four `in al,dx` instructions between Device/Head `out dx,al` and the existing indirect Status read. It emits no helper call, division, or loop. Handwritten assembly would add no value. Non-Xbox builds retain `KeStallExecutionProcessor(1)`.

## Release/native measurement

All runs used the fixed Forza map-stream XISO SHA-256 `d095682b8691b0c43deae66530a7ccd553d8bc828b4fe4537469b86c463b4b6b`, release64 BIOSes, 16 passes, 1,024 reads per pass, queue depth 12, and pressure 900. Every run qualified with 16,384 operations, queue high-water at least 12, zero reported failures, zero warmup oracle failures, and zero oracle records. Lower ticks are faster.

| Run | BIOS | APC batch median | Submit sum | Post-return-to-APC sum | Return-after-APC sum |
|---|---|---:|---:|---:|---:|
| J1 | final baseline | 50,237,586.5 | 42,396,885.5 | 211,156,718.0 | 35,599.5 |
| J2 | final baseline | 49,672,406.5 | 41,898,005.0 | 202,487,651.5 | 36,921.0 |
| B3 | adjacent baseline | 48,165,700.5 | 41,671,853.5 | 174,853,577.0 | 39,376.0 |
| S1 | candidate | 48,383,903.0 | 40,881,199.0 | 208,442,450.0 | 31,094.0 |
| S2 | candidate | 45,960,310.0 | 40,596,173.5 | 165,149,538.0 | 34,319.0 |
| S3 | adjacent candidate | 47,617,717.0 | 41,973,722.5 | 167,854,317.0 | 36,700.0 |

B3 began at `2026-10-16 07:24:59` and S3 at `07:27:09`, on the same Windows runner, making them the drift control pair.

| Comparison | APC batch | Submit sum | Post-return-to-APC | Return-after-APC |
|---|---:|---:|---:|---:|
| Adjacent B3 -> S3 | **-1.138%** | +0.724% | **-4.003%** | **-6.796%** |
| Three-run means, baseline -> candidate | **-4.129%** | **-1.997%** | **-7.995%** | **-8.743%** |

The adjacent end-to-end APC result improves 1.14%. Its submit-only +0.72% movement is smaller than run-to-run drift and is outweighed by the measured completion-side improvements. The three-run means improve in all four metrics. This is sufficient release/native evidence for integration, while the final assembled BIOS should still receive the normal game sweep and physical-Xbox smoke test before release.

## Build and apply-order result

Patch SHA-256: `cf08a257811155bcf4bb08032e64b701b8450785bf53d08da2b5cbbe741eb7c9`.

The patch applies with `--whitespace=error-all` to the exact final assembled source. It touches only:

- `drivers/storage/ide/pciidex/pata.h`
- `drivers/storage/ide/pciidex/chipset/pata_io.c`

Packet 0150 touches `native_packet.c` and its host test; ATA cache-capture 0151 touches `native_capture.inc`, ATAPI `scsi.c`, and its host test. There is no path overlap. A clean release64 build with 0150, then 0151, then 0152 passed all build provenance checks. Its exact disassembly retains three longer `PataStartIo` stall calls and contains four initial Alternate Status reads.

Validation commands:

```text
python3 tests/verify.py
PASS ATA alternate-status delay preserves selection/status/IRQ and ordering
PASS patch applies, exact release shape, xemu IRQ semantics, and 1024-call attribution

integrated release inspection
PataStartIo KeStall direct calls 3
initial alt-status reads 4
PASS integrated 0150/0151/0152 exact release shape
```

## Limits

The release/native performance evidence is from xemu. The hardware argument rests on ATA's observable I/O contract and the exact four-read instruction sequence; a physical Xbox timing trace was not available in this pass. For that reason the patch keeps the generic fallback and confines the alternate-read realization to `SARCH_XBOX`. The candidate changes no public kernel API, timeout, queue-depth rule, status mask, command order, or IRQ acknowledgment point.
