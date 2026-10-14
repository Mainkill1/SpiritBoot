# Current reference64 composition

The selected reference remains the optimized published 64 MB BIOS. The current
locked composition reproduces its complete flash SHA-256
`c630d22f2353d3898024d510f0b402b64bccdb331781fe7885389f73d6200853`.
This is the reference firmware used by the completed 36-case functional sweep.
It retains the old storage class implementation.

The [verification receipt](current-reference64-composition.json) binds the exact
successful CI build metadata, compiler/tool versions, epoch, all 146 ordered
patch hashes, source tree, kernel and flash. The current lock and every patch
were rehashed against that build. The local assembled index produces the same
source tree `7e891ec86f42b1313e5cd3453347836ac451ba79`, with no unstaged tracked
changes. The actual retained flash and matching local kernel bytes were also
rehashed; source labels alone were not used as firmware identity.

The receipt additionally records the frozen full36 plan/source manifest and its
14 distinct declared input identities, including actual emulator, EEPROM,
configuration and fixture media. Original HDD seed lineage is separate from
each private prepared disk; the [full36 receipt](full36-functional-native-receipt.json)
retains those measured per-run hashes and cleanup outcomes. The full build
receipt remains available in the recorded local evidence path and is hash-bound;
the checked-in composition receipt contains the relevant build facts.

This completes selection/reconfirmation of the current reference64 baseline.
Byte equality preserves the released optimized paths; it does not establish a
new speedup. New fixture or analysis changes need their own frozen identities.
A/A, storage-owned memory high-water, complete replacement qualification,
other final candidate profiles and license closure remain separate gates.
