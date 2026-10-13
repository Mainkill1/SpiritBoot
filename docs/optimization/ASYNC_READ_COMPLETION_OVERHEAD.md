# Remove unnecessary asynchronous-read completion work

The direct FATX read path allocates a one-pointer completion context for every
eligible read. The parent IRP already provides a unique, aligned identity that
stays alive through completion. The read now uses `(Irp | 3)` as the executive
resource owner and passes the resource pointer to its completion routine. This
removes the separate allocation/free pair while retaining the shared lease
until the storage request actually completes.

Buffer-pin failure releases the fresh lease. After submission, only completion
releases it. Immediate completion, cancellation, issuer exit and multiple
outstanding reads retain the same ownership rules. Completion never dereferences
the dispatcher context or frees the I/O manager's IRP/MDL. Internal executive
resource owner-table growth and the optional seek-checkpoint sidecar can still
allocate; this change removes only the explicit per-request context.

The storage class completion routine also reads a generic HAL performance clock
on every transfer to maintain idle-I/O scheduler timestamps. Xbox leaves that
scheduler disabled. The completion timestamp has no reader in the owned source;
the other timestamp is consumed only by the enabled idle scheduler. On Xbox,
timestamp collection is now conditional on `IdlePrioritySupported`. Desktop
behavior and enabled idle scheduling retain their existing clock/counter work.
No transfer status, length, pending propagation, retry, packet retirement, DMA,
interrupt, timeout or request lifetime rule changes.

## Evidence

Behavioral tests execute the actual production functions:

- The earlier allocated-context implementation fails 20 new lease assertions;
  the revised path passes 126 checks and five composed FAT/seek/read scenarios.
- Full storage completion passes 32 success/error/pending/idle combinations,
  including desktop behavior. The earlier unconditional-clock implementation
  fails the Xbox disabled-idle assertion.
- The original native lifetime fixture passes 7,833 checks with the IRP-owned
  lease. It exercises four issuers, pending close/truncate/delete, issuer exit,
  data/guard/IOSB/APC contracts and flat repeated-read page/pool counts.

These changes demonstrably remove work, but repeated untraced replay does not
establish an incremental end-to-end speedup. In the lease ABBA control, depth 12
with 900 available pages takes 75.2/78.7 ms on the earlier implementation and
82.2/75.4 ms on the new one for dataset 0; dataset 1 is 77.3/74.4 versus 75.3/85.9.
The clock-only ABBA likewise has mixed results. Separate public callback
attribution reduces exclusive completion time in all twelve phases by
0.872–2.483 ms per 1,024 requests. Instrumented attribution is not untraced
performance acceptance.

The exact packaged 64 MiB artifact also passes 10,779 native assertions across
zero-IOSB/APC (338), seek/mutation (2,071), immediate-delay (537), and lifetime
(7,833) fixtures. All four TAP plans are complete, each process exits normally,
and each launch receipt records ROM SHA-256
`0d49a1ab73140b823fc28e670e2fa9aa8421a9ba52b213a45fceebe7dff22ec6`.
Its assembled source tree is `988872775745048f118272197a13ec9c6a8db3f6`.
The evidence archive SHA-256 is
`12592f6a9d78ff766f7a4c163bab9e0516888a9028786430fa36172ef4509de4`.

The combined private candidate, also containing immediate-delay semantics and
the separate public critical-section owner fix, passes 11,040 native assertions
and four 19-check replays. It still trails Complex substantially. It is a
different composition from this PR and is not substituted for this PR's exact
artifact identity. None of these results establishes that delayed Forza scenery
is fixed; game-level and physical-Xbox acceptance remain outstanding.

The JSON beside this document records exact artifacts, source trees, controls,
archive identities and the separately qualified combined candidate. All
comparison fixtures use owned code and public APIs/callbacks; proprietary
firmware, game assets and implementation code are not included.

All CI checks at `416cbc73` pass, including the complete kernel host suite and
the 64/128 MiB debug/release matrix. Independent review confirms the packaged
source and ROM identities, audits every clock-field consumer, and reruns all
32 completion cases without a concrete concern.
