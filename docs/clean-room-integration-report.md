# Clean-room patch integration report

Date: 2026-10-07. Integration implementation is committed at
`1d3a4d7e828101520c48183e3e7e95d3a6ed5495` on `feat/clean-room-kernel`.
This report is a separate documentation commit following that frozen change.

## Source identity and scope

The public base remains `1569e2e89fb47cc72b9c704a8884f98200432bd4`.
The read-only reviewed kernel HEAD is
`f67f2b1d21f249e1dec8efa652f8747551fae844`, with tree
`8ba32f2153b4716c8cac269bad06a78553f98ded`.
`patches/roswell/0001-clean-room-kernel.patch` is the complete
`git diff --binary --full-index --no-ext-diff --no-textconv BASE HEAD --`
export: 162442 bytes, SHA-256
`747a5974ac714bcf76a6516fc1ed3ced148880907bd41a3f3f62fbd3d60b168f`.
The export retains source license notices and includes all production changes,
host fixtures, and guest tests. Its path/hash is in the ordered optional
`repositories.roswell.patches` array in the firmware lock.

Only the assigned clean-room brief, source files, reviewed public kernel diff,
kernel implementation report, and final review were inspected. No community
firmware, archive, attachments, disassembly, comparison artifacts, other
SpiritBoot checkout, or parent conversation was accessed. The kernel source was
not modified. Controller-owned documentation changes were left unstaged.

## Integration behavior

The driver rejects malformed patch entries, absolute/noncanonical/traversing
paths, resolved symlink escapes, missing files, and checksum mismatches. It
captures all validated patch bytes before applying them. Each patched build
creates a fresh `output/work-*/source` clone with its own `.git`,
`--no-hardlinks`, `--dissociate`, and an explicit rejection of remaining object
alternates. Every ordered patch is checked and applied with `git apply --index`
against saved patch snapshots. CMake uses that source and a separate
`output/work-*/build`; the supplied clean pinned checkout remains untouched.
No patches retains the original source/configure behavior.

The stable manifest key for both CMake and guest builds is `source_directory`.
For Docker builds it is an absolute `/work/artifacts/.../work-*/source` path;
native builds record their native absolute path. `source` still identifies the
supplied pristine checkout. `source_tree` records the patched Git index tree,
including newly added tests; `base_source_tree` records the baseline tree.
Ordered patch paths/hashes, `build_directory`, `output_directory`, executed
commands, lock hash, and base `SOURCE_DATE_EPOCH` are recorded. A failure removes
stale `flash.bin` and leaves a failed manifest and available diagnostics.

Git trusts only the supplied source for each source inspection. Local clone's
upload-pack does not inherit command-line `safe.directory` values, so the clone
process receives a private `work-*/git-safe.config` containing only the source
and its `.git` path. Git configuration creation runs from the verified pristine
repository and writes only the explicit private config path. No user global Git
configuration is changed and no wildcard trust is added. This is exercised in
the actual pinned root container against a foreign-owned checkout.

CI builds API regression, the targeted 23-check contracts guest, and the
5-check warm reboot guest from the tested variant's `source_directory`. The
pinned nxdk image gets `/usr/src/nxdk/bin` on PATH. Each variant runs all three
guests directly through the firmware runner and retains their captures. The
two targeted TAP plans are checked explicitly. BUILD_AND_RUN documents matching
mount paths, provenance, source isolation, and guest paths.

## Verification

The fixtures were written and run before implementation:

```sh
python3 -m unittest discover -s tests/host -p test_firmware.py -v
```

The red run had 39 tests, 20 failure records (including subtests), and 3 errors.
The failures showed that patch inputs were ignored and source identities were
missing. Existing baseline tests passed. Two further fixtures cover object
alternates and root ownership. The root fixture exposed clone trust and parent
worktree-discovery problems; those were corrected before freezing the code.

Final checks:

| Command/check | Result |
| --- | --- |
| `python3 -m unittest discover -s tests/host -v` | 41 tests; 40 passed, root-only ownership fixture skipped on native nonroot host |
| `docker run --rm -v /workspace/SpiritBoot-cleanroom:/work spiritboot-toolchain:verified python3 -m unittest discover -s tests/host -v` | 41/41 passed as root, including foreign-owned source |
| Fresh standalone clone of pristine `.reference/roswell`; `git apply --check --index` then `git apply --index` of full export; `git write-tree` | Exact reviewed tree `8ba32f2153b4716c8cac269bad06a78553f98ded`; all three guest Makefiles present |
| Pristine source HEAD/status before and after export application | Pinned base HEAD and clean checkout preserved |
| `git diff --cached --check` | Passed before implementation commit |
| `git -C /workspace/SpiritBoot-cleanroom-kernel diff --check BASE HEAD` | Passed for full exported source range |

Host fixtures verify changed content reaches CMake, newly added guest files are
tracked, ordered patches and reverse-order failure, fresh rebuilds, index-tree
identity, preserved base epoch/HEAD/content/status, detached object storage,
schema/hash/path/application failure before configure, stale image invalidation,
and normal absent/empty patch builds. They use synthetic CMake/image outputs;
they do not establish a real firmware compile or guest behavior.

Unified diff context encodes empty source lines as a single space. The scoped
`patches/roswell/.gitattributes` disables end-of-line whitespace checks on patch
containers, leaving the byte-exact export intact. Actual source whitespace was
checked separately with the full kernel range command above.

## Remaining validation and limits

The controller owns fresh release/debug/repeat builds, image reproducibility,
direct API/contract/warm guest execution, and direct XISO validation. None of
those large final firmware builds or emulator runs was repeated by this agent;
no HTTP test runner or publication was used. CI changes are committed but were
not executed on GitHub here. No final runtime, gameplay, or performance success
is claimed. Kernel-review limitations remain as recorded in
`clean-room-kernel-review.md`.

The isolated source and patch snapshots are intentionally retained per output;
repeated builds consume additional disk space. Manifests contain absolute paths,
so consumers must preserve the mount layout or translate paths explicitly.
Guest compilation adds worktree outputs after kernel attribution; use the
recorded index `source_tree` to verify the reviewed source identity.

## Independent integration review follow-up

The controller's fresh integration review found no blocking bug. Its suggested
CI hardening was accepted: the targeted 23- and 5-check guests must report
`tap.ok` equal to their expected plans, with zero TODOs and zero skips, as well
as a passing status and matching plan. Legacy API regression retains its generic
TAP grading, including acceptance of its six existing TODOs. All workflow Python
heredocs were parsed successfully and `git diff --check` passed. This small CI
assertion update changes no frozen build code, lock, patch, or kernel source.

## Container namespace correction

Controller-owned real debug/repeat builds subsequently exposed a blocking Git
namespace bug before clone/configure. Their output directories sit beneath the
mounted SpiritBoot worktree, whose `.git` file references host Git metadata
outside the `/work` mount. `git config --file` still performs repository
discovery; the attempted work-directory ceiling did not prevent discovery of
that unavailable ancestor. The failed build manifests/logs were retained by
the controller. The separate release ENOSPC failure is controller-diagnosed.

Private config commands now use `source_git(pristine_source)` to run inside the
already verified standalone Roswell Git repository. The absolute `--file` path
still names only `work-*/git-safe.config`; the pristine checkout's Git config
and source are untouched. No original SpiritBoot metadata mount is required.

The new host regression creates a fixture ancestor `.git` file pointing to
absent metadata, then builds a patched source beneath it and asserts the
pristine Git config bytes/content/status remain unchanged. It fails the prior
implementation with the exact missing-metadata error and passes the correction.
The full native suite now has 42 tests: 41 passed and one root-only skip. The
same pinned root-container suite passed 42/42. `git diff --check` passed. This
correction changes only integration tooling, its host fixture, and this report;
the kernel patch, lock, and reviewed kernel source remain unchanged. Fresh real
build/runtime validation and re-review remain controller-owned.
