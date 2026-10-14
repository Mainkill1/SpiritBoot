# Owned native storage recorder

This fixture observes public Xbox APIs on a disposable runner-owned HDD. It
changes no firmware implementation. The replay arrays are public request
metadata only, copied from the previously owned 2 × 1,024 capture; all data
bytes are independently generated. No original game resource is included.
The canonical public operation tuples are in `replay-requests.csv`; the build
renders their C initializer with `make-replay-requests.py`. All2,048 ordered
tuples match the preserved earlier header. Generated headers and binary/object
outputs are ignored, while frozen evidence retains their exact original bytes.

Build `MODE=pilot`, `MODE=replay`, `MODE=query`, `MODE=families`, `MODE=suite`,
`MODE=dvd`, `MODE=lifetime` or `MODE=metrology`:

```sh
PATH=/home/codex/src/nxdk/bin:$PATH NXDK_DIR=/home/codex/src/nxdk make MODE=suite
```

`MODE=dvd` additionally requires the two released public fixture ISOs and a
verified `extract-xiso` executable. The generator fixes the released ISO pins:
clean `8d01028844e508629d3f73481714ad46ea9931ba55f35956f28d7121f9eba475`
and performance `099d161a6010499cb86be58ccd2297a8be8802d8b8f4b97f7ef720ff5d0d6d33`.
For the preserved local qualification inputs and extractor, run from this directory:

```sh
PATH=/home/codex/src/nxdk/bin:$PATH make MODE=dvd NXDK_DIR=/home/codex/src/nxdk \
  DVD_CLEAN_ISO=/absolute/path/to/release-qualification-20261013/portable-evidence/fixtures/api-leaf-clean.iso \
  DVD_PERFORMANCE_ISO=/absolute/path/to/release-qualification-20261013/portable-evidence/fixtures/api-leaf-performance.iso \
  DVD_EXTRACTOR=/home/codex/src/nxdk/tools/extract-xiso/build/extract-xiso \
  DVD_EXTRACTOR_SHA256=9c3ac31eb215b312205ce193c6ddf5fb88617bb0fa57aa6fea825dea66f76df6
```

Choose the ISO paths explicitly; a clean source checkout does not contain these
external fixture inputs. The shown extractor digest identifies the observed
local tool, rather than every `extract-xiso` build. A different tool needs its
own verified pin. Each DVD build regenerates `dvd-metadata-reference.h` and
`dvd-reference-manifest.json` after verifying all three inputs. Extraction always
uses a fresh temporary directory, so a stale `default.xbe` cache cannot establish
ISO lineage. Only the first4,096 public header bytes are read; the declared
section table must fit within that read extent and section data must begin after
it. The generated header/manifest are build outputs and remain ignored.

For `families`, first run `python3 make-data.py` to create the owned optical
payload. It has SHA-256
`38be4bdff9e7042c7ae154c0ae6d047ec7c75bce729ac66aa3378bf52563262e`.
Avoid carrying that optional payload into another mode's ISO; use a clean build
or retain/hash the actual artifact. Input identity always follows actual bytes.

`make native-host-launchers` builds a Linux metadata/exec wrapper and the Windows
PowerShell desktop pipe wrapper with host GCC, Clang 19, llvm-dlltool and lld.
The Windows wrapper verifies WinSta0/Default through public Win32 APIs. Its
embedded owned PowerShell commands create an owner-only, one-job pipe server
on Codex's live USER desktop and a verified client handshake. `PROVE` launches
no guest; `RUN` launches only the pinned job's xemu command, then waits and
records server/child PID, session, command and output. Neither script files nor
ExecutionPolicy changes are invoked on the tester. Pipe constructor/security
behavior follows [the public .NET API](https://learn.microsoft.com/en-us/dotnet/api/system.io.pipes.namedpipeserverstream.-ctor?view=netframework-4.8).

Operate the existing runner over HTTP using `runner_tests.py` / `runner_xiso.py`
and their checked-in transport. Do not SSH, copy a denied disk into an import
root, alter shared host settings or terminate unrelated processes. Every new
attempt needs its own identity, private HDD/EEPROM and fresh process. Preserve
all errors/timeouts/invalid records. Submit and wait sequentially to enforce
actual pair ordering.

`STORAGE-PERF-META`, `OP`, `CASE` and `END` serial records preserve direct RDTSC
frequency/overhead, exact bytes/status/IOSB, per-operation issue-to-ready timing,
actual queue high-water, APCs, available memory pages and API flush/reopen
checks. No per-I/O firmware clocks/tracing are enabled. The host parser emits
actual JSON observations and leaves unobservable device/firmware counters null
or absent. API flush success does not assert an observed ATA cache-sync.

Standalone modes preserve the earlier grouped exploratory captures. `MODE=suite`
reads exactly one stable selected ID from the runner-injected private prepared
FATX plan slot, then executes only that measured case. Each case runs in a fresh
process and private HDD/EEPROM. A `.warm` selection performs one complete,
verified identical warmup; `.cold-ish` performs none. Data seeding stays outside
timing and host page/device caches stay uncontrolled. Pressure selections
restore exactly 900 available pages after warmup, record starting/ending pages,
and preserve the actual QD high-water. Batch endpoints are first issue to last
consumer-ready completion. NXDK objects are rebuilt when switching modes so
standalone objects cannot accidentally reuse `STORAGE_SUITE` flags.

The frozen suite includes an auxiliary owned optical payload. It does not
supply the two required released optical suites, device flush/reset evidence or
private structural counters. See
[the native baseline report](../../../docs/storage-replacement/NATIVE-BASELINE.md)
for real results, exact pins, retained failures and the remaining P1 gates.

## Corrected fixture generation2 and retained V1 limits

V1 source/ISO/parser/launcher snapshots and all observations stay frozen in the
native scratch evidence. V1 reused output buffers can pass no-fill/partial-fill
success; its nominal assertion counts and write persistence=1 are unqualified.
Old inferred-digest sidecars are revoked, not erased. The corrected parser
retains fatal/TAP failures and rejects contradictory/post-END framing. Inferred
SHA requires the corrected `fixture_generation=2`, complete per-byte equality,
exact fixture/seed/case pins, unique operations and zero failures. Digest origin
is explicitly `host_inferred_from_verified_equality`, never in-window SHA.

Generation2 complements every expected byte before every read, initializes
every IOSB, and uses an independent write readback buffer. Per-operation ticks
begin after poison preparation and include full equality verification; batch
duration includes between-operation preparation, without subtraction.
`reopen_readback_verified` never fills the physical durability gate. Actual
cache-sync/private counters remain missing, and `durability_verified=null`.

From the product root run:

```sh
python3 -m unittest discover -s tests/host -p test_storage_native_runner.py -q
```

The actual-source C mock tests inject successful no-fill/partial writes to
read outputs, first-fill-only repeated DVD headers, untouched/error IOSBs, and
Windows timeout/assignment/rundown failures. They use synthetic public ABI
outcomes and invented header bytes; no native ISO/private driver body is needed.
The Windows lifetime test copies the wrapper, mock and PowerShell sources to a
temporary source layout and generates `pipe-commands.h` there before compiling.
It therefore requires no ignored generated header from an earlier local build.
The DVD generator test pins invented ISO/extractor inputs and verifies fresh
extraction in the presence of a foreign cached header, plus rejection of changed
input/tool pins. A separate Makefile test exercises the declared DVD header
dependency in a clean source layout.

The generation2 Windows wrapper assigns the suspended client to an anonymous
owned JobObject before execution, bounds waits and retains the noninherited
kill-on-close handle until observed owned-job ActiveProcesses0. Pipe server and
client also have scoped Process-object cleanup and bounded output waits. This
follows [the public Windows job inheritance/lifetime contract](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects).
These builds/fault tests are local qualification only. Desktop-pipe normal and
controlled-failure native qualification requires new isolated jobs. Deck capacity
was recovered through a separate parent-owned operator procedure; Windows still
awaits that procedure's approval. No native test changes the disk guard.

V2.3 native caller validation binds the exact frozen plan/parser/source/request,
actual input hashes, explicit prepared-XISO or direct-copy seed lineage and the
same canonical operation records used by the parser. Query validation requires
the exact210 path/control/code/length matrix, complete initialized output extents,
terminal framing and byte-consistent partition-style details. Archived reanalysis
must match the original recorded serial/result/input hashes and cleanup object.
Actual runner failures stay distinct from collector qualification failures.

Deck byte-fill, public geometry and scoped timeout/post-timeout normal checks
have qualified under a separately reviewed plan. They do not establish a viable
P1 performance method. The first clock observer failed its package-config guard
because the runner supplies an isolated effective config; that failed run remains
intact. The corrected observer records observed executable/argv/config hashes
and PID lifetime before rejection, then validates the exact runner transform.
`metrology` emits50 idle/busy timing samples only for diagnostic clock relation;
backend/marker delivery remains unmeasured and CPU time is never substituted for
caller latency. `lifetime` writes no data and intentionally holds until the
declared owned timeout. The query XBE's matrix is read-only, while its auxiliary
private4KiB write/API-flush/poisoned reopen probe is separately described in the
native baseline report. No physical durability or real device flush is inferred.

The corrected proposed metrology source uses QPC delta/QPC frequency for busy
deadlines and QPC elapsed seconds. RDTSC stays in its own counter domain. The
preserved earlier V2.4 diagnostic used a wrong cross-counter deadline/denominator;
its raw observations do not qualify requested busy durations or RDTSC seconds.
An actual-C host mock with independently advancing QPC reproduces25 short busy
intervals in that source and verifies the corrected50-sample schedule. Serial
backend-delivery bounds require a separately reviewed marker/syscall experiment;
no syscall trace or clock acceptance is implied by this source correction.
