# Conker XDVDFS request-shape result

The diagnostic release64 run completed on the Windows runner without a QEMU
plugin. The firmware read path was unchanged except for two aggregate atomic
counter updates per XDVDFS file request. The counters were read once through
QMP after the 60-second workload window.

Run `20261016-101151460-2c11c76a306344efb5251aa17aab8994` recorded 3,444
validated file reads:

| Decision | Requests | Share |
| --- | ---: | ---: |
| Direct forwarding eligible | 3,099 | 89.98% |
| Existing path: sector shape | 345 | 10.02% |
| Every other refusal | 0 | 0% |

Of the eligible requests, 3,097 were noncached. The terminal decision counters
sum exactly to the total. The run completed normally with complete declared
evidence. Its 60.003-second window consumed 110.75 host process CPU seconds,
but this is not performance evidence because the counter writes changed the
hot path.

The observation supports an allocation-free direct-forward candidate: at most
3,099 child IRP builds, duplicate MDL setup/teardown pairs, and internal waits
can be removed from this workload. Timing and native lifetime acceptance remain
separate gates.

Counter order is documented in `xdvdfs-shape-counters.patch`; the raw QMP
result and runner manifest are retained under `windows-counter-trace/`.
