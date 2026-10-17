# Native adapter allocation and cancellation review hardening

This note records the scoped PR #248 follow-up performed from SpiritBoot commit
`143b38ac41bafb937b269b9aea5c8bd39bd51768`. The review used only the locked,
independently authored `nxstorage` patches and their owned tests. No legacy
ClassPnP, Disk, or nxcdrom implementation body was inspected or used.

## Fail-first evidence

The owned adapter harness was reconstructed from locked patches `0127`, `0129`
through `0135`, and `0138` through `0140`. Two production-function groups were
then added while the `0140` production source remained unchanged.

`initialization_cleans_only_constructed_envelopes` calls
`NxNativeAdapterInitialize` with pool allocations filled with `0xa5`. It fails
each of the two pool calls and, for four slots, fails every child-IRP allocation
and every control-MDL allocation. It verifies exact frees, no remaining owned
allocations, and no attempt to free an unconstructed pointer.

`cancellation_respects_transport_commit` calls the real read dispatch and
adapter submission paths. It covers an IRP whose cancel bit is already set,
cancellation injected from packet preparation before the request core's locked
transport commit, and cancellation injected from the lower call after commit.
The first two cases require zero lower submissions; the committed case requires
one lower submission, one lower cancellation, and terminal cancellation.

Against the unchanged `0140` production source, the plain harness reported:

```text
initialization_cleans_only_constructed_envelopes:140 !invalid_irps&&!invalid_mdls
cancellation_respects_transport_commit:182 NxNativeDispatchReadWrite(d,&already.irp)==STATUS_CANCELLED
10 adapter groups, 2 failures
```

The first failure showed that cleanup read poisoned envelope members when the
slot-array pool allocation failed but the envelope allocation succeeded. The
second showed that an already-cancelled data IRP entered the request core as a
live request and reached lower transport before cancellation was replayed.

## Minimal correction and result

`NxNativeAdapterInitialize` now clears envelope storage immediately after that
allocation succeeds, before either pool result can enter common unwind.

Data submission now copies a cancellation already latched by the cancel-spin
lock handshake into the request passed to `nx_start`. During preparation, the
adapter publishes the core slot/generation handle under its lock. This closes
both sides of the pre-commit race: cancellation seen first is replayed through
the newly published handle, while cancellation seen after publication can call
the core directly. The request core remains the owner of the commit decision.
Cancellation after commit still drains the one committed child request.

Focused verification:

```text
$ python3 tests/host/nxstorage/check_adapter.py adapter-green-output
adapter-plain: 10 adapter groups, 0 failures
adapter-sanitized: 10 adapter groups, 0 failures

$ python3 -m unittest tests.host.test_nxstorage_production -v
test_locked_independent_production_sources_pass_owned_checks ... ok
Ran 1 test in 6.928s
OK

$ python3 -m unittest discover -s tests/host -v
Ran 504 tests in 449.474s
OK (skipped=26)
```

## Integrated coverage follow-up

At integrated head `058442d8e1ede5511941f9042f330919a85d655f`, the exact
production harness expanded the already-cancelled data request case into an
explicit read/write and inline/delayed matrix. Each of the four cases requires
zero lower submissions, one cancelled parent completion, and zero completed
bytes. Both plain and sanitized adapter modes passed all 24 groups. The
production body already met these assertions, so this follow-up changed only
the owned test and its locked patch identity.

These host checks cover deterministic fault and cancellation boundaries. They
do not add native hardware, performance, durability, or legal qualification.
