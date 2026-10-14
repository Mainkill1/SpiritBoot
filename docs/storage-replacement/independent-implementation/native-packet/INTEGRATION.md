# Bounded native packet integration

Patch `0134` preserves the independently authored patch bytes exactly (SHA256
`c60a66a93729ada7427fddebb6421cb1fddf8cbcb872c7f29aace557c7543c4f`).
It adds packet preparation, copied result capture and their tests. Existing CMake,
driver registration and dispatch are unchanged. The new functions are unlinked.
This does not replace the legacy class driver or qualify a release.

The independent reviewer rebuilt the actual new functions plus the owned 0133
request core: all seven groups pass both plain and ASan/UBSan. Root separately
ran the product test that verifies locked patch hashes, extracts only owned
sources, and runs both the existing owned checks and new packet checks. It passed.
The test selects an available host compiler for the new packet runner.

A temporary Git index composed both patches 0133 and 0134 over the verified
146-patch reference tree. The resulting 148-patch tree is
`99a90b8f4f59f8f907fa41f1e9dd6a23f5441687`. Both firmware CI source-identity
assertions now name that tree. Native firmware CI remains legacy-reference.

The unchanged author writeup, exposure/output manifests, RED/GREEN logs and exact
target compiler recipe are retained here. The output manifest describes the
original isolated author workspace; it is not a manifest of this documentation
folder. The admitted declaration bundle remains at
`.scratch/pr248-native-packet-owned/inputs/declarations` with exact input hashes
in `INPUT-EXPOSURE-LEDGER.json`. The target recipe uses that bundle and the
isolated `source` tree. It is not a self-contained product CI target. It verified
250 original ABI assertions plus the measured SRB facts, with no code/data in the
assertion objects and only `IoReuseIrp` imported by the packet object. Those are
object checks, not installed linkage or runtime evidence. Declaration provenance
and unresolved grants retain their existing review scope.

Caller-proven descriptor residency, PFN capacity, exclusive idle child ownership
and genuine terminal ownership remain preconditions. Submission, cancellation,
rundown, teardown, retries, dispatch, native qualification and P1 remain open.
