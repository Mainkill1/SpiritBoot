# Clean-room source patch integration brief

Work in `/workspace/SpiritBoot-cleanroom` on `feat/clean-room-kernel`. The
upstream kernel baseline stays pinned to
`1569e2e89fb47cc72b9c704a8884f98200432bd4`. A separate history-free agent wrote
changes in `/workspace/SpiritBoot-cleanroom-kernel`; the controller supplies its
reviewed HEAD when dispatching this task. You may read that public-source diff
and the implementation report, but not the community archive, extracted
firmware, disassembly, comparison artifacts or parent conversation. No subagents.

Export the full kernel diff from the pinned base to the reviewed HEAD as
`patches/roswell/0001-clean-room-kernel.patch`. It includes independently written
kernel code and guest probes. Retain license notices. Add an optional ordered
`patches` array under `repositories.roswell` in the firmware lock; each entry
contains repository-relative `path` and lowercase 64-character `sha256`.

Modify `tools/firmware.py` and covering host tests to apply patches during the
build, without changing the supplied pristine checkout. No patches must retain
the original build behavior. The base checkout must still have the pinned HEAD
and be clean. Validate patch schema/path/checksum before applying; reject path
escape, malformed checksum and failed application. Create a fresh isolated
source copy under the existing output/build directory (not the source), check
and apply patches in order, and configure CMake against the patched source.
Keep base commit SOURCE_DATE_EPOCH. Record patch paths/hashes and source/build
directory identities in build.json. Any failure invalidates flash.bin as before.
Ensure git ownership/safe-directory rules work in existing root CI containers.

Add meaningful host tests for a changed fixture reaching CMake, multiple ordered
patches, checksum/schema/path mismatch, application failure, baseline checkout
preservation and normal unpatched builds. Run the full host suite and capture
commands/results. Update docs/BUILD_AND_RUN.md to explain patched source,
provenance and which source tree supplies guest builds. Update firmware CI to
build guest checks from the same patched source as its tested kernel, avoiding
an unpatched guest silently testing different contracts.

Do not overwrite existing baseline firmware files or validation evidence.
Build/run verification will be performed by the controller after review. Do
not execute the HTTP test runner, publish, or request approval. Commit the
integration and write `docs/clean-room-integration-report.md` with commits,
covering tests and remaining concerns. Return a short status/test summary.
