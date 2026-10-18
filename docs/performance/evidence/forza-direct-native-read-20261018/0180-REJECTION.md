# Patch 0180 transaction review

Patch 0180 must not be used without patch 0181. Independent host
reproductions found four priority-one failures that its original 48 adapter
groups did not cover.

| 0180 failure | Observable break | 0181 correction | Integrated regression |
| --- | --- | --- | --- |
| Generic recovery failure quarantined only the core | A later FATX-qualified direct read submitted and succeeded after quarantine | The core reports its first quarantine transition through `nx_port.quarantine`; the adapter publishes the same state before draining bypass traffic | `generic_quarantine_rejects_later_qualified_read` |
| Direct peers were outside the core slot domain | One direct read failed RELEASE QUEUE while another remained pending and received no cancel | First adapter quarantine scans the retained direct domain and cancels each live peer outside the adapter lock; dynamic envelopes never qualify for direct submission | `direct_quarantine_cancels_live_qualified_peer`, `dynamic_marked_peers_remain_in_generic_quarantine_domain` |
| Quarantine could begin during packet preparation | The newly prepared direct packet still committed to the lower driver | Direct submission rechecks adapter quarantine after preparation and before lower commit | `qualified_commit_rechecks_quarantine` |
| Inline completion during `IoCancelIrp` could reuse the retained child | A queue-frozen cancel completion prepared RELEASE QUEUE on the same child before the cancel call returned | Parent and quarantine cancellation hold `submit_active` through `IoCancelIrp`; completion captures and defers its result until the call unwinds | `qualified_cancel_holds_child_until_cancel_returns` |

The cancellation-without-callback case was added at the same boundary. A
successful `IoCancelIrp` return is not proof that the lower owner released the
packet; removal stays blocked until the terminal callback arrives. This is
covered by `qualified_cancel_without_callback_blocks_removal_until_terminal`.

The final qualification is intentionally narrow: FATX marker, non-optical
device, retained envelope, and exactly one command from the shared planner.
Split reads and dynamic overflow remain in the generic core, along with writes,
flushes, controls, optical requests, and non-FATX reads. This avoids a second
active-list implementation and leaves those requests within the core's
existing cancel/drain machinery.

The exact assembled source ran 54 adapter groups in both plain and ASan/UBSan
configurations. The broader core, concurrency, packet, ownership, cache and
geometry suites are recorded in [README.md](README.md). This review used public
I/O contracts and SpiritBoot source; no Complex implementation body was
inspected.
