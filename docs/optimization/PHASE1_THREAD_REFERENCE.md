# Release the completed Xbox initialization thread

On Xbox builds with `NXK_MM_PHYS`, Phase1 terminates after starting the title.
`PspInitPhase0` nevertheless takes another thread reference into the unused
local `SysThread`. Closing the creation handle and reaping the thread therefore
leave its object and CID retained. Patch 0112 omits this unused reference and
local declaration only when both `SARCH_XBOX` and `NXK_MM_PHYS` are defined.
The creation call, failure path, handle closure, and other configurations retain
their existing behavior.

The exact release-64 candidate completed 7,839 functional assertions, as did
its baseline: 15,678 total, with six stable pool snapshots per boot. The only
tag difference was one fewer 1,024-byte `Thre` allocation. This recovers **1 KiB
of reusable pool capacity**. Available, pool, stack, and cache page counts were
unchanged. There is no resident-page saving, timing result, or Forza speed claim.

## Ownership and boot ordering

The unchanged implementation establishes the reference ledger:

1. `ObCreateObject` begins with one object reference. `PspCreateThread` adds two
   keep-alive references before making the thread runnable.
2. `ObInsertObject` adds the handle reference and consumes the insertion
   reference. The creator then drops its temporary reference. Successful
   creation leaves one handle reference and one execution/reaper reference.
3. Closing the creation handle leaves execution ownership. If execution and
   reaping finish earlier, the handle still protects the object until closure.
4. `PspReapRoutine` frees the stack, clears `InitialStack`, then drops execution
   ownership. Final `PspDeleteThread` removes the CID and process-list entry and
   releases the owning process. Legitimate independent references still defer
   final deletion normally.

Creation and exit callbacks precede final reaping. The change does not retain
a raw thread pointer or add a dereference. The initial boot thread remains at
`HIGH_PRIORITY` throughout `ExpInitializeExecutive`/`PspInitPhase0` and lowers
its priority afterward. Resident `Phase1Initialization` returns from the
discardable initialization routine before retiring INIT and terminating.
Removing the unused object reference therefore introduces no INIT lifetime or
callback-order change.

The complete ownership path is in `ntoskrnl/ps/{psmgr,thread,kill}.c`,
`ntoskrnl/ob/{oblife,obhandle}.c`, `ntoskrnl/ke/{thrdobj.c,i386/kiinit.c}`, and
`ntoskrnl/ex/init.c`. Independent review checked this full path and confirmed
the seven supporting runtime files were byte-identical to the baseline.
The [review receipt](phase1-thread-reference-2026-10-13/independent-review.txt)
distinguishes source proof from modeled host services; its
[hashes and source locations](phase1-thread-reference-2026-10-13/independent-review.json)
pin that review. A separate root review found no blocker in the conditional,
creation failure path, handle closure, or reference ownership.

## Maintained checks

`tests/host/phase1-thread/check.py` extracts the actual boot creation tail and
actual `PspReapRoutine` from the assembled kernel source. Its object-manager and
scheduler boundary substitutes explicitly track handle and execution ownership,
stack release, and final allocation deletion. Full native creation and the
delete callback are not executed by this host fixture; source review and native
qualification supply separate evidence for those paths.

With ASan and UBSan, the candidate passes 1,968 assertions across 52 cases:
normal completion, completion before creation returns or during handle closure,
zero through three independent references, and creation failure. All four
Xbox/desktop and NXK/non-NXK macro combinations are exercised. The baseline
fails the final-deletion assertion only for Xbox+NXK; the other three
configurations retain their original behavior. The
[exact-source results](phase1-thread-reference-2026-10-13/host-lifecycle.json)
were independently reproduced. The full 32-bit `psmgr.c` translation unit and
the complete release-64 firmware also compiled successfully. Product tests
passed 129 numbered cases with three existing skips before and after packaging.

The firmware workflow pins the assembled source tree below and runs this host
check in all debug/release and 64/128 MiB jobs, alongside its existing source
checks and native guests. These include the packaged broad API fixture, whose
639 numbered checks include six established expected TODO mismatches (EOF
beyond space, read-only-volume flush, two floating-point emulator cases, and
two process/thread-list cases). Those TODOs are not actual passes. Final CI
results are recorded separately after the full matrix completes.

## Exact artifacts and native measurement

| Artifact | Identity |
| --- | --- |
| Product baseline | PR236, `b7b4651925356e885cc0b67b853e892fd38889c7` |
| Baseline source tree | `97b9fa45c2f6f4a2a8607ad5b0ed0cfc32b8c6aa` |
| Baseline release-64 ROM SHA-256 | `7451c5c3200f03eb544621b314ea582a96345a70e325a361fe08123385669b17` |
| Runtime-only patch SHA-256 | `45835106056c0289e934bd5482da9815984292884e3e15d6495e7161a9ab8db4` |
| Packaged 0112 patch SHA-256 | `c63d71de02086f4253be4f014ecee72730424d225931e3463fbeff26074806b4` |
| Candidate source tree | `83b47b2b73061eb31314b9f58b0fe01c8f510249` |
| Candidate release-64 ROM SHA-256 | `b28ae5fad49ba288c595732226d1dbaf1d3810ee734e36afa34d875bd3629aaa` |
| Shared native fixture ISO SHA-256 | `3edefbe58a9a992d3190eacf37e6521534141c287724899389bbcc7b923ebe38` |

Renaming the packaged patch from its temporary filename to 0112 changes neither
the patch bytes nor assembled source. The same fixture ISO ran on both exact
ROMs in isolated VMs using the owned original emulator, with recording disabled
and the same 2 MiB/s disk-read throttle. The source maps were identical. Census
reads were confined to owned allocation headers and allocator metadata, not
object payloads. The fixture also checked read/APC and pending-I/O lifetimes.
It logs inherited public thread ID/exit differences without asserting full
public thread ABI equivalence; PR230's stronger owner fixture was not used.

| Stable measurement | Baseline | Candidate |
| --- | ---: | ---: |
| `Thre` blocks / rounded bytes | 8 / 8,192 | 7 / 7,168 |
| Live bucket capacity, bytes | 121,888 | 120,864 |
| Free bucket capacity, bytes | 21,472 | 22,496 |
| Available pages | 15,633 | 15,633 |
| Public pool pages | 47 | 47 |
| Bucket / whole-pool pages | 35 / 12 | 35 / 12 |
| Empty bucket pages | 2 | 2 |
| Stack / cache pages | 37 / 16 | 37 / 16 |

Every other pool tag's count and rounded capacity was identical. These were
six quiescent phases per side in a synthetic lifetime fixture, not a Forza RAM
snapshot or a performance trial. The
[native receipt](phase1-thread-reference-2026-10-13/native-pool-census.json)
contains hashes, launches, complete census values, and comparison scope.
