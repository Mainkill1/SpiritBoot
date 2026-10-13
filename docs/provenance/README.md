# Provenance Records

This directory is for concise records describing how non-obvious compatibility behavior was learned.

Every compatibility fix must include a writeup in this directory. State what
SpiritBoot does differently, the demonstrated cause, the resulting change, and
the regression evidence. Record failed candidates and limits when they affect
the conclusion; distinguish observations from hypotheses.

Suggested file format:

```markdown
# <behavior>

## Question
What guest-visible behavior are we trying to establish?

## Environment
- Xbox revision / emulator revision:
- SpiritBoot revision:
- Test payload:

## Observation
What was observed?

## References
Public/open references, issue links, traces, or experiments.

## Implementation constraint
What must SpiritBoot reproduce, and what remains unknown?

## Regression test
Which test proves the behavior and catches future breakage?
```

Do not store proprietary dumps, disassembly, secret material, or copied proprietary source here.

Current compatibility records include:

- [Current-main performance and compatibility integration](OPEN_PR_INTEGRATION_2026-10-13.md): the exact composed 64 MiB baseline and the write-sensitive drafts excluded from save testing.
- [Saved transition images](SAVED_TRANSITION_IMAGE.md)
- [Public title interrupt objects](TITLE_INTERRUPT_PUBLIC_ABI.md)
- [Halo 64 MiB memory compatibility](HALO_64MIB_MEMORY_COMPATIBILITY.md)
- [Native handle classification](TITLE_HANDLE_CLASSIFICATION.md)

- [Public thread identity and terminal status](PUBLIC_THREAD_IDENTITY.md): full backing storage, exact pointer translation, lifetime publication and qualified caller wait blocks.
