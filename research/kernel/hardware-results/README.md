# Hardware kernel-test results

This directory is for normalized results from **actual** xbox_kernel_test_suite runs.

SpiritBoot intentionally does not infer a hardware PASS from test source code, comments, emulator behavior, or an implementation that "looks right."

## Import

Run:

```powershell
./scripts/import-kernel-test-log.ps1 -LogPath path/to/kernel_tests.log -Environment "Retail 1.6"
./scripts/correlate-kernel.ps1
```

The importer recognizes the current test-suite footer forms:

```text
001 - ExampleApi: All tests PASSED
001 - ExampleApi: One or more tests FAILED
001 - ExampleApi: SKIPPED - reason
001 - ExampleApi: Test completed in 0.123 seconds
```

It also records test-suite build ID, kernel version, hardware information, PIC version, submitter/name metadata, and the local source-log path.

## Provenance rules

For a result intended to become authoritative:

- preserve the raw log outside the repo or in an approved evidence store;
- record a hash/location for the raw artifact if it cannot be committed;
- identify Xbox motherboard/revision as precisely as the test suite permits;
- keep the exact test-suite revision/build ID;
- do not merge results from different test-suite revisions as though they were identical tests;
- retain failures and skips; do not publish only passing rows.

A normalized PASS means "this particular test passed in this recorded environment." It does not prove the API is completely specified.

## Source-code licensing

The current xbox_kernel_test_suite `LICENSE` file is GPL-3.0. SpiritBoot treats the suite as an **external test/reference tool** and imports metadata/results. Do not copy test implementation code into GPL-2.0-only SpiritBoot code without resolving the license implications first.
