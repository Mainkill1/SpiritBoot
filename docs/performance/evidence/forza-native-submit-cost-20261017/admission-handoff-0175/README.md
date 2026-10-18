# 0175 admission lock handoff

0175 hands the queue-publication adapter lock to the sole admission owner and
returns the owner's final lock to the originating dispatch epilogue. FIFO,
capacity decisions, cancellation publication and removal rundown remain under
the existing lock and lifetime rules. The common retained pending-read route
falls from 14 to 9 adapter lock/IRQL transitions.

All host checks passed. Seven of eight primary release observations improved;
the remaining 783-page/450 µs pair changed weighted cost by +0.23% and
throughput by -0.33%. The strict gate rejected 0175 as an endpoint. It is a
prerequisite of selected 0176, where both consecutive pairs and both memory
targets improve.

Patch: `0175-handoff-native-admission-lock.patch`.
Stable copy: `patches/roswell/0175-handoff-native-admission-lock.patch`.

