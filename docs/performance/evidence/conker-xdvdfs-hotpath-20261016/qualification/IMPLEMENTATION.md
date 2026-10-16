# XDVDFS direct-forward implementation record

## Problem

The release Conker census showed that the filesystem read route rebuilt a
child IRP over the caller's destination, described and pinned that destination
a second time, waited for the child, and then completed the parent. The lower
optical stack already accepts a parent IRP with a locked MDL and owns transfer
segmentation. This candidate removes the duplicate filesystem work when every
fact needed by the lower stack is already proved.

The diagnostic release counter recorded 3,099 eligible requests out of 3,444
file reads (89.98%). All 345 refusals had an unaligned offset or length; no
request failed the lifetime, MDL, paging, associated-request, or range gates.

## Clean-room path

The behavior rules were frozen in `../rust-model/SPEC.md` before the firmware
change. A dependency-free Rust model owns admission, completion normalization,
and cost accounting. Its exhaustive boundary tests and explicit refusal
reasons were completed before the C implementation. The new C bodies are a
repo-native transcription of that model:

| Production function | Independent input | Responsibility |
| --- | --- | --- |
| `XdvdPlanForwardRead` | Rust admission result | Validate offset, length, MDL span, lower stack space, alignment, and overflow without side effects |
| `XdvdForwardRead` | Frozen forwarding contract | Reuse the parent IRP and MDL, translate the lower byte offset, attach completion, and call the target once |
| `XdvdForwardReadComplete` | Rust terminal normalization | Propagate pending state; normalize cancellation, failure, short, overlong, and full success |

No external filesystem implementation or source expression was used. The
surrounding Roswell tree and the patch remain distributed under the
repository's GPL-2.0-or-later terms.

## Product boundary

The optimization is session-only and defaults off. Pressing Y from the main
setup menu opens Advanced, where **Optical async reads** controls bit 2 of
`NxkExperimentalFlags`. **All advanced settings** includes the same bit.

Eligible reads:

- keep the caller IRP and its single locked or nonpaged MDL;
- consume one existing lower stack location;
- translate file-relative bytes to the absolute disc offset;
- allocate no pool, construct no child IRP, pin no second MDL, and perform no
  internal wait;
- preserve lower optical segmentation and ATA timing.

Every rejected request executes the prior synchronous route. This includes
zero-length, past-EOF, unaligned, paging, associated, chained-MDL, insufficient
MDL-span, insufficient stack, overflowing, and misaligned-buffer requests.

## Verification

- Rust model: 19 tests pass in debug and optimized modes with warnings denied.
- Extracted production C: 25 admission/forward/completion checks pass under
  AddressSanitizer and UndefinedBehaviorSanitizer.
- Prior synchronous XDVDFS route: all 8 completion cases still pass.
- Setup UI: 48 sanitized and optimized checks pass; the session-only flag and
  aggregate advanced toggle are covered.
- Repository host suite: 535 tests completed successfully with 26 expected
  platform skips; the five new patch-lock/safety tests also pass separately.
- Exact 64 MiB release image builds and boots on the Windows runner.
- The release linker output contains `XdvdDispatchRead` and the asynchronous
  completion routine as symbols; `XdvdPlanForwardRead` and `XdvdForwardRead`
  are fully folded into dispatch by LTO, so the admitted path pays no helper
  call boundary.

The uninstrumented repeated release A/B result is recorded in `RESULTS.md`.
The forced-on qualification patch only changes the initial experimental flag
for unattended runs; it is not part of the product lock.

Exact image identities:

| Image | SHA-256 |
| --- | --- |
| Product release64, setting default off | `e7c70bbdc2b766c397bff4119cc65cdc2629dfe4e9f8ff21e922d0e869bf2326` |
| Product release128, setting default off | `540d825bbed8213470bb4ae889357621326eb46ba124a86e8b0dc44d28e8eca4` |
| Test-only release64, setting forced on | `0f306636dbad1d4ff2f6878dad9e48cedfee03cc0837aee6c29e43529c76614a` |
| Diagnostic counter release64 | `5cff81f97b187d537757c69b1cafe50bf570c63d7c0b32cf088a933c68cec064` |

The product release64 image was rebuilt independently and reproduced the same
SHA-256.

## Remaining acceptance limit

Automated Conker runs establish process survival and comparable rendered-frame
progress. They do not inspect game content or exercise operator-controlled
loading. The candidate must remain opt-in until live gameplay confirms correct
data and useful load behavior in Conker and a broader optical-load sample.
