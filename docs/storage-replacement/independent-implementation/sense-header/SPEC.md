# Independent sense tuple specification

This unlinked primitive accepts a borrowed readable byte range, its copied count,
its capacity, and an autosense provenance boolean. The caller guarantees the
range is readable for the stated capacity during the call. No pointer survives.
Reject absent provenance, counts above capacity or 96, null storage, and headers
shorter than eight bytes, in that order. Recognize only response codes 70–73 hex
with bit seven ignored. Preserve format and current/deferred timing.

A recognized header declares eight plus byte seven bytes. Record whether that
extent exceeds the copy, even if the tuple remains usable. A fixed tuple needs
14 bytes in both declared and copied extents; a descriptor tuple needs only the
eight-byte header. Report declared-short before copied-short when both apply.
An available tuple means only that key/ASC/ASCQ can be read: it does not validate
any descriptor, the tail, or the record as a whole. Initialize every output
member; unavailable tuples have zero key/ASC/ASCQ. No status or recovery policy.

The narrow gap is a missing standalone boundary for bounded sense-header facts;
root is measuring the broader P1 work independently. No rebuild is claimed here.
