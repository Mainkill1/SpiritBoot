# Kernel Call Optimization Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. The user selected independent agents previously and waived further approval gates.

**Goal:** Account for every exported kernel call and identify evidence-backed, bounded optimization work on a dedicated branch.

**Architecture:** Inventory the actual ABI input, partition read-only research across independent domains, verify full coverage, and prepare a concrete implementation plan from ranked findings. Source mutation happens only in that subsequent bounded plan.

**Tech Stack:** C/x86 Xbox kernel, public nxdk ABI, Python inventory verification, active CMake build graph.

**Spec:** `docs/superpowers/specs/2026-10-07-kernel-call-optimization-design.md`

## Global Constraints

The design's Global constraints apply verbatim. Prior source/image identity, ABI and observable semantics must be preserved. No community inputs reach workers, no HTTP test runner, no concurrent Docker jobs, and no unmeasured speedup claims.

## Review Focus

- Correct active backend rather than inactive ARM3/other-architecture code.
- Data exports, unmapped stubs and unused slots cannot masquerade as optimized calls.
- Alias/wrapper costs must be traced to the actual shared implementation.
- Fast-path proposals must retain overflow, ownership, IRQ/APC and ordering behavior.
- Measurement must count actual work or use matched paired trials; static speculation is labeled.

### Task 1: Complete disjoint public-source cost audits

**Files:** Coordination inventory and three JSON/Markdown report pairs; publication copies under `docs/optimization/`.

**Interfaces:** One report row per assigned ordinal with source refs, actual backend, decision, rationale, opportunity, risk and measurement. Read-only workers have disjoint output files; they do not commit or mutate source.

- [ ] Generate the inventory from the build's existing `parse_def` and `parse_map`; assert 371 unique exports, 337 functions and 34 data entries.
- [ ] Save exact domain assignments and active compile paths/defines from the matched baseline build.
- [ ] Dispatch three history-free read-only workers with their brief and permitted inputs.
- [ ] Verify every report's source tree, exact assigned ordinals/names and required fields; merge reports and assert complete, duplicate-free coverage.
- [ ] Assess top candidates, record concrete source and measurement obligations, and write the bounded source implementation plan before source edits.
- [ ] Commit the complete audit, design and implementation plan; keep a progress ledger and preserve the baseline.
