# Access and provenance record

Role: a separate implementation agent working from the parent task and a
filtered behavior/input package. Prior exposure to the excluded product
implementation at task start: none. Parent history was not supplied or read.
This is a record of this session's access boundary and authorship, not a
personnel-level independence claim, legal opinion, or firmware licensing
certification.

The task explicitly prohibited viewing the assembled product/Roswell tree,
excluded partmgr.c, old classpnp/disk/nxcdrom bodies, patches, Git/history,
old tests, disassembly, investigator-only notes, and linked binaries.
None was opened. There were no Git, VM, network-operation, or product-mutating
commands. No subagents were spawned. Public-documentation browsing below was
permitted; it did not operate a network service.

## Permitted local inputs actually read

All paths below are relative to the single permitted package,
/home/codex/xemu-shader-workbench-handoff/.scratch/pr248-permitted-inputs/.

| Input | SHA256 | Access/use |
| --- | --- | --- |
| README.md | e3556a3e4f46a083cb96e741c3b9af66bdede386e464c369db9c00ee0be1a565 | Package boundaries and evidence classifications; read in full. |
| approved-inputs.json | 1fcb751b17c5b7153d2675ce047db59677bbca03aa44209a489ed037672491f2 | Approved paths/hashes and exclusions; read in full, parsed for permitted public interface path. |
| GEOMETRY-WRAPPER-CONTRACT.md | 122f1bfa0ddcf6287ea119a8ec787e19f11d8a5cc95304799e3b7007761fe770 | Behavior-only geometry scope and acceptance cases; read twice. |
| PUBLIC-REFERENCES.md | ed242b01fb02d667e4bd63c84688505f00537e3f139ba46fc63b3224a8a17e98 | Approved primary interface links; read in full. |
| source/sdk/include/psdk/ntdddisk.h | 66817aa4381522928296c0ae33ab3231442386827473ba1f4e68fbdd0b233db7 | Declaration-context search scanned this approved file and displayed lines391-577; a later exact read displayed lines1-35 and365-397. Used public field order, widths, style/detection enum values, and notice. Whole file read only for hash computation. |

The header context search incidentally displayed the public
DiskGeometryGetPartition/GetDetect positioning macros at lines 519-531,
and the beginning of unrelated public partition declarations through 577.
This access was promptly reported to the parent. Those macros were not
imported or translated. The first 35 lines also displayed a compiler-extension
marker macro and the ntddstor.h include directive. That include was not
followed. No private helper body or transitive project include was opened.
The old public-domain notice was treated as applying to the admitted public
declarations, not as a license for unknown later helper implementations.

Other approved source/package files were not read. In particular, no retained
owner/caller implementation or previous test implementation shaped this code.
No broad directory listing, workspace search, or repository inspection occurred.

## Required workflow inputs

The following skill instructions were read as explicitly required by the task:

- /home/codex/.codex/skills/oss-clean-room/SKILL.md
- /home/codex/.codex/skills/oss-clean-room/references/separation-profiles.md
- /home/codex/.codex/plugins/cache/openai-curated-remote/superpowers/6.4.2/skills/test-driven-development/SKILL.md
- /home/codex/.codex/plugins/cache/openai-curated-remote/superpowers/6.4.2/skills/test-driven-development/writing-good-tests.md

The task's stricter allowed-input boundary took precedence over a generic
skill suggestion to inspect repository instructions and build guidance.
The independent package has its own complete test command and does not run
or inspect the excluded product test suite.

## Public documentation actually browsed

Primary Microsoft interface pages opened on 2026-10-14:

- [GEOMETRY_EX request](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntdddisk/ni-ntdddisk-ioctl_disk_get_drive_geometry_ex): minimum base extent, optional extent, returned byte count, and status family.
- [DISK_GEOMETRY_EX](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntdddisk/ns-ntdddisk-_disk_geometry_ex): public base/data field order and variable-record ordering.
- [DISK_PARTITION_INFO](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntdddisk/ns-ntdddisk-_disk_partition_info): public record size/style/identity meanings.
- [DISK_DETECTION_INFO](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntdddisk/ns-ntdddisk-_disk_detection_info): public BIOS record and detection discriminant meanings.

The GEOMETRY_EX structure page itself displayed the same public accessor
macros. No documentation implementation example, sample repository,
reference driver body, or linked page was followed. No reference code was
carried into the production function. The documentary source words quoted
in the deliverable are only protocol/API identifiers and necessary field names.

## Behavior-only parent messages admitted

Before production implementation, the parent supplied two new observations:
the baseline HDD public query reports BUFFER_TOO_SMALL for output 0/8/24,
SUCCESS/Information 32 for output 32, and SUCCESS/Information 40 for output 40;
the retained Xbox owner uses public PARTITION_STYLE_BRFR 128 for its fixed
layout. The parent required BRFR 128 with initialized empty identity and
accepted the explicit DetectNone candidate policy. No owner body accompanied
these messages. A later message held broad adapter work pending completion
of the native A/A freeze and clarified the host thread test's limited scope.
No native observations were performed by this implementation agent.

The later follow-up supplied behavior-only results from both native rigs:
whole-HDD GEOMETRY_EX returns Information 32/40/56/64/112/112/112 for output
lengths 32/40/56/64/112/128/256; the optional partition header is size 0/style 0
at 40 and size 24/style 0 at 56 and larger. The parent authorized a bounded
revision to preserve those counts with cleared unavailable padding and
complete fitting meaningful records. This was a new observational contract,
not access to the old expression or implementation. No native raw file,
product source, additional approved source, or new public documentation was
opened during this follow-up. Only this agent's own output files were read
or changed. The original approved-input boundary remained in effect.

## Necessary interface convergence and original decisions

Convergence is limited to required public wire facts: field widths/order,
little-endian Windows x86 serialization, MBR 0/GPT 1/RAW 2/BRFR 128, DetectNone 0,
record SizeOf fields, base 32, partition 24, and the candidate Windows x86
detection 56 layout. Internal function/type names, bounded serialization,
validation policy, metadata inputs, and tests were independently authored.
No old wrapper expression, source decomposition, helper call, old fixture,
or byte-count calculation was reused.

The independent SPECIFICATION.md was written before production behavior.
The test source was authored before the function body. An unconditional
red-phase scaffold compiled at the same production entry point; the test
executable failed 1403 assertions, then the new production behavior was written
to satisfy those tests. FAIL-FIRST.log preserves the observed failure output.
The final tests compile the exact production translation unit, including its
public ABI model assertions. They do not reconstruct or extract a baseline.

The first policy returned only complete-record prefixes and had a measured
40-byte count mismatch. SPECIFICATION-V1.md preserves that original choice.
The revised specification was frozen before changing production prefix
behavior. New tests first ran against the unchanged prior production source
(SHA256 eb0f3976eb30c139d985ee126959081c2f934e02f4cf635a8becd47db7fd9843)
and failed 263 assertions / 6001 checks. PREFIX-POLICY-FAIL-FIRST.log records
the exact production/test hashes and failure output. The new bounded count
selection was independently authored from the seven observed input/output
length pairs, not taken from old source or examples. All earlier validation,
aliasing, status, snapshot, and guard scenarios remain in the production suite.

Necessary behavior convergence now also includes those measured returned
prefix counts and the size-zero unavailable partition convention at 40.
The meaningful partition record is emitted only at capacity 56 or larger;
the meaningful initialized DetectNone record only at 112 or larger. Every
other reported optional byte is deliberately cleared, with no truncated
identity or BIOS payload. If a complete size field fits, it is zero for the
unavailable record; if fewer than four bytes fit, there is only cleared
padding and no readable size marker. This is an explicit public-interface
inconsistency: the published partition interface requires its structure
size, while the admitted native result uses zero at 40. No valid public
record is claimed for that padding. The declared behavior at unmeasured
33/39/41/55/63/111 is tested without representing it as native observation.
Observed style 0 does not settle the caller-specific BRFR snapshot mapping.

Compiler/toolchain commands read normal system headers and tooling, not
project reference source. Production includes only its own public neutral
header and the compiler's standard stddef.h. Host tests additionally use
standard stdio/stdlib/string and pthread declarations. No private project
headers are dependencies. Build outputs and all authored files are confined
to the independent output directory. SHA256SUMS identifies the authored
sources, documents, runner, and evidence logs; it excludes its own contents
and generated executable/object files to avoid a self-referential digest.

The final runner's outer login shell emitted an unrelated startup diagnostic:
`/etc/profile.d/devtools.sh: line 1: claude: command not found`.
The runner itself exited zero; all compilation/test logs are clean. The
profile script was not inspected and no environment repair was attempted.

## Qualification boundary

Host normal and ASan/UBSan checks, GCC static analysis, and i386 freestanding
compilation have passed. They qualify the standalone composer only. The
thread test exercises concurrent composer calls with independently stable
snapshots; it is not evidence of solved retained-owner synchronization.
The i386 build proves the explicitly modeled layout, not the excluded
target header's actual build ABI. No product integration, native boot,
native partition query, completion lifetime, baseline parity, full-stack
replacement, or release/license qualification is claimed.
Only returned counts at the seven admitted sizes match native observations;
record identity, full detection bytes, BRFR mapping, exact error statuses,
unmeasured sizes, and native consumers remain unqualified. No native adapter
was added; the parent may stage only the refreshed unlinked primitive.
