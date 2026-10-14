# Required upper MDL shape and transport domain

Status: bounded source-observed caller contract for root review; current composed
source 7e891ec86f42b1313e5cd3453347836ac451ba79. These findings cover the required
FATX, XDVDFS, cache and Xbox scatter/gather routes inspected here. They are not a
universal claim that arbitrary kernel callers never create chained MDLs.

| Required route | Shape reaching the retained raw class/lower boundary | Lifetime/domain consequence |
| --- | --- | --- |
| FATX direct whole contiguous-file read | The original parent IRP/MDL is forwarded unchanged through the fast route. A missing user MDL is locked into one descriptor. | Preserve its original virtual domain, pages and the upper tagged file lease through terminal completion. File-contiguous extent does not imply physically contiguous RAM. |
| FATX ordinary noncached/paging read/write | Each disk child allocates one partial MDL describing a subrange of the parent PFN vector. Multiple disk children are separate IRPs. | Each child descriptor has its own single vector; no Next chain is constructed by these builders. Parent physical fragmentation is preserved. |
| Cache page fill/writeback | One descriptor over a protected nonpaged buffer is passed to the paging builder. | Borrow its retained PFNs and mapping ownership; whole buffer residency does not imply one physical run. |
| Cache noncached zero-fill | One locked-page descriptor has numeric-zero original virtual base and repeated shared zero-page PFNs. | This is a valid descriptor, not an absent buffer. See the separately root-admitted zero-domain fact. |
| XDVDFS file read | Maps the supplied caller MDL into a CPU view; sector bulk and edge-buffer reads create independent synchronous lower IRPs, each with one freshly built direct-I/O MDL. | The lower child descriptor's domain is the buffer used by its own builder, which can differ from the upper caller's original domain. Preserve each child's descriptor/buffer lifetime. |
| Xbox ordinals 220/237 scatter read/gather write | The Xbox-specific implementation presents one MDL. Qualified large synchronous writes contain caller PFNs in one vector; other paths use one protected bounce-buffer MDL. | The caller's array of page pointers is not an MDL Next chain. Direct PFNs can be fragmented; a mapped CPU alias is not automatically the MDL's original virtual base. |

The generic desktop NtReadFileScatter/NtWriteFileGather stubs are not the operative
Xbox ordinal implementations. The current ordinal mapping binds XeNtReadFileScatter
and XeNtWriteFileGather. A title's scattered page array must therefore not be used
as evidence that the class receives linked MDLs. No required Next-chain producer
was found in these concrete routes. This narrowly closes the caller-shape question
for the stated scope; unexpected arbitrary chains remain a separately declared
unsupported input until a real required producer is shown. Do not conflate a PFN
vector with descriptor chaining or add a flattening copy for physical fragmentation.

For an admitted nonzero request, keep its actual descriptor distinct from its
numeric original virtual base, including base 0. Each command DataBuffer is a
checked subrange in that descriptor's original virtual domain. Verify extent,
page/PFN capacity and overflow before submission. The lower borrows the child
OriginalRequest's MDL and passes it plus the selected DataBuffer/length to hardware
scatter/gather; it does not walk Next to supply omitted bytes. Its bus-master
mapping uses the PFN vector and corresponding domain offset. Supplying an arbitrary
mapped alias as DataBuffer against a different original domain is invalid.

Borrowing the same descriptor for successive checked segments is supported by
that lower subrange contract. Lower-owned scratch release distinguishes its own
allocated MDL from the supplied borrowed descriptor. The adapter must not free,
resize, relayout, clear mapping flags or unlock the upper's MDL. The upper completion
owner already cleans its descriptor after the lower and adapter lifetimes end.
This permits a correct borrowed-MDL path without a reusable partial-MDL dependency.

Address and sector alignment are separate. The lower attempts DMA only for its
supported alignment; an odd transfer address skips SG construction and selects
PIO when that channel supports it. PIO resolves the selected original-domain
subrange through a mapped CPU view before port access. DMA-only channels can fail
this fallback. XDVDFS sector-aligned bulk reads do not establish word-aligned
caller addresses, so an adapter must preserve the supported odd-address optical
PIO route. FATX independently checks its noncached file alignment, with different
paging/volume conditions. No stronger buffer guarantee follows from sector-aligned
disk offsets or fragmented PFNs.

The retained PIO mapper maps the supplied MDL, not just the command's byte segment.
Its reserved-mapping fallback checks the whole descriptor's page span. Source
inspection does not prove mapping availability for every large borrowed descriptor
under pressure. Preserve bounded failure and test already-mapped, mapping-failure
and reserved-capacity paths. A segment-sized owned partial descriptor can be a
later resource optimization if measured/needed; it is not a blanket prerequisite
for the borrowed path.

If that optimization is chosen, cleanup of an owned partial mapping must finish
before its descriptor is rebuilt/reused. A borrowed parent mapping must remain
owned by the parent. Clearing flags alone cannot release a mapping or establish
safe reuse. MmPrepareMdlForReuse is a header helper, not a supplied callable kernel
service; its body remains excluded. The optional proposal declares only the actual
MmUnmapLockedPages service, whose SDK signature and retained selected-kernel symbol
are bound in SOURCE-BINDINGS.json. No caller is required to import that optional
service merely to borrow the unchanged upper descriptor. Native type/prototype,
mapping ownership, fault and final candidate link checks remain required if used.

No native candidate, physical hardware/DMA, PIO error path or performance result
is claimed. Independent tests should use one descriptor with fragmented/repeated
PFNs, subranges crossing page edges, numeric-zero domain, distinct mapped aliases,
odd-address optical I/O and preserved upper ownership. These are behavior scenarios,
not extracted tests or a segment-cursor implementation.
