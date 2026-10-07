# Kernel optimization qualification evidence

This directory retains byte-exact local build manifests and direct xemu captures
for public kernel commit `87aba89a6ba9b2a58f2edd6e52d5e3aa1e8649d7`, tree
`f7adb302a762ed1945cc07d9c2ff428c643ba959`. Container/controller paths in raw
records are historical provenance, not portable paths. Release means DBG=0;
checked means DBG=1, KDBG=FALSE. The source and two ordered patches are public.

`final-verification.json` binds BIOS hashes, source tree, release reproducibility,
qualification summaries and historical artifact preservation. `SHA256SUMS.txt`
binds every retained evidence file. Original disk snapshots, sparse raw HDDs and
build directories stay local; no game or community BIOS bytes are included.
The `guests/` directory contains only freshly compiled open test media and its
manifest, built from the actual patched source directory using pinned nxdk.

Both variants passed the direct API guest (626 checks and six expected TODOs),
contracts (23/23) and warm reboot (5/5). Full XISO acceptance is recorded in the
variant capture verification files, COMPLETE receipts and hash comparison.
Non-applicable S3TC diagnostics remain visible and are not hidden as applicable
oracle failures. The XISO suite establishes compatibility results; its elapsed
run time is not a qualified performance comparison.

`paired-v1/` retains all fourteen sequential alternating benchmark captures,
precise controller execution order and explicit mount mapping. Every run passed
42/42. `performance-report-final.json` retains all raw uint64 ticks, normalized
presentation values and exact rational classification inputs. Its companion
Markdown lists all 41 workloads: six timing improvements, 35 inconclusive,
zero threshold regressions. There is no overhead subtraction or FPS claim.
`source-host-evidence/` and `host-work.json` separately establish actual-source
work counts and differential correctness; millions of pin assertions mostly
check scratch slots and are not independent scenarios.

`benchmark-smoke-baseline/` is the failed first guest fixture: four pool-size
checks used a contiguous-allocation query. `benchmark-smoke-baseline-v2/`
retains the corrected 42/42 baseline using ExQueryPoolBlockSize. Neither smoke
is part of the formal paired dataset. `reviews/` includes intermediate review
findings and their later resolution; read the final review for final status.

To reproduce builds and captures, use the pinned lock and the [measurement
guide](../../optimization/2026-10-07/integration-and-measurement.md).
For offline analysis, copy `paired-v1/pairs.json`, retain its execution log and
capture paths, and replace only `asset_path_map` targets with local downloaded
fixtures identified by `runtime-inputs.json`. Supply local input paths with the
same hashes and sizes, local candidate build manifest and explicit BIOS hashes
to `scripts/analyze-kernel-performance.py`. The analyzer verifies accessible
file bytes; it does not infer mount mappings. Original records here remain
unchanged. `run-paired.py` records the original synchronous collection.

[Implementation, limits and timing table](../../optimization/2026-10-07/integration-and-measurement.md).
Conker gameplay, physical Xbox hardware, 64-MiB support and attached interactive
debugger input remain unverified. Source separation used fresh public-only
implementation agents; the shared filesystem boundary is procedural.
