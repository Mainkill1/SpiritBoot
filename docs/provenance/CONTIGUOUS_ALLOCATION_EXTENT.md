# Contiguous allocation extent

Forza's public `MmQueryAllocationSize` calls expose a contract mismatch:
Complex reports the occupied page extent, while SpiritBoot reports the original
request. For example, requests of 4, 4,192, and 16,416 bytes produce reference
sizes of 4,096, 8,192, and 20,480 bytes. The game observations come from the same
public caller, `0x3f5317`.

SpiritBoot already allocates complete pages. Its contiguous allocation table
stored the smaller requested byte count, which also caused persistence range
validation to reject the full allocation. Patch 0093 records the existing
rounded extent in that table. It adds no pages and preserves placement,
allocation, release, locking, and table growth. The disabled legacy allocator's
fallback reports the usable extent after alignment, excluding alignment slack.

The evidence is public API inputs/results, independent owned test buffers, and
public nxdk declarations. No proprietary implementation source or instruction
bytes were inspected. Raw game captures and ROMs remain outside the repository.

## Verification

All native runs use 64 MiB firmware and guests on Windows xemu source
`dcc536830deba245eec36cd009db5860ca04884c`, with separate HDD overlays. Firmware
builds use the same local GCC 13 win32 toolchain.

| Check | Complex | SpiritBoot baseline | Scheduler candidate | Extent candidate |
| --- | ---: | ---: | ---: | ---: |
| Allocation extent, 14 sizes and 3 allocation methods | 126/126 | 60/126 | 60/126 | 126/126 |
| Public ABI and five title-scale allocations | 16/16 | 16/16 | 16/16 | 16/16 |
| Zero-initialized IOSB and asynchronous I/O | 338/338 | 338/338 | 338/338 | 338/338 |
| Warm persistence: setup / restored state | 3/3, 4/4 | 2/3, 0/1 | 2/3, 0/1 | 3/3, 4/4 |

The allocation regression has 33 incorrect query results on each older
SpiritBoot build. Another 33 dependent extent-access checks are guarded out
and recorded as failures. All allocation requests succeed.

The warm reboot probe requests 4,192 bytes, fills and persists the occupied
8,192 bytes, then reloads itself through public launch data. Complex and the
extent candidate retain every byte, reject a competing allocation of the same
pages, and permit exact-range reallocation after unpersist/free. The older
builds reject the persistence range and report restored size zero.

The final diagnostic qualification runs have zero recorder errors/read errors.
Each asynchronous I/O fixture attributes all 32 exercised callbacks. The first
expanded-recorder run mishandled nonreturning thread termination; it is excluded.
After that diagnostic correction, the complete suite was repeated.

The host suite passes 129 tests with three skips: the root ownership fixture
and two plugin tests requiring an explicit QEMU header path. The 64 MiB firmware
build passes its INIT-reference and boot-menu placement checks. The assembled
source tree is `2e8979e1252ecff25db1bbd4f0d30fd2ec7733d5`.

Extent candidate ROM SHA-256:
`03a4124838a215c7dc8bfe0a69221791308abcfa1c6de11bbd7748907b4cf90d`.

[Receipt hashes and run identities](contiguous-allocation-extent-2026-10-13.json)
include the allocation, ABI, I/O, and warm reboot runs. The exact independent
warm-persistence source is retained in
[`evidence/contiguous-allocation-extent-20261013`](evidence/contiguous-allocation-extent-20261013/).
CI runs the 126-check `contig-extent` regression; the separate two-stage warm
probe is currently a manual native qualification.

Independent review verified patch application, exact source trees, ROM and
receipt hashes, game API arguments/results, and warm persistence. Its missing
CI registration finding was resolved by adding the guest to
`sources/native-regressions.json`.

## Forza and scope limits

The user tested `extent-candidate64.bin` and reported no improvement in Forza.
This is an API correctness fix, not a demonstrated fix for delayed scenery.
The scheduler-only candidate also failed that gameplay acceptance.

In the small allocation fixture, Complex starts and ends with 16,219 available
pages, versus 16,164 on SpiritBoot: a difference of 55 pages, or 220 KiB. Both
satisfy all five title-scale requests and return their pages after freeing.
This does not establish Forza's complete memory budget or rule out pressure.

Physical hardware, 128 MiB, and the disabled legacy allocator are not covered
by the native receipts. The branch is based on scheduler commit `62a1f6d4`;
the extent patch remains separately reviewable.

CI follow-up: the extracted allocator retry fixture still supplied the old
five-argument helper declaration and expected a 5,000-byte query result. The
production helper has four arguments and reports the occupied 8,192-byte extent.
The fixture now matches that contract while preserving all seven interleaved
allocation, reclaim, relocation, and ownership assertions. This test-only update
rebuilds to the identical qualified 64 MiB ROM hash.
