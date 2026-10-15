# Xbox public-kernel contract differential investigation

Status: **three firmware divergences are corrected and the identical final
native contract pair passes.** This work tests
public Xbox kernel behavior needed by titles. It does not implement or qualify
the independent storage replacement.

## Why this investigation was run

The expanded `kernel-export-contracts` XISO added coverage for public exports
which had not been exercised by the earlier 68-check fixture. Its first run on
the 64 MiB SpiritBoot candidate
`42ad0c392b97d195f6aacaa47b1c168f1f74038ddf3258257b21cfde99bcb647`
completed all 119 checks but failed six. The exact portable
[initial receipt](../provenance/evidence/pr248-kernel-public-contracts/initial119-receipt.json) has
SHA-256
`614aecb7c0aca771a3af6ab3506d5761012782717e7689da31a7ada9aa905e7c`.
The fixture ISO was
`b6523675a9b7f2e4be9967bae9659007ed75cff826838c143c6ef535da6b37e9`
and the XBE was
`5fe0b9eea75cba05fb1ce87a982936a24269c240a4cb7390c62f24744729a4be`.
No retry was used. Thirty preceding fixtures passed; the final-row Complex
control was intentionally withheld after the six disagreements.

The failed assertions concerned two observations of DPC state outside a DPC,
two `ZwFsControlFile` IOSB fields after a synchronous rejection, and two PCI
identity checks. Diagnostic V1 kept the 119-check product oracle unchanged and
added raw values. Its portable
[V1 receipt](../provenance/evidence/pr248-kernel-public-contracts/diagnostic-v1-receipt.json) has
SHA-256
`51975de0b8d40e9948abfca3ea254747d692f9356c89701289ecdde4da91833f`.
SpiritBoot reached all checks with 116 passing and three failing because the
extra logging changed the two outside-DPC observations. Complex reached check
88 and stopped with fatal error `0x44` when the diagnostic passed a deliberately
poisoned object to the invalid-request path. That object was not a valid IRP,
so V1 cannot establish an invalid-request completion contract.

Diagnostic V2 removed only that unsafe call and the pre-existing synchronization
level assertion so both BIOS arms could reach the later phases. The identical
115-check ISO was
`52590b7de10e0a2f2b6ed61849b3cecca7071aef8c9506cde8faf6e2fe39a16b`;
its XBE was
`c37057f66802c441f22fee35df460c478450110f729d252db799bee897460768`.
The portable [V2 receipt](../provenance/evidence/pr248-kernel-public-contracts/diagnostic-v2-receipt.json) has
SHA-256
`e73a9511505d2563918ee888e6f82cd55058fcf954a94a397e6f10600ebd203b`.
SpiritBoot passed 112 of 115 checks and Complex passed 113. Both returned
`STATUS_INVALID_DEVICE_REQUEST` (`c0000010`) for the rejected filesystem
control and left the IOSB status and information sentinels at `a5a5a5a5`.
SpiritBoot's synchronization export produced IRQL 2 while Complex produced 28.
Every one of ten SpiritBoot PCI reads left its output sentinel unchanged;
Complex returned the emulated Xbox identities, including `02a510de` for bus 0,
device 0, function 0, `ffffffff` for blacklisted function 1, and `02a010de`
for bus 1, device 0.

Diagnostic V3 used an isolated title device, a real IRP returned by
`IoBuildDeviceIoControlRequest`, and the device's dispatch table to call
`IoInvalidDeviceRequest`. The ISO was
`60abd451deefe884d5925480076f5f50cdcf690c9799ecad5648f618478133fb`
and the XBE was
`48d05a8f12d85ef4e867aeb5515ec49771b51325ebb37966ab0f19c4cdebd5ae`.
The candidate serial is under
`.scratch/pr248-ioinvalid-valid-irp-v3-20261015/runs/candidate/evidence/20261015-044115888-297bfa941f704af495735ab968442523/`
and has SHA-256
`876e85e8800d04ab05b24437141f8fee33137a34845ee26374788cf1ec0ae21e`.
It returned `c0000010`, did not signal the event, and did not publish either IOSB
field. A fallback `IofCompleteRequest` returned but still did not publish those
observations. The Complex serial is under
`.scratch/pr248-ioinvalid-valid-irp-v3-20261015/runs/complex/evidence/20261015-044610607-5866bf8b54464d0cadc713ef007b846f/`
and has SHA-256
`456be641c9075ef36ebbbc45081090a3a15d4b431173f29974581ab507cb3a64`.
Complex returned the same status and exposed the same event/IOSB values, then
the fallback completion raised fatal error `0x44` with parameter 1 equal to the
probe IRP. This is consistent with the IRP already being in a completed state,
but the probe did not install a completion routine and therefore cannot prove
which transition occurred or make the event/IOSB observations a valid oracle.
The two V3 runs are preserved in the portable
[V3 receipt](../provenance/evidence/pr248-kernel-public-contracts/diagnostic-v3-receipt.json),
SHA-256
`89c85ccda339ce4cc26fcc99b70e739e547a38b83c6b072ac732dd2627468a4d`,
as incomplete diagnostics rather than qualification.

Diagnostic V4 installed an explicit completion routine that returns
`STATUS_MORE_PROCESSING_REQUIRED`, retains the IRP for owned cleanup and never
attempts a fallback completion. Both arms used the identical XISO
`c52c4afb4dc8629b17dca5a679781ca410c1a32eafff71f74ee7f03872247983`.
The portable [V4 receipt](../provenance/evidence/pr248-kernel-public-contracts/diagnostic-v4-receipt.json) has
SHA-256
`4bc653267dfeee74831338a83283f2db2c7a559f979c5c40b037898c17666d57`.
SpiritBoot invoked no completion routine, timed out the finite wait and left the
IRP status sentinel unchanged. Complex invoked the routine exactly once,
signaled the event, passed the exact IRP and published
`STATUS_INVALID_DEVICE_REQUEST` in the IRP. Complex supplied a null device
argument to this final stack completion. Both arms safely unlinked and freed
the retained IRP without a second completion. This establishes that the
SpiritBoot export omits the required completion transition.

## Corrected oracle

Two original assertions were assumptions rather than stable Xbox contracts.
`KeIsExecutingDpc` sampled outside the DPC callback changed between the first
run and the logging run, even though the callback-contained DPC check remained
stable. Only the callback-contained assertion belongs in the product fixture.
Raising IRQL alone is tested through the observed IRQL; it is not used to infer
the transient outside-callback DPC state.

The rejected filesystem-control call has a stable synchronous return value on
both BIOS arms. Neither arm writes the caller's IOSB in that path. Qualification
therefore checks the returned `STATUS_INVALID_DEVICE_REQUEST` and successful
handle cleanup, without requiring an IOSB status or byte count that the
reference BIOS does not publish.

The invalid-request fixture now uses the V4 completion-routine method. It owns
a real one-stack IRP, returns `STATUS_MORE_PROCESSING_REQUIRED` from the
callback, verifies one callback with the exact IRP/context and final status,
then unlinks and frees the retained request. It does not infer completion from
the builder event/IOSB behavior disproved by V3 and never issues a second
completion.

A superseded 120-check product fixture then showed one last invalid assumption.
The corrected SpiritBoot candidate cleared `IoStatus.Information`, while Complex
completed the same IRP and preserved its `a5a5a5a5` sentinel. Both invoked the
completion routine exactly once with the exact IRP/context and final status.
That pair is retained in the portable
[superseded 120-check receipt](../provenance/evidence/pr248-kernel-public-contracts/superseded120-pair-receipt.json),
SHA-256
`605cc40d8dca9f5366e7d07757aed3adc01388cc0988aeebc71d478868e8a9b0`.
The final implementation and oracle therefore preserve the information field.

## Isolated firmware causes and bounded fixes

Public ordinal 130 currently resolves directly to the native
`KeRaiseIrqlToSynchLevel`. The retained uniprocessor definition aliases
`SYNCH_LEVEL` to `DISPATCH_LEVEL`, so the export selects 2. The reference BIOS
selects Xbox clock level 28. Changing the global constant would also change the
internal dispatcher locking policy. The bounded correction is an Xbox export
wrapper that calls the existing IRQL primitive with clock level 28 while
leaving every internal dispatcher user unchanged. The investigation report is
`.scratch/sync-irql-divergence/REPORT.md`, SHA-256
`a9ce4f57bbc875de085e037e8c7e82ea0c1acd171dce8814a3e451bdc40f22a6`;
its unintegrated proposal is
`d3a48a6376c7a7ba25a4d123851def985e206203e54193a99ddfa9cf10500d51`.

`HalReadWritePCISpace` currently delegates to generic HAL bus-handler lookup.
SpiritBoot's static Xbox device tree does not create those generic PCI bus
handlers, so the public export returns without performing configuration-space
I/O and leaves read buffers untouched. The retained Xbox PCI code already has
the Type-1 port access, blacklist and shared lock required by the static tree.
The bounded correction is a title-time range adapter over those existing
mechanisms: narrow bus/register inputs to the hardware field widths, ignore
reserved slot bits, preserve blacklisted reads as `ff`, use exact
byte/word/dword accesses, serialize the complete range with the retained lock,
clear CF8 before release, and avoid allocation or persistent state. The
investigation report is
`.scratch/pr248-pci-export-divergence-20261015/REPORT.md`, SHA-256
`7d3f37800698505f07975d63843769d7464f3a648bf8d23dd906ade91f576a3c`.
Its unintegrated suggestion has SHA-256
`820c88c029506962ed7a9bcf64b80f1252f9cd21b30e4809b33431849904a1d9`;
the product implementation is reviewed and verified on its own merits rather
than treating that suggestion as accepted code.

Two read-only native boundary pairs fixed the adapter's input-normalization
contract before qualification. Complex wraps bus and register numbers to eight
bits, permits a range to cross register 255, ignores the slot's reserved bits,
and returns `ff` for the two Xbox safety blacklists. The first portable
[boundary receipt](../provenance/evidence/pr248-kernel-public-contracts/pci-boundary-receipt.json) has
SHA-256
`3b68dd0b1009f5ca6a2afc6e0589d0236c581e7256325bdfdac621fd982ac4da`.
The final discriminator showed that Complex applies the blacklist after bus
truncation; its portable [receipt](../provenance/evidence/pr248-kernel-public-contracts/pci-blacklist-order-receipt.json) has
SHA-256
`305421cc2a4d7140193fcd9588fe24cfac15362641d3b98b33ae07c3caa5af1a`.
Both pairs ran each arm once through the Windows user desktop pipe with guards,
private state and cleanup verified. They performed no PCI writes.

`IoInvalidDeviceRequest` currently returns `STATUS_INVALID_DEVICE_REQUEST`
without setting the IRP status or completing it. The bounded correction sets
the final status, preserves the caller's information field as the Complex
reference does, invokes the existing completion path once, and returns the
same status. It adds no allocation or persistent state.

## Provenance and scope

V1, V2 and V3 are independently authored public-API fixtures. Their inputs are
the built BIOS images, public declarations and values printed by the guest.
They do not extract implementation expression from Complex. The Complex arm is
a behavioral reference only. Scratch reports and suggested hunks are review
artifacts, not linked build inputs or automatic authorization to copy code.

The synchronization and PCI investigations inspect SpiritBoot's selected
kernel source to explain SpiritBoot's own behavior. They do not inspect or feed
the excluded storage-class bodies into the independent storage implementation.
Any integrated production change must remain repo-native, appear as a locked
patch, compile in the pinned firmware toolchain, and pass the source/provenance
checks already required by PR #248. These corrections do not reduce the P2-P5
storage replacement, license review, native correctness, durability or game
qualification gates.

## Final bounded acceptance

Locked patch `0137-xbox-public-kernel-contracts.patch` has SHA-256
`f3e34548351cef6f6016dca58695e42945fc0bf62510fdf8dbde2563bd7590a1`.
The final assembled tree is
`8d0d83ef8ca0fcfb716c58bbec1f3aed2333d4f6`; its release64 BIOS is
`0f6e4f48269e0ef65bb27758e221b4bcdb707ef0cbf57c211d7e969866334d5e`.
An independent clean release64 build produced the same BIOS byte for byte.
The final patch also exposes `CLOCK_LEVEL` to the pre-existing extracted-body
interrupt fixture; this is host-test support only and leaves the qualified
firmware byte-identical.

The corrected 119-check XISO has SHA-256
`48e950a387cefc750bcdde184a4e0decbf11e0ec6f896ddd458a9ee0dd3b437b`;
its XBE is
`7d783ce7edca6b44d4ca939ce6cbf35df3a2beeefa4de576a94f6aaf8063a6da`.
SpiritBoot and Complex each passed 119/119 with terminal `PASS`, no
TODO/skip/failure and byte-identical serial output
`91c90aaebdfc4a4af1837954e03820b87ac49fb608e43a7e9da0711d8ee54232`.
The exact portable [pair receipt](../provenance/evidence/pr248-kernel-public-contracts/final119-pair-receipt.json) has SHA-256
`89081d9b5c67898d7c3375d004eca3de1c416ea528fa86446673b3f226f73fcb`.
Both one-shot arms used the Windows user PowerShell pipe, fixed 64 MiB memory,
identical XISO/xemu settings, private state and complete cleanup.

The actual assembled PCI adapter passed 77 host behavior assertions across 16
alignment/remainder cells. Seven focused Python tests and the complete product
host discovery pass; the final integrated run reports 499 passed and 26 explicitly skipped.
The 31 registered native fixtures also passed once on this final release64 BIOS:
5,481/5,481 assertions with complete USER-pipe cleanup. Its portable
[matrix receipt](../provenance/evidence/pr248-kernel-public-contracts/final119-candidate31-matrix-receipt.json) has SHA-256
`bded70a265fcc11781966b5a5c1d5a79d46369eff5a5cffa0071f8f277177cce`.

The expanded final Windows run passed all 36 registered fixtures on this image:
6,197 successful assertions and two declared TODOs out of 6,199 checks. Complex
passed 19, completed six with reference-oracle discrepancies and did not
complete eleven. The portable
[comparison receipt](../provenance/evidence/pr248-final-windows-matrix/COMBINED-36-COMPARISON-RECEIPT.portable-v2.json)
has SHA-256
`608c0b4126bfeed08810991395efc67e555062967a9051983eaf835ebbfc9a48`.
Two-run performance-fixture correctness also reproduced SpiritBoot 72/72 for
scatter/gather and 42/42 for kernel performance; Complex reproduced 72/72 and
35/42. The [portable performance summary](../provenance/evidence/pr248-final-windows-matrix/PERFORMANCE-TWO-RUN-SUMMARY.portable.json)
has SHA-256
`7f24f74740e6d1ed378eab41574245fd4983056dd00c53d45c7a721f98105ef7`.
The Complex support-discovery schedule used a shorter completion ceiling, so
these timings cannot support a cross-BIOS performance claim.

The synchronization correction must be export-only. Host/source checks must
show that internal dispatcher-lock call sites and their level remain unchanged.
The PCI adapter needs exhaustive width/alignment and wrapping-range tests,
exact-width write tests, blacklist no-I/O tests, one shared-lock interval
around a complete range, and no allocation or new persistent lock. Native write/restore testing
must use an isolated xemu-only field characterized on Complex first; the
read-only identity fixture is the hardware-safe gate.

The broken PCI no-op is not a performance baseline. A future write comparison
must characterize and restore an isolated xemu-only field; the accepted native
gate remains read-only. The export-only IRQL wrapper adds no work to internal
scheduler or dispatcher paths; map and call-site checks establish that scope.
All firmware profiles build from the same tree, but the installed independent
storage replacement, its before/after performance campaign, physical hardware
and game routes remain separate PR #248 gates.
