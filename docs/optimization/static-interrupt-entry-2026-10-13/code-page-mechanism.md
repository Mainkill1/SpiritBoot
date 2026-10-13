# Exact Xbox TCG code-page mechanism

Original xemu source HEAD is dcc536830deba245eec36cd009db5860ca04884c, corresponding to the original binary used for all replay tests. The two inspected files have no local changes. No emulator or firmware behavior was modified for this source audit.

The earlier report was too conservative and factually wrong when it said only intersecting byte ranges were invalidated. It missed the `#ifndef XBOX` around the byte-range overlap guard. Correct route:

1. `build.sh:263` supplies `--extra-cflags="-DXBOX=1 ..."` to the normal build.
2. In system mode, `accel/tcg/tb-maint.c:327`, `PAGE_FOR_EACH_TB` iterates `pagedesc->first_tb`, which is the complete page list; its start/last arguments do not filter the iterator. The interval-tree iterator above it belongs to CONFIG_USER_ONLY and does not apply to xemu's system emulator.
3. `accel/tcg/cputlb.c:1359`, `notdirty_write`, reads the cached code-dirty bit. If translated code is present, it calls `tb_invalidate_phys_range_fast`.
4. `tb-maint.c:1230`, that function locks the page collection and calls `tb_invalidate_phys_page_range__locked` with the written range.
5. `tb-maint.c:1147` wraps its precise overlap computation and conditional inside `#ifndef XBOX`; under XBOX the body is entered unconditionally for every TB on the physical page. `tb_phys_invalidate__locked` consequently removes even TBs whose bytes are disjoint from the store.
6. When no code remains, `tlb_unprotect_code(start)` permits ordinary writes again. This explains why the completion store is expensive but subsequent submission stores to the same channel are already cheap: the pool stub was executed before completion and will next be executed/retranslated on another IRQ.

Native metadata confirms the baseline's actual IDT entry c102d444→03baa444 shares physical03baa000 with the completion bitmap c102d868→03baa868. Static mode uses actual entry84002490→03402490 while those pool addresses and the unused template stay fixed. Matched RDTSC records mean5.025→0.124ms/1024 in the completion interval, whereas submission stores are already~0.1–0.2ms/1024. The untraced GPU replay improves~27ms/1024 at depth12/900pages.

This source proof supports actual invalidation/retranslation as a cause. It does not quantify how much of the additional~22ms is code translation, TB relinking, other affected objects, or dependent execution. A guest timestamp at the beginning of the IRQ stub cannot see time spent translating that stub before it executes. Host counters/timers around the owned TCG translation/invalidation route, or another external boundary, would be needed for that specific attribution. Such a diagnostic binary would remain secondary to the original binary's untraced performance gate.

The allocator-header fixture separately checks whether other native objects share the page; it reads only allocator-owned metadata, not object payloads. No further runtime optimization is justified solely by this source audit.

## Independent confirmation in the original Windows executable

The actual user's executable was copied read-only from `C:/xemu-lab/Requests/Forza Failure/gdcc536830deb.exe`. Local `original-xemu.exe` hashes to `cd4cfd696aa9c196cf44fd35765e16cf662afc16a689e1af4584fa79398784db`, identical to every native launch receipt. This is the owned/open-source emulator executable; no game or proprietary firmware instructions were inspected.

Its retained symbols identify `tb_invalidate_phys_page_range__locked` at VA1401ac7d0. Independent disassembly confirms the compiled Xbox route, rather than relying solely on build.sh provenance:

- VA1401ac816 loads the page's first_tb list.
- VA1401ac840 tests only whether the current list element is the currently executing TB. The ordinary path reaches `do_tb_phys_invalidate.lto_priv.0` at VA1401ac84d unconditionally; the special current-TB path performs state restoration and then joins the same invalidation call.
- VA1401ac852 loads the next tagged page-list element and VA1401ac867 loops. There is no start/last versus TB byte-range overlap comparison in this loop.
- The subsequent empty-page path clears code protection as expected.

The exact excerpt is preserved in `original-xemu-page-invalidation.txt`, generated with `objdump -d -Mintel --disassemble=tb_invalidate_phys_page_range__locked original-xemu.exe`. It proves the actual binary includes the broad page-invalidation route. It is still not a runtime count or timer of how often TBs were retranslated in the replay.
