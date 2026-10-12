# Title interrupt object and callback identity

A direct public-ABI test demonstrates that SpiritBoot v0.99.3 initializes and dispatches a title interrupt differently from the reference BIOS. In a matched Windows xemu comparison, the same independently authored 17-check XBE passes every check on the reference BIOS and fails nine on SpiritBoot. This is a confirmed interrupt wrapper defect. Whether it accounts for the Halo boot failures requires a separate candidate game test.

## Measured differences

| Observation | Reference BIOS | SpiritBoot v0.99.3 |
|---|---|---|
| Public object size | 112 bytes | 112-byte title buffer protected by a native shadow |
| IRQ3 public vector | 51 | 51 |
| IRQ3 returned IRQL | 23 | 24 |
| Initialization routine, context, IRQ level, IRQL, mode/sharing | Caller values; IRQ level3 | Unchanged A5-filled bytes |
| Connected after initialization/connect/disconnect | 0 / 1 / 0 | A5 / A5 / A5 |
| First ISR argument | Original title object `000228c0` | Internal NT shadow `84065a38` |
| Second ISR argument | Caller context `00022000` | Same caller context |
| Initialization ServiceCount | Preserves `A5A5A5A5` | Preserves `A5A5A5A5` |
| Neighboring guards / real bounded vblank delivery | Pass | Pass |

The IRQL difference is recorded separately. This fix does not change the native HAL priority mapping. The probe does not inspect the reference object’s dispatch instructions. It checks documented fields, guards, public return values, and the arguments received by its own handler.

## Why the wrapper differs

SpiritBoot already allocates a private native KINTERRUPT to avoid writing NT’s 484-byte object into the title’s 112-byte buffer. The old initializer used the public buffer only as a lookup key and passed the title’s ISR directly to native KeInitializeInterrupt. Native normal and chained dispatch pass their native interrupt object to ServiceRoutine. Therefore the title receives the wrong object identity and layout, and its public fields never reflect initialization or lifecycle state.

The independent repair defines the public layout explicitly, initializes its observed header fields, and installs a native broker. That broker calls the title’s current public ServiceRoutine with the original public object and its public ServiceContext. It mirrors native Connected before entering title code, covering an IRQ arriving during native Connect; the exported lifecycle wrappers also mirror state on return. ServiceCount, padding, and the opaque public dispatch tail retain their contents. Compile-time assertions cover the public size/offsets and native shadow capacity.

The driver-owned IDE interrupt remains bound to its actual hardware object. The title cannot replace or disconnect that borrowed owner, and detached ownership remains a tombstone. This change does not introduce shadow-slot recycling or define live connected reinitialization behavior.

## Reproduction and evidence

The matched native controls use xemu `gdcc536830deb.exe`, source commit `dcc536830deba245eec36cd009db5860ca04884c`, with a 64 MiB machine and the published 64 MiB BIOS. Every arm gets a separate HDD overlay and EEPROM copy from the same seed. There is no debugger attached. The probe saves and restores PMC/PCRTC interrupt enables, connects IRQ3, enables real vblank, waits at most two seconds, records handler arguments, disconnects, prints complete TAP, and requests power-off.

The frozen17-check payload has ISO SHA256 `102a01ecad92e9b85cd590c3415e1403f3fafce47b7387fe705209ca639e9c9e` and XBE SHA256 `ba7364adbc4e006fd792178efc51142345287b691c9c45a2f9f3ca4f1242f548`. The released BIOS is SHA256 `3dc3010a237fcf50bef2ecbe59c81115eabf9684e7a3ceb9caec19a16cb49611`. The initial16-check probe is retained separately; it used a loose nonzero Connected assertion that the17-check version strengthens to exact TRUE.

The baseline game comparison cold-boots Halo1 and Halo2 for45 seconds each on99.2,99.3,the reference BIOS,and the unrelated handle-lookup candidate. Both releases and the handle candidate remain black; the reference reaches the Halo1 menu and Halo2 title prompt. Consequently these observations do not establish a99.3-only regression. Local screenshots are retained and hashed; no proprietary firmware or game assets are included in the public evidence.

A bounded debugger run captures Halo2’s released-BIOS exception at SpiritBoot’s own bugcheck boundary: code `1E`, status `C0000005`, title PC `0033589E`. The later broad public-API trace changes timing and ends in a double fault instead. It is corroborating ABI evidence, not a faithful replay of the uninstrumented fault or performance evidence. Proprietary title/reference instruction bytes were not read.

The corrected candidate passes17/17 on the same frozen XBE. Both Halo titles remain black in four matched candidate/control cold boots; minimal candidate crash capture matches the released Halo2 bugcheck code, status, and title PC. Therefore this API repair does **not** resolve the observed Halo boot failures. The memory/output investigation continues separately.

The i386 actual-body fixture runs native initialization, normal/chained dispatch, synchronization, and lifecycle through the production Xbox wrapper. Identical test sources fail68 of310 assertions on the release, pass310/310 on the candidate, and fail exactly two injected first-delivery checks when only the broker Connected mirror is removed. Admission passes247/247 and protected IDE ownership24/24. Hardware and trap exits are explicit test shims.

Final kernel commit `b6342bebeb1d6a54e4e2b9affaa08c8a430991ce`, tree `80adbcb0b86010f31280e42d27a6689efdfc46b3`, is reconstructed by patch101 SHA256 `677a320b91aaf28642c9c643f54c628a3500975ee898a8745c97b2919909b166`. Production source matches the phase1 native ROM exactly; a clean final64MiB build produces the same firmware SHA256 `e4f5e2563b90e723d85d304cbf49c1cd6c0ea6761c073bec1e2f961626bea85a`. All release/checked64/128MiB and upper-reserve profiles build; all76 release64 host/source gates pass. Multi-profile native CI remains pending.

Two initially mislabeled candidate attempts are excluded: their launch substitution used `flash_path` rather than xemu’s `flashrom_path`, retaining the released BIOS. Those artifacts remain local. Corrected runs validate the actual configured firmware path, firmware hash, and uploaded configuration hashes. An early recorder also selected ESI instead of EBP from the x86 RSP register order; corrected diagnostic records use EBP index5. No discarded run is used as evidence of candidate behavior.

[Raw public evidence and manifest](evidence/title-interrupt-public-abi-20261012/manifest.json) preserve the frozen payload, controls, candidate17-check TAP, actual-body red/green/mutation receipts, profile identities, and matched game results.

## Public sources

The public layout and Xbox seven-argument initializer are declared in [nxdk’s public kernel header](https://github.com/XboxDev/nxdk/blob/29638d0b001f179b73c3513489af10ddc2986216/lib/xboxkrnl/xboxkrnl.h). The independent broker addresses the native dispatch behavior in SpiritBoot’s own pinned open source. No reference implementation source expression was used.
