# Provenance Records

This directory is for concise records describing how non-obvious compatibility behavior was learned.

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
