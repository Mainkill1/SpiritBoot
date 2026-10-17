# PR #248 second-pass review resolution

This note records the production fixes made in response to the second-pass
review of PR #248 at `143b38ac41bafb937b269b9aea5c8bd39bd51768`.
The implementation code is committed through
`6bc7bd3c2b07b77b7067b33019503f2741ad975a`. It remains confined to the
independently authored `nxstorage` class replacement, the public lower-driver
publication boundary, and their owned tests. It does not reuse the removed
ClassPnP, Disk, or nxcdrom implementation bodies. This is engineering evidence,
not a legal certification.

## Production corrections

1. HDD cache and durability state now comes from the lower ATA driver's actual
   command lifecycle. The lower driver classifies a completed IDENTIFY result,
   records whether the command used the PIO or DMA controller path, and
   publishes one atomic snapshot only after identity and addressing state are
   coherent. It revokes that snapshot on reset, reclassification, stop, remove,
   and teardown. The class adapter binds to the lower PDO's publication state
   and captures an immutable observation for each request. A disabled cache is
   accepted only when support and inactivity are known. An enabled cache is
   accepted only with matching controller proof and a qualified synchronization
   selector. Terminal epoch validation rejects a request whose observation was
   revoked or replaced while it was in flight. The public
   `StorageDeviceWriteCacheProperty` endpoint and the class write/flush path
   therefore describe the same lower facts. Admission adds no property IRP,
   allocation, wait, worker handoff, or global lock per I/O.
2. Adapter initialization clears the envelope array immediately after its
   allocation. Each child IRP and control MDL is stored only after successful
   construction, so partial pool, child-IRP, and control-MDL failure paths can
   safely scan the zeroed array and free only constructed objects, even when
   successful allocations contain nonzero poison bytes.
3. Direct READ CAPACITY, READ TOC, and CHECK VERIFY requests react to a frozen
   lower queue with one preallocated `SRB_FUNCTION_RELEASE_QUEUE` phase. The
   original control result is retained for the parent. Release preparation or
   completion failure quarantines both adapter admission and the request core.
   Existing multi-chunk work is cancelled/drained, and no later chunk is sent
   after quarantine.
4. Data admission carries cancellation latched under the cancel spin lock into
   the request engine. The core handle is published during prepare, closing the
   interval between cancel-routine installation and transport commit.
   Cancellation before commit submits nothing; cancellation after commit
   cancels and drains the one owned child and completes the parent once. The
   matrix covers READ and WRITE with inline and delayed lower behavior.
5. Optical state distinguishes unknown, absent, and present media. Fixed and
   descriptor sense for no-media and media-change/reset invalidate cached
   capacity. A private epoch prevents an older READ CAPACITY completion from
   overwriting newer media state. The public change count advances only on a
   known state or media-identity transition; repeated identical reports do not
   churn it. Optical geometry reports `RemovableMedia`, while HDD geometry
   reports `FixedMedia`.

The sense parser is local, bounds checked, and limited to the public fixed and
descriptor wire formats. Patch `0140` does not add `sense_header.c` to the
candidate link. Patch `0141` integrates the independently authored lower cache
publication primitive without adding a removed storage-class implementation to
the image.

## Fail-first and integrated checks

The allocation/cancellation fixture exposed the poisoned partial-allocation and
pre-cancel failures on the reviewed body. The direct-control/optical fixture
exposed frozen-queue, quarantine-drain, stale-capacity, change-count, and media
type failures. The lower-publication fixture rejected the old synthetic/public
property-query bridge because it did not prove the actual command or controller
path. These cases were recorded before their respective corrections.

The exact locked patch series now passes:

```text
request engine: 45 groups, 0 failures
pthread request races: 8 scenarios, 0 failures
geometry: 13 groups, 0 failures
cache query: 20 groups, 0 failures
owner/lifetime: 16 groups, 0 failures
lower publication: 34 groups, 0 failures
adapter plain: 26 groups, 0 failures
adapter ASan/UBSan: 26 groups, 0 failures
production wrapper: 2 tests, 0 failures
migration-gate unit suite: 35 tests, 0 failures
full host suite: 505 tests, 0 failures, 26 environment skips
```

The assembled source tree is
`abebfef7a717e0379057b5087b8ff71e75279018`. Patch `0140` has SHA-256
`4d531813949f9f123c0281061063b93967458c6f6ed99d30465409c5e22592da`;
patch `0141` has SHA-256
`cadc6fc0491712900f4fa1ca8e519458fe75f8062a8fac5f317181b9a57677ae`.

## Exact firmware and runtime matrix

All four complete-candidate profiles build from that exact assembled tree. Each
embedded migration preflight passes: `libnxstorage.a` is linked, while
`libclasspnp.a`, `libdisk.a`, `libnxcdrom.a`, their known symbols, and their
owned source references are absent under the bounded gate.

| Profile | Bytes | SHA-256 |
| --- | ---: | --- |
| release64 | 524,288 | `cff12e2cd1b1af1faf0060b676d8ffc37f8256400b12edfe5ad3b2a191943db9` |
| release128 | 262,144 | `b2de51291b6231e25fd6f1fda7db607595c94673f8312a78f02833825863931a` |
| debug64 | 524,288 | `5cf32acc210781f7a8337b94f5deff45b73b381d1b9777329a85d171f67d13bb` |
| debug128 | 524,288 | `ef99a89e607c52d339196aa491927971fa5c6f98c10c73c9666ecae1815a3185` |

The API XISO was rebuilt from that assembled source and has SHA-256
`b7ff416765d1a8aa895d0885b805a5a05a51c19761a116df0bf46b33c5e472a7`.
Using lock-pinned xemu revision `458730bf5373` and the lock-pinned open HDD,
release and debug at both 64 MiB and 128 MiB each complete all 639 planned API
checks as 637 pass, zero fail, two declared floating-point TODOs, and zero
skips. The
[machine-readable qualification receipt](pr248-second-pass-qualification.json)
binds every run to its firmware, XISO, emulator, HDD, kernel, linker map,
storage symbols, source tree, patch identities, and preflight result.

PR #248 remains draft and issue #245 remains open while physical-Xbox coverage,
paired exact-candidate performance, and the independent whole-image provenance
and legal review are still outstanding.
