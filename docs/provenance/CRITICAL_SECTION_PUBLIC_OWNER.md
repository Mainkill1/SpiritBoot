# Critical-section public owner identity

`RtlEnterCriticalSection` and successful `RtlTryEnterCriticalSection` must publish
an owner consistent with the title's current-thread identity. In the public ABI
probe, Complex stores the same pointer returned by `KeGetCurrentThread` and read
from `fs:[0x28]`. SpiritBoot instead stored its internal NT `KTHREAD` address,
while both public observations returned that thread's Xbox-shaped shadow.

For example, the old SpiritBoot probe returned `0xc103b9d4` from the public API
and `fs:[0x28]`, but stored `0xc103b820` in `OwningThread`. The corrected build
stores `0xc103b9d4` consistently. Absolute addresses are illustrative only.

Patch 0094 changes both acquisition paths to use the existing
`XeKeGetCurrentThread` adapter. The shadow lives inside the native thread and has
a stable address for its lifetime. No allocation, additional memory, or new
mapping is needed. Recursive acquisition compares the same public identity that
is published. Count updates, event handoff, wake signaling, and critical-region
entry/exit behavior are unchanged.

The earlier tests explicitly allowed the mismatch, and the contention fixture
expected native addresses. Those expectations are corrected. The host test now
uses deliberately different native and public identities and checks fresh
Enter/Try acquisition, recursion, and ownership after a contended handoff. The
native fixture continues to use owned native scheduler fields to control its
test threads, while all critical-section owner checks use the public identity.
The API regression retains its existing retail recursive-AndRegion limitation;
this patch does not change that separate behavior.

## Evidence and verification

Research used public ABI calls and structures, an independently authored XBE,
and owned SpiritBoot code. No proprietary implementation instructions were read.

Native runs use 64 MiB firmware and guest memory on the original Windows xemu
`dcc536830deba245eec36cd009db5860ca04884c`, executable SHA256
`cd4cfd696aa9c196cf44fd35765e16cf662afc16a689e1af4584fa79398784db`.
Each run has a separate HDD overlay and EEPROM copy. No debugger or API recorder
was attached.

| Check | Complex | Extent baseline | Public-owner candidate |
| --- | ---: | ---: | ---: |
| Public identities and bounded synchronization probe | 36/36 | 35/36 | 36/36 |
| Live contention, recursive ownership, retained wake, APC regions | — | — | 188/188 |

The baseline's only public-probe failure is owner identity. The extracted
production host test fails its new identity assertion before the implementation
change and passes afterward under address/undefined-behavior sanitizers.
The product host suite passes 129 tests with 3 existing skips.

The 64 MiB candidate ROM SHA256 is
`c0219ec36dd3d9f2c6d59657254d13c96ee7e327c2b40e051775fb4cb74523dd`.
The native contention fixture is tied to the tested build's generated kernel
layout; its scheduler-field observations are not claimed as a cross-BIOS ABI.

## Forza scope

Forza calls these public synchronization functions heavily in the recorded
workload, but the traces do not prove that it relies on the owner field in the
failing scenery path. This is a confirmed compatibility correction, not proof
that delayed scenery loading is fixed. No new Forza performance improvement or
physical Xbox qualification is claimed. The failed `extent-candidate64.bin`
manual test remains an explicit negative result.

The inherited allocation retry fixture was repaired in PR #229 and merged here.
The rebuilt 64 MiB ROM is byte-identical; assembled tree is `fd3ed364fead7b309dae41583c1cb0a969fbb3d0`.
