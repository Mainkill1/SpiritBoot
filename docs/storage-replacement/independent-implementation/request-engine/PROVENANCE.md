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

## Additional approved completion/cache packet and design extension

Root explicitly admitted the following new behavior/declaration inputs under
the existing permitted package; no I/O-manager/lower implementation body was
exported or inspected by this author:

| Input | SHA-256 |
| --- | --- |
| COMPLETION-OWNERSHIP.md | c074d61fbc50079dd0e5b38d81f808a6f23742c5477c677aeb38fca92fe94d6f |
| CACHE-CAPABILITIES.md | 3ec851eb9f492df664690d661cdd5b7214140a85803f1aa0f377b6b3c1198a40 |
| TARGET-API-AVAILABILITY.md | f23e255130bc48ead853f689a7445599f9955bcece666649379d506d0cfe5a27 |
| target-api-declarations.h | a0c7d6a9c24acacfa0f6f58ba95f18678afbef8dbb99db78bac1f82d84788f61 |
| LOWER-CACHE-QUERY-PROPOSAL.md | ee7a787d0214a53d0dbc629ac498f4b6a6f67555b03c6ae26c47ca9fbb3a4169 |
| updated approved-inputs.json | 9a56bd594159806de82f3a091aebcbaf88d624792bcec667933423f1540c5411 |
| updated SHA256SUMS | 831cc977ff010fe1d1b11640aa9a0d0b690aa27ec769aa4ff8f59877ed26fce8 |

The reviewed declaration-only target packet hash matched its manifest entry.
Narrow query/header/enum declarations in the already approved public-domain
ntddstor.h were additionally read (same pinned a79bf9a5... input); no transitive
includes or private native layouts were viewed. The updated manifest names a
geometry-wrapper packet, but that packet's contents were not studied in this
task. No other source/export is implicitly admitted from a file-name listing.

Primary public STORAGE_WRITE_CACHE_PROPERTY, WRITE_CACHE_ENABLE and WRITE_THROUGH
documentation on Microsoft Learn was read for public semantic facts; their URLs
are linked in CACHE-QUERY-DESIGN.md. No example/implementation body was copied.
The previous input/exposure record remains intact; no old class implementation,
history, binary/disassembly, product tree or native header closure was studied.

KERNEL-ADAPTER-DESIGN.md now records conditional target stopped-completion/reuse
support, continued device/channel epilogue lifetime, actual API availability
including header-only helpers, absent cache discovery paths, and successful
no-command SYNCHRONIZE CACHE branches. These supplied source-observed facts do
not imply a tested adapter or physical durability result.

CACHE-QUERY-DESIGN.md freezes a separately scoped consistent-snapshot, read-only
response primitive: recognized enabled/disabled states, explicit selected real
flush, conservative Unknown/no native FUA/configurability/power credit, descriptor
negotiation and bounded acceptance cases. It has no implementation yet. The
proposal supplies ordinary x86 full size 28 but the approved packet does not
yet supply the exact serialization offsets/widths, header/query minimum extents
and version/enum ABI facts needed to implement and assert a native response
without using unapproved headers. Precise behavior-only ABI facts were requested
from root; its instruction explicitly permits finishing design only when target
structure facts are missing. No guessed encoder/no-op shell or new pass evidence
is claimed while those facts remain unavailable.

The request core and all existing tests remain frozen and unchanged. No new
build/test/native run was needed for these prose changes. The existing 50-case
engine evidence is historical/current engine evidence only, not cache-query
qualification. Only own design/provenance/manifest outputs changed; no product,
Git, VM, ATA/IRQ/queue or full adapter mutation occurred. P1 and actual native
type/helper/callback qualification gates remain in effect.

## Separate cache encoder: approved declaration facts and final freeze

Root explicitly approved CACHE-ABI-FACTS.md, cache-abi-facts.json/h,
NATIVE-ABI-INVENTORY.md, native-abi-facts.json/h and ABI-PROBE-RECEIPT.json for
this bounded task. The approved manifests and these declaration-only packets
were read; their numeric native inventory was delivered in a combined output
that truncated some numeric rows. No native type/header closure, probe source,
object/assembly/dependency artifact, SDK helper or old storage body was viewed.
Only cache ABI facts are used by production/test assertions; native numeric
facts are discussed for future assertion requirements. New input identities:

| Input | SHA-256 |
| --- | --- |
| CACHE-ABI-FACTS.md, initial read | d0b6c7ae3494a1353b33f6df7373aa1a8c5f96781fdc5573900e5a30c08ba38f |
| CACHE-ABI-FACTS.md, public Version clarification | 62bc52dd83250de3b69221751d00f00baa36bb0eeb1943fdecef6f87fa88de46 |
| cache-abi-facts.json | 7e06c069f14ec8aa5fd9b88dae5d1a39a97339c713a957459886b1da4c094ecb |
| cache-abi-facts.h | 19b20d0ffbc993fa6120702d6f6559a7efa4364e5bc6dc24df97d74d0e6ed816 |
| NATIVE-ABI-INVENTORY.md | 2190a939e1a450128594f6c147be6177c41f7a000767b615966c50db217c5ec1 |
| native-abi-facts.json | 874a5625ac7e3191104fefa024e84cbd51eb2a47cf6157cdaa56c6082a5dc519 |
| native-abi-facts.h | cede9c2da88bbd9f896444ce6699391aee1c9b432984bc36e8b876439b2b484d |
| ABI-PROBE-RECEIPT.json, initial read | 15e9d163c044d54ce8e53966e3620b7eca64f5f95f4da199e8b12ca11b419f5b |
| ABI-PROBE-RECEIPT.json, public Version clarification | 361305fabcc7388fd934af230e959dccac76dea05207df266141904f5b4ed8ca |
| approved-inputs.json | fe9c8f587f041249cd121f27828c6608b94c098a6af285a65f2d178aabbe84fc |
| SHA256SUMS, clarified packet | 7058b4a6e863813de84e5557695de4e4a8cf1f20dc7d184a4d3ae53e8c2ae1f0 |

The cache proposal and numeric header were reread, along with own existing
design/provenance/test scripts. The native fact header was additionally searched
for status constants (no matches); no external source/header was opened for
them. tests/cache-input-validation.log verifies selected new input hashes
against the updated SHA/index and verifies the frozen engine source/test bytes.
The entire listed source closure was not read or implicitly approved by this
manifest review.

The DDI Version description did not establish a numeric convention. The
investigator supplied a primary-source clarification; this author independently
opened [Microsoft's Win32 STORAGE_WRITE_CACHE_PROPERTY page](https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ns-winioctl-storage_write_cache_property).
It defines Version as structure byte size and Size as total descriptor bytes.
That page's public declaration/semantic facts were visible, with no implementation
sample/helper body used. Combining those semantics with the exact measured
target 28-byte layout gives Version=Size=28 for this fixed response. The
investigator then updated the prose/receipt; the numeric packet did not change.
No desktop layout was substituted for the target measurements.

cache_query.h/test fixtures were authored before functional production code.
A documented temporary red-only production scaffold returned Unsupported/0 for
all inputs. tests/cache-query-red.log records its real strict-warning ASan/UBSan
execution: 18 expected assertion failures, two unsupported-path passes, exit 1,
and no sanitizer findings. The scaffold was replaced by real independently
authored bounded C. No historical source-shaped test, source-text grep or
expected-output encoder/structure overlay was used. The red scaffold was not
presented as an implemented query and no final implementation remains a no-op.

tests/cache-query-green.log records all 20 fixture groups passing under Debian
clang 19.1.7 with ASan/leak detection and UBSan halt-on-error. These include
literal expected enabled/disabled/Unknown bytes, E7/EA/None/unknown selector,
unsupported and contradictory cache facts, no native-FUA/type/configurability/
power/NV credit, every output padding byte, input 0..11 and output 0..34 bounds,
null pointers, Exists/standard and enum/property boundaries, malformed snapshot
Boolean/profile/opcode values, unaligned/full/partial input-output aliasing,
oversized/SIZE_MAX extents, untouched error/tail canaries, and immutable inputs.
SIZE_MAX tests use small backing storage to verify actual accesses remain
bounded; production still requires truthful resident readable/writable extents.
There are 20 named groups, many containing multiple boundary fixtures, not 20
native device cases. No known failing test or sanitizer finding remains.

The production module reads only public query fields and its by-value coherent
snapshot, writes exactly 0/8/28 response bytes, and has no callback, allocation,
clock, worker or hardware interface. It conservatively preserves unknown/
unflushable capability. Error precedence and rejecting malformed snapshot enums
are explicit candidate policies. Pure result enum values are not NTSTATUS;
future glue must map the documented symbolic statuses/actual Information.
Passing a selected opcode requires genuine retained-selector proof; the module
does not parse IDENTIFY or establish that a physical drive durably flushes.

tests/cache-query-i386.log records strict-warning freestanding i386 compilation
of real new production C: 442 text bytes, 972-byte ELF file, no data/BSS and no
unresolved symbols. A separate independently authored assertion-only test
includes the explicitly approved constant-only cache-abi-facts.h packet;
its object has zero text and passes all required field/enum/extent comparisons.
This is comparison against numeric facts, not an actual native type build.
CACHE-QUERY-DESIGN.md and KERNEL-ADAPTER-DESIGN.md specify mandatory assertions
against reviewed native sizeof/alignment/offsetof/width/enum/prototype declarations
under the exact target build before any glue is admitted.

At root's follow-up, a design-only lower glue plan was added from the already
approved behavior/declaration facts. No new lower body was read. The plan
separates coherent retained state/actual E7-EA selection from successful
disabled/unknown/no-op synchronization, defines status/Information mapping,
and lists the missing native declarations, cached-field/mutability/lock/IRQL/
rundown facts. It does not install a property handler, alter ATA/IRQ/queue/cache
state or implement the full adapter. New pure production is unlinked from the
product; native P1 and major integration gates remain with root.

Frozen request.c/h, request_test.c, pthread_ownership_test.c and run.sh hashes
remain exactly their prior identities. A single verification run, recorded in
tests/cache-task-engine-green.log, passes all 42 deterministic and eight real
pthread engine scenarios under the existing sanitizers. The unchanged engine
i386 verification remains 4569 text bytes with no unresolved symbols, recorded
in tests/cache-task-engine-i386.log. These results are engine evidence only and
do not substitute for native cache glue, IRQL/cancellation or physical durability
acceptance. No product/Git/VM mutation or full adapter work occurred. All new
sources/tests/design/logs/provenance/freeze records stay within this author's
own output directory. This record makes no personnel/legal certification.
