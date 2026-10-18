# Pending return versus completion work

`STATUS_PENDING` alone does not distinguish cheap admission from expensive work
performed before return. The v5 public-event records provide a stronger, though
instrumented, discriminator: whether the matching parent `IoCompleteRequest`
observation occurs before or after the native read returns.

Only joined world-callback requests whose API entry and return both fall inside
the saved-scene replay receipt bounds are included. Warmup is excluded before
validating the selected lifecycle records. Each selected record has exactly one
matched parent completion, successful completion/callback status and matching
requested, completed and callback byte counts. The producer selected callback
context `001103e0`; IOSB identity connects the observed events.

| Replay joined cohort | Complex | Spirit |
|---|---:|---:|
| Selected native calls | 236 | 493 |
| Return `STATUS_PENDING` | 236 | 493 |
| Parent completion observation before return | 0 | 77 |
| Parent completion observation after return | 236 | 416 |
| API median, before-return cohort | — | 320 µs |
| API median, after-return cohort | 31.5 µs | 173 µs |

The larger Spirit cost persists in requests whose own observed parent completion
occurs **after** return. Completion work charged before return can amplify the
cost, but cannot by itself explain that entire submission gap. Other requests'
completion work, interrupts and scheduling may still execute inside those calls.
This does not isolate a specific exclusive CPU cost.

After-return cohorts, controlled only for requested length:

| Bytes | Complex API median (n) | Spirit API median (n) |
|---:|---:|---:|
| 512 | 30 µs (104) | 58 µs (161) |
| 10,752 | 80 µs (12) | 176 µs (44) |
| 43,520 | 29.5 µs (10) | 195 µs (41) |
| 65,536 | 32 µs (25) | 198 µs (35) |

The scalar name `done` denotes the observed parent completion-function boundary;
it does not establish when its complete tail or IOSB publication finished.
Matching lifecycle records are not proof of exhaustive capture. The traces have
observer effects, finite event collection, different scene progress and different
request populations. These tables are not an uninstrumented speed ratio.

The v5 records alone contain no populated file/device names or open records.
Separate [offline object metadata](STORAGE-MEDIUM.md) now establishes that the
preserved Spirit world handle is on an HDD FATX16 volume. Complex's medium
remains unknown. The generated E: FATX HDD fixture matches Spirit's broad
medium/filesystem class, but not a verified partition, cache state, placement
or complete title workload.

## Reproduction

```sh
python analyze_completion_order.py complex-v5-joined-world-reads.json complex-v5-receipts.jsonl --output complex-v5-completion-order.json
python analyze_completion_order.py spirit-v5-joined-world-reads.json spirit-v5-receipts.jsonl --output spirit-v5-completion-order.json
python -m unittest -v test_completion_order.py
```

`completion-scalar-lineage.json` records hashes of the original scalar files,
private raw event logs and original join producer. `original_scalar_producer.py`
preserves that producer for audit; regenerating its joins requires the private
raw logs. Those raw logs are deliberately excluded because generic memory-value
fields can contain title bytes. The archived joined records contain scalar
request identities, times and lengths only. Receipt paths/details are sanitized.
