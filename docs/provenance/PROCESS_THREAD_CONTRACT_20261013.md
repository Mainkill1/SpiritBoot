# Public title process/thread contract

Issue #240 retained two compatibility TODOs:
`ke/procprio/a_new_thread_starts_at_the_process_priority` and
`ke/procprio/the_process_lists_its_threads`.

The process adapter still published an empty `KPROCESS.ThreadListHead`, even
though the complete public thread view now covers the `KTHREAD.ThreadListEntry`
at offset `0x104`. Creation inherited the shared native system process base
instead of the public title process base. The process setter updated only the
caller and its published fields; it did not update native base priorities or
other title threads. Registration also sampled the native process's
`ActiveThreads` into the public `StackCount`, counting system workers.

The implementation links the exact title creation path before notification.
`XeThreadTrampoline` identifies title threads independently of TLS size;
suspended and zero-TLS threads therefore receive membership and inherited
priority before their first title instruction. The five-argument public creation
API now uses that same path. `KeStartThread` restores title inheritance after
native initialization, preserving the native process settings for system workers.
The public list and stack count contain only live title threads.

The existing native scheduler retains its priority normalization, boosts and
saturation logic. Its base-priority setter/query reads the public process base
for title threads, and the native process base for system workers. Changing the
title process base preserves each thread's explicit base increment. An unchanged
process base leaves quantum and priority-decrement state alone. All changes and
list traversal run at DPC level on the single CPU; no pool allocation is added.

Exit notifications still see list membership. Final termination removes the
public link before signaling the thread; final object deletion provides a second,
idempotent cleanup path for failed creation. The public identity registry remains
valid until final object deletion. Title classification uses the existing native
`ETHREAD.StartAddress`, which remains `XeThreadTrampoline` after termination,
so referenced terminal objects keep the public process base for queries.
Neither native thread structure grows and pool allocation classes are unchanged.

The regression guest uses the pinned public nxdk structures and APIs. The
initial 50-check probe passed against the reference kernel and produced 14
ordinary failures against the original SpiritBoot image. It observed a worker
with base increment `+2` moving from base 11 to 12 when the process moved from
9 to 10, a creation observer seeing membership and inherited base before
startup, and an exit observer seeing membership before the terminal waiter.
The [raw reference](evidence/process-thread-contract-20261013/reference-initial-50.tap)
and [baseline](evidence/process-thread-contract-20261013/baseline-initial-50.tap)
receipts contain those observations. The final v3 fixture converts these
observations into 59 checks, including queries on referenced terminated threads
while the public process base differs from the native system base.

Host tests compile the actual production process adapter, native base-priority
setter/query, termination publisher and title classification. They first failed
for empty membership, incorrect inheritance, unchanged native bases, incorrect
base increments, loss of scheduler state on an unchanged base, and the terminal
query edge. All seven cases now pass with 32-bit ABI storage and ASan/UBSan.
Related registry, wait, IRP, stack-publication and immediate-delay fixtures pass.
The product host suite reports 134 successful tests and three environmental
skips; names and commands are in the
[host receipt](evidence/process-thread-contract-20261013/host-tests.txt).

Dynamic process priorities 1..15 are qualified. The existing raw process-field
store for other values remains; out-of-range thread behavior has not been
established by this repair. Detached public links are initialized to self for
safe repeated cleanup; the reference leaves stale link values after removal.
Only membership, notification ordering, terminal lifetime and reciprocal live
links are asserted. This change does not claim parity for every thread field.

Implementation inputs were the project's pinned GPL-compatible source, the
public nxdk ABI, and black-box guest observations. No proprietary firmware
source, disassembly or decompilation was used. Firmware builds use the pristine
pinned source read-only and export the changes through ordered patches `0119`
and `0119a`. Native Windows execution and the final API matrix are owned by the
root integration workflow; no subagent starts an emulator or changes that host.
