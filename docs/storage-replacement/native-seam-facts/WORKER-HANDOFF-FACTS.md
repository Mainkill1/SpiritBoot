# Internal worker result lifetime and publication boundary

Status: bounded investigator source facts and declaration candidate for root
review. Current composed source is 7e891ec86f42b1313e5cd3453347836ac451ba79.
No implementation body is supplied and no native behavior has been measured.

## Persistent owner and completion

The port worker has one internal request embedded in channel-owned PortData,
an embedded notification completion event and an independent worker thread.
Initialization installs the internal completion callback before that thread starts.
The synchronous internal sender uses this embedded request, waits on the embedded
event and inspects its terminal status after wakeup. The generic internal completion
branch calls the callback and returns before the normal pooled-request resource
release path. The callback signals the event; it does not free the internal request.
There is no installed nx_lcq_result/readiness handoff cell in these structures.

This is persistent storage, rather than a callback-local result or disposable
ordinary request. It is nevertheless mutable command storage: IDENTIFY, spin-up,
transfer-mode/configuration and other internal operations reuse it. Flags, command,
length and terminal status cannot serve as an immutable result across a later send.
The result must be copied before signaling readiness and consumed or explicitly
invalidated before another command can replace it. A completion event supplies a
wakeup, not a copied raw result or transaction/device identity.

The local IDENTIFY destination is channel-owned contiguous noncached storage,
shared by the channel's device contexts. The worker copy puts 512 identity bytes
into the selected PDO's persistent cached identity. Initial/re-enumeration performs
this copy before reporting SAME_DEVICE; post-configuration performs another copy.
The internal request and shared local buffer therefore have different ownership
from the per-device cached identity and publication state. Holding a raw local
buffer pointer through the next channel command is not a stable result handoff.

For already listed devices, the worker obtains remove-lock references for
port-event processing and retains them until its state-machine exit. The newly
constructed unpublished PDO follows the enumeration caller's creation/free path;
the same listed-device reference must not be assumed for it. Channel removal requests thread exit
and joins the worker before freeing its local buffer/extension. These are observed
source lifetime mechanisms; they do not by themselves qualify new callback storage,
every removal/error path or wakeup memory ordering. Candidate producer and consumer
must keep their actual device/channel references until their last cell access.

## Existing exclusion, and its exact limit

The worker freezes each existing device's port-busy queue state and waits until
normal port slots are empty before processing reset/enumeration/configuration
operations serially. Port-busy is a non-bypassable frozen reason: ordinary SRB
bypass flags apply only to queue-lock/error-freeze reasons. A new enumerated PDO
is also frozen before its worker IDENTIFY. Paused normal commands are deferred.
This is meaningful existing exclusion of regular queued hardware work during the
worker phase, not merely ownership of QueueLock at one instant.

Runtime cached IDENTIFY is marked exclusive. The slot allocator requires other
allocated commands to drain before granting it and holds the exclusive state until
after its completion callback. That callback runs under the device queue lock,
updates addressing and produces the public capacity reply before successor dispatch.
The device queue lock alone does not cover DMA/PIO write lifetime; the exclusive
command lifetime is a separate part of this path's source-side exclusion evidence.

There is an important additional software mutator: initial PDO classification and
addressing run in the enumeration caller after its device-enumeration event wakes,
not entirely inside the worker. The event can be signaled inside worker action
processing before the state machine finishes. Initial PDO initialization installs
a PnP freeze before exposing the device. Worker serialization alone is therefore
not proof that every classification/addressing writer shares one publication guard.
Runtime addressing, initial classification, post-config copies, reset/removal and
transport/profile changes must all obey the owned publication transaction rule.

The current composition has no installed metadata publication guard or complete
worker handoff. Existing freezes/draining and exclusive completion are useful
anchors for a narrowly scoped integration proof. Native code must demonstrate
that raw source and negotiated fields remain coherent through capture/publication,
that every independent mutation revokes the old epoch, and that owning updates
retain their existing epoch. Do not add a second invalidation solely for the owning
successful addressing update. A current-token check detects revocation; it neither
locks mutable source nor pins object memory. No universal/native exclusion gate
is checked off by this source review.

## Minimal admissible owned cell

An appended owned cell in the already admitted PDO extension is sufficient as a
storage candidate: copy the existing owned nx_lcq_result by value and pair it with
an aligned 32-bit readiness/publication word. The current callback can identify its
PDO from the request's Device; the waiting sender/caller already has that PDO.
Keep each cell associated with that PDO and one current internal transaction.
The declaration proposal contains no new private overlay, source helper or function.
It is an original data declaration using an already owned result type. Exact field
layout/size/alignment and readiness semantics remain candidate assertions/proof.

The PDO allocation uses sizeof(ATAPORT_DEVICE_EXTENSION) and clears that extent;
appending a resident member therefore follows the existing setup allocation path.
The channel allocation similarly uses sizeof(ATAPORT_CHANNEL_EXTENSION), if an
independently chosen channel-owned cell is preferred. Do not transplant the old
extension layout or reuse an unrelated field as spare storage. A per-device cell
avoids retaining a request pointer and separates the shared channel-buffer lifetime
from the owning PDO. No per-data-I/O allocation, worker or clock is required by
this metadata declaration. Actual resident growth must be measured on the candidate.

Required observable handoff outcomes are: no stale-ready result after a failed or
non-IDENTIFY internal operation; copied raw result precedes wakeup; readiness uses
release/acquire publication; matching device/transaction consumes once; request
reuse cannot alter that copy; a revoked transaction remains Unknown; and final
cache/profile/addressing consistency is established under producer exclusion
before Known publication. Initial and SAME_DEVICE consumers both matter. Tests
must exercise wakeup followed by request reuse and initial enumeration-caller
classification, not only a completion callback returning to its waiting worker.

This settles the storage-owner/allocation facts needed to author the small owned
handoff. It does not install or qualify its memory ordering, guard, error paths,
PIO/DMA proof, teardown or physical durability.
