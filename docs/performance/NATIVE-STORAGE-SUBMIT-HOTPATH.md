# Native storage submission hot path

## Trigger

The exact-current 64 MB firmware completed every operation correctly in the raw-device workload, but took 2.081 times the Complex batch time and 5.094 times its summed submission time. The workload issued 1,024 requests and transferred 10,871,296 bytes with no byte, status, APC, or cleanup failures.

## Change

Each admitted request already owns a preallocated adapter envelope. The core copies that envelope pointer into every command as its opaque lease. The adapter now validates and resolves the envelope directly from that lease instead of scanning every active envelope during prepare, submit, retire, and cancel.

The target build also uses an owned aligned dword loop for zero initialization. Host and freestanding builds keep their byte fallback. Two stack objects whose fields are fully assigned before use are no longer cleared, and the core skips clearing a first command that belongs to a freshly cleared slot. Later chunks and recovery commands are still cleared before reuse.

For a one-command request, the clear changes remove 208 bytes of redundant writes. Counting the unchanged IRP reset, the estimated fixed string-store iterations fall from about 1,228 to 567. This is a code-shape estimate rather than a throughput claim; the lower transport and completion work remain.

## Safety boundaries

The direct lease lookup rejects null, foreign-adapter, inactive, and wrong-parent envelopes. It does not derive the envelope from the reusable core slot. A reentrant completion test dispatches a second request after the first request's core slot is free but while its adapter envelope is still owned, proving that core-slot reuse and envelope lifetime remain independent.

The aligned clear path checks both address and size before entering the dword loop. Misaligned or partial sizes use the original byte loop. The implementation adds no kernel import. Sanitized host tests retain poisoned allocation coverage, inline and pending completion, cancellation, frozen-queue recovery, write-through ordering, media controls, and adapter teardown.

## Qualification

The functional gate consists of the nxstorage core, packet, adapter, owner, and optical host suites plus a release64 firmware build. Performance acceptance requires paired ABBA runs against the exact pre-change firmware using the same runner, xemu build, HDD overlay, request sequence, warm-up, and clock source. Report batch, submit, and post-return/APC intervals separately at queue depths 1 and 4. Queue depths above eight are saturation tests until the adapter pool is deliberately enlarged.

The 2026-10-15 long-run QD1 ABBA comparison used 16 measured passes per boot and two boots per arm. Each arm completed 32,768 reads and verified 347,881,472 bytes with zero protocol, payload, status, crash, or cleanup failures. Against baseline BIOS `cff12e2c...`, candidate `4b132b78...` changed mean per-pass timing as follows:

| Interval | Baseline ticks | Candidate ticks | Change |
| --- | ---: | ---: | ---: |
| Caller batch | 67,118,056 | 62,168,812 | **-7.37%** |
| Submission sum | 30,040,296 | 27,831,904 | **-7.35%** |
| Post-return to APC sum | 36,378,193 | 33,625,179 | **-7.57%** |

The APC-before-return tail increased from 979 to 1,437 ticks per pass, but it is about 0.002% of the batch interval and its median remained zero. It is too small and sparse to represent a material regression. Exact requests, run IDs, all 64 pass records, build receipt, schedule, and analysis are in `docs/performance/evidence/native-storage-hotpath-long16-20261015`.
