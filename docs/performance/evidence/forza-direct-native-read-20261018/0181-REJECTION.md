# Patch 0181 final-review rejection

Patch 0181 must not be used. Patch 0182 repaired these two defects, but the entire 0180–0184 direct-read architecture was later rejected after an early PGR2 crash and no material Forza improvement. Independent final review found
two priority-one correctness failures after the four 0180 lifetime failures had
been corrected.

| 0181 failure | Observable break | 0182 correction | Integrated regression |
| --- | --- | --- | --- |
| Unlocked quarantine-publication handoff | Generic recovery set `core.quarantined`, released the shared lock, and only then called the adapter quarantine callback. A FATX-qualified direct read submitted in that gap reached the lower driver and completed successfully after quarantine had begun. | `nx_port.publish_quarantine` publishes `adapter->quarantined` under the shared core/adapter lock at the quarantine linearization point. The drain callback runs after unlock and cancels live direct peers without holding the adapter lock. | `generic_quarantine_is_visible_before_direct_drain` injects a direct submission at the former handoff and requires rejection before any lower commit. |
| Private marker collided with scatter/gather completion | `IRP_XBOX_FAST_NATIVE_READ` and `IRP_XB_SG_COMPLETION` both used `0x00010000`. A raw scatter/gather IRP could falsely qualify for the FATX direct route, and the adapter cleared the scatter/gather flag used later by I/O-manager completion. | The FATX marker moves to unused bit `0x00020000`; a compile-time guard rejects any future collision. The adapter consumes only the private FATX marker and preserves `IRP_XB_SG_COMPLETION`. | `scatter_gather_completion_flag_is_preserved`, plus synchronous inline-error/cancellation read and write scatter/gather completion cases in the I/O APC fixture. |

The old quarantine-handoff reproducer produced a third successful lower call:

```text
handoff direct_completed=1 status=00000000 lower_calls=3 pending=0
```

The new handoff test failed before the correction and passed after quarantine
publication moved under the shared lock. The exact 0182 assembled source then
passed 56 native-adapter groups in both plain and ASan/UBSan builds, including
the handoff and marker-preservation regressions. Its I/O completion fixture
passed 65 cases with 121 IRPs freed exactly once, plus 48 MDLs and 24 buffers
freed.

The corrected marker is deliberately separate from the public Xbox
scatter/gather completion contract:

```text
IRP_XB_SG_COMPLETION       = 0x00010000
IRP_XBOX_FAST_NATIVE_READ  = 0x00020000
```

The later 0182 repair preserved the narrow direct-read qualification: FATX marker,
non-optical device, retained non-dynamic envelope, and exactly one command from
the shared planner. Split and dynamic reads, writes, flushes, controls, optical
traffic, scatter/gather traffic, and unmarked requests remain in their generic
paths. This review used public I/O contracts and SpiritBoot source; no Complex
implementation body was inspected.
