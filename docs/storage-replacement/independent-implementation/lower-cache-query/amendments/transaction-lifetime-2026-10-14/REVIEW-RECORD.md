# Transaction and local-result lifetime clarification

Root explicitly requested this narrow documentation correction following the
independent cache reviewer characterization. Original freeze.json SHA256:
b13d441f4676fa851aa688bebce3fa3b58e70d13076b76d857159fe193e6b1c5.
Original SHA256SUMS:
6daa6b73845490762c8e7f5d013e1742f59ed80fd698061e80b22f4265984a17.
Original INTEGRATION.md:
0accac54ac59639a8bd4e976fa01ccdf1f68e790647515ee703015891cf8638b.
All original frozen bytes are retained. Only this additional amendment is new.

The original table could be read as advancing the epoch again in the owning
IDENTIFY's addressing update, then publishing its now-obsolete saved result.
The own production contract deliberately rejects that result. The corrected
note says to preserve the owning already-invalidated transaction's token through
its guarded updates, while independent mutations/reset/reclassification revoke
it and require a fresh qualified transaction. Source exclusion and residency
remain external; current() is not a lock and does not permit concurrent raw
hardware/software mutation.

The generic internal-completion early return also requires a persistent handoff
of copied terminal facts into worker-owned storage before callback return/request
disposal. Merely saving a local variable or request pointer is insufficient. No
native storage/copy/signaling/worker consumption call site is present or qualified.
The revised note makes that limit explicit and adds corresponding acceptance
requirements.

Inputs used: own frozen INTEGRATION.md, cache_property.h/native_capture.inc and
existing own tests, plus approved behavior/declaration facts already pinned in
INPUTS.json. Review/root messages characterize the own implementation; no new
unapproved source, product history, external reviewer artifacts or type bodies
were read. The reviewer confirms the owning-token distinction and that no core
or helper body change is needed. Tests duplicate_reset_and_new_writer_revoke_old_terminal,
local_copy_publication_and_dma_proof_are_explicit, and native_local_dma_engine_and_reclassification
already verify publish-before-revocation, rejection after revocation, copied
result and explicit local-copy boundary. Their original32-group sanitizer result
is retained, not represented as a new run or native handoff qualification.

Verification for this documentation-only revision is review of token/lifetime
requirements against the own API and unchanged original hash manifest. No source
or tests were changed, and no broader tests/native integration were performed.
All original qualification limits continue to apply.
