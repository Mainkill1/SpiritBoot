# Halo 64 MiB memory compatibility

## Question

Why do Halo and Halo 2 stop on a black screen with the 64 MiB SpiritBoot v0.99.3 image while the same discs, HDD seed, EEPROM and xemu build reach their menus with the reference BIOS?

The demonstrated difference is available title memory at launch. SpiritBoot kept the loaded open kernel's immutable image pages in RAM at physical address `0x03400000` while also retaining their compressed source in flash. The reference environment presents a materially smaller resident footprint. Under the allocation sequence used by Halo 2, the difference exhausts memory and the title later writes through a null allocation result.

## Environment

The matched native tests use Windows xemu `gdcc536830deb.exe`, source commit `dcc536830deba245eec36cd009db5860ca04884c`, a 64 MiB machine, separate fresh HDD overlays and EEPROM copies, and no debugger unless a bounded exception or owned-kernel trace is explicitly identified. SpiritBoot v0.99.3 has SHA256 `3dc3010a237fcf50bef2ecbe59c81115eabf9684e7a3ceb9caec19a16cb49611`.

The final release-profile candidate has SHA256 `8d18ed1816d96bf4aff281799bdaaa91627781ec9478714a844ee99263ca77ac`, is 524288 bytes, and reconstructs kernel tree `eee7de60ad3d2047efab3161491edb17768b5482` from patch 102. The 64 MiB release profile enables ROM-backed kernel pages automatically. The 128 MiB release and checked profiles keep their existing policy.

## What SpiritBoot did differently

A frozen public memory-inventory XBE reports these first stable `MmQueryStatistics` samples:

| 64 MiB boot | Available pages | Used pages | Largest demonstrated contiguous allocation |
| --- | ---: | ---: | ---: |
| Reference BIOS | 16228 | 156 | at least 60 MiB |
| SpiritBoot v0.99.3 | 16079 | 305 | at least 48 MiB |
| ROM-backed candidate | 16169 | 215 | at least 48 MiB |

The released firmware therefore begins the probe with 149 fewer available 4 KiB pages than the reference. The candidate maps 91 verified immutable image pages from flash and returns their former RAM shadows to the title allocator, producing a measured net gain of 90 pages. The diagnostic frame categories differ between the two kernels and are not treated as cross-kernel accounting proof; the public total and successful allocations are the comparison boundary.

A prior controlled SpiritBoot bisection held the same 64 MiB layout and title path constant. Halo crossed from failure to progress when 22 additional pages were available. This establishes why the 90-page recovery is material rather than incidental.

## Failure chain and rejected alternatives

A bounded trace at SpiritBoot's own exception-dispatch boundary captures Halo 2 failing after the allocation pressure with access violation `C0000005` (the internal trap code is `10000004`), title PC `0033589E`, and exception information `[1, 320]`: a write to virtual address `0x140`. `EAX` is zero. No title instructions or payload bytes were read. This is consistent with a null allocation result used as an object base.

A separate owned-kernel trace follows a failed 416-byte `Irp ` pool allocation through the storage stack. The internal service path temporarily has fewer transfer packets, returns `STATUS_PENDING`, completes the local I/O status block successfully for 13,310,144 bytes, and returns a successful full-length public read. That failure is recovered and does not explain the later black screen.

The public interrupt-object defect repaired in PR #226 is also independent. Its exact candidate passes the direct 17-check interrupt test, but Halo and Halo 2 remain black until the memory footprint changes.

SpiritBoot v0.99.2 and v0.99.3 both reproduce the black screens in matched 64 MiB boots. This is an older compatibility limit, not a regression introduced by the retained-transition-image work in v0.99.3.

## Implementation

The build prepares a normal fixed-address PE image, then selects complete pages from readable, non-writable, non-discardable sections. It excludes the page containing the runtime-patched `RtlPrefetchMemoryNonTemporal` routine. Selected bytes are stored uncompressed near the end of a 512 KiB flash image; the RAM copy contains zeros for those pages plus a bounded table of RVA, page count, flash physical address and CRC32.

The loader accepts the ROM form only after validating the PE ownership, table bounds, image and flash capacities, page alignment, span ordering, section flags and CRC of every raw flash span. It decompresses the remaining image into the ordinary RAM location and installs read-only PTEs at the original kernel virtual addresses. If any admission check fails, boot stops instead of donating memory.

During memory-manager initialization, SpiritBoot verifies every live PTE against the admitted table before donating any page. Only after all mappings match does it return the contiguous RAM shadows to the title heap. Flash PFNs never enter the RAM allocator or its ownership tables.

Quick reboot needs an additional guard because a title may allocate and persist data in those newly available physical pages. Early reset code now treats ROM-shadow pages like other donated boot pages: it copies selected contents to bounded temporary RAM before decompression, restores them through the RAM alias, and only then returns ownership. The persisted page remains backed by RAM after restart; the kernel virtual address continues to read immutable flash.

The complete immutable set does not fit alongside the loader and compressed payload in the old 256 KiB release image. The 64 MiB release image is therefore 512 KiB. xemu is qualified with that size. Physical Xbox use requires a modchip or flash bank that exposes the complete 512 KiB image and remains unqualified.

## Regression evidence

The kernel host tests cover the independent image builder, malformed tables, writable/discardable exclusion, patched-page retention, CRC and capacity rejection, actual decompressor admission, 64/128 MiB paging, all-or-nothing RAM retirement and warm-staging capacity. The production build also runs the normal boot-image and boot-layout gates.

On the exact native ROM candidate:

- the public kernel API suite passes 639/639 checks;
- the ROM-shadow persistence XBE passes 7/7 checks across a real quick reboot, including content, allocation ownership, competing-allocation refusal, callback ordering and ordinary control pages;
- the frozen memory inventory shows 90 additional available pages over v0.99.3;
- Halo reaches its main menu and remains running at the 45-second observation;
- Halo 2 reaches `PRESS START TO CONTINUE` and remains running at the 45-second observation.

The game observations use window captures only as local review material. The public evidence records hashes and outcome labels without redistributing game images or assets.

[Public evidence and manifest](evidence/halo-memory-compatibility-20261012/manifest.json) contain the independently authored probes, public/owned trace metadata, exact build identities and regression outputs. They contain no proprietary BIOS, game payload, title instructions or disassembly.

## Limits

Native qualification covers xemu at 64 MiB. It does not establish physical flash electrical behavior, other emulator versions, gameplay beyond the title/menu observations, or every title that may depend on the recovered pages. The largest-contiguous-allocation probe still reports 48 MiB on the candidate; the demonstrated fix is the available-page margin used by these title paths, not a claim that every memory-layout difference now matches the reference BIOS.
