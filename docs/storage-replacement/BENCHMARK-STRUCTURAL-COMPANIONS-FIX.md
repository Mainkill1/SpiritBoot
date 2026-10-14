# Preserve untraced timing while structural evidence is collected

The public storage fixture records verified caller-issue-to-consumer-ready
timings on the exact published ROM. It cannot observe every internal upper
worker hop, new pool allocation, bounce copy, physical command or IRQ. The
original analyzer discarded valid small-HDD timing rows whenever those private
counts were missing, preventing timing A/A calibration as well as honest
reporting of the unresolved structural gate.

The optional frozen `structural_policy` now separates untraced timing records
from qualified structural diagnostics. Valid timing A/A can derive and freeze
the same confirmatory count before the counter collector exists. Method,
coverage, counter units, route and correspondence rules are declared before A/A;
the actual collector implementation/source and independent qualification are
bound before each later diagnostic capture. The original spec format retains
its strict same-run counter requirements.

Companions join scheduled case/arm/seed identities and bind host/profile/cache,
reference and diagnostic source/ROM manifests, runtime route proof and actual
readable artifact hashes. Complete, loss-free counter evidence and a reviewed
method/correspondence/interference sidecar are required. Valid same-run actual
counts can use equally qualified embedded evidence. A companion has its own run
identity and never substitutes its latency for acceptance. Missing or invalid
counts remain unknown, and combined P1 remains INCONCLUSIVE. Actual qualified
growth in any healthy worker/allocation/copy/command/IRQ component still produces
REGRESSION; unknown evidence elsewhere cannot hide that growth.

Independent review reproduced three false-PASS cases: a diagnostic reused a
different scheduled timing run's ID, a same-host diagnostic overlapped accepted
timing, and a failed diagnostic outcome was ignored. Regression fixtures now
keep the rehashed raw records coherent while exercising these failures. All
scheduled timing IDs are reserved; overlapping acceptance intervals lose timing
and embedded same-run count qualification while unaffected rows remain usable; explicit successful outcomes
must agree in the row and counter ledger. Failed/partial/missing outcomes remain
visible in `structural_attempts`. Coverage-plan and correspondence-rule descriptor
bytes must also match the frozen policy hashes.

Recorded failed/partial diagnostic lifetimes now participate in the same-host
overlap pre-pass before count qualification. Every overlapping diagnostic loses
structural qualification, so interference cannot turn its apparent count growth
into a qualified regression. A coherent failed-window growth fixture reproduced
that defect before the correction and now keeps those counts unknown.

The new host fixtures are explicitly invented. They test timing retention,
count/rule freezing, reordered joins, binding/route mismatch, event loss and
missing counts, raw/source artifact validation, qualified same-run counts,
diagnostic timing exclusion and all five growth gates. Existing uniform and
per-operation request-width tests remain in place. These tests qualify analysis
behavior, not a native collector, BIOS timing, structural result or memory
footprint. Full native A/A/confirmation, factual independent review and other
P1/P3 gates remain open.

The complete schema and CLI are in
[PERFORMANCE-HARNESS.md](PERFORMANCE-HARNESS.md#separate-structural-diagnostic-evidence).
