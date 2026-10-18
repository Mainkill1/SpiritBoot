# 0169: compile-time native port binding

**Not selected in the firmware stack:** ordinary release qualification did not
establish a repeatable performance gain. The patch and its frozen build are
retained as an experiment, not applied by the current firmware lock.

This candidate removes runtime callback-table dispatch from the native request
engine. It preserves the engine and every existing lock/IRQL and external
callback boundary. The earlier full-IRP-reset idea remains unimplemented: the v12
profile attributes only about 3.76% of aggregate public-read time to packet
preparation, which includes that reset.

## Observed linked cost

In the unchanged 0168 release image, `run_pump` at `0x84051c38` has seven
indirect port-call sites. Additional forwarding functions remain despite LTO:

| Function | Address | Relevant linked shape |
| --- | --- | --- |
| `lock` | `0x84050b4c` | Eight instructions, its own stack frame, indirect call through port table |
| `unlock` | `0x84052e04` | Eight instructions, its own stack frame, indirect call through port table |
| `pending` | `0x8405139c` | Conditional indirect mark-pending callback |
| `port_enter` | `0x840514fc` | Current IRQL load, dispatch-level store, saved-IRQL store and return |
| `port_leave` | `0x84051514` | Separate frame and direct `KfLowerIrql` call |

The ordinary pending retained-read path has six core lock pairs. It therefore
executes twelve indirect enter/leave calls, plus prepare, submit and one
mark-pending call: fifteen runtime port dispatches. The twelve lock forwarding
calls add another layer of calls/returns. This is a path count, not fifteen
distinct static call sites or a measurement of time saved.

The v12 baseline diagnostic has 191 clean world-read records without an
observed DPC interval. Computing each residual within its own record before
taking the median gives approximately 34.0 microseconds for adapter outside
pump, 30.8 for pump outside prepare/submit, 41.4 for submit outside PATA, and
14.4 for prepare outside packet preparation. These inclusive instrumented
intervals include probe overhead and the baseline's earlier 64-slot scan.
They do not establish exclusive CPU cost or predict 0169's gain. In particular,
the submit residual also includes real lower-driver work; direct binding
cannot be assumed to remove it.

## Contract

The native product has one implementation of the eight port operations, used
by multiple adapter instances. `NxNativeAdapterInitialize` is the only product
caller of `nx_device_init`; it installs these operations with that adapter as
the context. Each call must continue to use its own `device->port.context`.
No singleton adapter or global request context is introduced.

`port_binding.h` selects direct internal native functions only when
`NX_NATIVE_PORT_BINDING` is defined. The production nxstorage target enables
that flag separately from `NX_NATIVE_TARGET`, allowing the same binding to be
tested on the host. Without the flag, the existing runtime table remains the
portable core test interface. Both modes compile the same `request.c`; there
is no copied native state machine.

The native initializer first validates that every supplied callback matches
the bound implementation. A foreign table is rejected before either the
device or slot storage is modified. This prevents silently accepting a runtime
interface while dispatching different functions. The port table is established
at initialization and remains immutable during the device lifetime.

The adapter changes are symbol renames and removal of private function linkage
so LTO can see direct cross-unit calls. They add no Xbox export or ordinal.
An independent review mechanically normalized those edits and found the
remaining adapter body identical to 0168. Core replacements change only the
callee expression at existing call sites, plus initializer validation and
inline hints for the two forwarding helpers. Callback arguments, evaluation
order, lock acquisition/release count, cancellation commit, lower-unwind gate,
admission order, generation checks and parent completion timing remain governed
by the existing code.

## Validation

The assembly regression first ran on unchanged 0168 with the proposed binding
flag and failed: the flag had no effect and 44 indirect engine call/jump sites
remained in the Clang i386 object. The candidate has zero. GCC's corresponding
runtime control has eleven sites and its bound object also has zero. Compiler
layout changes the static count; both controls prove the checker exercises
runtime dispatch. The bound object imports exactly the eight native port
functions, has no `lock`/`unlock` forwarding symbols and needs no compiler
helper import.

All original 42 adapter groups pass in runtime and bound modes, plain and
ASan/UBSan. Two additional groups test every foreign callback-table member and
two simultaneous devices: complete the second device first, remove it while
the first remains active, then submit and complete further work on the first.
All 44 groups pass in all four configurations with identical emitted
observations, including the retained path's unchanged fourteen lock entries.
Removing the binding-identity guard makes the foreign-table test fail.

Exact locked reconstruction also runs the owned request, active-scan
differential, pthread ownership, packet, sense, geometry, cache and owner
checks. The production gate has two passing Python tests; 62 firmware/identity
tests pass with one skip, and six corrective tests pass. These targeted results
do not replace or relabel the earlier full-host-suite history.

Reproduce from the assembled source:

```sh
python3 tests/host/nxstorage/check_adapter.py /tmp/adapter
python3 tests/host/nxstorage/check_port_binding.py /tmp/binding
CC=gcc python3 tests/host/nxstorage/check_port_binding.py /tmp/binding-gcc
python3 tests/host/nxstorage/check.py /tmp/core
```

Final linked release assembly must separately confirm the direct dispatch
survives the real `-Os`/LTO build. Native qualification must retain byte,
callback, cancellation and lifetime correctness and report all fixture cases,
including regressions. No title-specific deadline, data layout or branch is
part of this change.

## Final release artifact

Release64 complete-candidate build passed, including its storage preflight.
Flash SHA-256 is
`c7dcfe9214d422ef0477e10a2ff552e08f6c78db0675085ad6cf88eef44a5527`;
assembled source tree is `261b24f5a7ae667cc8f39670b706112aafe3c285`.
The artifact is `artifacts/forza-static-ports-release64/flash.bin`.

[The linked assembly comparison](static-ports-linked-assembly.json) verifies
both flash identities and owned linked images. It records seven indirect
`run_pump` sites before and zero after, direct mark-pending dispatch, and the
absence of the old `lock`/`unlock` forwarding symbols. The native callbacks
remain separate direct functions under the final size-optimized LTO build;
this result does not claim that every callback was inlined. The actual lock
and IRQL operations remain. Reproduce with:

```sh
python3 docs/performance/evidence/forza-native-submit-cost-20261017/check_linked_port_binding.py
```

## Native decision

The consecutive 0169 / 0168 / 0169 release trials pass all 24 generated-data
cases, but the predeclared read-return-cost metric does not improve consistently.
At 450 us / 783 pages the control averages 74.929 us per read versus 76.523 and
73.363 us in the two 0169 runs. At 900 pages the control averages 70.550 us
versus 71.593 and 72.580 us. Throughput is mixed; both 0169 runs regress the
250 us / 783-page case. The [complete native archive](../forza-complex-cadence-20261017/candidate0169/)
retains every case, identity, recipe and correctness result.

The measured outcome rejects treating indirect dispatch as the dominant cost
or this patch as an established performance fix. It does not prove that each
removed call is free, nor rule out value as part of a separately measured
future design. Product selection and test identity pins therefore remain at
0168; this document's source tree and exact-stack results describe the frozen
experimental 0169 build.
