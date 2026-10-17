# Post-END DVD preparation

One clean/cold Deck method pilot passed on the published 64 MB ROM:
`20261014-211039702-3a13aa70039a4c37a75f9cc172358f16`, completed with exit code 0.
The same recorder `87eb31f8…` and mounted wrapper `6b8c26ab…` performed 1,024 × 4,096-byte
successful byte comparisons with matching statuses/IOSBs/counts, queue depth 1 and zero APCs and
cold-ish. No fixture binary, pause/resume, media change or host policy changed.
[The portable receipt](dvd-post-END-native-receipt.json) pins the exact source,
plan/caller/parser, raw artifact hashes, serial witness and actual context.

The frozen job waits for `STORAGE-PERF-END cases=1 failures=0` before one typed
readonly `query-block` and explicit `post` guard. The caller binds the actual
serialized job.Plan to that exact order and its hash to launch.jobSha256.
The guard drains the owned regular serial file through EOF, checks the existing
strict parser's complete unique successful selected END, then starts mapped
process/config/ISO hashes. Its 134,826-byte serial prefix has SHA-256
`9fa2987dbbaa8dbfea124d18e1f0c8ac165567082eb90a82f73405e1e7e0bed9`.
The receipt retains owner/inode/size/offset/read timestamps; the EOF read completed
before heavy hashing began. Both declared diagnostics completed, actual readonly
wrapper/process lifetime checks passed, and owned stop/evidence finalization
completed during the existing 20-second post-END grace.

The compiled fixture emits END after its measured loop and result records.
This supplies causal order for these post checks without a poll-gap or universal
backend-delay claim. Preflight input/config hashes, exact launch construction and
actual post context support a reviewed controlled-lab continuity assumption.
They do not continuously observe process/media/clock state. Unrecorded external
intervention remains an explicit assumption, and observed pause/reset/input/media,
identity, parser or counter violations must reject qualification.

Raw `operatorActivity.Intervened` remains true: two diagnostics, zero manual
inputs/pauses/screenshots/previews/transfers/host changes. This is not silently
rewritten into performance PASS. An additive reviewed importer policy must bind
exact declared post checks and their raw receipts. The Deck state reports Mesa
namespace verification and ComparisonReady=true, with OS page cache/driver memory
cache and omitted-default limitations retained verbatim. Windows driver-cache
qualification remains a separate unresolved gate; this Deck pass does not change
Windows `run_storage_state` or enable AllowUncontrolledDriverCache.

The exact unchanged opaque released payload is read as `target.xbe` on a derived
wrapper; original-media parity remains open. The inferred concatenated equality
hash is labeled host-inferred and is not a measured in-window digest. The earlier
swap/HDD-first failures and V31 initial/final method are preserved in
[DVD method qualification](DVD-METHOD-QUALIFICATION.md); full36 functionality is
reported separately in [full36 qualification](FULL36-FUNCTIONAL-QUALIFICATION.md).
The paused-beforeboot alternative was dropped because the current runner's
paused-only readiness check conflicts with the reference's fresh PRELAUNCH state.
No known-failing launch or runner workaround was attempted.

Freeze plan `5efaafee834c37c09859ccdcc15b88fefe8fa14125aa56e395fe92171f9681eb`;
outer manifest `ffd324dc5007c99fcf223beb92932a89c0bff8cc79ef21eab60331135b05c549`.
Four actual host guard tests and eight changed caller/order controls pass. This
is post-END functional preparation. A new predeclared A/A schedule, host binding,
actual importer/context-contract pins and count calibration are still required.
No old timing is retroactively qualified. Performance/P1, absolute host clock,
continuous observation, private structural costs and physical-flush/durability
acceptance are not established by this receipt.
