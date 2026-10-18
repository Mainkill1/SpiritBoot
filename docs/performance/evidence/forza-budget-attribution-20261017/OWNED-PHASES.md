# Spirit owned-kernel submission scopes — v12b

The callback-filtered replay places most observed native-read time in the
adapter and request-pump scopes. Packet preparation is a small observed scope;
these measurements do not support treating it as the dominant cost.

The corrected probe records **373 completed replay calls**, excluding **125
warmup calls**. Every selected call uses title thread `c1008c20` and handle
`0000042c`. Header row count is 498, with zero overflow, lost-slot events,
reentered reads, bad phase exits, or open phase depths. All phase durations fit
inside their native API scope. No possible replay-start overlap was detected.

| Inclusive scope | Median per completed read | Aggregate share of API time |
|---|---:|---:|
| Native read API | 272.5 µs | 100% |
| Native adapter submission | 164.8 µs | 64.30% |
| Request pump | 127.9 µs | 47.37% |
| Port submission | 68.6 µs | 22.59% |
| Port preparation | 25.4 µs | 9.02% |
| Packet preparation | 10.9 µs | 3.76% |
| PATA start | 27.2 µs | 8.77% |
| IRP allocation | 9.1 µs | 3.59% |
| Probe and lock pages | 6.8 µs | 2.87% |

The scopes overlap and nest: **do not add these percentages or medians**.
Same-phase recursion is measured at its outermost depth. The named scopes and
addresses are independently authored observer boundaries tied to the owned
baseline image; no proprietary BIOS implementation was used.

DPC processing was observed during 182 of the 373 calls:

| Completed-call population | Calls | API median | Adapter median | DPC median |
|---|---:|---:|---:|---:|
| No observed DPC retirement | 191 | 253.9 µs | 159.5 µs | 0 |
| Observed DPC retirement | 182 | 341.15 µs | 243.4 µs | 59.65 µs |

All 191 DPC-absent calls entered the request pump once. Among DPC-present calls,
62 entered it once, 111 twice, and nine three times. This is an association
between observed scopes, not an exclusive attribution of the duration difference
to DPC execution. Interrupts, scheduler activity and host/emulation effects can
contribute to elapsed duration.

Across all calls, total API duration is 109.3311 ms. Aggregate time outside the
union of measured phases can only be bounded from this representation:
**1.0032–38.6111 ms**. The lower bound subtracts all phase durations and clips each
call at zero; the upper subtracts the largest phase per call. Unknown nested
intersections prevent a unique residual. These bounds are not CPU-only time.

## Observer checks and limits

The independent review caught an ABI filter error in the first v12 attempt:
`ESP+12` is the native APC routine, whereas the title callback is passed as the
APC context at **`ESP+16`**. That invalid attempt produced no target observations
and is not firmware evidence. Only corrected v12b is archived here.

The corrected filter requires native caller `0026741a`, callback context
`001103e0`, and the expected cleaned-up return stack (`entry ESP + 36`, covering
return address plus eight stdcall arguments). The analyzer verifies those
bindings and each phase entry/return against `owned-phase-sites.json`.
The log field `status` is **IOSB.Status sampled at return**, not EAX or the native
API return status. Its zero values do not establish synchronous successful
completion of every read.

Only calls reaching the matching native return are emitted. An active call at
pause/exit is not included in the completed-call population. Host-end replay
filtering, boundary estimates and general clock limitations match v11.

The additional phase hooks increase instrumentation work. v12b's API durations
must not be directly substituted for v11 costs or compared to Complex as if the
observers were equivalent. The purpose is localization within this instrumented
owned-kernel run, not an uninstrumented performance estimate. The exact internal
CPU, blocking, scheduling or device-wait cause remains outside this scope.

## Reproduce

```sh
python -m unittest -v test_analyze.py test_analyze_owned.py
python analyze_owned.py spirit-v12b-owned.log spirit-v12b-receipts.jsonl v12b-owned-observer.c.txt owned-phase-sites.json --output spirit-v12b-owned-analysis.json
python verify_manifest.py
```

The archived raw log contains scalar counters and durations only. Control
receipts are sanitized; their original hashes are in `receipt-lineage.json`.
The source is an independently authored emulator observer, not firmware code.
No firmware edits or commits were made for this analysis.
