# Owned request admission: zero original MDL domain

The production core now admits a validated descriptor whose numeric original virtual-domain base is zero. The change replaces the incorrect `!mdl_virtual` presence test with `mdl_present != 1`. The neutral request interface appends `int mdl_present`; nonempty data requires exactly 1. Existing owned request and pthread fixture constructors supply it explicitly.

A native platform must set this evidence only after validating a non-null descriptor, its locked-page/PFN coverage and lifetime. The core has no native MDL/PFN layout and cannot independently establish those facts. It continues checking byte extent, offset, pointer-width overflow, sector/adapter alignment and CDB/disk range. A missing/invalid descriptor must remain rejected at the platform boundary (or with presence evidence withheld); zero original-domain address is not null descriptor evidence. No address is fabricated, no mapped alias replaces the original domain, no physical contiguity is inferred, and no page is dereferenced by the core. The real parent/MDL/lease ownership contract remains unchanged.

All integrators constructing nx_request must supply the new field after validation. Default-zero old initializers fail closed for nonempty data; they are not automatically compatible. This is an owned neutral interface change, not a Windows ABI assertion. Root must update the integration specification to require this field and compile all actual callers before native use. No adapter was implemented here.

## Regression evidence

1. Added `zero_domain_write_through` against unchanged request.c/request.h. Plain clang host run exited 1: `nx_start(...) == NX_PENDING` failed; 43 scenarios, 1 failure. See red.log. This identifies admission, before any transport preparation, as the cause.
2. Added the explicit header field, updated owned callers, and added negative descriptor/range cases while retaining the original production check. The next run exited 1 with both new scenarios failing. See interface-red.log. A nonzero address without presence evidence exposes why merely dropping the null-address check would be insufficient.
3. Applied the single production condition change. Full unmodified check.py exited 0; final plain request run also exited 0. See checks.log and green.log.

The positive regression executes actual nx_start/nx_lower_done with a logical descriptor representing base 0 and length 8192. It checks original-domain command addresses 0 and 4096, page-bounded 4096-byte segments, pending lifetime, one 8192-byte parent result, real ordered sync and a later write held behind that barrier. The transport is doubled and does not dereference virtual address zero. This test does not exercise physical PFN interpretation; repeated PFNs, native mapping, DMA and PIO still need native adapter qualification.

The negative regression rejects missing descriptor evidence at zero and nonzero bases, nonboolean evidence, exhausted/outside byte extents, adapter misalignment, base-plus-offset overflow and transfer-end overflow. Zero-byte requests explicitly retain the no-descriptor/no-command behavior. Existing tests continue covering cancellation, same-pointer stale reports, ownership/rundown, segmentation, mixed requests, partial outcomes, overflow, optical behavior and flush/write-through sequencing.

## Commands and results

RED and final plain host commands:

```
clang -std=c11 -O1 -g -Wall -Wextra -Werror \
  -Isource/drivers/storage/class/nxstorage \
  source/drivers/storage/class/nxstorage/request.c \
  source/tests/host/nxstorage/request_test.c -o review/request-green
./review/request-green
```

The earlier runs used `review/request-red` and `review/request-interface-red` as output names before the production correction. Their logs are retained; the final executable is distinct.

Full existing owned verification:

```
python3 source/tests/host/nxstorage/check.py review/checks
```

Results: 44 request scenarios; 8 pthread ownership scenarios; geometry composer 13 scenarios/6001 checks; cache query 20 cases; geometry owner 16 scenarios/61973 checks; lower cache publication 32 cases; all passed. The runner enabled ASan/UBSan, leak detection and stack-use-after-return detection, compiled all four production primitives for freestanding i386, checked undefined helpers, linked cache publication and checked its helpers, and compiled cache ABI assertions. These are host/freestanding checks, not native target ABI or firmware execution.

## Scope and handoff

Only request.c, request.h, request_test.c and the pthread fixture initializer differ from the admitted originals. `owned-zero-domain.patch` is generated against hash-verified copies in the already admitted planning workspace, using original product-relative paths for root's mechanical integration. Other production primitives and frozen inputs remain unchanged. OUTPUT-HASHES.json pins changed files, patch, documentation, logs and generated check artifacts; it excludes itself.

The actual exposure ledger retains earlier planning exposure, distinguishes hash-only reads, and records this packet and standard toolchain compilation. Origin paths were not followed. No Git, remote/native action, legacy source/history, or major adapter work occurred. P1, actual native ABI/caller coverage, MDL/DMA/PIO behavior, source closure and release gates remain open.
