# Benchmark input decoding correction

Independent review reproduced a contradictory JSONL row containing an error
status followed by a duplicate successful status. Python's default JSON decoder
kept the final value. In an otherwise valid invented 360-run A/A ledger, the
reader erased the earlier failure and the analyzer accepted every row.
This was a host-only probe, not an alteration of real native measurements.

The comparator now rejects duplicate decoded keys in every JSON object,
including nested identity/checksum fields and escaped spellings of the same
key. Both JSON configuration and JSONL results use this decoder. A malformed
results row retains its line number in the error and cannot reach calibration
or comparison. Separate objects and separate rows may still use the same
field names; valid raw-input hashes are unchanged.

Fail-first tests reproduced all four duplicate-key cases before the correction.
The positive control checks distinct nested objects, multiple rows and the
original byte hash. All 24 comparator host tests pass. Independent replay of
the original 360-row contradictory ledger rejects it before grading, while
the valid ledger retains its raw-byte hash. These tests use invented timings;
passing them does not qualify
P1, hardware durability, a native performance recorder or a replacement BIOS.
