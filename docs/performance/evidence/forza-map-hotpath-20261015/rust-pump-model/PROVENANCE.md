# Provenance and clean-room boundary

This model was authored on 2026-10-15 from behavior-only material. The same
agent froze `SPEC.md` before implementing the Rust state machine. This is an
independent expression and a source-exposure record; it is not a claim of
personnel-separated clean-room certification.

## Supplied observations

The task supplied these facts directly: upper queue depth 12; a 1,024-read
asynchronous workload; effective PATA lower depth one; two optimized pumps
stalling after warm-up with six and five outstanding requests; the original
pump completing; and a requirement to observe at least sixteen accepted parent
requests. These facts are labeled **[observation]** in `SPEC.md`.

## Read inputs

Only the following product-related prose was opened. All are inside the
explicitly permitted request-engine behavioral-document directory.

| Input | SHA-256 |
| --- | --- |
| `PROVENANCE.md` | `92e7dd0009935b4450b06f633982034bceaa9b6506ebabb9dfb58c0e2c504a74` |
| `DESIGN.md` | `cae376055f55c3d42eed6bd658f4abcd007688550708463ea3a6797b011b730e` |
| `ADAPTER.md` | `8e75c134df20ca2c0785e8ec55710ef9b8c6179c3d495860ddda97121d978d97` |
| `KERNEL-ADAPTER-DESIGN.md` | `09e5495cacd74feb951532b3a49403985f9b35730e1b8bf075ed9576f9cc7171` |
| `CACHE-QUERY-DESIGN.md` | `14ae001a44ce178af91a16e9cf16dabfde5d009d3db0ddb9d7fdb924138af11d` |
| `CACHE-QUERY-ERRATA.md` | `4da2250b620521bf3794748aad14c2f49cb59b26d8499fac70fc3796e852a001` |

The cache-query notes were inspected as part of the permitted document set and
did not contribute pump rules. The source directory was:

`/home/codex/xemu-shader-workbench-handoff/.scratch/spiritboot-storage-pump-candidate-20261015/docs/storage-replacement/independent-implementation/request-engine/`

Process instructions read:

| Input | SHA-256 |
| --- | --- |
| `oss-clean-room/SKILL.md` | `e18044b1e86a131242535c5053b90d818de804faaec8156db213a961fdb7d257` |
| `oss-clean-room/references/separation-profiles.md` | `7e341842b4f4cf2aa40e08e23879723468936bcfd5b3e23320f27a0304a5568c` |
| `test-driven-development/SKILL.md` | `64b03fce4aee5a97a93160cea8111f3ba13a17b7c001db4bd5836d67fd10705d` |
| `test-driven-development/writing-good-tests.md` | `51471c853306ff92ca8bb41dcaea05f31c0e46b03651f8f3c99754b7172f4ae1` |

## Excluded inputs

No current or legacy C implementation body was opened. In particular, no
`request.c`, `native_adapter.c`, prior ClassPnP/Disk/nxcdrom implementation,
implementation patch hunk, product object/disassembly, or repository history was
read. No existing host test implementation body was read or copied. Filename
enumeration was used only to locate the permitted prose directory and confirm
that output stayed isolated. No network source was used.

After the independent model and specification were frozen, the separately
authored prose transition document `NXSTORAGE-QD12-TRANSITION-SPEC-v5.md`
(SHA-256
`87eb7e8977c9180992c351f5e1f7f32d5e56fbfddabf7d4c9ccdc17ad7006c8d`)
was read for a one-way audit. Its findings are recorded in `V5-AUDIT.md`; it did
not influence or modify the frozen model or `SPEC.md`.

The subsequent prose-only v6 transition document was audited in the same
one-way manner. `NXSTORAGE-QD12-TRANSITION-SPEC-v6.md` had SHA-256
`f4de6551416f8660e67ee88c8ffe1e784e1410ba8a0089547a62e0d1889da8ea`.
Findings are recorded in `V6-AUDIT.md`; the frozen model and `SPEC.md` remain
unchanged.

Public contract convergence is limited to behavior named in the allowed prose:
fixed slots, one command per parent, generation/sequence token validation,
outside-lock callbacks, completion bytes, cancellation commit point, flush and
write-through barriers, queue release, quarantine, and parent/device ownership.
Model names, event decomposition, rescan protocol, fairness cursor, status enum,
tests, and Rust expression are independently authored.

