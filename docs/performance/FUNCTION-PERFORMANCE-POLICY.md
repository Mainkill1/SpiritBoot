# Kernel function performance policy

SpiritBoot treats performance as a release property with compatibility as a
hard constraint. Every function in an exact release kernel symbol inventory
must have a performance disposition. A disposition is one of:

- measured and improved on a representative route;
- measured and selected for a focused optimization;
- measured and retained because it implements required hardware timing,
  ordering, synchronization, error handling or another observable contract;
- not executed by the measured workload and assigned to a relevant XISO leaf
  or game route before any performance claim.

An unexecuted function is never labeled faster. A function is not rewritten
only to make the ledger say that it changed. Removing required work, changing
return values, weakening ordering, shortening a device interval without a
protocol-equivalent replacement, or shifting work outside a timer does not
count as a gain.

## Measurement order

1. Generate entry addresses from the exact release, unstripped i386 kernel.
2. Count calls, translated-block executions and weighted guest instructions
   inside a bounded workload phase. Keep profiler wall and CPU time diagnostic
   because callbacks perturb the emulator.
3. Attribute hot entries to a public-XBE or game route and record the behavior
   they preserve.
4. Test a replacement with exact production bodies, poisoned recycled state,
   boundary values, cancellation/reentry, sanitizers and release-i386
   disassembly as applicable.
5. Measure uninstrumented native release firmware in independent boots. A
   route must retain its byte/status/order oracle and complete cleanup.
6. Investigate every reproducible regression above 20%; smaller regressions
   are investigated when they affect a game-heavy path or fall outside the
   measured variance.

Assembly or intrinsics are appropriate when the exact release disassembly
shows avoidable helper calls, widening, copies, clears or branches and a C
shape cannot reliably remove them. The replacement must state its calling
convention, clobbers, alignment, lifetime and fallback behavior and must pass
the same native behavior gate. Compiler output that is already minimal is a
reason to keep the source clear.

## Current ledgers

The Forza QD12 census under
`docs/performance/evidence/forza-map-hotpath-20261015/deck-function-census/`
contains two views:

- `executed-kernel-function-ledger.csv` covers every entry reached in the
  first complete 1,024-request marker window and records its measured share,
  category, rationale and next step.
- `all-kernel-function-performance-ledger.csv` covers every entry in the exact
  release symbol list. Entries outside that marker window are explicitly
  assigned to a relevant-workload gate instead of receiving an unsupported
  claim.

`tools/function_performance_ledger.py` builds the full view and fails if an
executed entry cannot be reconciled with the final release inventory. Function
renames between measured and optimized builds are explicit evidence, not fuzzy
name matching.
