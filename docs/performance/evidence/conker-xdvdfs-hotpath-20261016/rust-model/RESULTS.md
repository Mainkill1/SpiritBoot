# Rust model results

Recorded 2026-10-16 on the PR #248 worktree.

## Test-first record

The first test invocation failed because `src/lib.rs` did not exist. After the
classifier was implemented, the initial ten behavior tests passed. A new
cached/noncached test then failed because that fact was absent; the input was
added without making it an eligibility discriminator. Parser tests failed
before `parse_trace_line` existed, and command-line integration tests failed
before the analyzer binary existed. Each was implemented only after its red
test.

Final results:

| Gate | Result |
| --- | ---: |
| `cargo test` | 19 passed, 0 failed |
| release tests with `-D warnings` | 19 passed, 0 failed |
| registry dependencies | 0 |
| malformed trace behavior | exits 2 without a report |

The 19 tests cover the aligned route, cached/noncached equivalence, zero and
EOF behavior, truncation order, unaligned tails, every ownership refusal,
checked arithmetic, transfers above 128 KiB, all completion outcomes,
conservative accounting, boundary values, strict parsing, and command-line
failure behavior. They also cover exact release-layout decoding, request flag
and MDL-shape preservation, pointer/stack rejection, PFN capacity, and checked
virtual-address selection.

## Current bound

The earlier 60-second release Conker census observed 1,729 XDVDFS file reads,
2,380 optical target reads, 2,393 filesystem request builds, and 5,456 page
lock/unlock pairs. If every file read proved eligible, the proposed route could
remove at most:

- 1,729 child request builds, or 72.3% of observed filesystem request builds;
- 1,729 internal waits;
- 1,729 duplicate MDL lock/unlock pairs, or 31.7% of observed pairs.

That is a structural upper bound. The model intentionally reports no
eligibility rate or performance improvement until a complete scalar request
trace is captured from the release workload.

## Decision

The design remains a candidate. It is narrower than changing optical timing
or replacing the lower adapter: only proved whole-sector file reads can use the
new route, while metadata, partial-sector, paging, associated, ambiguous-MDL,
and unsafe-stack requests retain the current implementation. ATA timing is
outside this investigation.
