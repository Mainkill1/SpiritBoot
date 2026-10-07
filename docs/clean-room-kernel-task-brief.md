# Independent kernel implementation brief

Read only the behavior spec supplied alongside this brief. You receive no
history. Implement in `/workspace/SpiritBoot-cleanroom-kernel` on branch
`spiritboot/clean-room-kernel`; baseline commit is
`1569e2e89fb47cc72b9c704a8884f98200432bd4`. Public ABI reference is
`/workspace/SpiritBoot-public-nxdk/lib/xboxkrnl/xboxkrnl.h` and its repository.

You own all kernel/guest implementation for the six features in the spec. Do
not modify SpiritBoot integration files, publish code or firmware, or dispatch
subagents. Do not inspect any other SpiritBoot checkout, artifact, attachment,
archive or conversation. The behavioral spec and this brief are the only files
you may read from `/workspace/SpiritBoot-cleanroom`.

Build tooling is available in Docker image `spiritboot-toolchain:verified`.
Mount your kernel tree as `/src` and a new isolated build-output directory as
`/out`; configure with its `toolchain-gcc.cmake`, Release, DBG=0 or 1 and
KDBG=FALSE. nxdk image
`ghcr.io/xboxdev/nxdk@sha256:bab707b7ed2544e9956d51e7b411a4575ab66120bd608b3237698495203d15f7`
is locally available for guest compilation. Do not mount any other workspace
into those containers. Place your logs under `/workspace/SpiritBoot-cleanroom-kernel-output`.

First send an implementation approach after reading public source, then work
continuously. Use meaningful targeted tests before implementation. A feature
is not complete if it only exposes initialized fields without its real path.
If a public contract is unavailable or an architectural integration is unsafe,
explain the precise missing information instead of fabricating behavior. Keep
commits independently testable and report limitations honestly.

Write your full report to
`/workspace/SpiritBoot-cleanroom/docs/clean-room-kernel-task-report.md` with
allowed reference URLs/revisions, design, changed interfaces, feature coverage,
commands/results, commit range and unresolved issues. Return a short status,
commits, test summary and concerns. Record whether the prohibited inputs were
accessed (expected: no). Do not request user approval.
