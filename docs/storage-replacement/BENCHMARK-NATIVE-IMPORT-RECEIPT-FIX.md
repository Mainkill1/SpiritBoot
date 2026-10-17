# Native importer receipt and zero-pressure compatibility

The first V351 native run completed its 1024 reads, but importer355 failed with
`KeyError: 'small-hdd-read.warm'`. The real parser returns one flat integrity
receipt containing `integrity_sha256` and provenance. The importer incorrectly
indexed that receipt by case ID. Its portable collector double returned a
case-to-hash dictionary and hid the mismatch. This is an importer bug, not a
native workload or plan-assembly failure.

The correction reads the actual `integrity_sha256` field and requires it to equal
the scheduled expected hash. The portable double now calls the actual product
parser's `infer_integrity` helper, preserving its return shape. That positive
test fails against importer355 before the correction and passes afterward.

A check of every declared V351 binding also found 120 unpressured FATX jobs
rejected by the importer. Comparator `pressure_pages: 0` means no clamp; the
native representation is absent/None. The corrected mapping accepts exactly
that representation. Positive pressure requires the same integer target;
conflicting zero/positive targets, booleans, negative values and floats reject.
This regression fails before correction. All 360 declared bindings pass after
it. Those checks use declared input observations and are not native captures.

Ten portable host tests pass; the optional archive class explicitly skips in
the isolated scratch layout. A complete local diagnostic replay of the actual
first V351 run passes through the emitter, source/artifact preparation, raw
counter export and downstream counter validation with the corrected code.

The additional actual V32 all36 shape replay includes both DVD variants,
write/flush/reopen, variable-size FATX and SG cases. Its 36 complete emitter
paths pass, with these explicit diagnostic substitutions:

1. The importer code-pin check temporarily uses the old355 pin. This is not
   approval of the corrected code under the old contract.
2. Historical cases map to future A/A job metadata without a historical
   `aa-binding.json`. The new recorder role label is supplied only after the
   pinned XBE bytes match the reviewed artifact map. These are schema checks.
3. Historical provider-context admission is excluded, and its missing post-END
   artifact is an explicitly unqualified marker in an isolated shadow copy.
   No provider observations or continuous-state proof are invented.
4. Future schedule/review precedence checks use diagnostic dates. Original
   native timestamps and raw outcome artifacts remain unchanged.

The actual historical collector evaluation and parser results are replayed.
All generated clock proofs are invalidated as `diagnostic_only_not_qualified`,
clock descriptors are removed from diagnostic rows, and every timing-eligibility
flag stays false. These shape tests establish compatibility of received fields,
not retrospective qualification of those historical runs.

The original failed import, V351 plan/schedule/contract, native rows and freezes
remain unchanged. The new importer hash requires a newly reviewed pre-capture
clock contract and a fresh schedule/request/attempt freeze. Old V351 timing
cannot be promoted. Physical durability, structural telemetry, total provider
precision and full P1 remain open. No native dispatch or Git operation occurred.
