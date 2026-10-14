# Bounded request core specification (frozen before implementation)

This slice owns transport sequencing, not an entire storage class driver. A
platform provides fixed resident slots and serializes short state transitions.
Multiple requests may remain with the lower device concurrently. No worker,
clock sample, heap allocation, retry, or bounce buffer belongs to the core.
Initialization receives the actual slot-storage byte capacity and rejects a
count beyond capacity/sizeof(slot) before clearing any device or slot bytes.
This bound also prevents count*sizeof(slot) overflow on 32-bit builds.

An admitted read or write describes an absolute disk byte offset and a range
inside a borrowed MDL virtual-address domain. Invalid arithmetic, sector or
adapter alignment, unsupported READ(10) addressing, and an insufficient MDL
fail before transport. HDD ranges stay inside capacity. Optical ranges may
cross advertised capacity, but writes are rejected. Zero bytes need no MDL.
Initialization validates a power-of-two sector size, then computes its shift
and mask once. Request alignment and CDB conversions use these values while
retaining 64-bit offset, length and MDL arithmetic through range validation.

One lower command is live per parent. Commands are sector-aligned and limited
by bytes, physical pages, ATA blocks, and READ(10)'s block count. Completion
bytes are authoritative. A short reply stops the parent; errors retain only
verified bytes and never trigger a write retry. Inline completions publish a
result for an iterative device pump; they cannot recursively launch segments.

Each command carries a slot, admission generation, and command sequence by
value. Duplicate or stale terminal reports have no effect. Slots and transport
storage remain resident. A prepared child is retired once, after its terminal
completion and after submit has returned. Parent delivery happens once, after
all child ownership ends. Parent MDL, buffer and upper lease remain borrowed.

Cancellation accepted before submission commit prevents transport. The commit
point is the locked assignment of inflight/prepared after successful prepare
and the final cancellation check. Cancellation after that assignment may race
with the actual unlocked port.submit call; the command may still reach lower.
The core requests cancellation once after submit returns if no terminal report
has already ended lower ownership, and retains resources through that report.
An already-terminal inline child is not canceled again. Verified bytes remain visible with
the cancellation status. Cancellation does not promise to undo hardware writes.
The platform must not report terminal ownership release before DMA/recovery end.

Flush establishes an admission barrier: earlier writes finish before cache
sync; later writes wait for that flush. Reads retain concurrency. Enabled cache
requires actual EXECUTE_SCSI/SYNCHRONIZE CACHE(10). Disabled cache still honors
ordering. An unsupported or unknown enabled-cache flush fails qualification.
Frozen completion causes one RELEASE_QUEUE operation using the same reserved
slot before parent delivery. Recovery is never allocation-dependent in the
core. Failed recovery quarantines new transport and terminates waiting parents;
already live lower commands receive one cancellation request and retain
ownership until terminal completion. Internal recovery cancellation returns
IO_ERROR unless the caller independently requested cancellation.

Candidate status policy: short successful data returns SHORT_TRANSFER; bytes
reported with a terminal data error count if bounded by the submitted length;
over-reported bytes return PROTOCOL_ERROR without credit for that segment.
Cancellation wins the parent's status once accepted. Recovery failures preserve
the original error, or return IO_ERROR if the original command succeeded.

Kernel integration remains a separate gate: real IRP/MDL/SRB construction,
pending marking, cancel-routine races, completion-stop return, NTSTATUS mapping,
and resident device teardown must be supplied and tested by a platform adapter.
Teardown must seal admission and track whole public-call/callback lifetimes.
Zero active slots is insufficient: the completion callback and pump may still
use device state. Callback sources must be fenced before device memory ends;
generation tokens do not make a freed device safe for later callbacks.

Write-through contract frozen before this extension: NX_WRITE_THROUGH is an
explicit request flag allowed only for NX_WRITE. Unknown flags and inappropriate
operations fail INVALID before transport; unqualified cache capability fails
DURABILITY_UNSUPPORTED before any write. Zero-byte write-through with qualified
cache performs no command. Ordinary writes keep their existing transfer behavior.

Write-through retains the same parent and slot across all data chunks and an
ordered real SYNCHRONIZE CACHE(10). Its data may execute alongside earlier
ordinary writes, but sync waits for their terminal completion. Later writes
wait until the write-through parent ends; reads retain available concurrency.
Independently established disabled cache requires no sync command but preserves
the same ordering. No FUA/SRB_FUNCTION_FLUSH shortcut establishes durability.

Candidate failure Information policy: preserve all bounded lower-reported data
bytes when sync preparation, sync completion or cancellation fails. A failed
or short data phase stops without further writes or a success claim; it issues
no sync. Cancellation before sync commit prevents its submission; after commit
sync may still reach lower, receives one cancel request if still nonterminal, and awaits terminal
ownership release. Sync contributes
zero bytes. Parent delivery remains exactly once after all resources retire.
This policy is explicit replacement behavior, not observed historical parity.
The eventual platform adapter will map FILE_WRITE_THROUGH/FO_WRITE_THROUGH/
SL_WRITE_THROUGH upper indications to this independent core flag.
