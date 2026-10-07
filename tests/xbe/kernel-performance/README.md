# Public Xbox kernel performance guest

Build once with the public nxdk checkout, preserve the resulting ISO hash, and
use the same ISO for both BIOS variants. There are no new ordinals or counters.

```sh
make -C tests/xbe/kernel-performance NXDK_DIR=/path/to/public/nxdk
tools/run-xemu --flash /path/to/variant.bin --dvd /path/to/kernel-performance.iso --mem 128 --serial file:/path/to/raw.log
```

The controller owns sequential builds and direct xemu scheduling. Use its
established direct-driver environment and capture raw serial and process
logs. Do not call `tools/api-regression-run` for the paired benchmark: that
script rebuilds artifacts and deletes its temporary raw logs. The guest
programs COM1 directly through the existing TAP emitter and issues SMC power
off after its terminal summary. No HTTP runner is used.

Each line is machine-readable:

```text
# PERF-META version=1 clock=KeQueryPerformanceCounter frequency=... samples=3
# PERF workload=pin-64 sample=0 iterations=100 ticks=... correct=1 checksum=...
# PERF-SUMMARY workloads=... failures=0
== kernel-performance end PASS ==
```

TAP includes a known-answer record and one record per workload. Tick values
are raw differences of the monotonic public 64-bit performance counter;
frequency is emitted once. Empty-loop/counter overhead is recorded as the
`empty` workload, without subtracting noise from samples. No timestamps,
absolute VAs or PFNs are included in checksums. All workloads have fixed
buffers, seeds, order and repetition counts; allocations are freed between
cases. Three samples are retained per workload except `object-cold-64`,
which inserts each new type once and has one genuinely cold sample.

Pin success uses a committed 16-MiB buffer, acquired/released every iteration.
Rejected prefixes 0/32/64/65 end at a verified reserved but uncommitted guard
page. Registry warm types are established before measurement and callbacks
check allocate/delete/free counts. The pool-fragmentation setup fills at most
4096 single-page allocations, frees pages with public page-index phase 0/1
modulo 4, verifies a four-page probe fails, then times failed four-page searches.
The setup and complete cleanup are outside timing. System-VA samples
include real backing zeroing and per-page zero checks: search-only PDE savings
can be hidden by unchanged backing work. Page tables persist after first use,
so the first sample is colder than later samples; no claim of pristine search
state is made. SHA includes two deterministic hash passes to check reset;
DES includes encrypt/decrypt round trips. Their times include these checks.

Host tests provide exact first-fit and full caller-state proofs. Run the
existing `api-regression` guest as well for public RSA, mutable vectors,
unaligned crypto and object/memory lifecycle regressions. The benchmark is
representative work, not a complete replacement for that suite. Runtime must
be measured by the controller; the repetition matrix targets at most 90
seconds and may need a lower matched repetition count before freezing the
single ISO if the actual emulator exceeds that bound.

Run at least seven paired baseline/candidate trials, alternating execution
order, under identical xemu settings and the existing 128-MiB configuration.
Preserve every raw sample. Report medians, min/max variation and paired
differences. Claim a timing improvement only beyond observed per-variant
variation and with a consistent sign in at least six of seven pairs; otherwise
report only verified work reduction. No gameplay or throughput claim follows
from these kernel microbenchmarks.
