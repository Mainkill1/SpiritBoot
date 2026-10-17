# PR248 scalar page-pin integration manifest

Port exactly the files below from the isolated candidate worktree. Do not port
`.scratch/`, `.scratch-red-page-pin.log`, generated firmware/XISO binaries, or
raw emulator captures.

## Product and native workload patches

- `patches/roswell/0144-page-pin-native-workload.patch`
- `patches/roswell/0145-scalar-page-pin-hotpath.patch`

## Host tests

- `tests/host/test_page_pin_scalar_candidate.py`
- `tests/host/test_nxstorage_production.py`

The second file is the required local PR248 gate correction that the isolated
experiment inherited. Its Git diff has SHA-256
`46effb1552ec1fe8c6eb6e63b3b8af6168447c75a9f9d73d07f3cddeb746f1a4`.

## Lock, workflow, regression registry, and coverage

- `sources/firmware-lock.json`
- `sources/native-regressions.json`
- `.github/workflows/firmware.yml`
- `sources/kernel-coverage-inputs.json`
- `sources/kernel-coverage-report.json`
- `docs/storage-replacement/KERNEL-COVERAGE-MAP.md`

For `sources/kernel-coverage-inputs.json`, preserve the key and array order that
already exists on PR248. Apply only the semantic value changes: the declared
assembled tree and the SHA-256 values for `sources/firmware-lock.json` and
`sources/native-regressions.json`. If the required 0143 production-gate fix is
not already present at the integration tip, its
`tests/host/test_nxstorage_production.py` hash also changes. Then regenerate the
coverage report. Do not port the earlier sort-only 1,062-line rewrite; this
worktree has already reduced its own coverage-input diff to four changed lines
against detached commit `a56f614`.

## Evidence and reproduction tools

- `docs/optimization/evidence/page-pin-scalar-20261015/README.md`
- `docs/optimization/evidence/page-pin-scalar-20261015/INTEGRATION-MANIFEST.md`
- `docs/optimization/evidence/page-pin-scalar-20261015/analyze.py`
- `docs/optimization/evidence/page-pin-scalar-20261015/analysis.json`
- `docs/optimization/evidence/page-pin-scalar-20261015/analysis.csv`
- `docs/optimization/evidence/page-pin-scalar-20261015/summary.txt`
