# Public kernel export contracts

Owned native XBE for 20 callable exports that initially lacked direct test-source evidence in the kernel inventory. It now contains 119 assertions:

| Family | Checks | Contract |
| --- | ---: | --- |
| Timers |22| `KeInitializeTimerEx`, `KeSetTimer`, `KeSetTimerEx`, `KeCancelTimer`: notification/synchronization initial state, pending replacement/cancel, rearm clears the previous signal, finite expiry, notification persistence and synchronization auto-reset |
| SLIST |16| `InterlockedPushEntrySList`, `InterlockedPopEntrySList`, `InterlockedFlushSList`: empty results, returned previous head, LIFO order, detached-chain links, reuse, header fences and node payload canaries |
| Semaphore |30| `NtReleaseSemaphore`: previous count, exact increments, overflow status with unchanged count, zero/negative release errors, `LONG_MAX` release from a nonzero count, failed-release output/count preservation, optional previous-count output, one-unit consumption, empty timeout and handle close |
| DPC and IRQL |12| `KeIsExecutingDpc`, `KfRaiseIrql`, `KeRaiseIrqlToSynchLevel`: callback-local DPC state, exact callback context, dispatch-level execution, balanced raise/lower and Xbox synchronization level 28 with restoration |
| Interrupt synchronization |6| `KeSynchronizeExecution`: exact context, one callback per call, synchronization IRQL, returned callback boolean and caller-IRQL restoration |
| Invalid dispatch |7| `IoInvalidDeviceRequest`: a real queued IRP, returned invalid-device status, exactly one retained completion callback, exact IRP/context, final IRP status and owned cleanup |
| Object directory |7| `NtOpenDirectoryObject`: create a private parent/child namespace, open the child by relative name, obtain a distinct handle and close every handle |
| Filesystem |7| `NtQueryFullAttributesFile`, `NtFsControlFile`: query the running DVD image, reject an unknown read-only DVD filesystem control synchronously and clean up the handle |
| Floating point and context |10| `KeSaveFloatingPointState`, `KeRestoreFloatingPointState`, `RtlCaptureContext`: x87 control-word round trip and frame-preserving captured control/segment context |
| PCI |2| `HalReadWritePCISpace`: read-only bus-0/slot-0 identity with Xbox NVIDIA vendor and a present device ID |

Use the public CC0 nxdk xboxkrnl declarations. The independently authored test reads no private KTIMER fields or SLIST header offsets. It zero-initializes the complete public SLIST object and aligns its storage16 bytes; only returned known node pointers/links are compared. It does not infer concurrent SLIST correctness from sequential ordering. Timer objects/nodes remain static through process shutdown. All three timer-expiry waits have finite two-second bounds; initial/cancel/poll checks use zero timeout. No timer DPC or callback retains stack storage. Both timers are cancelled before leaving the timer phase, including after failed assertions. The owned semaphore is drained and closed. Create failure ends a failed/incomplete cohort instead of continuing with an invalid handle.

This is a correctness fixture, not a performance benchmark. UART drain/shutdown use the existing owned TAP helper and the external runner deadline remains required if the guest stalls. The new filesystem checks read the boot DVD only and the PCI check performs no configuration write. No filesystem payload/save is written. An isolated HDD/EEPROM is still required for ordinary BIOS boot ownership.

The DPC and interrupt objects are static. Every raised IRQL is restored on the same path, the DPC records into static storage without using TAP at dispatch level, and the caller waits with a finite two-second bound. The interrupt object is initialized but never connected to hardware. The floating-point test restores through the public API and has a direct control-word cleanup fallback. The context test uses the same public frame-preserving assembly-call shape as the pinned API regression; the coverage inventory records it as a manual contract because its conservative C lexer deliberately ignores assembly strings.

The boundary releases start from queried count3 with limit3. Counts0 and-1 must return `STATUS_INVALID_PARAMETER`; `LONG_MAX` must return `STATUS_SEMAPHORE_LIMIT_EXCEEDED`. Each case checks its distinct previous-count sentinel and queries the unchanged current/maximum count. A compile-time check binds `LONG_MAX` to the native32-bit value2147483647. These are explicit fixture expectations for the next independent-reference comparison; retain any disagreement rather than changing an oracle after collection.

Build locally:

```sh
PATH=/absolute/path/to/nxdk/bin:$PATH NXDK_DIR=/absolute/path/to/nxdk make
```

Output: `bin/default.xbe` and `kernel-export-contracts.iso`. The local build uses `-O2 -Wall -Wextra -Werror`. A clean container build confirms the intended fastcall and stdcall imports resolve. That is link/build evidence, not proof the exports executed or satisfied their contracts.

Registered in `sources/native-regressions.json` as 119 checks. CI builds this product-owned directory separately from the assembled reference checkout, then uses the catalogue's 119-check count in the existing per-profile native loop and exact TAP plan/ok/failure/TODO/skip gates. It does not inject a test directory into the firmware build tree or alter driver code.

The earlier 59-check version has separate retained native evidence: Complex and the semaphore-fix release64 candidate completed 59/59; published c630 stopped after check 47 at the overflowing release. The later frozen 68-check version passed on Complex and the fixed SpiritBoot candidate. A superseded 119-check artifact exposed the public-contract differences documented in `docs/storage-replacement/KERNEL-PUBLIC-CONTRACT-FIXES.md`; a superseded 120-check artifact then showed that Complex preserves `IoStatus.Information` while completing an invalid request. Those observations remain bound to their exact artifacts and do not qualify this corrected 119-check version.

The final managed native pair used this identical fixture and emulator configuration on each BIOS. SpiritBoot and Complex both completed 119/119 with zero failures/TODO/skips, terminal `== kernel-export-contracts end PASS ==`, byte-identical serial output, successful guest shutdown and retained exact input/output/cleanup evidence. The portable [receipt](../../../docs/provenance/evidence/pr248-kernel-public-contracts/final119-pair-receipt.json) has SHA-256 `89081d9b5c67898d7c3375d004eca3de1c416ea528fa86446673b3f226f73fcb`. Broader kernel error/race/hardware coverage, full replacement integration and before/after extraction performance remain separate gates.

Source provenance: main.c and the Makefile are newly authored GPL-2.0-only public-API test code. TAP source/header and the regression helper are copied from the repository-owned timer-apc-mode fixture under their existing GPL-compatible terms; the helper adds only a fixture-specific terminal PASS/FAIL marker. [LICENSES.json](LICENSES.json) records the exact per-file grants and copied-source paths. Public declarations are consumed from the installed nxdk dependency and not recopied as implementation source.
