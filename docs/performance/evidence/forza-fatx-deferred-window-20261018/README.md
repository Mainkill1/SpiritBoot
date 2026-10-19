# Rejected FATX deferred-admission window, 2026-10-18

## Decision

Patch 0186 is rejected and is absent from the firmware lock. Its two-millisecond
window delayed transport instead of making the existing transport asynchronous,
so it did not improve the fixed release-build Forza route:

| Arm | Run ID | Load window |
| --- | --- | ---: |
| selected-0168 control A | `20261018-160712762-fd51137a6caf40b19fc88123309c6532` | 39.313 s |
| 0186 candidate A | `20261018-161111431-0749d991d45f4353b54226af1f334099` | 39.442 s |
| selected-0168 control B | `20261018-161516095-ee7320e408074a08a31c8486503157ed` | 38.788 s |

Candidate A was 0.33% slower than control A and 1.69% slower than control B.
That is no repeatable benefit. Candidate B was stopped after the rejection
decision and is deliberately excluded; its preserved receipt SHA-256 is
`e1c5534de406e322dc049172c1b693028772829d3ac771ad497df262c823cea3`.

## Purpose

Patch 0186 ports the observed cheap asynchronous-return behavior into
SpiritBoot's independently owned request engine. It does not restore the
legacy class path and does not add a second planner, packet, completion,
cancellation, quarantine, or teardown path.

With the manual session-only `FATX read batching` setting On, up to 12
eligible asynchronous noncached FATX reads enter the existing nxstorage FIFO
and return pending before any of them begins transport admission. A relative
2 ms timer exposes at most four waiting reads per DPC and rearms while marked
reads remain. The thirteenth marked request, or any ordinary read, write, or
flush, exposes the complete preceding FIFO prefix.

## Exact build

| Field | Value |
| --- | --- |
| Assembled source tree | `3ec739fa6a96e3a39d091f534bd32c598ac855a8` |
| Patch SHA-256 | `a3958e998a41dce0421f8643bb2fab295dc853d47a907c9746b917ed12f465d3` |
| Release64 firmware SHA-256 | `805fd6e0a877dff36707f021408af7c16b7ec051e0860a3947d8cd00975d0688` |
| Firmware size | 524,288 bytes |
| Kernel SHA-256 | `91e18119051eaf9af073f7d83e5c2d91a8474b6e08c7a889dfbf6f6ca21d2a29` |
| Linker map SHA-256 | `ab07aa499ed1e21e5a06479ab641760c8fc0066fe24355d77ada388368d808a3` |
| Firmware lock SHA-256 | `abcd60fa16c91b2c8c2e575b0d1a86b88e0a9729a0f3baa5df3106056b15050c` |
| Build profile | release, 64 MiB |

The local reproducible build receipt is
`.scratch/pr253-0186-window-final-release64/build.json`. Firmware binaries
are build artifacts and are not committed.

## Contract qualification

The exact assembled tree passes 55 native-adapter groups in plain and
ASan/UBSan builds. The added cases prove:

- 12 marked submissions return pending before transport work;
- timer callbacks admit no more than four parents per expiry;
- the thirteenth marked request bounds retained waiting ownership;
- ordinary reads, writes, and flushes preserve FIFO ordering;
- cancellation before timer fire never reaches the lower driver;
- cancellation and quarantine after a release boundary complete once;
- split and inline-completing reads use the ordinary request engine;
- quarantine before timer fire performs no data I/O;
- removal waits for the timer/callback lifetime;
- private marker consumption preserves scatter/gather and unrelated flags;
- a deterministic 64-round state model covers timer, overflow, barrier, and
  cancellation transitions;
- marked and unmarked pressure have identical allocation counts, peak dynamic
  ownership, and injected failure ordinals.

The exact FATX producer/adapter checks cover 166 cases. The advanced-menu
renderer and targeted production-selection tests also pass. The full host
suite result is recorded in `host-qualification.json`.

## Release-title result

The release gate used fresh processes and compatible private HDD overlays. It
proved `FATX read batching: On`, then ran selected-0168 / 0186 /
selected-0168 on the same Forza route. All three recorded arms completed, but
0186 lost to both adjacent controls, so the fourth arm was unnecessary and the
patch was rejected without operator testing.

An attempted comparison with the older IRQ-static firmware is invalid: that
firmware opened the prepared HDD with incompatible profile keys and showed a
damaged-profile screen, so no fixed route occurred and no metric from that run
is used.
