# Actual-source optimization checks

The fixtures accept a public source root. They extract named production
functions or the exact allocator search region, add host-only counters, and
compile with `cc -std=c11 -O2 -g -shared -fPIC -DSARCH_XBOX -Wall -Wextra
-Wno-multichar -Wno-unused-function`. Pin supply/API code is compiled with
`cc -std=c11 -O2 -Wall -Wextra` and the existing minimal host headers.
No operation counter or alternate implementation is shipped in the kernel.

```sh
python3 tests/host/kernel-performance/check.py SOURCE_ROOT OUTPUT
python3 tests/host/kernel-performance/check.py CANDIDATE OUTPUT --optimized --compare BASELINE
python3 tests/host/kernel-performance/pins.py BASELINE OUTPUT
python3 tests/host/kernel-performance/pins.py CANDIDATE OUTPUT --optimized
python3 tests/host/kernel-performance/pins.py CANDIDATE OUTPUT --optimized --diagnostics
```

`--optimized` asserts bounded work as well as correctness. It is expected to
fail against the public baseline. Full pin-scratch invariant scans are opt-in
with `DBG && NXK_PIN_BATCH_DIAGNOSTICS`; ordinary checked and release builds do
not run them. The fixture independently checks every scratch slot at every
exit, including increment-then-reject, invalid PFNs and sparse/bulk boundaries.

Independent scan oracles enumerate first-fit candidate order (including
wrapped candidates extending across the hint). Python `pow`, `hashlib.sha1`,
FIPS DES and public three-key EDE known answers supply crypto oracles. Entire
SHA caller contexts and DES/CBC outputs/feedback/tails are hashed after every
call and compared across source roots, covering artificial count carry and
overlapping caller buffers where an independent mathematical oracle cannot
describe the complete caller state. The fixed PRNG seed is `0x7807`.
Words 512 is covered with bounded exponents; full-width highbit/dense
exponents use Words 1/2/32. These fixtures do not model real page tables,
IRQL timing, allocator backing rollback or native callbacks: the existing
public API guest remains required for those contracts.

`work.json` retains measured operation arrays for both source roots.
Slots have family-dependent meanings:

| Slot | Meaning |
|---|---|
| 0 | pool bitmap reads / system PDE reads / registry comparisons / big-integer multiply calls |
| 1 | system PTE reads / big-integer squares (`A == B`) |
| 2 | DES six-bit loop iterations |
| 3 | `RtlCopyMemory` bytes |
| 4 | `RtlZeroMemory` bytes |
| 5 / 6 | pool allocation attempts / frees |
| 7 / 8 | SHA compression calls / SHA load bytes |
| 9 | decoded DES six-bit groups |
| 10 | pool candidate probes |
| 11 / 12 | big-integer 64-bit products / Montgomery factor products |
| 13 | bit-reduction steps |

Pin logs retain each success/rejection size, alias mode, translation count,
scalar/bulk cleared bytes and bulk clear count. These are source work counts,
not throughput or emulated cycle measurements. The initial 64-page pin
budget remains a tuning candidate until paired guest timings establish its
crossover, especially added translations on small rejected prefixes.
