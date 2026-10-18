# 0176 submit-lock return

0176 arms submit deferral in the packet handle-publication critical section.
When lower submission returns without inline completion,
`NX_SUBMIT_LOCK_HELD` transfers the held adapter lock into the core
post-submit update. Inline completion releases it and uses the original
unlocked deferred-result path. This preserves the rule that transport calls
run without the adapter lock while avoiding another lock/IRQL round trip on
the common no-inline-result path.

Combined with 0173 and 0175, the retained pending-read route falls from 14 to
7 adapter lock/IRQL transitions. The exact built source passes all core,
active-scan, ownership, adapter, packet, optical and sense checks, including
sanitizer variants. The release A/B/A/B trial improves all four primary
450 µs cost/rate comparisons and all sixteen weighted costs. The selected
evidence, every measurement and the required outlier investigation are in
[`candidate0176`](../../forza-complex-cadence-20261017/candidate0176/README.md).

Patch: `0176-transfer-submit-lock-to-core.patch`.
Stable copy: `patches/roswell/0176-transfer-submit-lock-to-core.patch`.
