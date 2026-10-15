# PR #248 direct-control and optical-state review

This record covers the direct-control frozen-queue and optical-media findings
from PR #248 issue comment `6198942417`, reviewed against head
`143b38ac41bafb937b269b9aea5c8bd39bd51768`. The implementation remained
inside the independently authored `nxstorage` sources and public interface
contracts. No ClassPnP, Disk, or nxcdrom implementation body was inspected.

## Fail-first result

The final 22-group adapter fixture was compiled against the unchanged patch
0140 production body. It reported `22 adapter groups, 13 failures`. The
failures were the three missing direct-control release-queue submissions,
missing recovery-failure quarantine, lack of recovery under allocation
exhaustion, verify-driven change-count churn, retained capacity after no-media
and reset sense, failure to refresh new-media capacity, repeated no-media
counting, descriptor-format no-media invalidation, stale in-flight capacity
publication, and optical geometry reported as fixed media.

The focused red command was:

```sh
python3 tests/host/nxstorage/check_adapter.py <output-directory>
```

## Implemented behavior

Each preallocated native envelope now carries one saved control result and a
bounded release-queue phase. READ CAPACITY, READ TOC, and CHECK VERIFY preserve
their original terminal result, submit `SRB_FUNCTION_RELEASE_QUEUE` before
returning the envelope, and require no recovery-time allocation. Failed
release preparation or completion quarantines the adapter, so later data and
control requests fail without reaching the lower device.

Optical state now distinguishes unknown, absent, and present media; capacity
validity is independent from presence. Valid no-media, media-change, and reset
sense observations are decoded by a local bounds-checked parser for the public
fixed and descriptor header formats and revoke cached capacity. Repeated
identical sense reports advance the private invalidation epoch without
repeatedly changing the public count. The public generation advances on media
transitions rather than on every successful verify or capacity call.
An internal epoch captured at control submission rejects a capacity result
that completes after a newer media transition or publication. Geometry uses
the public `RemovableMedia` and `FixedMedia` constants for optical and HDD
devices respectively.

## Focused verification

The updated exact production adapter passed both compiler modes:

```text
adapter-plain: 22 adapter groups, 0 failures
adapter-sanitized: 22 adapter groups, 0 failures
```

The complete assembled owned nxstorage checker also passed its request,
threaded, cache, lower-query, profile, and publication suites before export.
The repository host suite passed 504 tests with 26 declared skips, and the
focused storage migration gate passed all 35 tests.
The patch 0140 hash captured during this isolated review was a pre-integration
identity. The authoritative current hash is the value recorded in
`sources/firmware-lock.json`.
