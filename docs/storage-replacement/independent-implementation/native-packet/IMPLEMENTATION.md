# Unlinked owned packet preparation and result capture

Root authorized this standalone primitive before P1, analogous to the existing owned geometry/request primitives. It is not an installed native adapter. P1 still gates major driver implementation. There is no lower submission, callback implementation, cancellation, rundown, boot/dispatch, metadata wiring, benchmark or performance tuning here. No CMake or existing source file changed.

## Production boundary

`nx_packet_prepare` validates caller-owned resources and a bounded copied command before modifying anything. It requires an idle driver-owned child with no installed cancel callback and caller evidence of no thread association. It checks stack capacity, callback presence, finite positive timeout within the supplied limit, command size/direction, byte/page/alignment limits, and a single borrowed MDL with consistent original-domain metadata, complete address extent, selected subrange and sufficient caller-verified PFN capacity. Zero original address is valid. Descriptor validity/residency, trustworthy PFN storage capacity and absence of concurrent mutation are platform preconditions; this primitive cannot validate an arbitrary kernel pointer or pin memory.

On success it calls IoReuseIrp, initializes the SRB, provided sense extent and next stack, binds Scsi.Srb/OriginalRequest/borrowed MDL, copies CDB/direction/timeout, installs the caller-supplied completion routine for success/error/cancel, and returns an immutable transaction ticket. No callback is implemented or called. The original MDL and mapping are unchanged. No mapping, physical contiguity assumption, partial MDL, PFN walk, address substitution, heap, worker or clock is introduced. Execute-SCSI CDB lengths 6/10/12/16 and no-data RELEASE_QUEUE are the bounded supported packet forms; accepting a CDB length does not certify that a drive supports its opcode.

The target is the already selected retained ATAPI PDO. The admitted CONTRACT explicitly says that lower fills PathId/TargetId/Lun and clears SrbExtension for its own transport scratch. Initial zeros are intentional. This module is not a generic miniport-addressing API, and cannot supply caller-owned lower scratch.

`nx_packet_capture` copies token, raw terminal IOSB status/count, SRB base/modifiers, SCSI status and bounded autosense by value. Child IOSB Information is authoritative; the input SRB transfer length is never substituted. It rejects STATUS_PENDING, any nonnegative IOSB status paired with pending SRB base 0, over-counts and inconsistent sense extent/pointer as protocol results, while preserving raw status/count for diagnostics. Informational NTSTATUS values with terminal SRB status remain intact; negative immediate failures with untouched SRB 0 are preserved. No media/sense interpretation or request-core status mapping is implemented. A protocol result authorizes no completion or byte credit. No returned pointer aliases native child/sense storage.

Caller ownership must hold across both operations; an idle/thread-unlinked assertion is not a synchronization mechanism. Calling prepare again on a live child is forbidden. Capture requires genuine lower terminal ownership supplied externally. Duplicate completion, cancel races, frame reuse, final parent completion and actual device/reference drain belong to the future lifecycle adapter. The primitive does not make any of those safe by itself.

## Provenance and interface scope

Input hashes were recorded before new source authoring. Existing production/tests were copied from the exact owned 0133 source export; their hashes remain unchanged. Reviewed declaration types and all 250 assertions are copied without modification. The selected SRB typedef is an interoperability declaration from the admitted exact srb.h; its original public-domain notice is retained, SAL annotations omitted and anonymous union expressed directly. No SDK helper body was copied. Native scalar stddef/stdint compilation shims are original declarations using compiler predefined scalar types; they are not opaque-layout reconstructions.

Root supplied only SRB-ABI-FACTS.json (SHA 08645e84fe7422eb7d0aae7e53d958fee5584af16dbd57ce4c181403f88a56e6) from its separate probe. No other probe files or origin source were opened. The final native assertions compare every supplied SRB fact plus four width/capacity checks. Declaration admission does not resolve remaining per-file/component grants or authorize transitive body imports. Existing notices and limitations remain.

## RED/GREEN evidence

The initial independent host harness failed four of five groups against preparation/capture stubs; rejection-only tests passed, as expected. `review/red.log` records the missing successful behavior. Root review identified an overbroad positive-status rejection: `review/status-red.log` demonstrates failure for informational 0x40000000 before narrowing the check to STATUS_PENDING. `review/pending-srb-red.log` then demonstrated informational IOSB plus pending SRB incorrectly accepted; the final check rejects that pair while preserving negative immediate failure with untouched SRB. A further boundary test demonstrated acceptance of an invalid full MDL address extent despite a fitting selected segment; `review/extent-red.log` records RED before adding the full-domain wrap guard.

Final host tests execute actual production preparation/capture plus unchanged 0133 request.c. Seven groups include 27 rejection variants, 11 terminal variants, zero-domain/repeated-PFN and fragmented-PFN address simulation, distinct mapped aliases, page-edge/odd-address input, no-data and RELEASE_QUEUE packets, 16-byte CDB, bounded sense/canaries, copied result surviving packet poisoning, and actual core two-segment write-through followed by cache synchronization. The PFN simulator interprets packet fields through independently owned page tokens; it does not dereference VA zero. It proves host packet/domain behavior, not native DMA/PIO.

Commands:

```
python3 source/tests/host/nxstorage/check_packet.py review/final-host
python3 source/tests/host/nxstorage/check.py review/owned-checks
```

Both plain and ASan/UBSan packet runs pass all 7 groups, with leak/stack-use-after-return checks enabled for the sanitizer run. The unchanged full owned runner passed: 44 request, 8 pthread, 13 geometry-composer scenarios/6001 checks, 20 cache-query cases, 16 geometry-owner scenarios/61973 checks, and 32 lower-cache cases; its freestanding i386/helper checks also passed. Existing owned sources remained unchanged after that run.

Exact target declaration/object check:

```
docker run --rm --pull never --network none \
  -v /home/codex/xemu-shader-workbench-handoff/.scratch/pr248-native-packet-owned:/work \
  -w /work sha256:ae07b0897b48d511a166e9892c223118aaac7da21cdbf1f502c36b527b7310ca \
  bash review/target_compile.sh
```

This uses only the isolated workspace mount and root-authorized default rootless Docker context. GCC 13-win32 compiled all 250 unchanged native assertions with the pinned target options/default pack 8, and all measured SRB/width checks. Both assertion objects have zero .text/.data/.bss and no undefined symbols. The production packet object has exactly `_IoReuseIrp@8` undefined; no memcpy/libatomic/arithmetic helper is required by this pinned GCC build. This is an object/declaration check, not candidate linking or runtime execution.

The initial forced local-socket Docker health check found no socket; root explicitly authorized its functioning default context. An initial GCC standard-header attempt encountered a toolchain stddef wrapper with no include-next target under -nostdinc; the final build uses the original freestanding scalar shims instead. Earlier exploratory clang Windows objects are intermediate only (clang emitted memcpy); they are not the final GCC helper-closure evidence.

## Review and handoff

Root reviewed the production body. Its status finding was fixed and its addressing/scratch finding resolved against the admitted lower behavior, with explicit contract/tests. A fresh reviewer spawn was attempted but all agent slots were occupied. Root requested this exact freeze and will activate the independent reviewer after this author completes, before integration.

`owned-native-packet.patch` contains only new primitive/declaration/test/harness files under product-relative paths; it adds no build or dispatch wiring. `INPUT-EXPOSURE-LEDGER.json` records copied inputs and supplemental scope. `OUTPUT-HASHES.json` pins final outputs and evidence, excluding itself. Independent review, actual candidate link/native ABI use, kernel allocation/mapping/cancel/rundown behavior, P1, physical persistence and release readiness remain open.
