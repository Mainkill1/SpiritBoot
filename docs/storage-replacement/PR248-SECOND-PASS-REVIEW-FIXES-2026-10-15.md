# PR #248 second-pass review fixes

This note records the production fixes made in response to the second-pass
review of PR #248 at `143b38ac41bafb937b269b9aea5c8bd39bd51768`.
The implementation remains confined to the independently authored `nxstorage`
class replacement and its owned tests. It does not reuse the removed ClassPnP,
Disk, or nxcdrom implementation bodies and is not a legal certification.

## Production corrections

1. HDD cache state is now qualified from the retained lower driver's public
   `IOCTL_STORAGE_QUERY_PROPERTY` result. Initialization and a successful lower
   `IRP_MN_START_DEVICE` can qualify the state; stop, surprise removal, removal,
   and sealing revoke it. Enabled volatile cache is accepted only with a
   qualified synchronization command, disabled cache stays disabled, and
   malformed, failed, unknown, or enabled-without-flush results stay
   unqualified. Write-through and flush admission only reads the cached state:
   it performs no allocation, property query, wait, or worker handoff per I/O.
   Epoch checks reject stale concurrent qualification results, and removal
   drains the preallocated query envelopes before their storage can be freed.
2. Adapter initialization clears the envelope array immediately after its
   allocation. Partial pool, child-IRP, and control-MDL failure paths therefore
   free only constructed objects, including when successful pool allocations
   contain nonzero poison bytes.
3. Direct READ CAPACITY, READ TOC, and CHECK VERIFY requests now react to a
   frozen lower queue with one preallocated `SRB_FUNCTION_RELEASE_QUEUE` phase.
   The original control result is retained for the parent. Recovery failure
   quarantines the adapter, and later work fails deliberately rather than
   continuing against a frozen queue.
4. Data admission carries cancellation already latched under the cancel spin
   lock into the request engine. The core handle is published during prepare,
   closing the race between cancel-routine installation and transport commit.
   Cancellation before commit submits nothing; cancellation after commit drains
   the one owned child and completes the parent once.
5. Optical state now distinguishes unknown, absent, and present media. Fixed
   and descriptor sense for no-media and media-change/reset invalidate cached
   capacity, and a private epoch prevents an older READ CAPACITY result from
   overwriting newer media state. The public change count advances only on a
   known state or media-identity transition. Repeated identical unit-attention
   and no-media reports do not churn it. Optical geometry reports
   `RemovableMedia`; HDD geometry reports `FixedMedia`.

The sense parser is local, bounds checked, and limited to the public fixed and
descriptor wire formats. Patch `0140` does not add `sense_header.c` to the
candidate link, so the existing GPL-2.0-only source-only boundary is unchanged.

## Fail-first and integrated checks

The allocation/cancellation fixture failed two new groups against the reviewed
body. The direct-control/optical fixture failed 13 groups. The production cache
fixture failed because AddDevice performed no lower property query. Those
failures were recorded before their respective corrections.

After source-level integration, the exact patch-series production fixture
reports:

```text
adapter-plain: 24 adapter groups, 0 failures
adapter-sanitized: 24 adapter groups, 0 failures
```

The integrated binaries also passed 50 consecutive plain runs and 10
ASan/UBSan runs. The locked production wrapper passes, and the 35-case storage
migration gate passes. The complete assembled source tree for these fixes is
`5e427e695c7790966191ed8a0a56b10a441c6ab8`.

## Exact firmware matrix

All four complete-candidate profiles build from that exact assembled tree. The
build receipts confirm that `libnxstorage.a` is linked and the legacy
`libclasspnp.a`, `libdisk.a`, and `libnxcdrom.a` archives are absent.

| Profile | Bytes | SHA-256 |
| --- | ---: | --- |
| release64 | 524,288 | `3a273ba1f213bb2523dddfcf4755071403784f1e25affacef4a4a7b48d47f895` |
| release128 | 262,144 | `d35a5bca5cd0d60fdc0764012a9525724bd0481d8589ac837c8ef089c2ca23e0` |
| debug64 | 524,288 | `90d46ef658aa9a355cd53948d4216b6c63c59aa920ce963ae20e4539fbb27798` |
| debug128 | 524,288 | `3d9be11f1b2a2e8290b76a5d9c6368ebcf7a23f3e89954dbfc0bd15623623b4c` |

Runtime qualification uses the API XISO built from the same assembled source,
the lock-pinned xemu revision and the lock-pinned open HDD fixture. Release and
debug at both 64 MiB and 128 MiB each complete all 639 planned API checks as
637 pass, zero fail, two declared floating-point TODOs, and zero skips. The
[machine-readable qualification receipt](pr248-second-pass-qualification.json)
binds each run to its firmware, XISO, emulator, HDD, kernel, linker-map,
storage-symbol, and preflight identities.
