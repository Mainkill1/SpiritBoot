# Optional SpiritBoot execution-frequency discovery

This first profiler measures guest translation-block entry frequency from
xemu. It changes neither BIOS code nor the existing 41-workload benchmark.
The plugin must be explicitly loaded; ordinary firmware runs do not load it.

## Build and capture

Use an isolated, clean xemu checkout at the pinned source revision
`dcc536830deba245eec36cd009db5860ca04884c`. Its normal release disables plugins;
`-help` advertising `-plugin` does not prove they are enabled. Configure a
separate build with `--enable-plugins`, retaining the usual Xbox/SDL/OpenGL
options. Compile against that checkout's plugin header:

```sh
python3 scripts/build-profiler.py --xemu-source /path/to/xemu --output /path/to/new/plugin-build
python3 scripts/run-firmware.py --xemu /path/to/plugin-enabled/xemu \
  --flash /path/to/flash.bin --hdd /path/to/seed.qcow2 \
  --dvd /path/to/kernel-performance.iso --output /path/to/new/capture \
  --expect-tap --tb-plugin /path/to/plugin-build/tb_frequency.so
python3 tools/kernel_hotpaths.py --capture /path/to/capture/tb-frequency.ndjson \
  --kernel /path/to/exact-build/ntoskrnl/xboxkrnl.unstripped.exe \
  --output /path/to/new/report.json
```

Use the unstripped PE from the same BIOS build, never the newest available
symbol file. Retain the firmware build manifest, runner launch/configuration,
BIOS and executable identities beside the capture. The analyzer records the
capture and symbol-image hashes but cannot independently prove the BIOS/image
relationship. Inspect the run outcome: a complete plugin footer is a clean
profile export, not proof that a game reached its expected scene.

For game discovery, add `-plugin` with
`/path/to/tb_frequency.so,output=/path/to/new/capture.ndjson` to the otherwise
unchanged diagnostic launch. Keep normal performance comparisons on release
executables. Profiling perturbs execution; do not claim an FPS gain from it.

## Bounds and interpretation

The plugin supports one i386 system-emulation vCPU. Translation hashes include
instruction lengths and bytes; changed code at the same PC gets a distinct
record. Execution increments use QEMU's inline per-vCPU scoreboard operations,
without an execution callback, allocations or per-call logging.

Default retention is 65,536 records, with an explicit `max_records=1..131072`
option. Storage grows only during translation, to the configured limit; each
retained entry owns a fixed record, hash-table entry and one-vCPU scoreboard.
After the limit, two aggregate inline counters retain untracked executions and
instruction-weighted hotness. Reports expose dropped translations and limited
coverage. Existing output files are rejected. Missing exit footers, duplicate
identities and malformed counts fail parsing.

All retained records are exported, including the last or only record. Named
symbols and aliases are resolved only within executable PE sections, including
`PAGE` and `INIT`. PE symbol sizes are unavailable: next-symbol intervals are an
**estimate**, and attribution uses the TB start PC. Unknown addresses remain
unknown; they are not automatically called title, bootloader or kernel code.

`instructions × TB executions` is translated-instruction-weighted hotness.
Blocks can exit early; this is **not retired instructions, API call counts,
exclusive CPU time, waiting time, or a call tree**. Capture covers the entire
run, including boot calibration. Follow up with targeted kernel counters or
phase-aware observation before deciding which runtime code to optimize.

## Validation and remaining milestones

The maintained host suite tests symbol aliases, section bounds, large integer
counts, changed code, truncated export and overflow. A deterministic transport
harness executes the actual production plugin's registered inline operations;
it is distinct from native xemu qualification. CI compiles with warnings as
errors against the exact pinned plugin header. Native discovery artifacts and
private game data stay outside the source repository.

Later independent slices add phase/module attribution, kernel call/work/wait
timers and bounded histograms, realistic stress guests, frequency/cost
correlation, and paired uninstrumented performance qualification. The existing
pinned benchmark analyzer and its historical evidence contract are preserved.
