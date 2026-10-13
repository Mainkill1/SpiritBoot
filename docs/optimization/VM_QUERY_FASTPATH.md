> Main integration: this PR is now prepared directly on `main` at
> `e250e9924fc738ffd2502264a6f5559ca534ec43`. Only patch 0110 is added to
> main's firmware lock; none of the earlier unmerged optimization stack is
> included. The original stacked measurements below remain historical evidence.
> Exact new source/artifact identities and validation are recorded in the
> main integration section below.

# Bounded virtual-memory query work

`NtQueryVirtualMemory` used to walk the reservation list twice for free addresses
and inspect each 4 KiB page of an absent page table. It now finds the containing
or next reservation in one walk and skips absent page-table spans, stopping at
the reservation boundary. An address at or beyond the last reservation's end
uses the existing list tail to prove that the remaining address space is free.
This adds no cache, allocation, index, or invalidation rule.

The existing mutex covers every lookup. Initialization, invalid-address/output
checks, output initialization, protection decoding, and mutating callers of
`NxvFindRegion` remain unchanged. A present software `PAGE_NOACCESS` PTE still
reports committed memory. A committed run stops at an absent PDE; a reserved
run skips only to the earlier of its reservation end and the next 4 MiB boundary.
The valid address limit keeps the boundary arithmetic within 32 bits.

This addresses [issue 216](https://github.com/Mainkill1/SpiritBoot/issues/216).
The captured Forza startup pass on Spirit made 16,329 queries, of which 16,326
reported free memory. The Complex prefix contains two passes of 16,334 queries,
with 32,652 free results in total. Most inputs advance by 128 KiB; the final
address, `0x7fff0000`, is invalid. These captures differ in progress and allocation
layout. Their traced elapsed times are not API CPU costs. No queries occur in
the captured late streaming interval, so this change does not explain or fix
that symptom.

## Correctness and work

The maintained host harness extracts the actual query, lookup, and protection
functions from the assembled source and compares them with frozen prior
production functions. It checks complete output bytes, status, guards, mutex
ownership, and work counts across 38,061 cases under ASan and UBSan. Coverage
includes empty/one/16/256-region lists, adjacent regions, free gaps, unaligned
inputs, absent PDEs ending inside reservations, multiple PDE boundaries,
present empty page tables, software noaccess pages, protection/cache flags,
and invalid top addresses with untouched output.

| Input | Earlier work | Final work |
| --- | ---: | ---: |
| Free address beyond 256 reservations | 512 forward node visits | 0 forward visits, 1 tail observation |
| Reserved 12 MiB + 12 KiB with absent tables | 3,075 PDE reads | 5 PDE reads |

The earlier source fails the new forward-walk budget before the implementation
is changed. No output/status comparison is weakened to make the optimization
pass. Host pointer widths differ from Xbox; the native test supplies the target
28-byte ABI check.

The native fixture creates fixed, owned reservations and commits, records all
seven public MBI fields, and protects the output with guard words. The final
989-check version asserts all 145 captured public reference results directly,
including reserved/committed/free segmentation, RO/RW/noaccess, decommit across
a PDE boundary, fragments, and invalid high addresses. It never reads private
kernel metadata or proprietary implementation bytes. NULL output is checked
only in the host harness; the public output parameter is required.

Qualification proceeded reference-first:

- Initial boundary oracle: Complex and original Spirit each passed 831 checks;
  all 145 full MBI/status records matched.
- One-walk/PDE-skip ABBA with reference controls: six boots each passed 844 checks.
- Tail shortcut versus the qualified one-walk build: reference plus ABBA,
  five boots each passed the stronger 989 checks.
- Exact PR233-based packaged 64 MiB ROM: 989/989, normal process exit, and every
  full MBI/status record matched the reference.

The exact package uses source tree
`727b298f573a6ec5e444dae990efbda37c0b6d4e` and ROM SHA-256
`b0d96da18a573a992c6547fc65328481febc0247fa528cd1d122e93de0150a87`.
The runtime query body matches the independently qualified tail candidate.
Product tests pass 129 tests with the three existing skips. The new maintained
host harness passes on the exact packaged source. The local full source suite
stopped at an unchanged 32-bit object-handle harness because this host lacks
32-bit libc headers; that local run is incomplete. The [complete CI matrix](https://github.com/Mainkill1/SpiritBoot/actions/runs/38414713844)
passed the full source suite and all native regressions at implementation commit
`99fbc69774211e9852a42376a5181409dc5f0c80`, including 989/989 query checks in
each debug/release 64/128 MiB job. CI also passed the optional upper-RAM profile
and clean release rebuild checks. The later upload-list follow-up retains the
query guest serial/result files and does not alter source or firmware.

The CI release64 ROM is
`705549aabc37e689ab17cf67a720760d6ed3690091bd2a2a790a45dbfbfc71e8`.
The loader region differs between the Ubuntu CI container and Debian local
host, which use native GCC 13 and 14 respectively for the loader. Its compressed
payload starts 96 bytes later in CI. The entire 46,904-byte compressed stream,
565,248-byte prepared RAM image, and all 91 immutable ROM kernel pages are byte
identical. Both images passed their own native query run. The JSON records both
toolchains, payload hashes, and every immutable span; whole-ROM identity is not
claimed.

## Measured effect

Measurements use public performance-counter batches with no API recorder.
Each value below is a per-boot median in microseconds per query. The first
change and the tail addition were measured in separate ABBA controls; values
from different controls are not presented as one matched experiment.

| Workload | Original, first control | One-walk build, tail control | With tail, same control |
| --- | ---: | ---: | ---: |
| Sparse 12 MiB reservation | 29.687–30.167 | 0.252–0.255 | 0.250–0.259 |
| Free beyond 256 reservations | 4.565–4.718 | 2.751–2.846 | 0.169–0.173 |
| Gaps among 256 reservations | 2.454–2.480 | 1.430–1.540 | 1.177–1.230 |
| Whole-range sweep, 256 reservations | 2.947–2.961 | 1.735–1.847 | 0.205–0.210 |
| Free address, few reservations | 0.248–0.294 | 0.197–0.198 | 0.176–0.178 |
| Whole-range sweep, few reservations | 0.254–0.265 | 0.201–0.203 | 0.180–0.183 |
| Small committed query | 0.334–0.354 | 0.349–0.353 | 0.316–0.317 |

The reference sparse-query median in the tail control is 0.257 microseconds:
this workload reaches parity. The few-region 16,384-query sweep saves roughly
a millisecond across the complete optimization; the isolated tail addition
saves only about 0.3–0.4 ms. The 256-fragment workload deliberately stresses the
algorithm and is not the game's measured reservation layout. No game-level
loading or scenery improvement is claimed.

The clock is approximately 3.375 MHz. Fractional-microsecond batch averages do
not establish individual sub-tick latency. The isolated final change adds 60
`.text` bytes, 24 of them from the tail shortcut, with no change to rounded
section sizes, writable sizes, mapped image size, or resident-page count.

Independent root review found no source blocker in the mutex/list-tail proof,
reservation-bounded skip, noaccess handling, or high-address arithmetic and
independently reran all 38,061 cases on the one-walk built source. The later
tail addition received a separate source review; the packaged host run covers
that final version. The adjacent JSON records artifact and
receipt identities; source tests and public fixtures are maintained in patch
`0110-vm-query-fastpath.patch`. No firmware image or game assets are included.

## Standalone main integration

The merge candidate starts directly from main product commit
`e250e9924fc738ffd2502264a6f5559ca534ec43`. Its firmware lock adds only
`0110-vm-query-fastpath.patch` after main's `0103` patch. The runtime patch bytes
are unchanged from the previously qualified implementation. The quantum,
extent, critical-section, asynchronous-read, immediate-delay, completion,
public-thread and static-IRQ branches are not pulled into this PR.

| Artifact | Identity |
| --- | --- |
| Main-based assembled kernel tree | `6e48b91d281158eaa260666598b718ca4438f535` |
| Local supported-toolchain release64 ROM SHA-256 | `f11b41250d92f81daa5dad7cfffad8e015691ee38a7208f631d4e656d98da70d` |
| Unchanged runtime/test patch SHA-256 | `fd3efb3840e24c5b3b8d02812f869ca2583ebcc24e3f101bd9827708089355d9` |

The supported Docker toolchain builds the standalone release64 image and its
placement checks successfully. The full product suite passes 129 numbered
cases with two existing optional skips. The workflow pins the new assembled
source tree in normal and upper-RAM builds, runs the actual-source differential
on all four profiles, and requires all 989 public query checks on every native
profile. Its ordinary API and remaining native regressions are retained.
The exact-head PR check rollup records the final integration gate; the earlier
CI/tree/ROM records above are explicitly the historical stacked qualification.
No Windows game session is launched for this integration: the user's current
Forza test continues on the previously supplied IRQ candidate.

This PR addresses the query implementation and closes issue #216. It does not
claim a Forza scenery-loading improvement or replace the user's current BIOS.
