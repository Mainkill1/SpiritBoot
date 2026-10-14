# Windows native clock-context diagnostic

The retained V4 diagnostic completed on Windows under PowerShell5.1.19041.6456,
using the normal runner and protected Codex/session1 desktop pipe. The
[receipt](windows-clock-context-native-receipt.json) binds the exact observer,
shared guard, request, xemu `8a1cbacd…`, 64 MB BIOS `c630d22f…`, configuration and
unchanged causal-clock disc `bc02de4d…`. The observer source and portable controls
are retained in `tests/xbe/storage-perf/windows-clock-context.ps1` and
`tests/host/test_storage_windows_clock_context.py`.

Both actual Windows API samples succeeded and returned QPF 10,000,000, with
positive monotonic QPC brackets. One QPF count corresponds to 1/10,000,000 second,
or 100 ns. The reviewed exact PE startup construction can conditionally derive
an integer 100 ns conversion scale for that frequency; the pilot does not read
xemu's internal scale/frequency globals or import slots. For the reviewed
733,333,333 Hz guest RDTSC branch, the strict arithmetic conversion error bound
is 1/733,333,333 second under its stated runtime/source assumptions. This bound
excludes provider resolution, precision and physical-time accuracy.

The guest emitted every marker 0..99 and sample 0..49 plus the complete END frame.
It performed zero fixture storage operations; this is not a count of BIOS boot
storage activity. The initial/final managed status responses were running, and
the process/lifetime/source/desktop guard completed. These snapshots cannot
prove continuous VM state or exclude every intervening offset/reset/pause event.
Serial polling detected END only; no Windows causal-delivery or clock-rate bound
was measured from polling gaps. The raw
[context](native-observations/windows-clock-v4-context.json) and
[serial frames](native-observations/windows-clock-v4-serial.log) remain available.

The runner recorded completed execution, passed fixture correctness and complete
evidence, then stopped the target and finalized cleanup. Its `run_storage_state`
check remains false because driver/cache qualification is unavailable. Three
declared diagnostics set the runner's diagnostic intervention flag; the ledger
records zero manual inputs, pauses or host-state changes. Neither condition is
silently waived for performance acceptance. This is collection qualification
for the exact diagnostic route, not P1, durability or full-driver acceptance.

V2 failed before QPF because the constructed effective path retained mixed
separators. V3 failed before QPF because PS5.1 selected the Framework enum
overload of String.Split. Both failures remain retained; the
[parser fix](WINDOWS-PIPE-FIELD-PARSER-FIX.md) preserves all identity checks.
Portable PS7 parser/control checks remain bounded host evidence; actual native
compatibility is established only by this recorded V4 route. Future timing
importer/calibration policy must declare its mapping and limitations separately.
