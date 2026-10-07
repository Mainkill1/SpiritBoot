# Clean-room Kernel Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development. The user
> has selected another implementation agent and waived further approval gates.

**Goal:** Replace confirmed missing kernel behavior with independently written
implementations and validate the resulting firmware directly in xemu.

**Architecture:** A history-free implementation agent works from public ABI
contracts in an isolated Roswell worktree. A separate integration task exports
reviewed changes as hashed source patches applied by SpiritBoot's pinned build.

**Tech Stack:** C, x86 Xbox kernel/ATAPI, nxdk guest tests, Python build tooling,
Docker firmware toolchain, direct xemu XISO execution.

**Spec:** `docs/superpowers/specs/2026-10-07-clean-room-kernel-design.md`

## Global constraints

- No community firmware, disassembly, extracted data, keys or binary-derived
  implementation detail reaches implementers or reviewers.
- Preserve upstream Roswell revision `1569e2e89fb47cc72b9c704a8884f98200432bd4`
  and all existing licensing; distribute independent changes as hashed patches.
- Use direct XISO execution; do not invoke the HTTP test runner.
- Keep the published v0.1.0 baseline unchanged; publish fresh images only after
  validation. No unmeasured speedup or untested game compatibility claims.
- No further approval questions. Report technical blockers instead of guessing.

## Review focus

- Concurrent asynchronous I/O on the same handle retains independent completion.
- Pinned pages resist relocation and count operations do not wrap/underflow.
- Warm reboot restores ranges before allocator reuse; malformed handoff fails safe.
- IDE integration shares driver IRQ ownership and respects public object sizes.
- Shutdown callback reentrancy/lifetime cannot corrupt or deadlock the registry.

### Task 1: Independent kernel compatibility implementation

**Files:** Roswell `ntoskrnl/xb/{xbe.c,ordinals.map,sizeddata.c,scattergather.c}`,
`ntoskrnl/xb/mm/{api.c,contig.c,pagesupply.c,mm.h}`, boot/ATAPI integration
modules selected after reading public source, and `tests/xbe/` guest probes.

**Interfaces:** Public nxdk exports retain their existing ordinals/signatures;
internal interfaces are chosen by the implementer and documented in its report.

- [x] Read allowed source and public ABI, record references and technical design.
- [x] Add guest checks that expose missing behavior, retaining baseline failures.
- [x] Implement the six behavioral requirements in focused modules.
- [x] Compile kernel and guest checks; run attainable checks without test runner.
- [x] Commit independently authored changes and report commands/results/limits.
- [x] A fresh reviewer receives spec, report and a complete task diff; fix all
      material findings through the implementation agent before integration.

### Task 2: Reproducible source patches and firmware validation

**Files:** SpiritBoot `patches/roswell/`, `sources/firmware-lock.json`,
`tools/firmware.py`, host build tests, provenance documents and new evidence.

**Interfaces:** Optional ordered patch entries contain repository-relative path
and SHA-256. The base revision remains pinned; patches apply only in a separate
build-source copy. The manifest records applied patch paths/hashes.

- [x] Export reviewed Task 1 commits as patches, without firmware-derived data.
- [x] Add failing host checks for checksum mismatch, failed application and
      baseline checkout preservation; implement optional patch application.
- [x] Review the integration diff and run the covering host checks.
- [x] Build release and checked flashes in the established Docker toolchain.
- [x] Run targeted guest probes and the pinned XISO suite directly in xemu;
      retain original logs, complete receipts and parsed results.
- [ ] Review final branch/provenance and publish validated source/images with
      accurate feature coverage and remaining limitations.
