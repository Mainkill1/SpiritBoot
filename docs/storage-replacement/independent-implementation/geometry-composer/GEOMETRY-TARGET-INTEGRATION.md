# Narrow target integration requirements

This is guidance for the parent integrator, not an applied product change.
It does not qualify a native storage backend or the new native geometry route.

1. Compile the pinned geometry_composer.c and geometry_owner_adapter.c with
   geometry_composer.h, geometry_owner_adapter.h, geometry_kernel_api.h and
   geometry_target_assertions.h. Supply approved actual platform declarations
   for PFDO_EXTENSION/PIRP and the public kernel/disk types before the adapter
   translation unit. Retain the owner's original notice and review dependency
   rights; no unknown SDK helper implementation is supplied by this package.
2. Do not use geometry_host_platform.h or define its guard in a native build.
   The semantic host types are test doubles. Mandatory actual-build assertions
   must run against target declarations with the checked Xbox x86 field layout,
   ordinary local C entrypoint, NTAPI/FASTCALL API conventions and scalar facts.
   A packing/prototype mismatch blocks integration rather than being cast away.
3. Route the retained extended-geometry local dispatch to
   NxPartComposeExtendedGeometry(current_owner_extension, upper_irp). The
   signature is ordinary C NTSTATUS(PFDO_EXTENSION,PIRP). The enclosing dispatch
   continues to assign final status and complete the upper IRP exactly once.
   Exclude the old local wrapper body and private geometry response type at
   the approved integration anchors; their presence is not required by this
   ABI. Do not reintroduce the status-only lower-query helper as this path.
4. Establish the caller preconditions: initialized owner synchronization event
   not already exclusively held by this call, valid coherent cached metadata,
   boot-fixed owner/attached lower lifetime covering the entire query, a valid
   writable buffered output, and a kernel-thread context at permitted IRQL.
   No new hot-remove or media-change atomicity guarantee is provided. The
   adapter releases layout ownership before lower building, dispatch or wait.
5. Link the checked IoBuildDeviceIoControlRequest, IofCallDriver, KeInitializeEvent,
   KeSetEvent and KeWaitForSingleObject APIs plus the frozen composer. The
   lower operation is basic geometry with no input and exactly 24 output bytes.
   It requires terminal status/count, with synchronous-child disposal left to
   the I/O manager. Do not add upper completion or synchronous-child frees.
6. Verify actual native compile/link, request/attachment lifetimes, buffered
   completion-copy bounds, dispatch ownership and observed queries before a
   native parity claim. Use the admitted measurement receipt's ROM/run/raw
   artifact pins. The candidate declares cleared unavailable optional padding
   and checksum 0; the receipt does not establish full detection/checksum or
   internal failure Information parity. Full native class/backend/P1 gates
   remain separate and open.

The author run_checks.py command verifies only this independent package.
Prior normal and sanitizer results remain valid for unchanged functional
source. Host/i386 semantic builds do not replace the target declaration gate.
Current source/input identities are in GEOMETRY-OUTPUT-FREEZE.json; all
authored files and evidence are pinned by SHA256SUMS.
