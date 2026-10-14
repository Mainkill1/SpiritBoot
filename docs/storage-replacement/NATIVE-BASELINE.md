# Native storage baseline evidence, 2026-10-14

**P1 remains INCONCLUSIVE.** These are real published-ROM observations and
measurement-method pilots, not an accepted full-matrix calibration or candidate
performance result. No full replacement candidate performance run was executed;
the partial geometry lab ROM ran only its public-query/private-file probe.
Missing measurements,
launcher failures and plan/order mismatches remain visible. **All V1 inferred
integrity and write-persistence claims are revoked following source review.**
The immutable V1 records are observations with known false-positive checks.
Both runners stopped at their configured free-space minimum. Separate
parent-owned recoveries restored capacity. Corrected fixtures completed bounded
byte-fill, public-query and lifetime qualification on both hosts; Deck also
completed clock-observation collection. The [Windows receipt](WINDOWS-NATIVE-QUALIFICATION.md)
preserves its failed V23 deadline and successful fresh V27 checks. P1/full-matrix
calibration and normative clock qualification remain incomplete; real
flush/durability and private structural evidence remain missing.

## Approved hosts and unchanged baseline

The user subsequently approved the actual Windows host at `10.0.7.1` alongside
the Steam Deck at `10.0.0.42`, replacing the earlier assumed i9 requirement.
The runner's Windows hardware inventory identifies **AMD Ryzen 9 6900HX**, 16
logical CPUs, approximately 16 GiB, NVIDIA RTX 3070 Ti Laptop and AMD graphics,
Windows 10, machine `DESKTOP-52C4KS5`. Its observed power scheme is High
performance. Results from this host are reported separately from Steam Deck;
they are never labeled i9 results or averaged across machines.

Steam Deck inventory identifies `MainDeck`, AMD Custom APU 0405, eight logical
CPUs and SteamOS. A later read-only host-control capture observed:

- CPU governor `powersave`, driver `amd-pstate-epp`, all eight CPUs; configured
  frequency bounds approximately 1.7026–3.5013 GHz.
- Kingston `OM3PDP3512B-A01`, firmware `EDFK0S03`, nonrotating NVMe, 512-byte
  logical and physical sectors.
- GPU performance policy `auto`, AC online, battery full at 99%, and the exposed
  ACPI thermal sensor at 50 °C. This single observation does not establish a
  sustained CPU/SSD thermal envelope.

No power, governor, global cache, shared HDD, EEPROM or existing title save was
changed. HDD runtime copies use the runner's immutable clean FATX catalog seed
`pr256-clean-fatx-compat010-v1`, SHA-256
`78af83a6c8a1f84cefd37b811a4197419ace68e09ad197376ca9bb2cca05e56b`.
Each attempt receives its own writable HDD and EEPROM and fresh xemu process.

The ROM is the exact published `SpiritBoot-v1.0.0-64MB.bin`, 524,288 bytes,
SHA-256 `c630d22f2353d3898024d510f0b402b64bccdb331781fe7885389f73d6200853`.
Its release build metadata records assembled source tree
`3c23ea01cf43c2979c4c3ef247236e03d079f465`, Roswell base
`1569e2e89fb47cc72b9c704a8884f98200432bd4`, the ordered patches through 0125a,
release/ROM-kernel, 64 MiB, no pool audit or per-I/O diagnostic tracing. The
linked PE SHA-256 is
`7fba000d149eef7af5ca6145e7fffce6314424bab671c85c3aab901eb575e3f8`;
unstripped PE is
`35631dbff4499ccb6d45624c6b3c9e61146b75796be1ee1d63580b0499b35c5f`.
PR composition changes were documentation-only when this capture began.

Native emulator pins differ by host and remain constant within each cohort:
Deck `ee9baadc62679bab44ea937e465b95059304ce5a19db33835932b2350a12b0ba`;
Windows `8a1cbacd133450ab4311bb08c4a8cf9efd1a296d47eae3bf6d094097ca0c343d`.
The authored config fixes OpenGL, 1280×720, vsync off, 64 MiB, DSP JIT enabled,
application shader caching off, independent runtime HDD/EEPROM. Actual original,
effective and final configs and verified input manifests are retained per run.
The nxdk fixture checkout is `29638d0b001f179b73c3513489af10ddc2986216`;
Clang 19.1.7 built the new public-API fixtures. Its dependency working state is
not asserted clean; the fresh-case method plan pins its actual generated fixture
bytes, source snapshot, tool inputs and catalog separately. This method freeze
does not qualify the complete acceptance experiment.

## Windows desktop pipe requirement

The user's later clarification requires graphical Windows launch through a
PowerShell pipe into the live Codex desktop. Earlier session-1 .NET launches
are retained as **provisional method evidence**, and are not retrospectively
claimed to satisfy this requirement.

The owned launcher now checks the actual Win32 window-station/desktop names
`WinSta0`/`Default` before starting PowerShell. A per-job
`NamedPipeServerStream` server and client both run as desktop login Codex in
session 1. The protected pipe DACL grants only that user's SID full control.
The client verifies server identity, session, PID and desktop before sending a
one-use request. The pipe accepts only `PROVE` or `RUN` for the immutable owned
job; it accepts no arbitrary executable, path or command from the client.
The server records the exact xemu command, server/child PID and child session,
waits for exit, drains output and closes the pipe. No service/admin GUI launch,
ExecutionPolicy change or `Bypass` option is used. Reviewable PowerShell source
is compiled into the launcher as ordinary inline commands.

A no-guest proof completed at run
`20261014-091943332-ec600bd46236424d931026e3c0e63ca6`: matching Codex/session 1
client and server, verified handshake, protected owner-only DACL and
`WinSta0/Default`. The runner labels this intentionally no-QMP/no-guest job
`runnerFailure`; it is pipe setup evidence, not a performance pass. Read-only
pipe enumeration retained the existing PSHost pipe names. No dedicated prior
desktop bridge was documented in the scoped handoffs.

An actual guest subsequently completed through this pipe at run
`20261014-092454983-c94dca0ec3b04aa79724e5e64b28367d`: pipe server PID11816,
xemu PID27364, matching Codex session1/WinSta0/Default, verified `RUN` handshake.
Its two 1,024-read exploratory phases reported zero failed conditions.
The V1 reused-buffer limitation means these reports do not prove full byte fill. All newer Windows fresh-case attempts retain the actual pipe and child
receipts. The read-only storage association query maps package/runtime drive C:
to physical drive0, Samsung PM9A1 NVMe 1024GB, firmware36308229, 512-byte sectors.
The secondary drive is Samsung SSD980PRO1TB, firmware5B2QGXA7; it is not the
measured runtime drive. USER thermal WMI access was denied and remains recorded;
CPU/SSD temperature is unknown. Runner GPU temperatures remain in raw metrics.
No administrative query or setting change was attempted.

## Captured workload families

Owned source lives in `tests/xbe/storage-perf`; the protocol parser is
`tools/storage_native_runner.py`. No class/disk/private driver implementation
was consulted for these fixtures. They use public Xbox APIs and independently
generated bytes.

| Capture | Executed work per process | Evidence and limits |
| --- | --- | --- |
| Aligned small HDD read | First-use and declared warm phase, each 1,024 × 4 KiB; 4 assertions/read | Five independent paired processes/host; reported zero failed conditions. V1 reused buffers and nominal counts leave full byte-fill integrity unqualified. First-use follows fixture seeding and does not prove cold host pages. Both phases share that fresh process. |
| FATX request metadata replay | Two exact 1,024-request offset/length/alignment lists; QD 1/4/12; normal and actual 900 available pages; 12,288 reads/process | Reported QD high-water 1/4/12, one APC/read and 61,440 nominal conditions/process. V1 buffer reuse/short-circuit checks remain unqualified. Original game resource media was unavailable through the permitted import API; no game-media or title parity claim. |
| Optical owned payload | 1,024 × 4 KiB from an independently generated 4 MiB XISO file | Reported data/status/count; reused V1 buffer is unqualified. One owned ISO, not the two required released suites. |
| Scatter/gather layouts | 1,024 × 33 pages each, adjacent and nonadjacent page lists | Reported data/status/bytes and unused-page canaries; V1 output reuse leaves byte-fill proof unqualified. 33 pages is a declared request shape; lower split/PRD/command counts remain unobserved. |
| Write/API-flush/reopen | 1,024 × 4 KiB write, API flush, close/reopen/read verification | 1,024 reported successful API flushes; old persistence=1 is unsupported because readback reused the just-written expected buffer. ATA cache-sync observation, reset/abrupt-stop durability and actual device-flush counts remain missing. |

Cheap fixture timing uses direct guest RDTSC around each caller operation and
consumer byte/status verification. Five 100 ms QPC-reference calibrations and a
back-to-back counter-overhead probe run outside measured batches. Overhead is
recorded, not subtracted. Firmware per-I/O tracing and diagnostic clocks remain
disabled. Serial formatting/output occurs after each measured batch. These
earlier grouped prototypes remain exploratory. The newer fresh-case method
freezes the exact first-issue/last-consumer-ready batch endpoints and explicitly
separates cache preparation, while leaving missing acceptance gates visible.

The first small-read pilot plan declared five pairs before capture, alternating
AB/BA; both arms were the same ROM. Its stored plan SHA-256 is
`c958adae36be279f6dd8269f9c0630ec063eee943bab32b714915f8b71bc747f`.
Queuing several requests allowed runner ID ordering to alter the intended
alternation. This mismatch is retained. Future paired capture must submit and
wait sequentially, then validate actual start order.

The first pilot reported 20,480 reads and 81,920 nominal conditions per host,
with zero reported failures. Full byte-fill integrity is unqualified after review. Exploratory one-sided 95% upper ratios for batch
latency, using Student t on the five independent pair log ratios, were:

| Host | First-use | Warm |
| --- | ---: | ---: |
| Steam Deck | 0.9666 | 1.9105 |
| Approved Windows Ryzen | 1.0491 | 1.0994 |

These exploratory bounds do **not** pass calibration. A Deck warm pair contained
an observed batch of about 344.7 ms versus 979.9 ms; this outlier and all other
runs remain in the report. The small subset, order mismatch, uncontrolled host
caches, missing structural counters and missing broader independent pairs
prevent a powered full-matrix conclusion.

## Public query and persistence survey

The latest v3 survey produced matching status/data observations for 210 control
calls per rig: whole HDD, Partition1 and optical handle; geometry, extended
geometry, length, device number and partition information; output lengths
0/8/11/12/16/20/24/32/40/56/64/112/128/256.
Output buffers begin as 0xa5 and IOSBs as 0x5a. Complete trailing bytes are
preserved; failed calls are never decoded as successful output.

HDD extended geometry: 0/8/24 return `c0000023` with unchanged IOSB; length32
succeeds with Information32, length40 with Information40. At length40 the
returned DWORDs at offsets32/36 are record-size0/style0; lengths56 and larger
return record-size24/style0. Observed Information values for lengths
32/40/56/64/112/128/256 are respectively 32/40/56/64/112/112/112. These are byte-level observations, not a normative
claim that style0 is correct for Xbox BRFR or that a partial record is safe.
The proposed BRFR128/complete-record policy requires explicit parity review.

Length information succeeds at length8 and larger with Information8. Device
number fails at lengths0/8/11 and succeeds at exactly12 with Information12;
lengths16/20/24 and larger also return Information12 and retain initialized
trailing bytes. Whole-HDD output is type7/device0/partition0. Error paths retain
caller IOSB poison `0x5a5a5a5a`/Information1515870810. That syscall observation
cannot establish the internal driver's Information field; the structured
summary explicitly leaves it unknown.
Mounted optical extended geometry/length and root-handle reads return
`c0000010`; these handle observations do not establish lower optical capacity
or sector behavior. Whole-HDD flush returns `c0000010`; Partition1 and the owned
regular file flush calls returned success. The old 4 KiB write/reopen
observation used a weaker zeroed readback buffer and did not freshly poison its
write/flush/read IOSB. Its persistence report is unqualified; the earlier
independently initialized control-call status/data records remain useful byte
observations. No-disc, device cache-sync and reset persistence remain unobserved.

## Frozen fresh single-case A/A method pilot

The new baseline-only method plan is frozen at workspace-local
`.scratch/pr248-native-baseline/frozen-single-case-v1/plan.json`, SHA-256
`71d3bece8a0dc416a6c94fa575e5fbb19be62e3c23abb0e6f32372174ac8592f`.
Its exact suite ISO is
`02c8b038eab6e216cc5957203b3aa485d14e59128e0b005d8091a46fe55a2515`;
the 34-leaf catalog identity is
`sha256:a99caf1b57a7f60a67d87a5351a1f2f0aff2244d40d7258bcf9cb02fe0678fd8`.
The frozen directory retains a hash-verified source snapshot, generated ISO,
host launchers, metadata/case checksums and exact run order. Every A and B arm
uses the identical published 64MiB ROM; no candidate timing was captured.

There are five pairs per case per host: 340 scheduled fresh processes on each
machine. Each process executes exactly one selected case through the supported
runner-injected private prepared FATX configuration slot. The matrix includes
aligned small reads, both 1,024-request metadata sequences at QD1/4/12 with
normal/900-page pressure, write/API-flush/reopen and both SG shapes, separately
under warm/cold-ish preparation. Two owned-DVD payload cache cases are auxiliary
and do not fulfill the two required released-suite DVD variants. Those required
ISO hashes are pinned as explicit missing coverage in the plan:
`8d01028844e508629d3f73481714ad46ea9931ba55f35956f28d7121f9eba475` (clean) and
`099d161a6010499cb86be58ccd2297a8be8802d8b8f4b97f7ef720ff5d0d6d33` (performance).

Both hosts submit, wait for completed archive, collect and append one record
before submitting the next job. Pairs alternate actual AB/BA, and observed UTC
start/finish times remain available for order validation. Warm cases run one
complete matching verified warmup outside timing. Cold-ish cases have no
intentional read warmup, but independent file seeding/API flush occurs first;
host page/device caches remain uncontrolled. Pressure cases restore900 pages
after warmup and record pages before/after measurement. The first verification
showed warmup reducing900 to895; that retained method observation led to explicit
pressure restoration before freezing the current suite.

Append-only observations are in `deck-fresh-single-case-v1.jsonl` and
`win-fresh-single-case-v1.jsonl` under the native scratch directory. Each line
records schema version, frozen plan/collector hash, schedule index, host/case,
pair/arm, job/run/PID and UTC times, raw artifact location/hash, manifest,
config/state contract and runner outcome. Native values retain full per-operation
latencies, elapsed batch time, reported operations/bytes/nominal conditions, observed QD,
starting/ending pressure, APC/read/write/API-flush counters and clock frequency/
overhead. Windows records also include matching actual named-pipe child receipts.
Submission, timeout, incomplete-output and correctness failures remain records.
Unobserved private structural counters and real device cache-sync counts remain
missing; API flush success is separately counted and cannot populate them.

The earlier `integrity-policy-v1.json`, SHA-256
`7cbd9af327fb8e1a05b19c703582adfb2bde3275b91670e2f1ba0a70afe10e87`, accepted
host-inferred expected SHA only as a deterministic implication of complete
exact-byte equality. Source review then disproved that premise for V1:
write readback reused expected input, repeated DVD headers stayed initialized
after the first read, and other reused outputs could mask missed/partial fills
at repeated offsets or pattern collisions. Old automatic IOSBs could retain
indeterminate/stale values after errors. Nominal N*4/5/11 conditions were not
actual executed counts on short-circuit failures.

`integrity-policy-v2.json` preserves that revocation; corrected reanalysis uses
`integrity-policy-v3.json`, SHA-256
`e616fb7189ae2a3c0cd459490e643c34b5fec42ba30e79c10928a1f95289494f`.
The parser now retains fatal `STORAGE-PERF-ERROR` and TAP `not ok`, refuses
inference when present, and rejects protocol records after END and contradictory
framing. The absence of these records in a captured run does not qualify the
formerly permissive parser. V2 inference additionally requires
`fixture_generation=2` and the pinned corrected source/media/seed/case policy.

Raw JSONL lines, V1 ISO/source snapshot, original parser snapshot, launchers and
old inferred-sidecar history remain unchanged. Separately versioned
`*-fresh-single-case-v1-reanalysis-policy-v3.jsonl` binds original line, serial,
manifest, result, new parser and policy hashes. It records corrected parser
issues independently from raw runner/native statuses, and retains preflight
failures as unstarted attempts. Every V1 row has integrity unqualified,
`assertions_executed=null` with its old nominal count retained separately,
`durability_verified=null`, and no inferred digest. Descriptive timing ratios
are not comparison-eligible. The stopped matrix contains 149 completed Deck
runs plus one unstarted failure, and 312 Windows runs plus one unstarted failure.
There are zero qualified integrity rows on either host.

V1 Windows normal completion provides a happy-path exit chain: the client waits
for its server, the server waits for its actual child, and all return zero.
Source review found that timeout/error paths lacked bounded child/server
cleanup and descendant containment. The external runner calls
`Kill(entireProcessTree:true)` only while its tracked parent has not exited
(`RunnerEngine.cs:987`, `1570`). That cannot guarantee rundown of descendants
left by an already-exited wrapper. V1 timeouts are therefore never upgraded to
confirmed child exit or fresh-process qualification.

## V2 corrective fixture, locally qualified only

V2 independently initializes every operation IOSB to 0x5a and every expected
read byte to its exact bitwise complement before every read, including warmup.
Write verification uses a separate poisoned readback allocation. Its initialized
status/count/data predicates are evaluated with bitwise combinations, and the
replay completion path counts the checks it actually executes. Full byte
comparison remains inside each caller-to-consumer-ready interval. Poisoning
occurs before that operation's tick; between-operation poisoning/loop work is
included in the first-issue-to-last-ready batch duration and is not subtracted.
The protocol version stays1; metadata separately declares fixture generation2.

Actual-source host fault tests execute `families.c`, `dvd.c`, `query.c` and
`windows-launch.c` against synthetic public ABI outcomes. Full fill succeeds;
no-fill/partial/untouched-IOSB/error reads fail verification. DVD first-fill then
1,023 no-fill successes reports 1,023 failed comparisons. A flush error leaving
IOSB untouched preserves caller poison instead of the preceding write result.
The Windows lifetime test exercises normal completion, client timeout,
assignment failure, unsuccessful rundown and failed accounting query. All24
focused tests pass. These are meaningful fault regressions, not native timing
or proof of Windows runtime job compatibility.

The V2 Windows wrapper owns an anonymous noninherited JobObject with
`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, creates its PowerShell client suspended,
assigns it before resuming, and refuses an uncontained fallback on assignment
failure. It bounds the client wait at170s and owned-job rundown at5s, clears
owned descendants after client exit, and requires observed ActiveProcesses0.
PowerShell additionally bounds guest120s/client completion145s, output drains
and exact Process-object cleanup. It records client/server/child identities and
lifetime receipts. Job inheritance and kill-on-close follow the public
[Windows job-object contract](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects).
No unrelated process name/PID sweep, service/admin GUI launch, ExecutionPolicy
change, host power change or global control is used. Windows native successful
launch and controlled timeout qualification remain pending the parent operator
capacity authorization. Deck uses its foreground runner process and a separate
runner-timeout contract.

`reopen_readback_verified` describes qualified V2 poisoned close/reopen equality.
It cannot populate `durability_verified`, which stays null until actual device/
reset persistence qualifications. API flush count and actual device-command
count remain separate; real flush/private structural counters stay missing.

The local V2 freeze is
`.scratch/pr248-native-baseline/frozen-fixture-v2/manifest.json`, SHA-256
`2a27d4597ff98a56fb5aeeba1ec78b8dbf4e5354f943e5d5707b0c96ff9ea665`.
Its50 individually hashed inputs include copied source, generated references,
parser/tests and build logs. The source/input hash-manifest is
`8563014cd54828b5240accaa37163dda60d5b90f746c299b17e7e24dc1359919`.
Corrected suite/DVD-recorder/query ISO pins are respectively
`2c89b0a693e862e4b2b6b97c29d74ded491c9477ff8359a597d2266e9b69f82b`,
`d7da2a23350306d07a2579edfa6b24c1c6302a5ddb871e4d0f245f505a0ba222`, and
`89f7570875fb27d30a0a3a2022d3c71dfeddef0c0533e610f02ab4e4b71d08a3`.
Windows launcher pin is
`366531cbfcdc4d2f81b4033a6d56c669b5ff1d051c0177fc826b444655ff090f`.
The query boot ISO is655,360 bytes, matching its declared optical-tail offset.
This source/artifact freeze has0 native runs and explicitly does not freeze a
viable performance acceptance plan. Native qualifications will be separate new
cohorts and receipts; V1 observations and pins remain immutable.

## V2.1 retained attempts and V2.2 corrected qualification

The parent completed separate Deck operator recovery: 298 files verified,
296 identical immutable duplicate files sharing two anchors, every path/byte/
result preserved, free bytes increased from971,841,536 to22,254,170,112. The
receipt is `.scratch/pr248-operator-recovery/deck-apply.jsonl`, SHA-256
`863ba32d563f10306e7f7e839af5778dfc21886c51a2c1ff31f477560c373a72`.
Normal native testing performed no archive cleanup or host-policy change.
At the V2.1 freeze, Windows was blocked pending separate operator authorization.
Its later recovery and bounded V27 checks are recorded in
[Windows qualification](WINDOWS-NATIVE-QUALIFICATION.md).

V2.1 plan SHA-256
`174e74d2f88a8fe3d9ae271a820c228649555458b12da712acaa84674ded61f1`
produced two fresh Deck runs against the exact published untraced64 ROM:

| Owned job | Run | Raw outcome |
| --- | --- | --- |
| `pr248-native-deck-v21-normal-small` | `20261014-123555723-3def302426df41cc82e0b7aae3c1cdac` | Runner completed/exit0; 1,024 reads,4,194,304 bytes,4,096 declared conditions,0 failures |
| `pr248-native-deck-v21-public-query-reference` | `20261014-123805215-7ba4fd47b7d144478486c3800a2a85dd` | Runner completed/exit0; original collector failed qualification with missing `SeedSha256` |

Both raw rows remain unchanged in `deck-v21-qualification.jsonl`, SHA-256
`51cd75a1fe6c9ce9dbb74ea6f63f7fe37be8ec34e0e322612b8db986805de62d`.
Review found four Important qualification defects: direct-copy seed lineage
uses `Sha256`, prepared-XISO uses `SeedSha256`; a second literal-space scan
could skip tab-separated operation checks; query END/matrix checks admitted
invented records; lifetime grading admitted arbitrary failed outcomes.
V2.1 qualification claims are superseded and pending corrected reanalysis.
Its fixtures, parser, raw evidence and failure history remain preserved.

V2.2 freezes the corrected parser and collector in
`.scratch/pr248-native-baseline/frozen-fixture-v22`. Manifest SHA-256 is
`872cfa6c0a5863149be61391ebfd694b2f83101ebca5ee31011a4f89a12ccd50`;
qualification-plan SHA-256 is
`59fdd837e3c8ed14b6e6aeeec25085bf2c21aeb3b9c38f93d14f34b520a00dc6`;
parser SHA-256 is
`8bd1794f7102ba18a9db17db6c4226f51b3b08a5761c70be1c0cdc271272b742`.
The generation2 core XBEs/ISOs remain byte-identical to V2. Thirty-three focused
tests pass after observed failing regressions. The full host run preserved in
`v22-host-tests.log` ran242 tests with3 skips and one unrelated production
dependency-check failure; the parent corrected that check and its exact test
passes separately in `v22-production-check-retest.log` (one test,3.509s). The
remaining241 tests were already successful or explicitly skipped; the full
suite was not repeated without a new failure.

Native inferred integrity now binds the exact plan/parser/source-manifest,
request hash and explicit seed mode, actual verified inputs, selected case,
generation, QD/cache and canonical parsed per-operation sizes/APC schedule.
The expected digest is host-inferred only from complete successful poisoned
exact-byte comparison; no SHA calculation is represented as timed-window work.
Public query qualification requires exactly210 unique path/control/code/length
records, all requested initialized output bytes, terminal END and consistent
geometry partition-style bytes. Fatal/TAP failures and post-END records reject
qualification. All ordinary and clock observations require the actual runner
completed/exit0 outcome. Clock diagnostics retain unmeasured backend/marker
delivery bounds and cannot establish performance acceptance.

Deck lifetime requires runner status `timeout`, assessment `timedOut`, exact
20-unpaused-second detail, the unique generation2/no-write HOLD marker, and
confirmed stopped/finalized cleanup. Crashed/failed/cancelled outcomes reject.
Future Windows lifetime separately requires the owned120s graphical-child
deadline error, wrapper exit1, failed runner outcome, matching live desktop
pipe/client/server/child identities and actual owned JobObject ActiveProcesses0
with confirmed child/server exits. It is unexecuted and cannot borrow Deck's
timeout qualification. No unrelated processes are controlled.

The two archived runs pass V2.2 local reanalysis checks, with new append-only
sidecars in `deck-v22-reanalysis.jsonl` explicitly marked
`pending_independent_review` and `acceptance_eligible=false`. The query's original
failed qualification remains attached to its corrected sidecar. No new native
execution or qualification acceptance occurs before independent review.
Reference observations include HDD GEOMETRY_EX lengths32/40/56/64/112/128/256
with caller Information32/40/56/64/112/112/112, and partition style0 at successful
lengths40 and larger. DeviceNumber length11 fails; length12 succeeds with
Information12. Caller poison on an error does not reveal internal driver
Information. Optical unsupported statuses are observations, not inferred
no-disc capability or normative parity. Read-only prototype query, clock,
lifetime, broad A/A calibration and both released DVD measurements remain
pending. Missing real flush/durability/private counters remain null.

Before accepting V2.2, review found that qualification exceptions could omit
the actual runner outcome from its summary, and archived reanalysis did not
compare new hashes to the original raw row's pins. V2.2 is therefore preserved
as superseded. V2.3 was prepared for independent review at
`.scratch/pr248-native-baseline/frozen-fixture-v23`, manifest SHA-256
`2d5761b35ccd45b53e80135903e7f83542e539ba3e2ed83eb78b5da76cbc0a7e`,
plan SHA-256
`968253699409067adb9414de3c7cdeecdd3353269f7f394dbe2b2a495b498511`.
Its parser/core fixture bytes are unchanged from V2.2. All77 frozen files verify.
Observation capture now retains each available actual runner status, assessment,
exit, timestamps and result/input/cleanup/serial hashes before grading can fail.
Archived reanalysis binds the unchanged original V2.1 ledger hash, each original
serial/result/input pin and the exact recorded cleanup object. Original failed
query status/error remain attached to the new sidecar.

The host-only actual-collector regression utility fails against V2.2, then
passes against V2.3 for an invented crash/exit17, missing serial and changed
ordinary serial text. Crash outcomes remain failed; available completed-result
metadata remains visible when serial is missing; changed archived text is
rejected against the original serial pin. These are controlled host faults,
not native runs. Red/green receipts are `v23-collector-fault-red.log` and
`v23-collector-fault-green.json`. Both genuine archived runs pass local V2.3
checks in `deck-v23-reanalysis.jsonl`, initially pending independent review and
ineligible for performance acceptance. Native launches remained paused through
the review.

The query fixture's210 IOCTL observations are read operations. The same XBE
also creates one owned4KiB file in the private disposable HDD overlay, writes
known bytes, invokes API flush and verifies poisoned close/reopen readback.
That auxiliary probe does not write shared/raw media and does not establish
physical durability or real device flush. Geometry comparison uses its IOCTL
matrix separately; describing the entire query XBE as read-only would be
inaccurate.

Independent V2.3 review completed with no Critical/Important findings. The
reviewer verified all77 frozen pins, reran all three controlled collector faults
and checked both archived attempts against their original hashes/cleanup.
`v23-independent-review-receipt.json`, SHA-256
`f748bc22efa39aa6da86ca2e9df5d2cf9336c465f5a3f36661485b80eb531120`,
records the bounded review. The parent explicitly authorized the remaining
exact-pinned Deck jobs. Both archived reanalysis rows now separately qualify
for fixture byte-fill/public observation scope; the original query failure and
all previous pending sidecars remain intact. Performance acceptance stays false.

The first new Deck run is
`pr248-native-deck-v23-public-query-geometry-prototype`, run
`20261014-130930469-c7e3771734e54e93961429aa4fa53cd4`, completed/exit0 with all210
matrix rows and finalized owned exit. Against the published reference, statuses,
caller IOSB/Information and partition-record size/style all match. Five rows
have raw byte differences: whole-HDD/partition1 length64 at offsets56,60,62;
whole-HDD/partition1 length112 at offset76; partition1 length256 at offsets48–55
and64–111. `v23-reference-vs-geometry-prototype-query.json`, SHA-256
`6b4eb9ceab00c2de5fb2033812bdf4d6ae4d7540107f5796a80ce916c2e25579`, preserves
every difference without claiming normative parity or interpreting reference
indeterminate bytes as meaningful identity. The prototype's private4KiB write,
API flush and poisoned reopen readback succeed; flush caller Information0,
reset0, actual device-flush/durability unknown. Clock/lifetime/post-timeout
normal qualification proceeds sequentially under this plan; Windows remains
unexecuted.

The complete-field audit in
`v23-geometry-complete-field-initialization-audit.json`, SHA-256
`43f719c7aa7fa0c1fc8d65663018cc05d970781c07803899a66dec1a24aa4f4b`, verifies
all14 successful GEOMETRY_EX Information prefixes against an initialized public
schema. Basic geometry/disk bytes and meaningful MBR fields match reference;
MBR signature1481589336/checksum0 are preserved, partition size24/style0 at
complete extents, complete detection size56/type0, inactive union bytes0 and
partial detection header0 at length64. All103 successful control observations
return Information within the requested extent and preserve every oversized
tail byte as0xa5. Absence of poison alone is recorded as an observation, not
used as independent initialization proof. Reference indeterminate bytes remain
in the raw comparison.

V2.3 clock diagnostic run
`20261014-131009446-8a71538c685343058f52717d6e833e3e` failed: runner `plan_failed`,
assessment `failed`, exit137, observer external exit1 before any sample. Its
literal package-config guard rejected the runtime-isolated target. Actual
argv was not recorded by that failed observer and remains unknown. Saved xemu
stderr and runner report identify the isolated config at
`diagnostics/run-state/effective-live.toml`, SHA-256
`6db40e778d5bfd7a45c873a7b7d775060fdb25611b194bb48fb9e1d21f2ad26c`;
runner source explicitly replaces the authored config argument with that
isolated file. The failed result, external stderr/request, source hashes and
zero-sample limitation are retained in
`v23-clock-guard-failure-investigation.json`. The frozen sequence stopped; the
failure is not promoted to timing qualification.

The parent separately authorized continuing only the two independent exact-pinned
lifetime cases, recorded in `deck-v23-root-lifetime-continuation.json`:

| Job | Run | Observed result |
| --- | --- | --- |
| `pr248-native-deck-v23-owned-timeout` | `20261014-131423621-ff002319ac4a4409bce9af428735413e` | Runner timeout/assessment timedOut, exact20-unpaused-second detail, unique HOLD, stopped/finalized private-HDD cleanup; lifetime scope qualifies |
| `pr248-native-deck-v23-normal-after-timeout` | `20261014-131521968-0714e9c2238343c1a73a22df0238b18d` | New process completed/exit0, all1,024×4,096-byte reads and exact comparisons; byte-fill scope qualifies |

The clock failure remains an actual failed row in
`deck-v23-qualification.jsonl`. These lifetime qualifications cannot satisfy
storage timing, powered A/A counts, device flush or physical durability gates.

V2.4 prepares one separately named corrected clock diagnostic,
`pr248-native-deck-v24-clock-metrology`, without a native rerun at freeze. Plan
SHA-256 is
`9824f77dceff01d9ab73e34beafbd69a53885f6f3159c71d9a5fefdddd138b19`,
manifest SHA-256
`3e212b76c9efba4877ca77d05382f737299d8b40e3dcd62fee99de4221a9a5ec`.
The source independently requires exact mapped executable path/hash, complete
runner-transformed argv, authored/isolated config paths+hashes and recorded
owned launcher PID/UID/start time, including the sampler-end lifetime. It
persists available actual observations before rejecting a guard. The collector
also checks the target receipt against actual result PID, launch/input records
and frozen guard source. All34 focused host tests pass, including rejection of
foreign executable/hash/UID, changed PID lifetime, wrong launcher PID, config
hash and authored-path substitution. Metrology XBE/ISO,50 samples, spans,
polling cadence and timeouts stay identical; no performance-method delay or
threshold adjustment is introduced. Independent review is required before the
new job executes. Windows, broad V2 A/A pilot and both released DVD measurements
remain pending; no powered/performance acceptance plan is frozen.

## Clock counter cause and reviewable qualification receipts

The V2.4 clock run `20261014-132844328-4d5d1e32116241d3b45c92cb61de7514`
completed/exit0 and captured50 raw counter/receiver observations with confirmed
owned target/PID lifetime. Its method does **not** qualify requested busy
intervals or RDTSC seconds. The diagnostic incorrectly compared RDTSC delta to
QPC frequency and divided RDTSC ticks by QPC Hz. Recorded QPC frequency is
3,374,488 Hz; requested5-second busy spans actually bracket22.663764–23.922337ms
of receiver wall time. The roughly217-times direct-denominator ratios are a
counter-domain mistake, not evidence of emulator slowdown. Original derived
rows remain preserved as superseded/unqualified for those fields.

The storage paths use a different conversion. `pilot.c`, `replay.c`,
`families.c`, `dvd.c` and legacy `main.c` sample paired QPC/RDTSC deltas around
five100ms relative delays, then report median RDTSC frequency:

```text
RDTSC_Hz = median(delta_RDTSC * QPC_Hz / delta_QPC)
PERF operation_ms = operation_RDTSC_ticks * 1000 / META.RDTSC_Hz
PERF batch_ms = CASE.RDTSC_ticks * 1000 / META.RDTSC_Hz
```

`suite.c` dispatches only the selected storage family. It does not enter the
standalone metrology busy loop. Actual V2 small-read META rates are733,177,379
and733,169,414 Hz, with minimum overhead87/88ticks. Their conversion does not
use QPC Hz directly as an RDTSC denominator. The metrology defect therefore
requires no new bulk revocation of PERF CASE timing units. V1 integrity remains
revoked for its separately documented stale-buffer faults; every cohort remains
ineligible for P1 performance acceptance. Two V2 small-read processes do not
establish A/A repeatability, sufficient count, threshold or powered planning.

Correct-domain descriptive reanalysis of the preserved diagnostic uses actual
QPC ticks/QPC Hz and keeps RDTSC as raw ticks or a receiver-rate estimate. For
five nominal5s idle spans, QPC/receiver ratios are0.999986–1.000151 and observed
RDTSC rates733.211–733.331MHz. These estimates retain unmeasured backend delay;
they are not a calibration PASS or a retrospective qualification of the old
busy schedule. Zero receiver estimates and negative lower uncertainty brackets
on short spans remain explicit. No CPU time is substituted for caller latency.

The corrected proposed V2.5 diagnostic compares QPC delta with QPC frequency
for its busy deadline. It declares diagnostic revision2/deadline counterQPC,
five repetitions × five spans(1ms,10ms,100ms,1s,5s) × idle/busy,50 samples;
requested idle and busy totals are separately30.555s. Polling remains1ms,
observer/runner deadlines150s/180s, setup attachment5s outside measurements.
Idle delay is a requested API delay whose actual elapsed counters remain
observed. The actual-C host mock advances QPC independently of host RDTSC:
all25 old busy samples fail duration checks, then the corrected source satisfies
all50 counter-duration checks. A separate host test rejects cross-counter
seconds/ratios and nonpositive counters. All36 focused host tests pass; corrected
native metrology builds. No new native job executes before review/authorization.

V2.5 plan SHA-256:
`1a471b75ce7a00885c8c3e00d84eb482d16a4ec919f31bb352e007bd3bc56a68`;
manifest SHA-256:
`4039810c94f2b087cad0183b53e8f1690fb464ec70c988e9325a9cd72abaa502`;
parser SHA-256:
`c60b654aa08e59b867020be28abe0e3eb08719b9d12a08ec66b3c256dc01f066`.
The target observer is unchanged at
`128d82e6d10bd8da064c887b9be98963fdc525972e803c890963c9e9e1f2a475`.
Only the diagnostic XBE/ISO changes; released firmware and frozen performance
suite/DVD/query artifacts do not. Prior freezes remain immutable: V2 source,
V2.1 defective qualification, V2.2 failure-summary/archive binding gap, V2.3
corrected native caller plus failed clock guard, and V2.4 corrected guard with
unqualified cross-counter busy/ratio semantics.

Serial-bound research confirms the mapped Deck executable SHA-256
`ee9baadc62679bab44ea937e465b95059304ce5a19db33835932b2350a12b0ba`, also verified
on the preserved138,874,920-byte reference image; ELF BuildID
`bbe3fda783b68f7c5f636672690d1ae1f7f6d2c0`. Its historical build receipt names
reference commit `dcc536830deba245eec36cd009db5860ca04884c`; a fresh full-source/
compiler/dependency reproduction has not been performed in this task. Exact
binary symbol disassembly confirms the file writer delegates synchronously to
its channel and the file channel calls `writev`. Read-only reference source
shows regular-file output, blocking send, UART TEMT after transmit return and
an EAGAIN retry path. The owned `tap_drain` waits for TEMT. These establish a
causal handoff model; they do not establish a universal scheduler/blocking
latency bound, and the observed1.399201ms poll gap does not bound backend delay.
No emulator source expression is carried into the independent fixture/tool.

A viable next qualification proposal is a diagnostic-only causal interval
method: bind the exact owned UART file descriptor, collect guest counter values
before/after each marker emission and host syscall entry/exit timestamps for
those exact single-byte marker writes, and derive conservative counter-rate
intervals. Source/compiled backend identity, the trace's monotonic timebase,
actual tool availability and all matching/timeout rules must be frozen and
reviewed first. Trace overhead stays in the diagnostic bounds; traced runs never
count as performance results. The acceptance firmware binary need not change.
Finite error bounds are still unqualified; broad V2 A/A workload counts,
both released DVD variants, physical durability
and structural counters remain open.

The proposed backend experiment is separate from V2.5 and requires these gates:

| Stage | Required receipt or rejection condition |
| --- | --- |
| Freeze | New diagnostic-only marker-bracket XBE/source/ISO, unchanged published firmware, exact emulator/tool identities, fixed50-sample schedule, expected metadata and timeout/cleanup policy; independent review before launch |
| Availability | Runner-approved tracer exists with pinned version/hash and supports own-user attachment plus decoded-write restriction to the owned UART FD; unavailable/denied stays failed, with no privilege/policy change |
| Target/FD | Exact mapped executable/hash, argv/config, PID/start-time/UID and one FD whose path+device/inode match the owned serial file; reject FD reuse or target changes |
| Clock | Verified monotonic nanosecond syscall timestamps; realtime-only timestamps require independently bounded paired monotonic mapping and clock-step rejection |
| Pairing | Match each unique indexed begin/end byte with its successful one-byte write entry/exit and guest counter-before/after-emission bracket; missing, partial, duplicate or reordered pairs reject |
| Bounds | Host delta bounds are end-entry minus begin-exit and end-exit minus begin-entry; guest bounds are end-before minus begin-after and end-after minus begin-before. Require positive lower extents for finite conservative rate bounds; retain uncertainty and freeze a precision/tolerance contract before clock acceptance |
| Lifetime | Trace only the owned process/FD, bounded tracer completion, exact exit/cleanup receipts and retained partial failures; no global process controls or settings changes |

Guest brackets include emission/drain cost and syscall brackets include trace
overhead; neither is subtracted or reused as performance latency. Synchronous
file delivery supplies causal ordering; measured brackets supply per-attempt
error extents. Poll intervals alone cannot bound backend delay. This is a
concrete route to finite-error evidence without assuming a universal scheduler
deadline or changing acceptance firmware. Trace/tool/timebase qualification and
marker code remain separate work. Source study is attributed to the pinned
xemu/QEMU serial and character-file backend; no code is derived from it.

The compact native receipts below are included in the product document for
review without requiring access to the private scratch directory. Original
failed/superseded rows remain visible; corrected reanalysis is a separate record.
The V2.1 normal/query rows later qualify under exact V2.3 archived-hash checks;
the original query collector failure remains retained. V2.4 qualifies only raw
diagnostic capture, with its busy-duration/direct-ratio method unqualified.
All receipts have performance acceptance false and preserve missing actual
flush/durability/private counters.

```json
{
  "schema_version": 1,
  "performance_acceptance": false,
  "native_receipts": [
    {
      "job": "pr248-native-deck-v21-normal-small",
      "run": "20261014-123555723-3def302426df41cc82e0b7aae3c1cdac",
      "runner_status": "completed",
      "execution": "completed",
      "exit": 0,
      "original_collector_status": "qualified_for_declared_scope",
      "serial_sha256": "a706d8655564284588f3ea8fc182beab7ea844a64f74098d55388e37076cbaf3",
      "result_sha256": "8bf9e5e982dde7dcb8c2f1d1f8ac84f7d46abc6b6e00a0f15d6defaa9f951395",
      "input_manifest_sha256": "c196ec6f6c372dc730bba047e109286aef07e0115856cf713d92a2d558fe09d7",
      "cleanup_sha256": "2e2387b025f3937c871f9e70dee36033cd7146670154af480b2a88f435871021"
    },
    {
      "job": "pr248-native-deck-v21-public-query-reference",
      "run": "20261014-123805215-7ba4fd47b7d144478486c3800a2a85dd",
      "runner_status": "completed",
      "execution": "completed",
      "exit": 0,
      "original_collector_status": "failed_qualification",
      "serial_sha256": "5a2557f669ee42da403e9638dbb0cf030386f9241e46747c49684eed430a50ec",
      "result_sha256": "e26eabbc1fe595b40d019fc3977303de2cbac3069e6d3d95669fa2a68aa42fc0",
      "input_manifest_sha256": "036709651d20e3f2bd84dc0ff2c19cf8e4e966b10b215f702f51952844570ec2",
      "cleanup_sha256": "3c36b17aa613aa6f41bcfcff71e15045ed9f05eed5956b097f7f7d5cb4b38d78"
    },
    {
      "job": "pr248-native-deck-v23-public-query-geometry-prototype",
      "run": "20261014-130930469-c7e3771734e54e93961429aa4fa53cd4",
      "runner_status": "completed",
      "execution": "completed",
      "exit": 0,
      "original_collector_status": "qualified_for_declared_scope",
      "serial_sha256": "bb96c1b9000aa9c8a159c544d8ffc1cf70c057d749be00f2b7bd3259336b95c6",
      "result_sha256": "c72f46c76d6c979caf38a473e2badf20a6eb55596c12f2df6a91c81932657405",
      "input_manifest_sha256": "80f3d87f0cb9071f7c32fd9c69c4257cfe5b7acac865ad70154486309ffa37cb",
      "cleanup_sha256": "f7046d342b67003012c1e890cc04885ddb8bcad819eb88f8e568eda9994a4a5d"
    },
    {
      "job": "pr248-native-deck-v23-clock-metrology",
      "run": "20261014-131009446-8a71538c685343058f52717d6e833e3e",
      "runner_status": "plan_failed",
      "execution": "failed",
      "exit": 137,
      "original_collector_status": "failed_qualification",
      "serial_sha256": "030fbae4ffda895dcd0032ade8a6fe3c82dce728c32a43f6476a0773a6b1e9e5",
      "result_sha256": "0a99d9b2d2d59d4dcf383909c86391b397e232afc82cfb9817e4a244726dcb80",
      "input_manifest_sha256": "28a8fb35a751c9222ad8fe8d18ffbd703bbb118aa9d5c8b611ea9f7e659477af",
      "cleanup_sha256": "f81ba1d376dd30c6533a2e75a5d78c095386f826f270582a0f5165912ef8bd0c"
    },
    {
      "job": "pr248-native-deck-v23-owned-timeout",
      "run": "20261014-131423621-ff002319ac4a4409bce9af428735413e",
      "runner_status": "timeout",
      "execution": "timedOut",
      "exit": 137,
      "original_collector_status": "qualified_for_declared_scope",
      "serial_sha256": "94af459624a27a15d6c0f5148a2f51d23a227c695bf7ac51145d218ff4c05d47",
      "result_sha256": "84d6d75702b82ab2eaad89c782fc44657c7088133e32646e538af61a20e33abd",
      "input_manifest_sha256": "6da3643bf235b892b58741a32bc8d9949f69b42cdae49773c966b993b1d5d1a6",
      "cleanup_sha256": "0e8fa8706bfcff1ed033b82cb3ba8c207b96277cbbe8b18ba01dd3acd9fb9405"
    },
    {
      "job": "pr248-native-deck-v23-normal-after-timeout",
      "run": "20261014-131521968-0714e9c2238343c1a73a22df0238b18d",
      "runner_status": "completed",
      "execution": "completed",
      "exit": 0,
      "original_collector_status": "qualified_for_declared_scope",
      "serial_sha256": "4e9f3932aa0f0210208822a5c45a3e427f7165bb07e4b392b9f01dfc2e102d14",
      "result_sha256": "482bfee73d4d011f2bb742dfe6e9a0498f144c4a45066ca28770e717f032e6af",
      "input_manifest_sha256": "ce40172f7225c34923f2f8d42f50e20079e8fcd9a588534b641e3dc1ed3beef8",
      "cleanup_sha256": "7cb99999966dbfe4b45f2a45340908149b53072e2228b27c0f7dcc1aaad26b73"
    },
    {
      "job": "pr248-native-deck-v24-clock-metrology",
      "run": "20261014-132844328-4d5d1e32116241d3b45c92cb61de7514",
      "runner_status": "completed",
      "execution": "completed",
      "exit": 0,
      "original_collector_status": "qualified_for_declared_scope",
      "serial_sha256": "28230db4958706677b377cb5590633d60106fbe489376547c881b0cb88738568",
      "result_sha256": "2ed449fa189ce8ff2026e481154a4c03926b4c6a36c45459046c83c502a8e528",
      "input_manifest_sha256": "b91574d633d12f1506b61efaece73104eac08d74b92f864664fbe42b62bd8c73",
      "cleanup_sha256": "ef5c074bd4ccc8477fff8be63268219688cc80b7fb7634cd6e20d784e92e884c"
    }
  ]
}
```

## Corrected V2.5 native diagnostic result

Independent review found no Critical/Important issues in all23 frozen inputs,
exact-C50-duration fault checks and adversarial clock-branch parsing. The parent
authorized exactly one fresh Deck diagnostic; no syscall trace or Windows run
was authorized. Run `20261014-135510663-4b003024df444c1481bfa728a0ed8f35` completes/
exit0 with50 unique samples, exact target/config/argv and same-PID lifetime.
All25 busy QPC deadlines satisfy the corrected counter schedule. Nominal5s busy
samples report QPC5.000001482–5.000027263s and receiver4.998445727–5.000040922s;
QPC/receiver ratios0.999996853–1.000311426. Actual raw brackets and short-span
uncertainties remain retained. This qualifies diagnostic capture only; finite
backend error, normative calibration and P1 acceptance remain INCONCLUSIVE.
No old V2.4 requested durations or direct-denominator ratios are upgraded.

The corrected result receipt is included here for direct product review:

```json
{
  "run_id": "20261014-135510663-4b003024df444c1481bfa728a0ed8f35",
  "plan_sha256": "1a471b75ce7a00885c8c3e00d84eb482d16a4ec919f31bb352e007bd3bc56a68",
  "status": "qualified_for_declared_scope",
  "runner_status": "completed",
  "runner_execution": "completed",
  "exit_code": 0,
  "samples": 50,
  "reported_qpc_hz": [
    3374488
  ],
  "same_pid_lifetime_confirmed": true,
  "serial_sha256": "37bb9f344d4acf749746e6b55f78c9ca7d28152c23ca4d867f580680fa4eb33e",
  "result_sha256": "1bd0f46ef90dcac5f20f7e6740e092272db30ab9502d4927155e5c4a95ccee81",
  "input_manifest_sha256": "96b9c445a6e8f38d63edd98b96250b5a93177dbce824f518528e3f2da7cd202c",
  "cleanup_sha256": "317af84bb88c41a6ab1f939834d2db8c3e2865dd519a3080b42038f3f7f9e208",
  "target_sha256": "adedb5b39db0b20abbc5393aea79e7f19fd019f57c882ae7b8dcbb5425ac7fa0",
  "clock_qualification": "INCONCLUSIVE backend/marker delivery bound unmeasured",
  "backend_delivery_bound": null,
  "performance_acceptance_eligible": false
}
```

## Windows corrected native integrity, query and lifetime checks

After its separately scoped capacity recovery, the approved Ryzen host ran the
published untraced64 baseline through the protected PowerShell desktop pipe in
Codex/session1/WinSta0/Default. The original V23 owned deadline reached its
120-second server limit and cleared its child/job, but strict qualification failed
because client EOF handling lost the server's error output. Run
`20261014-162325708-a52e392832b24f58ae9aaee08b090691` and the stop-on-failure
result remain preserved. The [EOF correction](WINDOWS-PIPE-EOF-FIX.md) waits for
the exact owned server and drains its output before interpreting completion.

The new V27 launcher SHA-256 is
`a61757b17e2da594607e82d3f8595b1faba61c3ed4d1b6276373e39b15613b79`.
All four new identities pass the original strict integrity/query/deadline grading:

| Scope | Actual run | Bounded result |
| --- | --- | --- |
| Normal reads | `20261014-164514066-8083861d1f224f40bcefa285c873ac81` | 1,024 ×4,096-byte poison-verified reads, exact counts and zero assertion failures |
| Public query/private-file probe | `20261014-164525285-17dfb7728e96485d82abf5238c672c29` | Complete210 public observations; auxiliary isolated4KiB write/API-flush/reopen remains separate from durability |
| Owned deadline | `20261014-164534904-a0eb64328b094dbeb127b56168c7fd39` | Expected runner failed/exit1, exact server deadline reason retained, owned descendants confirmed cleared |
| Fresh normal after deadline | `20261014-164741936-bbc6a31c90d64dddaba121e161e6ffd6` | New process passes the same complete poison-verified read contract |

The [portable V27 native receipt](windows-v27-native-receipt.json), SHA-256
`aa5229881fb7610824bae4d795bb77a466cbc7b0843ede9dbcc15f41e40377f7`,
binds plan, parser, launcher, review, raw outcomes, input hashes and scoped cleanup.
[Windows qualification](WINDOWS-NATIVE-QUALIFICATION.md) retains recovery pins,
the original V23 failed row and V27 provenance. These checks qualify the bounded
native launch/integrity/query/lifetime method. They do not qualify Windows clock
metrology, full workloads, P1 performance or a replacement class driver.

## Source-only build preparation corrections

Final toolkit review found three clean-checkout preparation defects after the
V2.5 native run: DVD mode omitted generation of its ignored header; the earlier
generator trusted a cached `default.xbe` after checking only the ISO; and the
Windows lifetime mock compiled the wrapper without generating its ignored pipe
header. An isolated repro with the real pinned released ISOs and invented cached
4,100-byte XBE files confirmed the stale-cache defect without invoking extraction.
Its receipt SHA-256 is
`feb7a9a5fe339ff7084e93bb2197dd4c4cc771ee2425606c65093835c9c09a21`.
The source-preparation red log retains the missing DVD dependency and missing
Windows header failures, with SHA-256
`15a3c63cef98492fa5dc0946b713c98d45a1bc48bbf57a6b33ceb200fec4323a`.

The corrected generator requires explicit ISO/extractor paths and the extractor
SHA-256; its native CLI fixes both released ISO pins. Every invocation extracts
into a fresh temporary directory and checks the input/tool pins before and after
extraction. It reads only the first4,096 public header bytes and verifies that
section metadata fits that extent. `MODE=dvd` declares this generated prerequisite
and rechecks all pins on each build. The Windows host test creates an isolated
source layout and generates the pipe header from the owned PowerShell sources
before compiling. Generated headers/manifests and all binaries remain ignored.

A source-only copy, containing no ignored local headers, passes all38 native
host tests and a real clean NXDK DVD build. Fresh extraction matches the preserved
V2 public headers: clean
`33a591adbeba2e34173da62327be779ade079aa9961dbfbebda87e4dbab82df9`,
performance `d5f57723bdde2539a598bfac9b7c4cf9753a9ed286cc30d072888fb4b10dfb2f`.
The observed extractor SHA-256 is
`9c3ac31eb215b312205ce193c6ddf5fb88617bb0fa57aa6fea825dea66f76df6`.
The clean-build receipt SHA-256 is
`eec69af61154cc56e0ccff2cc920540dc598ae07654c87067ad8c01857d69832`;
its build log SHA-256 is
`9e4498b2dd4a3b36e9f2c4067e9cbaf8f9241f272062d8035919ac8570a4636e`.
The build emitted the existing NXDK linker warning that `.edata=.rdata` was
already merged into `.edataxb`; compilation, XBE creation and ISO creation
completed successfully. This is source-build verification only. The new temporary
ISO was not launched, and all frozen V2/V2.5 files and native observations remain
unchanged. The newly generated header bytes reproduce the already verified V2
metadata; the earlier generator defect does not erase its separate byte proof.

## Free-space block and read-only cleanup preview

Deck stopped at `pr248-native-deck-c09-p02-b-fresh-v1` on 10:44:17 UTC with
available972,095,488 bytes below required1,073,741,824. Windows stopped at
`pr248-native-win-c27-p04-a-fresh-v1` on 11:14:38 UTC with available1,039,994,880
below the same required minimum. Both runners were idle with no active job at
the subsequent HTTP inspection. No threshold was reduced and no data deleted.
Local waiting DVD coordinators were interrupted; their prepared unstarted
drafts and all API failures remain preserved.

GET-only `*-owned-completed-package-cleanup-preview.jsonl` lists only the149 Deck
and312 Windows completed owned packages, their exact job/run IDs, recorded/
contract-derived archive paths, declared file sizes/pins, normal child/server
exit evidence, finalized runtime cleanup, retained local artifact hashes and
HTTP inventory-length verification. Diagnostic ZIP hashes additionally match
the runner's explicit SHA receipts. Source/templates, raw Results, frozen pins,
shared seed/boot assets and failed/unstarted packages are protected references.
No physical directory listing or allocated-size claim is available through this
API, so logical package bytes are not a guaranteed reclaim quantity.

Deck declared completed-package bytes total21,574,735,269 plus3,703,820 diagnostic
mirror bytes; downloaded eligible artifacts total236,360,874. Windows totals
15,659,717,424 plus5,942,140 mirror bytes; downloaded artifacts67,148,080.
All461 inventories/lengths/diagnostic hashes verified with zero preview issues.
Complete catalog pagination found no owned `pr248-native-*` assets: supported
own catalog disk-delete reclaim is0 bytes. The runner has no reference-aware
package/evidence prune API. Operator storage recovery is a separate dependency;
no SSH or shell deletion bypass was used.

The observed declared package costs are144,796,881 bytes/Deck attempt and
50,191,402/Windows attempt. A future10-pair ×36-primary-case method would retain
720 fresh packages per host: about104.25GB/36.14GB respectively, plus evidence
and headroom, until a supported separately authorized retention policy exists.
This is a logical-byte planning forecast, not a physical allocation measurement.

The live runners advertise `payloadReuse`, but the public runner source defines
reuse as a verified copy into each new draft (`AgentJobStore.Reuse.cs:7,44`).
Application/test selection likewise creates a new package and streams every
file through `ReceiveAsync` (`AgentJobStore.RequestedTests.cs:218`); from-test
and clone use the same copy contract. Uploading an application once saves
network transfer, not per-attempt executable allocation. Native emulator role
must identify a declared package payload. Asset kinds are only `xiso-seed`,
`snapshot-carrier`, `readonly-input`; the read-only binding is limited to
bootROM/flashROM/DVD config fields. No typed executable content store,
reference-only runtime executable binding, hardlink/reflink materialization or
reference-aware pruning is exposed by the supported HTTP workflow.
`runtime-payload-reuse-gap.json` preserves exact source hashes/line evidence and
live capability receipts. No executable was misclassified as a disk asset and
no remote archive was edited by this normal-testing workflow. A separately
scoped operator recovery of identical immutable completed-package files is
owned by the parent agent; it is not yet a native qualification receipt.

## Proposed second controls method (not executed)

`proposed-controls-v2.json` in the native scratch directory proposes new owned
process controls after a separately reviewed fixture/metrology plan and operator storage recovery. The current runner
job contract exposes no affinity/priority fields. A future owned USER launcher
could set/read back only its actual xemu process affinity and normal priority;
physical-core/SMT topology and legal masks must be measured and pinned first.
The proposal includes fixed untimed input reads/CPU settling, matched configs,
actual-child monitoring and independent host monotonic batch-wall brackets.
Every host, source/media identity, cache preparation, planning count/threshold
and marker uncertainty must be frozen before candidate measurements. Current
hosts, active processes and global power/governor settings are not changed.

Read-only pilot inspection shows very small between-run calibrated RDTSC
frequency differences compared with large observed timing ratios; this does
not independently prove correspondence to host wall time. Windows minimum
back-to-back counter overhead is zero and remains an observed emulator
quantization limit. Current Windows process telemetry monitors the wrapper PID,
not actual xemu child; whole-run GPU utilization also varies without timed-batch
or process attribution. These limitations motivate new metrology/control work,
not a claim that a particular background task caused the variance. Whole-run
wall duration includes setup/warmup/teardown and cannot replace caller latency.

## Retained failures and remaining gate work

Windows failed setup attempts remain archived: blocked `.ps1` file execution;
an overly literal account-name guard; unavailable `Get-FileHash` autoload; and
an initial GUI-child argument/waiting path without guest serial evidence.
The V1 desktop-pipe launcher records actual command/PID; its normal exit waits do not qualify timeout cleanup.
No failed setup was silently counted or retried under the same identity.

Early replay logs truncated long summary lines. Their cache labels are invalid,
so the parser rejects them. Corrected logs use shorter records and enlarged
owned buffers; v3 replay has 12 complete framed cases on both rigs, whose V1 byte-fill integrity remains unqualified. Earlier
v1/v2 artifacts remain present. The parser's behavior tests also reject duplicate
operations, count mismatches, bad IOSBs and missing end records, and preserve
missing firmware/device counters rather than filling them with zero.

Full acceptance still requires all predeclared primary cases under both cache
policies, a fresh process per case, controlled actual run ordering, sufficient
independent pairs, complete fixture/tool/config pins, observed healthy-path
structural costs, real device flush/reset evidence and both optical suites.
Windows vendor/OS caches remain explicitly uncontrolled; the runner comparison
state is not qualified and no waiver was enabled to make it green. Title frame
and asset deadlines, physical-console behavior and candidate results are not
present in this native baseline evidence.

Workspace-local raw evidence is retained under `.scratch/pr248-native-baseline`:
per-job requests/receipts, `evidence/RUN_ID` serial/TAP/config/input/state/host
records, per-host `*-pilot-native.jsonl`, `*-pilot-summary.json`,
`*-query-v2-raw.txt`, replay/family parsed records and pipe proof. These paths are
local evidence locations, not claims of published or committed artifact access.
