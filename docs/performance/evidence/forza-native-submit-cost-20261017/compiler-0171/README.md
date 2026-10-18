# 0171: scoped optimization of the owned submission files

This is an **unselected performance experiment**, directly on selected 0168.
It appends `-O2` only to `request.c`, `native_adapter.c`, and `native_packet.c`
in Xbox/GNU Release builds. There is no 0169 static binding, no C source change,
and no change to synchronization, cancellation, completion, or lifetime rules.
Four consecutive release runs did not establish a repeatable improvement.
The experiment remains unselected. A code-shape improvement is not a Forza
streaming fix or a measured latency improvement.

## Offline evidence before the candidate build

The four-way experiment uses the exact native compiler definitions, ABI flags,
and generated headers from frozen 0168 and 0169 release builds. It compiles
isolated copies of the three owned files, then performs relocatable LTO code
generation. The original artifact directories were mounted read-only.

| Owned three-file link | `-Os` text bytes | `-O2` text bytes | Increase |
| --- | ---: | ---: | ---: |
| Selected 0168, runtime port table | 17,900 | 23,280 | 5,380 / 30.1% |
| Unselected 0169, static port binding | 18,132 | 23,728 | 5,596 / 30.9% |

With 0168, `-O2` inlines the core's `lock`, `unlock`, and `pending` helpers;
runtime port dispatch remains. It also inlines adapter enter/leave helpers
into `NxNativeAdapterSubmit` and admission. With 0169, `-O2` additionally
inlines native enter/leave and pending bodies into the core. Native prepare
and submit remain distinct functions. These are genuine removed layers of
calls and stack manipulation, with a substantial text-size tradeoff.

In both variants the adapter submit function's initial stack reservation falls
from 180 to 148 bytes; the pump grows from 76 to 84 bytes. These are individual
prologue reservations, not cumulative peak stack requirements. The unchanged
0168 pending retained-read path uses fourteen adapter acquisition/release
pairs, six in the core. Inlining removes helper overhead; it does not remove
any of these synchronization operations or establish their elapsed cost.

This partial link cannot predict the exact final kernel. Kernel functions are
opaque to this experiment. The actual 0168 whole-kernel link already folds
the acquire helper into PCR accesses and internalizes `nx_start` into
admission. Final candidate assembly must therefore be compared against the
actual selected 0168 kernel before native qualification. Static instruction
or call-site counts are not dynamic pending-path instruction counts.

`receipt.json` binds compiler commands and input-file hashes. Each variant
contains linked assembly, symbols, and section sizes. Reproduce the summary:

```sh
python3 summarize.py . --output /tmp/compiler-shape-summary.json
```

To recompile, mount the product repository read-only at `/work` and a new
writable output directory at `/experiment` in `spiritboot-toolchain`, then run
this directory's `compile.py`. It uses the preserved artifact source/header
trees listed in the receipt. This runs no firmware builder or native runner.

## Scope and validation contract

The patch uses a source-property append, after the existing global `-Os`.
Every other compiler option remains intact, including Pentium targeting,
LTO/fat LTO objects, strict-aliasing policy, frame/stack alignment, sibling-call
policy, and unwind settings. Other owned files and other configurations retain
their existing optimization setting. The selected product lock is unchanged.

`check_compile_scope.py` configures the real owned CMake file in four contexts:
Xbox/GNU Release, Xbox/GNU Debug, PC/GNU Release, and Xbox/Clang Release.
It inspects emitted compiler commands rather than matching source text. The
unmodified baseline fails specifically because the intended three files lack
the appended `-O2`; `scope-red.log` preserves that failure. The candidate passes
and verifies the retained ABI flags on every emitted command.

`exact_gate.py` validates every patch hash, reconstructs the exact owned source
and tests, and runs the existing core, adapter, packet, owner, and sense gates.
The `clang-o2` compiler wrapper replaces only optimization arguments so these
unchanged gates execute at `-O2`, including plain, ASan/UBSan, and packet MSan
configurations. The passing run is in `exact-gates.log`. Independent review
compared all 55 owned source/test files against built 0168: only CMake differs.

From the product repository:

```sh
python3 docs/performance/evidence/forza-native-submit-cost-20261017/compiler-0171/exact_gate.py \
  --repository . \
  --lock docs/performance/evidence/forza-native-submit-cost-20261017/compiler-0171/build-lock.json \
  --output /tmp/forza-0171-gates
```

The archived lock normalizes only the candidate patch path from the original
isolated `.scratch` lock; the build receipt must retain both hashes. No patch
selection or second firmware build is implied. The one authorized candidate
build uses the established recipe with a pristine source checkout at `/source`:

```sh
python3 /work/scripts/build-firmware.py --source /source \
  --output /work/artifacts/forza-owned-o2-reproduction \
  --storage-backend complete-candidate --variant release --memory-mib 64 \
  --lock /work/docs/performance/evidence/forza-native-submit-cost-20261017/compiler-0171/build-lock.json
```

Final generated-command validation must compare all native target files against
0168, allowing only the three appended optimization options. Final linked
assembly and image size must be recorded before qualification. Native tests
retain byte, callback and buffer-lifetime checks and report every case,
including regressions. Cancellation, removal and reentry are covered by the
owned host gates; the frozen native fixture does not exercise cancellation.

## Final linked result: mixed, bounded qualification authorized

The one isolated release64 build passed preflight. Flash SHA-256 is
`903e8a9462a5457966a1327373297a19e53a48401724db8f6c2ec15e26752f37`,
source tree `807f37784296969446caa6036abc701e5ad42b5b`. The artifact is
`artifacts/forza-owned-o2-release64/flash.bin`. `build-receipt.json` retains
original and normalized lock hashes. Effective commands for all nine owned
translation units match 0168 after path normalization, with exactly the three
intended trailing `-O2` additions. Independent review confirmed this separately.

The final kernel's `.text` grows from 345,252 to 350,468 bytes (+5,216); total
reported section size grows by 5,292 bytes. Core `lock`, `unlock`, and `pending`
forwarders disappear. Adapter enter/leave bodies inline into submission and
admission; runtime port calls remain in the core, as required without 0169.

However, the actual whole-kernel result exposes an offsetting change:

| Boundary | Selected 0168 | Experimental 0171 |
| --- | --- | --- |
| Native enter helper | Direct PCR accesses | Calls `KfAcquireSpinLock`, which performs those accesses |
| Native leave helper | Calls `KfLowerIrql` | Calls `KfReleaseSpinLock`, which calls `KfLowerIrql` |
| Core lock/unlock forwarders | Present | Inlined |
| Direct adapter enter/leave forwarders | Present | Inlined, but kernel helper calls remain |

Consequently the usual synchronization call depth is effectively exchanged,
rather than clearly reduced. Other pending/cache/zero helper inlining remains,
but this final binary does not prove a useful pending-path cost reduction.
Native launch was initially held and the mixed result reported. The parent
then authorized four consecutive runs with the existing artifact to measure
the uncertain net effect of the remaining helper and stack changes. This is
not a claim that synchronization call depth improved. The selected product
lock remains 0168. No second build or compensating source optimization was made.

Reproduce the actual command and final assembly comparison:

```sh
python3 docs/performance/evidence/forza-native-submit-cost-20261017/compiler-0171/check_linked.py \
  --repository . --output /tmp/forza-0171-linked-summary.json
```

The result must match `linked-summary.json`. Unlike the earlier partial link,
this check includes the actual kernel spinlock helper bodies and explicitly
asserts the offsetting call chain.

## Native decision: unselected

The [four-run comparison](../../forza-complex-cadence-20261017/candidate0171/README.md)
uses the same frozen XISO and published release xemu in the order 0168, 0171,
0168, 0171. All 32 cases run for at least ten seconds and pass the full fixture
oracle. At the primary 450 us deadline, throughput changes are +1.13% then
−0.19% at 783 free pages and +8.39% then −1.81% at 900 pages. Native read-call
cost changes reverse direction in both pairs as well. No paired mean-cost or
throughput regression exceeds 20%, but the required repeatable gain is absent.
The selected firmware remains 0168. These results do not justify further
compiler-flag changes without new evidence of a specific costly path.
