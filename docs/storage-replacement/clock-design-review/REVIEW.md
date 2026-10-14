# Causal clock measurement: bounded design review

The proposed arithmetic is correct under the stated causal assumptions. No
concrete formula error was found. The review does not qualify a fixture, backend,
guest clock, calibration, sample count or performance result. Seven independently
chosen exact toy cases are recorded in `EXACT-TOY-CASES.json`; no native or remote
operation was performed and the product document was not edited.

The reviewed document is `docs/storage-replacement/CLOCK-MEASUREMENT-PLAN.md`,
SHA256 `d7ae5266dcf062218ff526e6e212aac04ecaba1dbc303b26f7a0ff6cf136317b`.

## Mathematical result

Let each actual host appearance be within its host bracket and the corresponding
actual counter value be within its guest bracket. Subtracting the interval
endpoints gives lower and upper bounds on the counter difference and host
duration. When both differences are nonnegative and duration has a strictly
positive lower bound, the smallest allowed counter difference divided by the
largest allowed duration is a safe rate lower bound. The converse endpoints
give a safe upper bound. Counter linearity is not required. Dependencies between
the endpoints can make these bounds wider, but do not invalidate them.

The nonlinear counter case has a tenfold change in local slope. Its actual
average is `43/8` ticks per second and is safely enclosed by `10/9` and `76/7`.
The delayed-write case demonstrates why the conservative timestamps matter:
an absence read ending at 140 ns can have observed EOF at 130 ns before a marker
appears at 135 ns. Its read-start supplies a lower bound; its read-end does not.
A presence read beginning at 350 ns can return a marker appended at 375 ns and
observed at 380 ns. Its read-end supplies an upper bound; its read-start does not.

Overlapping host brackets correctly remain INCONCLUSIVE under the proposal.
Known marker order alone does not supply a positive duration lower bound. A
negative guest lower difference can be conservatively replaced by zero in a
pure mathematical analysis, but the plan's stricter rejection is safe and
avoids claiming precision from that case.

An exact long-run average can coexist with radically different local rates.
One case has idealized exact markers yielding 100 MHz over ten seconds, while
the first second advances at 500 MHz and the remaining nine seconds average
`500000000/9` Hz. No amount of narrowing those two endpoint brackets certifies
a uniform calibration for short storage requests.

## Important assumptions and current design clarifications

**Appearance event.** The root revised the plan during review to define complete
uniquely identified framed-marker appearance, including its final delimiter.
This addresses the wording clarification; it remains an implementation gate.
The complete identified framed marker is the
natural event for a parser that returns a marker only after receiving all its
bytes. First-byte visibility is a different event. If a prefix appears at
10 ns, a poll at 15 ns sees only that prefix, and the complete record appears
at 20 ns, absence of the complete record at 15 ns cannot lower-bound first-byte
visibility. The current plan's rejection of partial observations is conservative;
the fixture still needs one precise event definition and independently checked
counter-to-record pairing.

**Actual EOF witness.** The revised plan now requires actual unbuffered
read/EOF start/end timestamps and byte offsets, choosing EOF-call start for
absence and containing-read end for complete presence. This addresses the
design wording clarification. An absence receipt must identify the owned
descriptor/inode, byte cursor, actual reads and their timestamps, decoder state,
and a genuine EOF observation after consuming all bytes needed to decide the
marker predicate. A cached size limit, short chunk, EAGAIN result or decoder
prefix is not an EOF witness. A read loop is not one atomic snapshot: an actual
EOF read or complete-record read supplies a witness within its own bracket.
The broader poll-start/poll-end bracket remains safe if it demonstrably contains
that witness. State which timestamps are retained and how their operation
boundaries include all relevant reads.

**Prove monotonic visibility, rather than infer it from a pathname.** The
append-only, single-writer, unchanged-file assumption is what allows an absence
observation to apply back to read-start and a presence observation forward to
read-end. The owned pathname alone does not prove descriptor identity, absence
of replacement/truncation or hidden buffering. File visibility is the property
needed here; storage durability or a hardware flush is a separate property.
The host timestamps also need a coherent monotonic clock domain and stated
resolution/error treatment for the rate tolerance being proposed.

**Prove the guest-to-host causal link independently.** One toy case polls within
0.2 ms around each appearance yet obtains a mechanical rate interval of
`380000/107` to `420000/103` ticks per second, excluding the real 2000 ticks per
second. The first marker was delivered after its guest after-reading. Poll
precision cannot detect or repair that violation by itself. A regular-file
backend is promising only when the exact mapped binary/build and actual descriptor
route are bound to the inspected synchronous behavior, with transmit/drain
semantics that establish the required event ordering. The plan correctly leaves
these claims unproved. Windows requires its separate evidence.

## Remaining proof gates

Before execution, freeze an implemented collector and marker fixture with a
specific event definition, counter units/identities, syscall/byte-position
receipts, exact mapped backend identity and lifetime checks. Independent faults
need to demonstrate rejection of unread bytes, stale size/decoder state,
partial/duplicate/reordered records, changed file identity, rollback, mixed
writers, overlapping brackets and delivery outside the counter bracket.
An implementation cannot infer the last causal fault solely from polling data;
it must rely on separately established source/runtime evidence.

A new run can then supply collection and causal evidence. Qualification for
short requests additionally needs rate-stability evidence at relevant durations,
explicit bracket uncertainty limits, drift/quantization treatment, a rule for
missing or inconclusive samples, and a valid frozen statistical/calibration
decision. The existing run receipts cannot gain missing observations
retrospectively. All actual clock and performance qualification remains open.
