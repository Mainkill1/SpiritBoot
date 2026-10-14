# Proposed causal clock measurement

Status: design only. This method has not been implemented, run or qualified.
The corrected V2.5 diagnostic establishes bounded collection preparation;
its existing marker observations do not provide a backend delivery bound.
Neither this note nor a successfully parsed diagnostic freezes P1 counts or
qualifies performance.

The V2.4 error compared RDTSC ticks against a QPC frequency. Each counter must
retain its own identity and units. The performance fixtures separately derive
their RDTSC frequency from paired RDTSC/QPC differences; that conversion is
dimensionally distinct from the diagnostic error. The remaining question is
how each guest counter advances relative to host elapsed time.

An alternative to a universal scheduler-delay bound is to retain causal
intervals around each marker. For each counter independently, the diagnostic
would read immediately before marker emission and after `tap_drain`. The
observer would preserve monotonic start/end timestamps of each read, including
the last observation that lacks the marker and the first that contains it.
An absence observation supplies its read-start time as the conservative lower
bound; a presence observation supplies its read-end time as the upper bound.
The read's own linearization point must lie between those timestamps.
Absence must be established by draining the owned file through EOF at the
expected byte position. A partial read, a stale size snapshot or a buffered
decoder that has not consumed available bytes cannot supply that lower bound.

Let marker `i` have guest counter bracket `[G_i_before, G_i_after]` and host
appearance bracket `[H_i_before, H_i_after]`, with host values in nanoseconds.
For two ordered markers, define:

```text
D_min = G_1_before - G_0_after
D_max = G_1_after  - G_0_before
T_min = H_1_before - H_0_after
T_max = H_1_after  - H_0_before

lower average rate = D_min * 1,000,000,000 / T_max
upper average rate = D_max * 1,000,000,000 / T_min
```

Both markers must have valid brackets, the counter must be monotonic, and
`D_min >= 0`, `T_min > 0` and `T_max >= T_min`. Overlapping host brackets
provide insufficient precision and must remain INCONCLUSIVE. Use exact integer
or rational arithmetic before presentation. Do not divide RDTSC by a QPC
frequency, substitute CPU time for elapsed time, or subtract a guessed marker
overhead. These bounds describe average counter advancement between the marker
appearances; further sampling and explicit uncertainty gates are needed to
qualify a calibration used by short storage requests.

The method requires a verified causal link: each marker's host-file appearance
must occur between the corresponding guest readings. Exact mapped executable
identity, backend implementation/behavior, synchronous transmit completion and
`tap_drain` semantics must support that link. The diagnostic must prove its
owned serial file/descriptor identity, stable inode and byte positions, and
reject replacement, truncation, mixed writers, partial/duplicate/reordered
markers, counter rollback and target-lifetime changes. Poll gaps alone do not
prove these properties. The current receipts cannot retrospectively create
missing before/after observations.

Source and binary research supports a synchronous regular-file backend on the
recorded Deck reference, but source/build identity and the complete causal
contract still require their own review. A syscall-trace diagnostic is another
possible route; it would additionally require a pinned trace tool, an actual
monotonic trace clock and exact owned descriptor/PID lifetime. Either method
needs a separately frozen fixture, fail-first host faults, independent review
and a new run identity before execution. Windows needs its own backend proof
and must retain the protected PowerShell desktop-pipe launch.
