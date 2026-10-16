# Provenance and separation record

This investigation uses the **owned/internal reference** profile. SpiritBoot
controls the target work and the relevant current filesystem code is part of
its GPL-compatible Roswell foundation. The purpose is to derive a smaller,
measurable design contract, not to recreate a third-party implementation.

The same agent previously received a source-level hot-path audit and therefore
is not personnel-separated or source-unexposed. This artifact must not be
presented as strict third-party clean-room certification. The writing boundary
is instead temporal and documentary: `SPEC.md` was frozen in original prose
before Rust implementation, and the Rust model is built only against that
specification.

Inputs used before the freeze:

- conversation-supplied release census counts and behavior summary dated
  2026-10-16;
- operator observation that Conker blocks skipping while background loading is
  incomplete;
- existing SpiritBoot provenance policy and the clean-room workflow;
- current project-owned test contract descriptions supplied in the hot-path
  audit.

No external source, proprietary game content, decompilation, disassembly, or
Microsoft storage implementation was used. No Rust implementation from another
project was inspected. Public compatibility convergence is limited to Xbox
sector size, checked byte ranges, MDL/IRP ownership facts, status outcomes, and
existing SpiritBoot behavior.

The model and its tests are independently authored under GPL-2.0-or-later. A
successful model result is design evidence only; it does not establish source
license closure or native correctness.
