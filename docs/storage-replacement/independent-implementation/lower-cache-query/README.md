# Bounded read-only cache property layer

Implemented: fixed resident publication metadata, retained IDENTIFY selector
facts, copied writer/result ownership, raw capture and a pure aliased-buffer
query hook using the separately frozen nx_cache_query_encode. No handler is
installed and no native producer call sites are patched.

Run from any directory:

```sh
.scratch/pr248-independent-output/lower-cache-query/tests/run.sh
.scratch/pr248-independent-output/lower-cache-query/tests/check-i386.sh
```

Final evidence:32 host groups pass ASan/UBSan with real pthread cases; i386
production publication1268 text, encoder442, combined1722; actual new static
producer/query helpers429 text with logical doubles. Both combined objects have
no undefined symbols. These checks do not qualify native opaque types or native
lifecycle guards. See INTEGRATION.md for required target assertions, all producer
anchors and candidate-only routing. PROVENANCE.md records red/green chronology,
exposure and qualification limits. INPUTS.json and approved-manifest44.json pin
exact admitted facts; SHA256SUMS covers this output freeze.

The query takes one atomic snapshot and never reads an in-flight raw IDENTIFY
buffer. Raw publication needs the external source guard and device/request
rundown. Unknown/error/partial/unproved/revoked results cannot qualify cache;
PIO counted and DMA controller-inferred completion remain separate. Physical
flush/durability diagnostics and the full class adapter are separate work.
