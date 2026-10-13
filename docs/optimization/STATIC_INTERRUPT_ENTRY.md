# Keep Xbox interrupt entry code off mutable pool pages

The remaining Forza request replay gap exposed an expensive write in the IDE
completion path. SpiritBoot's disk-channel data and an executable native
interrupt stub occupy the same physical page. The candidate routes the sixteen
PIC vectors through fixed kernel text and keeps their interrupt-object pointers
in a separate 64-byte table. It preserves the existing dispatchers, device
callbacks, acknowledgement, IRQL handling and interrupt chain lifecycle.

The measured combined prototype is based on async4; the packaged PR is based on PR233. It excludes the public thread prototype
whose broader I/O qualification subsequently found a compatibility regression.
No release or Forza gameplay acceptance is established.

## Evidence identifying the mechanism

All diagnostic runs use the owned kernel source and public request replay, with
no proprietary instruction inspection. PM-timer instrumentation first placed
about 5 ms per 1,024 reads inside a few completion bookkeeping operations. A
second diagnostic using RDTSC, independently calibrated against the PM timer,
reproduced the cost. Clock and local-store controls exclude a timestamp-only
explanation: status-byte write 0.134–0.192 ms, channel bitmap update plus success
branches 4.863–5.181 ms, subsequent task-file flag check 0.141–0.186 ms per 1,024
reads. No task-file save or command error occurs in any of the 12,288 reads.

The metadata-only v5 extension passes all 19 replay checks and reports:

| Owned object | Virtual address | Physical address |
| --- | --- | --- |
| IDE native KINTERRUPT | c102d408 | 03baa408 |
| Its executable DispatchCode | c102d444 | 03baa444 |
| Channel ActiveSlotsBitmap | c102d868 | 03baa868 |
| Request SrbStatus | c10035c4 | 03bf85c4 |

Thus the hot channel write and executable dispatch stub share physical page
03baa000. IoConnectInterrupt allocates the native object, including copied
instruction bytes, from the same general pool used for mutable driver data.
The user's xemu revision routes writes to pages containing translated code
through `notdirty_write` and `tb_invalidate_phys_range_fast`. In this revision's
Xbox build, `#ifndef XBOX` disables the precise byte-range overlap check:
system-mode traversal invalidates every translated block on the physical page.
Consequently even the disjoint channel write invalidates the executed stub;
the following interrupt must translate it again. Later data writes become cheap
once the page has no translated code. This corrects the earlier report, which
missed the compile guard and incorrectly described only a range scan. The
source route and native addresses establish this mechanism; host translation
counters have not quantified its individual contribution to the measured gain.
See [the exact source audit](static-interrupt-entry-2026-10-13/code-page-mechanism.md).

Diagnostic v4 ROM: 786ca4d65b7fa4838557fbf0097f7be180dc23ed3b601dedf6bb70867c24915e.
Diagnostic v5 ROM: f6ea48bcb12d0154d9eec48016fb228bc94070ba74933428cf8aa11edd7bd83f.
Run directories and detailed analysis are owned by `storage-cost-agent`.

## Implementation and lifecycle

Sixteen aligned entries in kernel text push their vector index and branch to
one shared existing trap-frame prologue. The index temporarily occupies the
synthetic error-code slot; after saving every register, the common entry loads
the native object from the table, clears that slot, and invokes the existing
KiInterruptTemplateHandler. The original object layout is unchanged.

KiGetVectorDispatch recognizes only the corresponding fixed entry as owned.
Other IDT handlers remain unknown/unconnected as appropriate. Connection,
chained head replacement and disconnection publish the table and IDT route
with interrupts disabled, restoring the caller's previous interrupt state.
The native chain algorithm and HAL enable/disable behavior are unchanged.
Desktop builds keep their original dispatch route.

The built release64 image adds 516 bytes of text and 64 bytes of BSS. All section
virtual addresses and mapped page counts remain unchanged. No new pool
allocation, page reservation, per-request state or cache is introduced.

## Validation

The actual-source host fixture first fails the intended fixed-code dispatch
contract on the baseline (2 of 5 initial assertions). The candidate passes
2,236 assertions covering all sixteen vectors, enabled/disabled entry state,
normal and shared dispatch, middle/head/last removal, reconnect, rejected
sharing, invalid vectors and failed HAL enable rollback. ASan/UBSan are enabled.
The same matrix passes against the exact built source.

Owned compiled-code inspection verifies all sixteen entries are at 16-byte
strides, the shared prologue saves registers before scratch use, and the object
table and both IDT halves are stored before interrupts can be re-enabled.

The maintained public interrupt XBE passes 17/17 on Complex and the candidate,
including actual NV2A interrupt delivery, public object/context identity,
deferred event signaling, disconnect and neighboring guards. Runs:
`irq-static-public-stock-{complex,async}-20261013-142539-{1,2}`.
Broader regression, checked-build and uninstrumented performance results follow.
A passing interrupt probe alone is not a complete firmware verdict.

Candidate source tree: 6108cf4b697353bada1f9fa9df923db9d84054a8.
Candidate ROM SHA-256: 913293b4a86eac808313555867aa3099aba40903cc17a63c3c424b89a5c5dd77.
Patch SHA-256: 37d864ce713857c6f9ed95480d85d60548f4f8542ff423d54d5a357be265407f.
Local ROM: `irq-static-release64/flash.bin`.
Lab ROM: `C:\xemu-lab\incoming\forza-api-native-20261013\irq-static-candidate64.bin`.

## Measured uninstrumented improvement

On the original xemu executable, six serialized runs used
Complex / async4 / candidate / candidate / async4 / Complex order. All runs
pass 19 checks, all 72 phase hashes match, and all pressure phases begin and
end at exactly 900 available pages. Depth-12 pressured batches average
75.847 ms on async4 and 48.736 ms with this change: 35.74% less elapsed time.
Complex averages 44.690 ms in the bracketing controls, leaving a 9.05% gap.
These means combine two runs and two recorded request sequences; they are
not a statistical confidence interval or proof of full-game scene behavior.
Every tested depth/memory group improves, with reductions of 24.9–35.7%.
The full gain is not attributed solely to the isolated completion bitmap write.
A guest timestamp at IRQ entry cannot measure translation performed before
that entry executes; invalidation, translation and subsequent execution costs
have not been separately apportioned.

The prototype additionally passes the broad 639-check API suite on both
release64 and debug64, and the 17-check interrupt probe on debug64. The checked
image was built in the existing firmware toolchain container after the outer
host failed on missing 32-bit libc headers; that environment failure is retained.

## Packaged PR artifact

This PR is based on PR233, and introduces only the static interrupt route and
its maintained tests. Its separate packaged release64 ROM is
7451c5c3200f03eb544621b314ea582a96345a70e325a361fe08123385669b17, source tree
97b9fa45c2f6f4a2a8607ad5b0ed0cfc32b8c6aa. The measured combined prototype also
contains PR230's critical-section owner fix; that fix is held constant in the
async4-versus-prototype comparison and is not introduced by this PR. The
packaged runtime differs from the prototype only by that pre-existing owner
change; the interrupt patch also corrects a comment to acknowledge that the
legacy object template is still copied, although the IDT no longer executes it.

The product suite passes 129 tests with three existing optional skips. The
exact packaged source passes all 2,236 actual-function lifecycle checks. CI
runs those checks and validates the assembled sixteen entry strides, jump
target, trap-frame allocation and executable/data section separation for all
four firmware profiles. All four firmware CI profiles pass at implementation commit decc35d1. Exact
packaged native results follow. The PR remains a draft pending integration
and game-level acceptance.

Each fix retains its API contract and evidence. No ATA acknowledgement or wait,
interrupt callback, cancellation contract or memory-pressure threshold is
relaxed by this change. Physical Xbox behavior has not been measured here.

## Completed packaged qualification and paired attribution

The exact packaged release64 image passes 10,898 native assertions across its
API suite (639), public interrupt lifecycle (17), IOSB/APC contracts (338),
seek/mutation (2,071), and outstanding I/O lifetime/rundown (7,833). Each full
numbered sequence, fixture/ROM identity and normal process exit was verified.
A separate cross-branch control using PR230's stronger owner fixture fails
13 checks on both the unchanged PR233 base and this packaged image: five
known owner-identity assertions return before releasing critical regions,
causing eight later APC checks to fail. This is retained evidence of the
missing sibling owner fix, not a newly introduced interrupt failure. The
combined prototype includes that fix and passes the stronger API fixture in
both release64 and debug64. No failed control is counted as a passing fixture.

A matched RDTSC pair on async4 with/without fixed entries accounts for all
24,576 reads and proves that the actual IDE IDT entry moves from physical
03baa444 to 03402490. The channel and native interrupt object keep exactly
their original addresses; only the executed entry moves. Completion bitmap
time averages 5.025→0.124 ms per 1,024 reads. The newly measured submission
stores were already cheap (about 0.12–0.28 ms), so the entire 27 ms throughput
gain must not be attributed to six expensive channel stores. Other observed
completion spans shrink, but nested and intrusive timings are not additive.
See the matched-attribution report for complete/quiet coverage and controls.

Stage13 evidence archive SHA-256:
544053fc49167c90f1a18e3afbfbd5a094e6f1bb90aa1c226d57d15bd4a95231.
It contains only diagnostic logs/configuration/receipts, excluding HDD and
EEPROM data. The native qualification JSON preserves both inherited-failure
controls and all successful exact-image receipts.

## CI receipt

All 13 reported checks pass at code commit
`decc35d11b02907d05225db76ae9e1f15d5839c1`, including release/debug firmware
for both 64 and 128 MiB, host tests, setup and plugin contracts. The PR workflow
is [38415108614](https://github.com/Mainkill1/SpiritBoot/actions/runs/38415108614);
the branch workflow is [38414965831](https://github.com/Mainkill1/SpiritBoot/actions/runs/38414965831).
The attached receipt records exact job URLs and completion times. Subsequent
documentation-only commits do not change the measured patch or firmware.

A second independent review reproduces all 2,236 actual-source checks and the
assembled-entry checks on the packaged source. It independently checks the
six raw replay logs, all 114 assertions and 72 phase records, and recomputes
the stated 35.7438% reduction. The original xemu executable's retained-symbol
disassembly also confirms the broad page-invalidation loop is present in the
actual tested binary; no runtime retranslation count is claimed. Both review
and owned-executable evidence are retained beside this writeup.
