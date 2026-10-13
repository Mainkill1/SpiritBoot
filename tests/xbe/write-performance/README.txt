Build from this worktree:
  PATH=/home/codex/src/nxdk/bin:$PATH make -C tests/xbe/write-performance NXDK_DIR=/home/codex/src/nxdk

Parse a native serial capture from this worktree:
  python -m tools.write_performance /path/to/serial.log

81 assertions, nine cases × nine samples. Sample 0 is first invocation of the
case; samples 1..8 are warm. Every successful case resets its path, preventing
warm loops from silently measuring a different disposition, EOF or data size.
Frozen leaves include their checks/setup/cleanup in timing. Six controls time
only one operation and verify afterwards. No test output is timed. See
../../../docs/optimization/write-performance-investigation-2026-10-13.txt for
scope, control definitions, provenance, and limitations.
