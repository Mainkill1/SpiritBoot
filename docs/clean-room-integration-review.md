# Clean-room source patch integration review

Date: 2026-10-07. Read-only implementation review of
`1d3a4d7e828101520c48183e3e7e95d3a6ed5495` against `3de911f`.
Re-review includes the integration report, targeted TAP hardening `e4195b2`,
and namespace correction `0894900`. No implementation files were edited;
this review document is the only review-owned write.

## Result

The original integration had a blocking container namespace defect exposed by
controller-owned real builds after the first review. The initial no-blocker
conclusion missed it. The defect is corrected in `0894900`; re-review found no
remaining blocker in that correction. Real firmware and runtime validation
remain controller-owned and are not claimed as passed here.

## Resolved blocking finding

**P1: Private Git config creation discovered unavailable ancestor metadata.**
At `tools/firmware.py:144-145` in `1d3a4d7`, `git -C OUTPUT/work-* config
--file ...` attempted repository discovery beneath a mounted host worktree.
That worktree's `.git` file names metadata outside the container mount. The
attempted `GIT_CEILING_DIRECTORIES` setting did not prevent this discovery.
Consequently a valid pinned standalone Roswell checkout could not build at
all: the command failed before clone/configure with an unavailable Git
repository error. The failed debug/repeat manifests and logs in
`artifacts/clean-room/final-debug/` and `final-repeat/` establish the concrete
failure. Stale flash invalidation still worked.

`0894900` changes private config creation to `source_git(source) + ["config",
"--file", ABSOLUTE_PRIVATE_PATH, ...]` (`tools/firmware.py:143-149`). Discovery
now starts in the already validated standalone source repository; explicit
`--file` writes only the private output config. The original source config is
not changed. The new regression (`tests/host/test_firmware.py:298-311`)
places output beneath a broken ancestor gitfile and checks successful patched
configure/build plus unchanged pristine config, content, and status.

The reviewer independently ran that focused regression on the correction:
one test passed. Running the same fixture with the original module loaded
in-process reproduced the exact absent-metadata failure and confirmed flash
invalidation. No disk implementation files were modified for either run.

## Scope and clean-room boundary

Reviewed the assigned integration brief and diff, `tools/firmware.py`,
`tests/host/test_firmware.py`, `sources/firmware-lock.json`,
`.github/workflows/firmware.yml`, `docs/BUILD_AND_RUN.md`, the integration report,
the patch's identity and guest build filenames, and the public pristine source's
HEAD/status. Build/run entry points and the public toolchain Dockerfile were
read to follow the integration's command and mount behavior.

The separately approved kernel implementation was not reviewed again. Its
reviewed HEAD remains `f67f2b1d21f249e1dec8efa652f8747551fae844`, with expected
tree `8ba32f2153b4716c8cac269bad06a78553f98ded`.
No attachments, community firmware, disassembly, comparison artifacts, other
SpiritBoot checkout, or parent history were read. No subagents, publication,
HTTP test runner, or expensive duplicate firmware/runtime runs were used.

## Integration checks

- `tools/firmware.py:45-57` validates an optional ordered patch array, exact
  entry keys, canonical relative POSIX paths without traversal, and lowercase
  64-character hashes. `74-88` resolves containment and rejects missing files
  before reading and hashing each patch. All verified bytes are retained before
  any clone/application; later application uses those bytes, not another read
  of the original patch files.
- `91-118` rejects overlapping source/output directories, removes a previous
  published image before lock/source/patch validation, and verifies pinned HEAD
  and a clean source. The base commit supplies the tree and epoch. Operational
  failure paths remove the image and leave a failed manifest (`173-179`). The
  preexisting overlap guard deliberately preserves source contents.
- `125-161` creates fresh output-owned source/build paths, clones without
  hardlinks, dissociates inherited alternates, rejects a remaining alternates
  file, and checks out the pinned revision. Each patch is separately checked
  and applied with `--index` in declared order. The pristine checkout supplies
  objects but is never the patch target.
- `67-71` supplies invocation-local source trust. `142-151` creates a private
  clone configuration containing only the explicit source and `.git` paths;
  configuration creation runs from the verified source repository, avoiding
  unavailable ancestor metadata. No wildcard trust
  or global configuration mutation is introduced. The reported root-container
  foreign-owner fixture covers the intended ownership case.
- `112-119`, `126-128`, and `162-166` attribute ordered patch identities,
  baseline tree/revision/epoch, actual source directory, index tree, build/output
  directories, and executed build commands. CMake and its toolchain path point
  to the same patched clone. Absent/empty patches retain the original source
  and original fresh configure-directory layout.
- `.github/workflows/firmware.yml:64-100` obtains guest paths from the tested
  variant's `source_directory`, uses the same `/work` mount as the firmware
  build, and runs API regression plus the two targeted guests against that
  variant's flash. Guest Makefile/ISO names match the exported patch. Shell
  failure propagation and runner exit codes make failed/incomplete/timeout runs
  fail CI; the targeted plans are additionally checked as 23 and 5, with all
  checks passing and zero TODO/SKIP records after `e4195b2`.
- Host coverage exercises changed content reaching configure, newly tracked
  guests, application order and reverse-order failure, fresh clones, preserved
  baseline, hash/schema/path/symlink/application errors, empty/absent patch
  compatibility, object isolation including inherited alternates, base epoch,
  and foreign ownership. Synthetic CMake outputs are correctly described as
  host integration evidence, rather than real firmware/runtime evidence.

## Evidence and limits

The reviewer independently ran patch SHA-256 and public source HEAD/status
checks. The patch hash is
`747a5974ac714bcf76a6516fc1ed3ced148880907bd41a3f3f62fbd3d60b168f`.
The reference remains at
`1569e2e89fb47cc72b9c704a8884f98200432bd4`, with empty porcelain status.

The initial integration report records 41 native host tests (40 pass, one
root-only skip), 41/41 passing in the pinned root container, and exact patch
application to the reviewed tree with a preserved baseline. Those runs did
not cover the broken ancestor gitfile. The corrected integration report
records 42 native host tests (41 pass, one root-only skip) and 42/42 in the
pinned root container. These full runs were supplied as evidence and were
not duplicated by this reviewer. The reviewer's independent focused red/green
regression is described above. The controller is separately running fresh real
firmware builds. GitHub Actions itself has not been executed in this review.

Documented limits are appropriate: output clones/snapshots consume disk;
absolute manifest paths require a matching mount layout; guest build products
appear after the attributed index tree is recorded. The source-tree claim is
about the recorded Git index, not future arbitrary worktree modifications.

## Accepted optional improvement

Generic TAP grading intentionally permits TODO and SKIP records. `e4195b2`
adds `tap.ok == plan` and zero TODO/skipped checks at
`.github/workflows/firmware.yml:96-100`, explicitly requiring all 23/5 targeted
checks to execute successfully. This accepted hardening leaves the legacy API
regression's existing TODO behavior intact.
