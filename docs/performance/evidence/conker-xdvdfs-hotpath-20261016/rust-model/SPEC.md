# Frozen behavior specification: optical read forwarding model

This is the behavior-only specification for a host-side Rust investigation of
the Conker optical-load hot path. It was frozen before the Rust implementation.
It describes decisions, outcomes, and accounting rather than a C decomposition.

Each rule is tagged by its evidence class:

- **[observation]** comes from the existing release Conker census or operator
  reports.
- **[contract]** comes from current SpiritBoot-owned public tests and ownership
  requirements.
- **[inference]** is a conservative rule chosen for this model and requires
  native validation before firmware use.

## Goal and boundary

1. **[observation]** A prior 60-second release Conker census recorded 1,729 file
   reads, 2,380 optical target reads, 2,393 filesystem request builds, 5,456
   page lock/unlock pairs, and 594 directory-table reads across 272 path
   resolutions.
2. **[observation]** The file-data route creates an intermediate request,
   describes the caller buffer again, waits for lower completion, and only then
   returns. The candidate removes that duplicate work for requests already
   safe to pass to the lower optical stack.
3. **[contract]** The model does not alter ATA timing, the lower 128 KiB
   segmentation policy, media verification, directory parsing, or unaligned
   bounce-buffer behavior.
4. **[inference]** The model has two outputs for nonzero reads: `Forward` and
   `ExistingPath`. A refusal to forward is not an I/O failure; product code
   would retain the current route.

## Input facts

A request supplies only scalar facts:

- data purpose: file bytes or filesystem-owned metadata;
- signed file offset, requested byte count, file byte count, and file start
  sector;
- paging and associated-request flags;
- caller buffer address and target alignment mask;
- whether one unused lower stack location exists;
- whether an MDL exists, is a single descriptor, describes locked or nonpaged
  memory, has a validated PFN span, and covers the effective byte count.

The model does not dereference a guest pointer or infer residency from an
address.

## Eligibility

5. **[contract]** Metadata reads always use the existing path.
6. **[contract]** Negative file offsets use the existing path.
7. **[contract]** If the offset is at or past end of file, or the request length
   is zero, the model returns `CompleteZero` without lower work.
8. **[contract]** A request that crosses end of file is truncated before any
   alignment or coverage decision.
9. **[contract]** Sector-to-byte conversion, file-base plus offset, and buffer
   range arithmetic must be checked. Overflow uses the existing path.
10. **[inference]** The absolute disc byte offset and effective byte count must
    both be multiples of 2,048. An unaligned head or EOF tail stays on the
    existing path.
11. **[contract]** Forwarding requires exactly one present MDL, a validated
    locked-or-nonpaged state, a valid PFN span, and declared byte coverage of
    the effective transfer.
12. **[contract]** The caller data address plus effective length must not
    overflow. The address must satisfy the lower target's alignment mask.
13. **[contract]** Forwarding requires another lower stack location.
14. **[inference]** The first candidate excludes paging and associated
    requests. The cached/noncached bit does not decide eligibility because the
    filesystem route performs device I/O in either case.
15. **[contract]** No 128 KiB upper cap is imposed by this model. The lower
    optical adapter owns bounded segmentation of an eligible parent transfer.

## Completion normalization

16. **[contract]** A full successful lower transfer completes successfully with
    the effective byte count and advances the file offset by that count.
17. **[contract]** A successful short transfer becomes end-of-file with zero
    information and does not advance the file offset.
18. **[contract]** Lower failure or cancellation completes with zero
    information and does not advance the file offset.
19. **[contract]** A lower byte count greater than the effective request is a
    protocol error with zero information and no offset advance.
20. **[contract]** Pending state is propagated independently of the terminal
    result. The completion operation allocates nothing and waits for nothing.

## Cost accounting

21. **[observation]** Every forwarded request can remove at most one child
    request build, one second MDL lock/unlock pair, and one internal wait.
22. **[inference]** `estimate` reports those removed operations from measured
    eligibility. It must never extrapolate more forwarded reads than observed
    file reads and must retain ineligible reasons individually.
23. **[observation]** With no request-shape trace, 1,729 forwarded requests is
    only an upper bound: 72.6% of the 2,380 optical target reads, 72.3% of the
    2,393 filesystem request builds, and 31.7% of 5,456 page lock/unlock pairs.
    It is not a performance claim.

## Acceptance properties

- Every refusal has one deterministic reason.
- EOF truncation occurs before alignment and MDL coverage checks.
- Arithmetic overflow never produces a wrapped forward plan.
- Terminal normalization credits bytes only for a full success.
- The estimator conserves total samples and never reports impossible savings.
- Exhaustive boundary request facts cannot panic.

## Deliberate limits

This Rust crate is an executable design artifact, not firmware. It does not
establish native IRQL safety, cancel ownership, device lifetime, queue overlap,
media-change handling, actual Conker eligibility, or release performance.
Those require a release trace and target tests before a C candidate exists.
