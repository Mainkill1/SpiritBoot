# Independent author provenance and evidence

Author role: `/root/pr248_independent_engine`, fresh delegated implementer,
2026-10-14. Prior exposure in this agent context: no old classpnp/disk/nxcdrom
implementation, original implementation tests/patches/disassembly, repository
history, investigator-only handoffs, product source tree, or linked old binary.
The task message supplied scope and the environment supplied cwd/date/shell.
No parent conversation history was studied. This is a record of this agent's
inputs and actions, not legal or personnel-independence certification.

The approved behavior package was the sole product reference. README, CONTRACT,
ACCEPTANCE, CALLER-MATRIX, PUBLIC-REFERENCES and approved-inputs manifest were
read. A file-name enumeration within that package identified approved exports;
no transitive source include was followed. Only narrowly searched numeric SRB
function/direction/status facts, opening public-domain notices, and the CDB10
layout in the two listed declaration headers were viewed as source. Whole
header bytes were hashed for identity, not copied into the output. The manifest
was read to establish allowed/excluded input boundaries and checked for these
two source hashes. No other approved source body was needed or inspected.
No network fetch, public documentation example, additional SDK header,
repository agent file outside the supplied package, Git operation, product
mutation, build of the product, or VM/hardware operation occurred.

The four skill/instruction files below supplied process rules. Compiler standard
headers (`stdint.h`, `stddef.h`, plus host-only stdio/stdlib/string) and the host
sanitizer runtime are build dependencies, not reference storage implementation.
Clang 19.1.7 was used. Tests run Linux x86_64, not a native Windows/Xbox kernel.

Inputs and pinned bytes:

| Input | SHA-256 |
| --- | --- |
| `/home/codex/xemu-shader-workbench-handoff/.scratch/pr248-permitted-inputs/README.md` | `e3556a3e4f46a083cb96e741c3b9af66bdede386e464c369db9c00ee0be1a565` |
| `/home/codex/xemu-shader-workbench-handoff/.scratch/pr248-permitted-inputs/CONTRACT.md` | `3e1bee5be3eb445b51310afc47aee2ad6410ffd855804c4686362d09f9b767b7` |
| `/home/codex/xemu-shader-workbench-handoff/.scratch/pr248-permitted-inputs/ACCEPTANCE.md` | `b194ffbc56f183157024b94c13c52c93a9382716a162aa03c55c7c7fd1a24fee` |
| `/home/codex/xemu-shader-workbench-handoff/.scratch/pr248-permitted-inputs/CALLER-MATRIX.md` | `b882e311e462d853d3a153ff4ff9f34a5611e9bfaf6b59df50cb068a01fe91d2` |
| `/home/codex/xemu-shader-workbench-handoff/.scratch/pr248-permitted-inputs/PUBLIC-REFERENCES.md` | `ed242b01fb02d667e4bd63c84688505f00537e3f139ba46fc63b3224a8a17e98` |
| `/home/codex/xemu-shader-workbench-handoff/.scratch/pr248-permitted-inputs/approved-inputs.json` | `1fcb751b17c5b7153d2675ce047db59677bbca03aa44209a489ed037672491f2` |
| `/home/codex/xemu-shader-workbench-handoff/.scratch/pr248-permitted-inputs/source/sdk/include/ddk/srb.h` | `870c13c119506ecb7e25047c95fbc0e81b8e6c21c83cd6cae34c27540efc5bde` |
| `/home/codex/xemu-shader-workbench-handoff/.scratch/pr248-permitted-inputs/source/sdk/include/ddk/scsi-interface-only.h` | `002f04c8ecd5437e23e7c143c431e65805fded9167047874d333bfb34787446c` |
| `/home/codex/.codex/skills/oss-clean-room/SKILL.md` | `e18044b1e86a131242535c5053b90d818de804faaec8156db213a961fdb7d257` |
| `/home/codex/.codex/skills/oss-clean-room/references/separation-profiles.md` | `7e341842b4f4cf2aa40e08e23879723468936bcfd5b3e23320f27a0304a5568c` |
| `/home/codex/.codex/plugins/cache/openai-curated-remote/superpowers/6.4.2/skills/test-driven-development/SKILL.md` | `64b03fce4aee5a97a93160cea8111f3ba13a17b7c001db4bd5836d67fd10705d` |
| `/home/codex/.codex/plugins/cache/openai-curated-remote/superpowers/6.4.2/skills/test-driven-development/writing-good-tests.md` | `51471c853306ff92ca8bb41dcaea05f31c0e46b03651f8f3c99754b7172f4ae1` |

The implementation specification is `nxstorage/DESIGN.md`, written before
production behavior. Independent choices include API names, slot state fields,
round-robin iterative device pump, admission-order write/flush barriers, value
command tokens, and quarantine/cancellation policy. No reference algorithm,
private class layout, helper implementation, test body, or incidental identifier
was copied or translated. Compatibility convergence is limited to these facts:
EXECUTE_SCSI=0x00, RELEASE_QUEUE=0x04, DATA_IN=0x40, DATA_OUT=0x80,
READ(10)=0x28, WRITE(10)=0x2a, SYNCHRONIZE CACHE(10)=0x35, ten-byte CDB format,
big-endian LBA/count fields, 32-bit LBA/16-bit block-count limits, actual child
completion bytes, and public pending/MDL/IRP ownership semantics. These are
necessary transport interoperability facts. Published source header notices
were observed; new independently authored code carries the proposed project
GPL-2.0-or-later grant. Final repository provenance/license review is separate.

Tests exercise newly authored production request.c, never extracted baseline
routines. The OS/lower transport is doubled because no kernel/hardware backend
is authorized in this slice. Doubles publish full command/outcome records and
retain the borrowed parent lease while lower ownership exists. Expectations
use literal, manually checked bytes, CDB fixtures and ordering outcomes.

Evidence and all observed failures:

* Initial test-first red scaffold compiled. All 17 initial scenarios failed the
  intended observable assertions. Their early assertion returns also exposed
  16 test-fixture buffer leaks (536870912 bytes); the harness cleanup was fixed,
  then `tests/red.log` recorded 17 expected assertion failures with no sanitizer
  finding. Original failure is retained as red-initial-harness-leaks.log. The
  empty red scaffold is not a deliverable implementation and was replaced.
* `tests/green-first.log`: all 17 passed the actual new production engine.
* Six hardening/coverage scenarios were added. Two regressions failed first:
  missing terminal report caused premature release; null parent caused invalid
  delivery. Four scenarios characterized already implemented behavior and
  passed on addition (cancel during prepare, duplicate segment, odd optical
  buffer, and READ10 count cap). No new production behavior was claimed for
  those four. red-hardening.log and green-hardening.log retain both outcomes.
* Initial freestanding i386 compile failed because hosted string.h required
  unavailable 32-bit libc headers. The core's zeroing was refactored to a local
  byte clear. i386-initial.log retains the failure; green-freestanding.log and
  i386.log record the subsequent passing host suite and x86 compile.
* The failed-recovery drain regression failed first: already live lower work
  did not receive cancellation after RELEASE_QUEUE failure. red-recovery-drain.log
  retains that failure. The correction preserves pages until terminal lower
  completion, cancels live commands once, and fails waiting/admitted work.
* Final `bash tests/run.sh`: 24/24 scenarios pass, with clang -Wall -Wextra
  -Werror -Wconversion -Wshadow, AddressSanitizer including leak detection,
  UndefinedBehaviorSanitizer with halt-on-error. green-final.log is the final
  output. No warning, sanitizer error or known failing scenario remains.
* Final `clang -target i386-none-elf -ffreestanding -std=c11 -O2 ... -c
  nxstorage/request.c` passes. This is an object compile, not a kernel link.
  i386-symbols.log reports only compiler helper __udivdi3 as unresolved. No
  allocator, worker, clock or libc symbol is referenced by that object.
* Output hash verification matched every recorded file. Its login-shell startup
  emitted `/etc/profile.d/devtools.sh: claude: command not found`; this was
  unrelated to compilation/tests. Verification was repeated with login disabled
  and all 20 artifact hashes matched without startup output.

Covered behavior includes one inline read/write, authoritative short/error
bytes, duplicate admission and segment callbacks, pending returned after inline
completion, 50,000 segments at submission depth one, byte/page/ATA/CDB bounds,
negative/alignment/pointer/LBA validation, odd optical buffers and crossing
advertised capacity, four simultaneous lower-owned requests, slot exhaustion,
pre-submit and delayed cancellation, preparation failures on first/middle/final
segments, write/flush/later-write ordering with concurrent reads, real sync
opcode and cache capability qualification, queue release, failed-recovery
cancellation, and bounded quarantine. The suite is deterministic and
single-threaded; it does not prove multiprocessor lock/cancel races.

Candidate policies are frozen in DESIGN.md and ADAPTER.md. Short success returns
SHORT_TRANSFER with actual bytes. Error completions credit bounded verified
bytes. Over-reported segments get no credit. Caller cancellation returns
CANCELLED after lower ownership ends. Unknown/unsupported cache durability
fails visibly. Failed recovery preserves the original error and asks to cancel
other live commands; internal cancellation reports IO_ERROR. Lower negatives
outside core status codes can be preserved for distinct platform errors.

Unknown/unimplemented gates: real kernel IRP/SRB/MDL adapter and its allocation,
mapping and autosense sites; pending IOSB/event/APC and priority delivery;
DISPATCH_LEVEL/nonpaged behavior; cancel-routine/device teardown races; real
controller queue recovery across HDD/DVD; device capacity/capability discovery;
physical durability; optical controls/sense/media policies; PnP/names/boot and
partition IOCTL behavior; native alignment/PIO/DMA tests; baseline parity and
performance. A missing lower terminal callback retains resources rather than
inventing completion; bounded drain depends on the adapter/lower contract.
No full driver replacement, final firmware qualification or performance parity
is claimed. Root performs composition/backend/baseline work independently.

## Independent sector-math follow-up

Root requested a scoped optimization of this author's own request engine and
additional boundary checks. No new external/product/reference source was read.
Inputs for this step were the same author's request.c, request.h, host tests and
the already produced i386 object. Their pre-change identities were request.c
dc2bff67fadd5d5486a24e4b8fb5bc469aa54219392d3f83ac27b06a843cd9c0,
request.h 5e1fb535cc2a70c47318ea66e48e987b1e2f1a262a26b51cab81c1047de6966c,
and tests/request_test.c
2e92d840a06b0dcd9d95e33b2d88cfc7fee5ea8f51e83f435e925304866be645.
Toolchain commands size, nm and Python byte/hash inspection operated only on
this independently authored output. No old object or disassembly was inspected.

Five boundary groups were written and run before production edits: 512/2048/
4096/65536-byte sectors at literal high offsets, last legal LBA and exact media
end, low alignment remainders, non-power configuration rejection plus valid
2^31-sector initialization, and full-width host MDL metadata. All five plus the
existing 24 passed before optimization, preserving existing legal behavior;
this is refactoring characterization, not a claim that those tests were red.
The host MDL-width fixture uses abstract metadata without data dereference and
does not certify a real 4-GiB MDL or native DMA path.

A new executed freestanding gate failed before production changes because the
i386 object required __udivdi3. tests/shift-red-helper.log retains the expected
failure; tests/shift-before-tests.log retains the pre-change 29/29 sanitizer run.
The change computes sector shift and mask once after the existing power-of-two
validation. All hot sector alignment, byte rounding, block-limit construction
and CDB LBA/count conversion now use shifts/masks. Offset, request length,
range checks and MDL accounting retain their prior widths; narrowing to CDB
fields occurs only after the supported LBA/block limits are validated.

tests/shift-green-tests.log records 29/29 passing ASan+UBSan cases with the same
strict compiler flags as the first slice. tests/shift-green-helper.log records
the passing i386 gate. The updated tests/i386-symbols.log is empty: the latest
object has no unresolved symbols, including no divide/modulo runtime helper.
The earlier helper-bearing object is preserved as request-i386-before-shift.o
and its symbols/bytes/hash are recorded in shift-before-object.log. The old
first-slice i386 helper observation above is historical, not a claim about the
latest object.

| Identical i386 -ffreestanding -O2 build | Before | After | Change |
| --- | ---: | ---: | ---: |
| Object text bytes (size) | 4342 | 4390 | +48 |
| ELF object file bytes | 5056 | 5012 | -44 |
| Unresolved runtime helpers | __udivdi3 | none | eliminated |

Object text grows by about 1.1%. The ELF file shrinks; neither measurement proves
kernel linked-size reduction or native latency improvement. No runtime timing,
baseline performance comparison, new kernel adapter or hardware validation
was performed in this follow-up. Compiler/runtime helper elimination is the
verified performance-related outcome. The two new cached uint32 fields add
eight bytes to the core device state before any platform layout effects.

Write-through was reviewed as a missing behavior contract. Current NX_WRITE
has no durability flag and may complete before a later NX_FLUSH. DESIGN.md and
ADAPTER.md recommend a future explicit core intent flag that retains the same
parent/slot through real cache synchronization. A platform composite could work
only by owning one upper parent across two internal requests and suppressing
upper completion after data. Missing approved facts are the public upper intent
indication/mapping, required sync behavior and partial-error/cancel/sync-error
status/byte policy. No write-through implementation or parity is claimed.

The provenance note and artifact manifest are updated for these new sources,
tests, object snapshots and logs. No product, Git, VM or broader adapter mutation
occurred. The original scoped source exposure statement remains unchanged.

## Independently authored write-through extension

Root supplied an explicit behavioral contract: write-through success requires
durable data completion, an upper adapter maps FILE_WRITE_THROUGH/
FO_WRITE_THROUGH/SL_WRITE_THROUGH intent, real cache-sync is required with
enabled cache, established disabled cache may skip it, and failure Information
must remain a declared candidate policy. This task message plus this author's
existing engine/tests were the only new inputs. No external source, old class
code, SDK helper, extra header, or documentation sample was viewed. Browser
verification was unnecessary for implementing the supplied behavior-only
contract; the public flag names were supplied as facts, not assigned guessed
numeric Windows values. The initial and sector-follow-up exposure boundary
remains unchanged. Pre-extension own source identities were request.c
e1b43c8c1f194729f18c94ff7083c7d183ea9965defa3051bce57cfd944a5716,
request.h a6fffa52aa5ab3196b55b4a016b5872971036e73442010ee15090db9ee9f619d,
and request_test.c
16cb5cf01b2ec413658fb2018fc9e62f10d4c073dd6996eb0beb361d0b305afc.

DESIGN.md was updated with this extension's outcomes before production behavior.
The independent public engine flag NX_WRITE_THROUGH has the local value 1 and
is accepted only on NX_WRITE. It is not a copied Windows flag value. The same
parent, admission generation and device-owned slot remain across data chunks
and real SYNCHRONIZE CACHE(10), using one new sync-phase state. No child pool,
worker, clock, write retry, SRB_FUNCTION_FLUSH shortcut or FUA durability claim
was added. Command generation still produces distinct value tokens per phase.

Twelve scenarios were added before implementation. tests/write-through-red.log
records the original 29 passing, one new partial-data-stop characterization
passing, and 11 intended failures exposing the missing sync phase, barrier and
flag validation. The flags field and name initially represented the requested
API only; the red engine ignored them, then the passing implementation replaced
that missing behavior. No red failure or sanitizer finding is hidden.

tests/write-through-green.log records all 41 passing with the same strict
warnings, ASan leak detection and UBSan halt-on-error. Covered cases: inline
multi-chunk data then sync; delayed sync retaining parent/resources; inline and
async sync error with all verified data bytes; short and failed partial data;
cancellation before sync and while sync is lower-owned; following-write ordering
with available concurrent reads; sync waiting for a prior ordinary write;
established-disabled-cache ordering without a command; duplicate old-data and
sync completion reports; zero-byte and illegal/unknown flags; unqualified cache
rejection before data; and sync preparation failure without lost byte accounting
or admission progress. Partial-data-stop passed on addition because that
behavior already existed; its flag recognition is covered by the other cases.

Candidate policy is now explicit in DESIGN.md and ADAPTER.md: lower-reported
bounded data bytes remain parent Information on sync preparation/completion
failure or cancellation. Sync contributes no bytes. A short/error data phase
stops without subsequent data/sync and never reports durable success. Accepted
cancellation wins after all owned resources terminate. A qualified zero-byte
write-through emits no command; unqualified cache rejects even zero-byte intent.
Unknown flag bits and non-WRITE uses reject INVALID. This is independently
chosen replacement policy, not historical failure-Information parity.

The same source passes tests/check-freestanding.sh. Latest i386 object text is
4553 bytes (versus 4390 before this feature), file size 5176 bytes, and there are
no unresolved symbols or division/modulo helpers. These are object-build facts,
not kernel size or latency measurements. The healthy ordinary single-command
path still submits exactly one command and performs no extra allocation,
clock sample or worker dispatch. Write-through adds only its required real
cache-sync phase while reusing the existing slot and transport ownership seam.

The prior write-through contract-gap note is historical. Engine intent and
candidate phase policy are now implemented; actual FILE/FO/SL mapping, kernel
IRP/MDL/cancel/event/APC integration, capability discovery, native races,
physical durability, baseline parity and performance remain qualification
gates. No kernel adapter, full-driver change, product/Git/VM mutation or claim
of legal/personnel certification was made. All output hashes are regenerated.

## Commit-point, capacity and threaded ownership review

Root supplied candidate-only review feedback and clarified the requested
ownership contract; no old/reference source material was included. This author
checked the existing independent core and confirmed the mismatch: its locked
inflight/prepared assignment commits submission, then port.submit runs outside
the state lock. A cancellation arriving in that gap cannot promise to prevent
the port call. Ownership drain was already safe. No extra hot-path synchronization
was introduced to manufacture a stronger hardware-cancellation guarantee.

The additional process input was the receiving-code-review skill at
/home/codex/.codex/plugins/cache/openai-curated-remote/superpowers/6.4.2/skills/receiving-code-review/SKILL.md,
SHA-256 091df1629510af1b92fc4abd6f96732ebedb4cb2c0f3457e8f2740b0504a2438.
It was read for review/verification procedure, not implementation expression.
The prior approved package and own-output source exposure boundary is unchanged.
No third-party storage body, history, disassembly, extra SDK implementation,
product tree, adapter source or network source was consulted. Pthread, C atomics,
and test-only condition-clock interfaces are standard build dependencies; their
implementation source was not viewed. Pre-review own production identities were
request.c afc30f361b9ff87b0470ebf5c52ef940658884c27771e3297d752c88c87c5746,
request.h 6d6dff31cb980ce780424956e1787eb3c71fc19f9d77c185e80b95d617181836,
and request_test.c
a6037011de374482aaa680e178fb04b54a5204c135121e7de09e196d583b56a9.

Tests-first capacity reproduction: nx_device_init gained a byte-capacity
argument with an initially ignored red scaffold. A two-slot count with only
one-slot declared capacity returned success and modified storage;
tests/capacity-red.log records the intended failed assertion with the original
41 scenarios passing. This reproduction used physically sufficient backing
storage, avoiding an intentional sanitizer crash. The passing implementation
rejects count greater than slot_storage_bytes/sizeof(slot) before clearing any
device or slot byte. The test then verifies an impossible UINT32_MAX count is
also rejected with all canary bytes intact. Because count <= capacity/sizeof
implies count*sizeof <= capacity <= SIZE_MAX, the subsequent multiplication is
safe on the 32-bit target as well as the host. The caller must supply true actual
storage capacity; this interface does not detect a lying pointer/size pair.

Seven real-pthread scenarios were authored and ran before the guard fix; all
passed the existing core's ownership behavior in pthread-prechange.log. These
are review characterizations, not claims of failed tests or a new cancellation
algorithm. The test transport uses actual pthread mutex enter/leave, a separate
event mutex, condition-variable gates outside the core lock, and independent
threads calling nx_start/nx_lower_done while another thread calls nx_cancel.
Private slot state is observed only under the real lock to position the commit
gate and to demonstrate the explicitly requested active-zero/pumping-live case.
Outcome assertions concern command arrival, resource retention/retirement,
terminal bytes/status, duplicate suppression and external rundown ownership.

The scenarios deterministically cover cancellation after data commit but before
port.submit, cancellation during prepare before commit, write-through sync
commit, a terminal callback while submit is blocked, callback/pump rundown after
active becomes zero, callback admission/reuse with real heap-parent reclamation,
stale tokens across reuse, returned dispatch-stack lifetime and flush barriers
with independent read concurrency. The test-only adapter model tracks whole
call references, seals admission, rejects further admission, and refuses resource
destruction while a call/callback is live. It is not a production kernel adapter.

An eighth characterization verifies a committed child that finishes inline
before cancellation is processed: it must not receive a late cancel after
terminal ownership, but the parent returns CANCELLED with actual written bytes.
For still-nonterminal committed transport, exactly one cancel is issued after
submit returns and resource retirement awaits the terminal report. Cancellation
does not imply hardware writes or cache synchronization were undone.

Latest tests/threaded-capacity-green.log records 42 deterministic scenarios plus
8 real-pthread scenarios passing (50 total), with strict warnings, ASan leak
detection and UBSan. Pthread execution additionally enables ASan
detect_stack_use_after_return=1, exercising dispatch_result after originating
thread/callback stack returns and parent reclamation before core-call return.
No warning, sanitizer finding or known failing scenario remains in the latest
run. This is deterministic host concurrency evidence, not exhaustive scheduling,
ThreadSanitizer evidence, native IRQL behavior or kernel cancel/rundown parity.

DESIGN.md and ADAPTER.md now define commit explicitly, including the same rule
for write-through sync. They require external sealed admission, outstanding
parent/transport residency, whole-call rundown and fenced callback sources
before device/slot memory ends. Active-slot count alone cannot authorize teardown:
port.complete may still be blocked while active==0 and pumping==1. Generation
defense applies only while the device is resident; it promises nothing for a
callback after device/token-resource lifetime ends. No new core quiescence or
teardown API was added, and the real adapter remains unimplemented/unqualified.

Only the initializer capacity guard/signature and explanatory production comments
changed; no worker, heap allocation, clock read, hot-path lock or mandatory wait
was added. Test gates/threads/clocks live solely under tests/. The latest i386
freestanding gate passes: text 4569 bytes, ELF file 5192 bytes, no unresolved
helpers. The initialization ABI requires the new actual-storage-byte argument
when root refreshes its prototype. All production/test sources, notes, logs and
artifact hashes are updated only in this independent output directory.
