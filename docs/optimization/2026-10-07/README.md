# Xbox kernel performance audit — 7 October 2026

Branch: `perf/kernel-call-optimization`, based on validated `feat/clean-room-kernel` product a88247760c91de599a14342158561373b072dfce. Source references in this report identify the exact public kernel snapshot291ad9759f7993cb1f96d73bfa1c6f333c2bef34, tree8ba32f2153b4716c8cac269bad06a78553f98ded, before optimization. Build inputs include569 release and583 checked source files; unused desktop and other-architecture code is excluded.

[JSON audit](kernel-call-audit.json) and [CSV audit](kernel-call-audit.csv) give a source reference, backend, verdict, reason, risk and measurement proposal for every declared export. Coverage checks confirmed371 unique entries, exact names/kinds against the actual build definition, matching source tree, and existing source files/line references.

| Kind | Count |
| --- | ---: |
| Callable exports |337|
| Data exports |34|
| Total declared exports |371|
| Unused ordinal slots367–373 |7|

| Static decision | Count |
| --- | ---: |
| Candidate callable entries |37|
| Callable entries with no recommended change |288|
| Stub or intentional no-op callable entries |12|
| Data entries |34|

The fifteen ranked candidate families share backends reached by several exports. Seven bounded families were selected for implementation and measurement: pin scratch clearing; pool bitmap conflict skipping; absent-PDE spans in system allocation; known custom-object type fast path; unused final modular square; live-prefix SHA context loading; arithmetic six-bit DES schedule reversal. Selection is not a claim of measured speedup. Actual source work counts and paired guest timing evidence determine retention and benefit claims.

Deferred candidates require separate proof: combined FPU storage and APC caches change ownership/lifecycle; single handle lookup must preserve type/error precedence; short object-name scratch affects OOM/error behavior; virtual-memory query fusion must preserve MBI boundaries; Unicode fast paths need complete NLS equivalence; shutdown scan fusion has low-frequency lifecycle costs; split HMAC updates may cost more dispatch than the copy they save. Full obligations and existing test coverage appear in the three domain reports and candidate JSON.

## Stub behavior

Missing implementations are correctness work, not a performance opportunity. Fatal generated exports: DbgLoadImageSymbols7, DbgUnLoadImageSymbols11 and MmDbgAllocateMemory/MmDbgFreeMemory/MmDbgQueryAvailablePages/MmDbgReleaseAddress/MmDbgWriteCheck374–378. MmUnmapIoSpace183 is an intentional no-op for preexisting static windows. Default XcCryptService350 returns0 but installed mutable vectors must still dispatch. IoMarkIrpMustComplete359 ignores its IRP. DbgPrint8 has a release no-op and checked transport. DbgPrompt10 returns0 in both matched builds: checked has bounded transport code but its availability check returns false without KDBG enabled. No return-success substitution is proposed for missing semantics.

## Existing correctness findings

The scheduler audit identified a wait-block gap: NxkWaitForMultipleObjectsMode accepts up to64 handles but supplies no external wait-block array, while the active KeWaitForMultipleObjects backend rejects counts above the3 embedded blocks. XeNtReleaseMutant also drops its reference before reading SignalState on the nonowner path and uses an untyped reference. These are existing source findings requiring separately validated fixes. They are not evidence of an optimization regression, nor assumed safe behavior to bypass. See [scheduler report](scheduler_objects-report.md) for exact references and other bounded behavior limitations.

## Evidence and limits

Before implementation, product host checks:41 passes and one root-only skip; kernel clean-room host checks88/88. Validated starting BIOS passed direct API/contract/warm-reboot guests and both full XISO variants. Its GitHub firmware workflow37689569960 also completed successfully. No optimization timing, new firmware qualification or Conker gameplay result is asserted by this audit. Per-export decisions are static source assessments; runtime frequency and speedups require actual measurements. Existing public Xbox test coverage was inspected, not rerun by audit workers. Clean-room agents received public source and behavior requirements only; shared filesystem separation is procedural.
