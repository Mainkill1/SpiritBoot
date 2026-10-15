# PR #248 control quarantine follow-up

This follow-up was implemented from integration head
`058442d8e1ede5511941f9042f330919a85d655f` within the independently authored
`nxstorage` implementation and its owned host fixture. No removed ClassPnP,
Disk, or nxcdrom implementation body was inspected or reused.

## Fail-first case

The production adapter fixture starts a two-chunk optical read and leaves its
first lower command pending. A concurrent CHECK VERIFY then reports a frozen
queue, and its preallocated RELEASE QUEUE command fails. Against the unchanged
integration production body, retiring the read's first chunk submitted a fourth
lower command for its second chunk:

```text
failed_control_recovery_drains_active_core:375 lower_calls==3
25 adapter groups, 1 failures
```

## Correction

The request core now exposes a bounded `nx_quarantine` operation. It marks the
core quarantined under its existing state lock and runs the existing pump over
the preallocated slot table. In-flight non-recovery commands receive one lower
cancel and retain their envelope until the lower completion drains. Active
commands without lower ownership complete with I/O error. Packet preparation
also rechecks quarantine before committing a new lower submission.

Both direct-control release preparation failure and release completion failure
set adapter admission quarantine and invoke the core operation. The path adds no
allocation, worker, global serialization, retry, or unbounded state.

## Verification

The focused production fixture reports:

```text
adapter-plain: 25 adapter groups, 0 failures
adapter-sanitized: 25 adapter groups, 0 failures
```

The owned `nxstorage` suite also passes all 44 request tests, eight pthread
scenarios, geometry checks, cache checks, and owner checks. Patch `0140` has
SHA-256 `b053febe20a7cafba474f5ae21271dc5f881ad7ca40cf1e31c7e0031ee0056c8`.
