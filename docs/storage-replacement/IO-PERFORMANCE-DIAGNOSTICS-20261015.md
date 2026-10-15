# Storage I/O diagnostic update — 2026-10-15

These measurements refine the pre-extraction baseline for PR #248. They use the
fixed release64 SpiritBoot image `42ad0c392b97d195f6aacaa47b1c168f1f74038ddf3258257b21cfde99bcb647`,
Complex `1de4c87effe40d44f95581d204f9fa0600fbd5fe2171692316dcf97af0f4113f`,
and xemu `14777b55740706608cdfde97349eefa3d5115ece4c889679c9c8b96641a85f2d`.
All native runs used 64 MiB, the interactive user PowerShell pipe, separate
runner-created HDD overlays, and post-run overlay deletion.

## Queue depth and memory pressure

The ten-run V3 campaign covered five warm dataset-0 leaves: QD1 and QD4 at 0
and 900 pressure pages, plus QD12 at zero induced pressure. Every run passed the
full byte, canary, status, callback, cleanup, and shutdown checks: 10,240 reads
and 108,712,960 bytes with zero failures.

SpiritBoot was about 1.96 times Complex at QD1 under both pressure settings.
Both BIOSes sustained caller occupancy close to one, and pressure changed QD1
batch time by only about one to two percent. Queue starvation and the 900-page
condition are therefore lowered as primary causes. SpiritBoot's QD1 median was
about 1.44 times Complex while its p95 was 4.58–4.64 times Complex, which raises
a tail-heavy per-request or lower-service path.

This expands observed V3 functional coverage from one to six distinct leaves.
Each added condition has only one descriptive pair; the earlier repeated
QD12/p900 work remains the stronger repeat-order observation.

## Public call-return split

V4 recorded a timestamp immediately after `NtReadFile` returned. Its initial
pair suggested that most of the positive SpiritBoot/Complex component gap lay
inside the public call. A later A/B/A control exposed a flaw in V4's oracle:
the completion APC can legally enter before the caller executes its post-call
timestamp. Data, status, count, callback identity, and canaries were correct in
those rejected records. V4 is retained as evidence of the recorder defect and
must not be used as a general correctness gate.

V5 accepts both completion orders. Its current/worker/current sequence passed
3,072 reads and 32,613,888 bytes with zero failures. Forcing the established
filesystem worker route took 1.6475 times the mean current-BIOS batch time and
1.9048 times its issue-through-return sum. Removing the direct asynchronous
path is rejected as a performance fix.

The V5 native result is binary-bound diagnostic evidence. Its scratch
`source-provenance.json` inherited V3 hashes for files changed in V5, so it is
not presented as source-reviewed evidence. The manifest, payload input hashes,
native logs, verifier, and output remain retained; no V5 source is promoted into
the product by this note.

## Raw-device discriminator

V6 bypasses FATX and replays dataset zero through the public whole-disk handle
inside a fixed scratch window on disposable overlays. The counterbalanced
SpiritBoot/Complex/Complex/SpiritBoot sequence passed 4,096 reads and
43,485,184 bytes with zero failures.

| Metric | SpiritBoot mean | Complex mean | SpiritBoot / Complex |
| --- | ---: | ---: | ---: |
| Batch ticks | 49,634,347 | 32,731,197 | 1.5164 |
| Issue through `NtReadFile` return | 19,763,472.5 | 6,168,347.5 | 3.2040 |
| Return through APC entry | 29,196,928 | 25,583,140.5 | 1.1413 |

This proves that the gap is not confined to FATX. Comparing these descriptive
raw means with the V5 SpiritBoot FATX mean and the earlier V4 Complex FATX
sample attributes roughly 55 percent of the observed FATX batch gap to the raw
path and 45 percent to unequal added file-path cost. The sessions were separate
and the Complex FATX side has one sample, so this is a root-cause discriminator,
not an acceptance statistic.

V6 also found a public behavior difference. All raw seed writes succeeded, but
`NtFlushBuffersFile` on the whole-disk handle returned
`STATUS_INVALID_DEVICE_REQUEST` on SpiritBoot and success on Complex. The probe
records the exact status, closes and reopens the handle, and then requires every
read byte. Both SpiritBoot runs were byte-exact, establishing immediate
coherence in xemu. Reset durability and raw-flush compatibility remain open.

The subsequent [clean-room boundary review](independent-implementation/raw-flush-adapter/README.md)
executes the existing independent request core and confirms that its ordered
`SYNCHRONIZE CACHE(10)` primitive is already correct. The missing correction is
in the installed public dispatch, lifetime, lower-packet and cache-qualification
seam. The approved inputs do not yet define that seam sufficiently for a safe
production adapter, so the review records the eight required interface groups
and an executable failing contract instead of mapping the public error to
success.

## Decision and next boundary

Keep the current direct FATX path in the pre-extraction baseline. The next
replacement and optimization work must preserve its behavior while addressing
both the lower raw I/O setup/dispatch cost and the added FATX cost. A candidate
must also define and test whole-disk flush behavior; successful immediate reads
do not substitute for a durability contract.

These campaigns are diagnostics. They do not provide the frozen A/A calibration,
powered sample count, two-host acceptance, physical Xbox result, completed
storage replacement, or license closure required by the implementation plan.
Exact evidence hashes are recorded in
`io-performance-diagnostics-20261015.json`.
