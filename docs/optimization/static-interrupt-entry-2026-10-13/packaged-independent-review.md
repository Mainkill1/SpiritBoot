# Independent static IRQ review

No source blocker found in PR236 patch `0111-static-xbox-interrupt-entry.patch`
SHA256 `de73974de3e25af2638c3faeeee184a7db0b7a9d39a6e28ae9c3ef5e3e207104`,
assembled source tree `97b9fa45c2f6f4a2a8607ad5b0ed0cfc32b8c6aa`.
This was a read-only review; no source or shared product files were changed.

The sixteen fixed entries preserve the hardware frame and save all registers
before using scratch registers. Their pushed index occupies the error-code
slot; the common `KiEnterTrap 0` reserves the remaining 0x64 bytes, matching
the earlier 0x68-byte synthetic-frame allocation. The index is read only after
register saves, then cleared before entering the unchanged native handler.
The table is writable BSS and the entries are executable, nonwritable text.

Object/table and IDT publication occur with interrupts disabled on Xbox's
single CPU, retaining the incoming interrupt state. Normal, shared-head,
replacement-head, disconnect and failed-HAL-enable paths continue using native
ownership and chain algorithms. An IDT entry is recognized only at its exact
vector slot; arbitrary handlers are not reinterpreted as interrupt objects.
Desktop behavior remains under the existing non-Xbox branch. The copied legacy
template remains part of the object but is not the IDT target.

I independently ran the exact packaged source's actual-function lifecycle
harness: **2,236/2,236 under ASan/UBSan**. I also ran its assembled-entry checker
against the packaged unstripped PE: all sixteen entry strides and destinations,
trap-frame allocation, text protection, and the separate 64-byte table passed.
The host model does not execute hardware interrupt dispatch; the parent's
separate real ISR/DPC/disconnect qualification supplies that native coverage.

The corrected code-page mechanism agrees with owned original xemu commit
`dcc536830deba245eec36cd009db5860ca04884c`; inspected build.sh, cputlb.c and
tb-maint.c have no local changes. build.sh defines XBOX. The system-mode
PAGE_FOR_EACH_TB macro enumerates the entire physical-page list. The byte-range
overlap calculation/conditional is inside `#ifndef XBOX`; therefore each listed
TB is invalidated under Xbox, including a disjoint pool interrupt stub. Once
no TB remains, code-write unprotection explains subsequent cheap data stores.
I refreshed the main writeup after the author's correction and confirmed its
old range-scan-only paragraph has been replaced. No proprietary bytes were read.
The storage agent's separate exact-binary confirmation is not represented as
an independently rerun part of this review.

I independently checked the six raw replay serial/launch/result receipts
against the published world-replay JSON: all 114 numbered assertions, 72 phase
records and expected byte hashes match, all 36 pressure phases start/end at900
pages, and all processes exit normally with no recorder. Recomputed depth12
pressure means are 75,846.75 us baseline, 48,736.25 us candidate, and 44,690.25 us
reference: **35.7438% reduction**, with **9.0534% remaining reference gap**.
These are four batches per side across two captured sequences, not confidence
intervals or full-game acceptance. The isolated ~4.9 ms interval saving cannot
be equated to the full ~27.1 ms replay gain without further host attribution.
Prototype and packaged branches differ by the separately held owner fix;
the replay keeps it fixed on both baseline/candidate. Packaging does not claim
that unrelated sibling fix or count its known failing control as passing.

The adjacent JSON records source hashes, independently verified counts and
recomputed means. Runtime source and mechanism are sound within the stated
scope; final product CI and full-game qualification remain separate gates.
