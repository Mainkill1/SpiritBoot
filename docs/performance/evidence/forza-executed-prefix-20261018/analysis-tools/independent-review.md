# Independent synthetic parser and join review

Only synthetic identity/prefix records and synthetic objdump text were used.
No guest capture, firmware build, host control, or external source/disassembly
was used in these tests.

`test_prefix_independent.py` adds 20 tests covering exact decoded-PC ownership,
unknown PC retention, symbol boundaries and section resets, instruction-start
versus REP-iteration accounting, count conservation, and malformed, duplicate,
and truncated records. Together with the original 11 parser tests they passed.

`test_join_independent.py` uses the published strict identity parser, timeline,
and prebind analyzers. It exercises two selected calls and one legitimate
full-capture call outside the replay receipt. An older queued request starts
inside the next API call: that event is deliberately distinct from the next
call's own drive-start boundary. Selected phase counts sum to 86; five other
instruction starts belong to the explicitly excluded call.

The first independent join run had 11 tests: nine passed and two failed because
an entirely absent API and an absent sequence on a known off-receipt API were
silently excluded. The root added full-capture reference validation. Further
tests cover excluded-call translations, sequences outside calls, missing
selected prefix data, empty cohorts, and a CLI receipt/hash round trip.

The first endpoint-based receipt guard rejected one-sided overlaps, but did
not reject a receipt window wholly contained inside an active call. The
15-test run preserved in `join-independent-red-boundary.log` has exactly that
failure: call [6000,14000], receipt [7000,13000]. It requires rejection because
silently selecting zero reads would hide the partially observed call.

A separate review observation: a cohort named `nearby_queued_later` whose only
predicate is queued-start-after-return does not control for intercall gap. The
synthetic first call has no prior gap and exposes this naming issue. Counts
under an active API/phase are execution-interval observations, not proof that
all observed work belongs to that API's request. Neither instruction starts
nor static symbol attribution establishes CPU time or runtime byte identity.

Final re-review: the root now rejects references outside known full-capture
calls before filtering, and rejects any call overlapping but not wholly
contained in the receipt interval. It applies `0 <= gap < 1000 us` to the
nearby-queued cohort, excludes unknown first-call gaps, and explicitly states
that execution-interval counts do not establish ownership. The new boundary
tests cover None, negative, zero, 99, 100, 999.999, 1000, and 10000 us. These
predicate-unit mutations are not presented as new physically realized traces.
All 50 tests passed in `independent-final-green.log`, including 16 independent
join tests. No review blocker remains for this synthetic tool validation.
This does not validate a future recorder capture or establish performance.

Reviewed join SHA256:
`b32778dfe8a4bc07e4dcf7371456d6586686a8c29418b95f5aa730378f6ac45b`.
Independent join test SHA256:
`3e3a00b3b6c3a082db970fffb8ff20c5dd6bdd193c500dfdb355e022b6cba708`.

## Version two follow-up

`test_prefix_v2_independent.py` adds synthetic owned/excluded/unknown and
REP-count accounting, range endpoints and overlap, every owned instruction PC,
health overflow/probe/allocation checks, singleton/version misuse, admission
closure, full-capture excluded identity references, and CLI identity-count and
handle binding. The synthetic trace has 103 total instruction starts, of which
12 are excluded; selected phases contain 96 starts, of which 10 are excluded.
Excluded counts remain excluded even if a supplied static symbol map contains
the runtime TB entry. That entry is not a per-instruction PC list.

The initial 18-test run found one standalone-parser inconsistency (three
failing subcases): admitted=returned=0,1,2 was accepted despite observations
naming three distinct APIs. `independent-v2-red.log` preserves this result.
The full CLI identity-count guard already rejects contradictory admission,
but standalone parse/count output must also reject impossible cardinality.

Final v2 independent confirmation: the parser now compares the distinct API
set across owned rows, excluded rows, and translation records with the declared
admitted count, and rejects an underclaim. The exact previously failing tests
now pass. All 74 parser/join tests passed independently; the full run is saved
in `independent-v2-final-green.log`. No synthetic-validation blocker remains.
The baseline-red log remains unchanged.

Reviewed parser SHA256:
`24d62d73045fdb56a86f25abc9839e972780190a2ca9ba5e172a733804e43ec6`.
Reviewed join SHA256:
`2352247b63b1f6231f9587ed5a4b1d6c13deea08020cd9cc3adf884be5a3eb9f`.
Independent v2 test SHA256:
`6d35f4ed3f9903b46e1214fbabcd39a5364e218bc99e32f718e38048f03dc6b9`.

This is synthetic parser/join validation, not a native recorder qualification
or a performance result. The native run must independently bind the intended
capture configuration (handle 0x42c, max_api 64, and the exact two owned ranges)
as well as the actual identity, symbol-map, and capture hashes.
