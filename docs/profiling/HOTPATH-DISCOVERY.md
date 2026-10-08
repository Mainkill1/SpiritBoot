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

## Sampled host CPU attribution (Linux)

For cost discovery, use xemu's existing `-perfmap` independently of the TB
plugin. Attach Linux perf to the exact owned process and retain its PID, event,
frequency, clock, sampling window, lost-sample count, executable/BIOS identities
and `/tmp/perf-PID.map`. No firmware change is required. Example sampling and
export commands (operator access and perf permissions must already be available):

```sh
perf record -e cycles:u -F 97 --clockid mono -p PID -o perf.data
perf script -G --ns -F comm,pid,tid,time,period,ip,sym,dso -i perf.data > samples.txt
python3 tools/kernel_cpu_samples.py --samples samples.txt --pid PID \
  --kernel /path/to/exact-build/ntoskrnl/xboxkrnl.unstripped.exe \
  --host-executable /recorded/absolute/path/to/xemu \
  --output /path/to/new/cpu-report.json
```

Stop sampling with SIGINT when the bounded diagnostic ends; retain perf's
recording log. Use the actual numeric PID in both commands. Keep the matching
map available when exporting. The analyzer accepts only this explicit leaf
export, at most one million rows, and rejects malformed records, foreign PIDs,
foreign guest-map PIDs, zero periods, and empty windows. Existing reports are
never overwritten. `--start-ns` and `--end-ns` select an inclusive window in the
recorded monotonic clock; they do not take wall-clock UTC or guest time.

`--host-executable` matches the exact absolute DSO path from the recorder.
Without it, the compatibility default recognizes basename `xemu` only. Supply
the recorded path for `qemu-system-i386` or a renamed binary; a different module
with the same basename must not be charged to the selected executable.

Shares use each sample's event **period**, not equal weighting of sampled
rows. Categories separate mapped kernel instruction PCs, other guest code,
xemu host work, libraries, and unresolved samples. An unresolved symbol in a
known library still belongs to that library. QEMU's map associates a generated
host instruction span with its guest PC: an optional perf symbol offset is a
host-code offset and must not be added to the guest address.

Kernel symbol intervals remain estimates from the exact PE. This report does
not attribute host helpers or library work to guest callers, measure blocking,
count function calls, or identify frame-critical cost. Direct kernel JIT share
is **not total kernel cost**. Plain perf maps do not prove code-generation
identity across host address reuse; use generation-aware JIT evidence when
that affects the investigation. Input hashes identify supplied files, not the
correctness of the recorder's PID, event, clock, BIOS pairing, or scene. Retain
and review that evidence separately. Sampling runs are discovery runs, not
release-performance comparisons; no profiler is loaded in ordinary runs.
