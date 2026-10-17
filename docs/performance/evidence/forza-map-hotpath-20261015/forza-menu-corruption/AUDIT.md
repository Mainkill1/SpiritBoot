# Forza menu corruption audit — final 64 MiB

## Final disposition

Patch 0152 was removed after the prepared `no0152` release64 BIOS restored the complete Forza profile menu and the user confirmed it worked. The audit found a timing-equivalence gap in 0152: four Alternate Status reads meet the ATA bus-delay idiom on physical hardware, but xemu executes `ide_status_read()` synchronously without advancing virtual time. The release therefore changed the prior real 1 us wait to effectively zero elapsed time at optical ATAPI device/control transitions. Status value and IRQ behavior remained correct, but timing did not.

The final `00aa2536...` image is rejected. The corrected product retains 0150 and 0151 and restores `KeStallExecutionProcessor(1)` at the ATA settle boundary. The other prepared arms were not needed because the one-change removal isolated the failure.

## Exact comparison

- Prior tested release64: BIOS `07c52600c710adb5a7ca7748904603a13174e261ce2ce24923dafb0df4b2277a`, source tree `a8f3fc46e27bc8e0f51f23708a02a73237565b2e`.
- Corrupt-report final release64: BIOS `00aa2536dbda14ee851665be98e903c32c9705996832b335bbab72ab81c8ead6`, source tree `d79d23a68f97e58e2f0182062d291884289e2f08`.
- The source delta is exactly 0150, 0151, and 0152. Queue depth, retained SG, completion bridge, and FATX extent patches 0146–0149 are common to both images.

## 0152 — credible timing trigger; immediate revert prudent

`drivers/storage/ide/pciidex/pata.h` changes Xbox `ATA_IO_WAIT` from `KeStallExecutionProcessor(1)` to four reads from `ChanData->Regs.Control`. Register construction proves this is the correct Alternate Status port, 0x3f6 for the primary legacy channel. xemu's regular Status path lowers the IRQ; its Alternate Status path returns the selected device status without lowering the IRQ. The patch therefore gets port selection, status, and IRQ semantics right.

The missing equivalence is elapsed time. xemu updates device selection immediately and its four Alternate Status callbacks do not advance its virtual clock by 100 ns apiece. The old path spends a calibrated microsecond in the guest. The new path can reach the next ATAPI command/status transition with effectively no elapsed delay. The patch changes eight linked 1 us call sites, including `PataStartIo` and `PataChangeInterruptMode` on the optical channel.

The prior 0152 benchmark replay verified FATX HDD reads. It did not perform the game's optical XISO/menu read sequence. Its success does not rule out an ATAPI timing regression or a latent completion race exposed by shorter command transitions.

No safe adjusted optimization is recommended now. Four reads plus the old 1 us stall removes the gain; a sub-microsecond calibrated API is unavailable. Reverting 0152 restores the known behavior with the smallest change.

## 0151 — no data-path mutation found

0151 changes cache-query accounting around `AtaReqCompleteRequest`:

- Direct field zeroing is byte-for-byte equivalent to `nx_lcq_define(OTHER, 0, 0)` followed by storing the temporary writer.
- Early return in `NxAtapiCacheTrack` for commands other than IDENTIFY (`0xec`/`0xa1`) leaves the request writer in the same zero state established by `NxAtapiCacheWriterReset`.
- Ordinary reads have no callback and are not internal, so `NxAtapiCacheCaptureResult(..., false)` skips copying an unused writer/result into request-private `NxCacheResult` storage.
- The skipped operation is a pure structure copy. It has no atomic operation, barrier, SG-list access, transfer-count update, IRP mutation, queue mutation, DMA operation, or callback.

0151 is therefore a low-probability direct corruption source. It can remain in the first no-0152 isolation arm. An `only0151` BIOS is available if the first binary split does not isolate the issue.

## 0150 — highest direct data-path blast radius, but no specific defect proved

0150 changes packet preparation used by game reads: SRB/stack clearing, CDB copying, and page-count validation. Exact release disassembly and source review found:

- `rep stosl` clears exactly 64 bytes for the SRB and exactly 36 bytes for the I/O stack location. The previous aligned `clear_bytes` path used the same `rep stosl`; the patch removes the already-proved alignment branch.
- CDB copies touch exact admitted extents: 6, 10, 12, or 16 bytes, with no over-read or over-write. READ(10) copies bytes 0–9; optical READ(12) copies bytes 0–11.
- The 32-bit page formulas are algebraically equivalent to the old widened formulas after the preceding nonzero, containment, and overflow checks.
- Release-queue CDB length zero performs no source access.

No concrete 0150 corruption bug is established. It remains the second-ranked candidate because it is the only new change that writes every game-read SRB/CDB/stack and validates every data range. If no-0152 still corrupts, remove 0150 next rather than modifying several queue paths.

## Queue/completion audit

Patches 0146–0149 are identical in the prior and final BIOS. The class layer admits concurrent requests, while the PATA port stays at queue depth one. The retained SG workspace is allocated only when PATA `QueueDepth == 1`, so only the serialized active command uses it. The completion bridge releases the current command and starts the successor under the existing queue/interrupt ordering.

This makes those patches unlikely to independently explain a regression that appears only in the final image. A faster 0152 transition could expose a latent race in that machinery, so a clean no-0152 result would identify 0152 as the trigger without claiming the lower queue design is universally race-free.

## Prepared release64 isolation arms

| Arm | Included new patches | BIOS SHA-256 | Source tree |
|---|---|---|---|
| `no0152` | 0150 + 0151 | `412bb8a53312777709f0a855e7d1e36d590f5ed0caf770fee39051e61bd13991` | `7419a93367e90411f87ff7113c797fef2955c16e` |
| `no0150` | 0151 + 0152 | `708961edf8c14518c93e73ef85ae0bb7359d674dc48e35ef409c6d56121bee28` | `71c5fe068bba391aea43ba789d8718a4e2a9366f` |
| `only0150` | 0150 | `c0eaf3a73f75c7a57865a62a3df47cbece1d1c5a3d43b19ed1fd2d0bef08e4ec` | `63ce2832cea9bf6fe9fd7b93bc42a7c4d5a59674` |
| `only0151` | 0151 | `10613e4f583ccbebf25c8091dc5b0f69d06c098bf616baeb55a49f2e11b15576` | `f20fc4b2da9067416c2787b5c69ad655daeb277a` |

Paths are `/home/codex/xemu-shader-workbench-handoff/.scratch/forza-corruption-isolation/<arm>/build-release64/flash.bin`.

Test order:

1. Reproduce on final `00aa2536...` only if its identity was not already confirmed.
2. Test `no0152` at the same Forza menu transition.
3. If clean, discard 0152 and repeat the menu transition plus a normal race load.
4. If still corrupt, test `no0150` and `only0150`. Exactly one corrupt arm isolates the group; both clean implies an interaction; both corrupt points back to the common 0146–0149 stack or test state.
5. Use `only0151` only if 0151 must be separated from 0152 after the group split.

All isolation builds were produced in scratch. The shared product tree was not edited.
