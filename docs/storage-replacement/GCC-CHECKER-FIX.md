# Freestanding i386 checker correction

The four firmware profiles at commit `69aa26a` built successfully, then failed
their owned storage checks. CI run `38570141776` archived the actual
`nxstorage.log`: all 32 publication fixtures passed, followed by the rejected
`_GLOBAL_OFFSET_TABLE_` and owned `nx_cache_query_encode` references. A local
`CC=gcc` run reproduced the failure.

The checker compiled bare-metal i386 objects using a distribution GCC whose
default position-independent mode introduces a GOT reference for the encoder
call. Patch `0132` explicitly disables PIC/PIE in the freestanding checks. The
publication object still must reference only its exact owned encoder, and the
combined two-object check still rejects every unresolved helper. This changes
the verification command, not firmware implementation or runtime behavior.

The exact locked-patch production check passes with both `CC=gcc` and `CC=clang`,
including sanitizer fixtures and linked i386 helper validation. Original CI and
local failure logs remain preserved. [CI run 38571239412](https://github.com/Mainkill1/SpiritBoot/actions/runs/38571239412)
at exact fix commit `7c54af612ff58ad7dbb4ec4bbc637f28e6fe688c` passed host tests
and all four release/debug 64/128 firmware jobs. The bounded
[CI receipt](freestanding-checker-ci.json) retains job identities and result
hashes. The downloaded release64 artifact contains source tree
`7e891ec86f42b1313e5cd3453347836ac451ba79`, the completed owned production-check
log, and actual ROM bytes matching the published `c630d22f…` reference hash.
These firmware builds select the legacy reference; this correction does
not qualify a complete backend.
