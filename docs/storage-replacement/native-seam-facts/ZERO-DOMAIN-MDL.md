# Required zero-domain MDL interoperability fact

Status: investigator fact candidate for root review, not an implementation or
native test result. This is a narrow required-caller contract in current composed
source 7e891ec86f42b1313e5cd3453347836ac451ba79. No source body is exported.

A non-null MDL can legitimately describe a nonzero transfer while its original
virtual-domain base is numeric zero. The current noncached CcZeroData path does
this deliberately: one allocated MDL starts at virtual address zero, has byte
offset zero, has locked-page metadata and a PFN vector containing the same
resident shared zero-page PFN for every covered page. The zero page was allocated,
cleared and its physical frame recorded during cache initialization. This does
not ask the class to dereference a null CPU pointer or treat an absent MDL as valid.

The paging write builder passes that same non-null MDL and its original numeric
virtual base through the IRP. FATX supplies one partial MDL for a checked subrange;
its original virtual-domain base may also be zero on the first subrange. Neither
MDL construction nor the partial-range copy rejects numeric-zero VirtualAddress.
All these paths use one PFN vector, not a Next chain. The upper owner retains the
source descriptor, physical pages and completion/wait lifetime.

The retained lower transport obtains the MDL from the child OriginalRequest and
uses DataBuffer as an index in that descriptor's original virtual domain. Hardware
scatter/gather derives physical addresses from that PFN vector and supplied segment
extent. Repeated PFNs are not a contiguous-physical-memory promise. If PIO is
selected, the lower first obtains a mapped CPU view and resolves the subrange in
that view. A zero original virtual base is therefore distinct from a null mapped
CPU address or absent descriptor. Odd-address and device alignment rules remain
independent; this finding grants no additional alignment guarantee.

The owned request primitive currently rejects a nonzero operation solely when
mdl_virtual is zero. Consequently truthful admission of this required descriptor
would fail before transport preparation. This is a source-observed compatibility
gap in a future native adapter/core pairing, not evidence that the currently
published baseline fails CcZeroData. The neutral admission contract needs to
represent descriptor presence separately from its numeric virtual-domain base.
A native adapter must still reject an absent/invalid MDL, insufficient byte/PFN
coverage, overflow, misalignment and unsupported range. Do not replace zero with
a fabricated address or rebase only DataBuffer to a mapped alias.

Independent acceptance scenarios can use a valid non-null logical MDL owner with
base 0, byte count 8192 and repeated physical-page tokens: admit its aligned first
4096-byte segment and aligned second segment at offset 4096; preserve aggregate
bytes/barriers and original-domain command offsets. Separately reject missing
MDL evidence, a range exceeding 8192, integer wrap and unsupported alignment.
These are proposed independently selected cases, not observed native values or
copied retained tests. An owned primitive correction plus production host tests
can close this narrow contract; actual candidate MDL/DMA/PIO behavior stays open.

Exact file/range/hash bindings are in ZERO-DOMAIN-MDL-SOURCE-BINDINGS.json:
cache allocation/initialization, CcZeroData, paging builder, FATX partial writes,
MDL allocation/partial construction, lower MDL selection, DMA PFN interpretation,
PIO mapping and the independently owned admission validation.
