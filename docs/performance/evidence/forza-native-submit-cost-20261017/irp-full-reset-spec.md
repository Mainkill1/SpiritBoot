# Full IRP reset: preparatory contract and measurement gate

No production change is proposed yet. The ordinary 0168 owned image and the
preserved baseline have identical `IoInitializeIrp` machine code at
`0x840150a8`: a `rep stosb` at `0x840150be` clears `PacketSize` bytes. The public
initializer sets the header, stack count/location, current APC environment and
empty thread list afterward. `IoReuseIrp` preserves allocation flags, performs
the same initialization and sets the requested status. Its preconditions remain
no cancellation routine and an unlinked thread-list entry.

The retained child path calls `IoReuseIrp` once per prepared packet. Native
layout is 128 IRP bytes plus 36 bytes per stack entry. Even the one-stack case
therefore executes 164 byte-store iterations; a full dword implementation
would need 41 iterations for the same byte coverage. This is a static iteration
count, not a latency prediction. Parent allocation also calls the initializer.
The previous coarse profile's `irp_ns` measures `IoAllocateIrp`; it does not
separately measure the retained child reset inside packet preparation.

Before implementation, measure packet preparation as an upper bound on this
cost, then initializer time/count and actual `PacketSize`/`StackCount` if needed.
The parent allocation interval was roughly nine microseconds in the earlier
diagnostic, so this candidate is plausibly a partial gain and cannot explain
all remaining submission time without further evidence.

Any implementation must satisfy these obligations:

* Clear every byte in the original `[Irp, Irp + PacketSize)` range, including
  all stack entries, padding and any non-word tail. Never round the range up.
* Preserve exactly the existing post-clear header, stack pointer, APC
  environment and thread-list assignments, and reuse allocation/status behavior.
* Preserve valid alignment requirements of the typed IRP API. If a generic
  byte-range helper is introduced, separately test arbitrary destination
  alignment and zero/short lengths; those are helper obligations, not permission
  to pass an under-sized or misaligned IRP to the public API.
* Keep callbacks, IRQL transitions and cancellation/lifetime gates unchanged.
  Omitting supposedly unused IRP state is outside this proposal.
* Retain a byte-exact fallback for any length/alignment the chosen wider path
  cannot safely handle. The final i386 disassembly must demonstrate actual wider
  stores; a host benchmark alone cannot establish target code shape.

`check_irp_reset.py` extracts the two exact functions from a supplied owned
source tree and compiles them with a deliberately opaque host IRP model. The
oracle compares the entire backing arena: every zero byte, assigned field,
pointer, retained reuse flag and both outer poison regions. It tests multiple
naturally aligned addresses, stack counts, APC states, sixteen tail lengths,
and near-USHORT-limit sizes with ASan/UBSan. It does not assert a native ABI or
model real IRQL/thread concurrency. The full owned adapter suite remains
required for lifetime/reentry behavior.

```sh
python3 docs/performance/evidence/forza-native-submit-cost-20261017/check_irp_reset.py \
  --source-root artifacts/halo-final-queued-release64/work-3y5us6t0/source
```

The optional `--mutation truncate-tail` and `--mutation overrun-tail` runs must
fail. They demonstrate that the oracle rejects both skipped tail bytes and
writes beyond the requested packet. A future implementation using a helper
must add that exact helper to this build rather than replace it with a model.

Baseline result: 2,568 complete-arena observations pass with ASan/UBSan.
Both tail mutations fail at the first odd-sized packet.
[The code-shape record](irp-reset-code-shape.json) preserves the identical owned
initializer instructions from the baseline and 0168 builds.
