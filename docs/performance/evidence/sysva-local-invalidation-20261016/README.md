# Warm small SYSVA local invalidation

## Result

Patch `0154-system-va-local-invalidation.patch` replaces two full CR3 reloads
per warm one-page `MmAllocateSystemMemory`/`MmFreeSystemMemory` pair with one
`invlpg` for publication and one before the cleared mapping's frame returns to
the page supply. Ranges of one through four pages use this local path. Larger
ranges retain one global invalidation after allocation and one after free.

The accepted Windows release64 A/B/B/A campaign ran four samples of 1,048,576
allocate/write/verify/free operations in each of four boots. Every sample
reported `correct=1`, all checksums were `789c9dc5`, and every guest emitted its
final PASS marker.

| Arm | Run mean 1 | Run mean 2 | Two-run mean |
| --- | ---: | ---: | ---: |
| Current control (`e7c70bbd...`) | 10.695066 s | 10.684733 s | 10.689900 s |
| Local invalidation (`6f4070f7...`) | 1.579390 s | 1.590474 s | 1.584932 s |

The candidate/control ratio is `0.14826445`, an **85.1736% reduction**. Each
individual sample contains more than one million operations and lasts
1.577--1.594 seconds on the candidate or 10.654--10.720 seconds on the control;
the complete measured work per arm is 8,388,608 operations. This is a focused
SYSVA result, not a whole-game or frame-rate claim.

The runner's generic outcome marks these jobs `unresponsive` after the plan
quits the emulator while the reused game-profile launcher is still within its
60-second host sampling window. That label does not describe the guest: all
four serial logs contain the complete two-test TAP plan, the expected semantic
checksum, zero failures, and `== kernel-performance end PASS ==`. The raw
runner result is retained rather than rewritten.

The `a1` v1 request is a retained, unexecuted draft that used the incompatible
older launcher/file layout. It has no job, result, or serial record and is not
part of the A/B/B/A result. The four v2 requests are the executed campaign.

## Correctness boundary

The production-body fixture executes the real allocation, free, page-supply,
first-fit, ownership, pin, rollback, page-table and TLB-selection bodies under
both 64 and 128 MiB policies. It checks:

- one through four pages use one invalidation per changed VA and no CR3 reload;
- larger mappings retain one global invalidation and do not duplicate work;
- free invalidates a small VA after clearing its PTE and before returning its
  frame to the allocator;
- cold page-table creation, PDE crossings, physical pins, exhaustion rollback,
  interleaving, reserved upper RAM and first-fit placement remain correct.

The selected threshold is deliberately small. It removes the measured warm
one-page bottleneck without turning a large mapping into an unbounded sequence
of privileged invalidations.

## Identities

- Candidate assembled source tree: `2b1a5b77493d16fe05a226684e4db5d745300b3a`
- Candidate release64 BIOS: `6f4070f788355d88cf44f37b792a6aceb1e9ead91bc441fe04df800c0a0fc077`
- Control release64 BIOS: `e7c70bbdc2b766c397bff4119cc65cdc2629dfe4e9f8ff21e922d0e869bf2326`
- Sustained XISO: `f7c7b0e6941a7d86a9f79b19a248efd10a04e6ff38c48dad4f5ceaca18f9049b`
- Fixture `main.c`: `6fad40e1f09597f6e70ae2d553ebf99935262a8421666881e3c23bb535c67c6f`
- Windows xemu: `75a2abdd708ed761b8ba5d95cb5f37b259567d5434e7d499dad3952d5d8505f6`
- Clock frequency in every run: 3,374,488 Hz

`fixture-source/`, `run_abba.py`, all four executed frozen requests, the
rejected draft request, runner job/results,
raw serial logs, and `windows-abba/analysis.json` reproduce the measurement.
`release64-sysva-disassembly.txt` records the selected release image's actual
`MmAllocateSystemMemory` and `MmFreeSystemMemory` code, including the bounded
`invlpg` branches and retained CR3-reload branches.
`run_abba.py` takes the product, workspace, runner URL/source, fixture directory
and both BIOS paths from environment variables, with the original lab layout
as defaults where applicable. Its required variable names are declared at the
top of the script.
`SHA256SUMS` binds the retained evidence.

## Sweep disposition

The latest broad 144-leaf release suite remains faster in 119 leaves versus the
previous SpiritBoot candidate (82.64%) and improves the sum of two-run leaf
means by 8.09%. It does not prove a 90% win rate, and most slower rows are GPU
or emulator work outside firmware control. The Forza kernel census has an
explicit disposition for every executed entry: pump, FAT mapping, packet
preparation and ATA cache bookkeeping were optimized; ATA settle removal was
rejected after optical corruption; required interrupt, locking and hardware
ordering remains intact. This SYSVA change closes the largest separately
measured firmware-owned gap without using GPU noise to manufacture a 90% claim.
