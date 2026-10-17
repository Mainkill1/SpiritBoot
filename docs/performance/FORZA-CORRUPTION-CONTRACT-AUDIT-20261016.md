# Forza corruption contract audit — 2026-10-16

## Trigger and scope

The first operator test of release64 image
`6f4070f788355d88cf44f37b792a6aceb1e9ead91bc441fe04df800c0a0fc077`
reported worse sporadic Forza corruption. This audit treats that report as a
compatibility regression and separates default behavior from the three
session-only advanced experiments.

| End patch | Release64 SHA-256 | New behavior |
| --- | --- | --- |
| 0151 | `412bb8a53312777709f0a855e7d1e36d590f5ed0caf770fee39051e61bd13991` | Last operator-clean storage candidate |
| 0152 | `b266d2a130c4c3c02cf396aea4af3d294107ccffbf04593e1d156d9a638b51cd` | Advanced controls, default mask zero |
| 0153 | `e7c70bbdc2b766c397bff4119cc65cdc2629dfe4e9f8ff21e922d0e869bf2326` | Optional XDVDFS forwarding |
| 0154 | `6f4070f788355d88cf44f37b792a6aceb1e9ead91bc441fe04df800c0a0fc077` | Small-SYSVA local invalidation |
| 0156 | `c416cc97dc1d78028a88827692fc3d9e277e66286912d20193b4365c386707b4` | SYSVA rollback plus ordered XDVDFS forwarding |
| 0157 | `bcc3145cd832beef0918d5ca99244009b56f98b7e59673e074a2b1cebe5f9b33` | Per-request payload association qualification and accurate Advanced label |

## Input/output contract review

| Change | Required contract | Disposition |
| --- | --- | --- |
| 0143 native submit | A command lease continues to name the same active adapter envelope and parent IRP through prepare, submit, cancel, result, and completion. | Retained; exact-envelope and re-entry tests pass. |
| 0145 scalar pin | Eligibility and pin transition remain under one uninterrupted PFN lock and preserve counts, overflow, and deferred-free state. | Retained; only a repeated predicate was removed. |
| 0146–0148 queue, pump, SG | Each parent owns its slot, envelope, child IRP, MDL, and buffer through its terminal completion. Out-of-order completion eventually services every runnable slot. | Ownership and status tests pass. Patch 0157 adds distinct first/last payload stamps to every request in the 1,024-read QD12 randomized completion and buffer-reuse stress; plain and ASan/UBSan builds pass. |
| 0149 FATX extent | A hit maps the requested logical bytes to the same contiguous physical clusters as a fresh FAT walk under `MainResource`; every allocation-chain mutation invalidates it. | Retained; arithmetic, locking, generation, randomized oracle, and full-byte Forza replay pass. |
| 0150 packet prepare | SRB, stack, CDB, MDL, and scatter outputs equal the prior constructor for accepted and rejected inputs; a zero CDB length never reads its source. | Retained; release disassembly and sanitizer matrices pass. |
| 0151 ATA cache capture | Ordinary requests have no cache-publication consumer; IDENTIFY requests publish the same writer/result record as before. | Retained; only unused ordinary-request copies were removed. |
| 0152 ATA timing experiment | Device selection waits until the selected device satisfies the ATA timing contract. | The forced experiment bypasses the normal wait and already produced intermittent freezes/menu corruption. It remains default-off and is not an acceptance profile. |
| 0152 contiguous alias experiment | Returned VA, physical translation, cache policy, and GPU/CPU coherence match the caller-visible allocation contract. | Reference observation returns cached KSEG0 even for WC/UC requests. The alternate alias intentionally diverges and remains default-off. |
| 0153 XDVDFS forwarding | Status, information, bytes, MDL lifetime, cancellation, absolute offset, and `CurrentByteOffset` equal the legacy path. | **Fault found.** Asynchronous forwarding published `CurrentByteOffset` in completion order while legacy XDVDFS publishes in issue order. Patch 0156 keeps asynchronous handles on the ordered legacy path and forwards only serialized synchronous handles. |
| 0154 SYSVA invalidation | Returned VA, PTE/PFN ownership, mapping visibility, revocation before PFN reuse, and free count equal the CR3 path. | Local instruction ordering is correct, but qualification omitted interleaved VA/frame reuse, DMA, MDLs, and Forza. Patch 0155 restores the qualified CR3 behavior pending representative native coverage. |

## Reproduction and validation

The XDVDFS failure was reproduced before the repair with two reads on one file
object. Requests at offsets 0 and 4096 completed in reverse order. The direct
path left `CurrentByteOffset` at 4096 instead of the legacy value 8192, so a
later position-based read could fetch the wrong asset. The regression fixture
passes after asynchronous handles are made ineligible for direct forwarding.

Windows release64 default-off runs compared the pre-0154 and 0154 images with
the complete Forza-shaped fixture. Each completed 16 passes, 16,384 reads,
queue depth 12, exactly 900 available pages, full-byte verification, canaries,
IOSB/APC validation, and cleanup with zero failures. Median intervals were
47,578,263.5 and 47,132,909.5 ticks. This rules out a simple FATX payload mix-up
in the modeled sequence. It does not reproduce real XISO menu reads, GPU
allocation use, frame scheduling, or the sporadic operator failure.

The repaired release64 image then completed the same Windows release workload:
16 passes, 16,384 asynchronous reads at queue depth 12 and 900-page pressure,
with byte oracles, IOSB/APC identity, canaries, and cleanup all passing. The
guest emitted its final TAP pass and xemu exited normally. The runner labels
that capture `correctness: notEvaluated` because the reused managed plan permits
a post-run QMP diagnostic; this prevents the receipt from being used as a
formal performance comparison, but does not alter the recorded guest results.
Evidence is retained under run
`20261016-225122514-e3efb56de2884ac586037d96dd371f5d`.

After the second audit, two clean release64 builds produced identical SHA-256
`bcc3145cd832beef0918d5ca99244009b56f98b7e59673e074a2b1cebe5f9b33`.
Release128 is
`15c77c938d11d1dadd8bdd2b9879dd06c11b2319b644482269310b75f59f405b`;
both assemble source tree `76266ba77fdf73210b3d4dea47ed7922bdc6b0cf`.
The firmware behavior change from 0156 is limited to renaming the Advanced
option from `Optical async reads` to `Optical direct reads`; 0157 otherwise
strengthens the host qualification source bundled with the assembled tree.

The second-audit release64 image completed another Windows release replay in
run `20261017-010257902-098bbb5f2523496a887283394df35e14`: 16 terminal
batches, 16,384 reads, zero workload failures, zero pointer mismatches, zero
byte-oracle failures, and complete cleanup. The process exited normally. The
managed runner again labels correctness `notEvaluated` because its inherited
plan executes one post-run QMP diagnostic, so this is supporting guest-output
evidence rather than a formal performance comparison.

## Release decision

Patch 0155 rolls back the newly reported default-path regression window rather
than retaining an 85% microbenchmark gain with inadequate game coverage. Patch
0156 fixes the demonstrated optical file-position divergence. **All advanced
settings is not a correctness profile**: it combines two reference-divergent
experiments with the ATA timing experiment. Real-game isolation starts with
every advanced setting off, then enables one bit per boot.

The repaired image still requires a matched Forza game test. Test it with all
advanced settings off first. If clean, enable only optical forwarding; test
the contiguous alias and ATA timing options separately and last.
