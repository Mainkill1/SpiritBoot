# Preserved code and owned symbol-image identity

The pinned preserved RAM page tables and exact baseline flash reconstruct the
owned kernel's `.text` and `PAGE` code ranges. `.text` has 345,088 bytes, with
84 pages backed by flash and one by RAM. There is exactly one differing byte
against the owned PE. `PAGE` has 2,824 bytes, all flash-backed, and matches exactly.
The input and complete reconstructed range hashes reproduce the independent
root analysis. No code payload is retained in this evidence directory.

The mismatch is at virtual address `0x84002600`, the entry of
`RtlPrefetchMemoryNonTemporal`, mapped to RAM physical address `0x03402600`.
Owned `ntoskrnl/ke/i386/kiinit.c` enables this routine when FXSR and XMM support
are present. Owned `ntoskrnl/rtl/i386/prefetch.S` documents that initialization
replaces its initial early return with a no-op. The scalar proof verifies that
this exact expected entry change is the sole code difference and emits only a
boolean result, addresses, counts and hashes. Both entry forms occupy one byte:
this patch changes execution flow but does not shift instruction or symbol
boundaries. Symbol attribution using the pinned owned image remains supported;
assuming the unpatched entry's early-return behavior at runtime would be wrong.

The comparison is based on preserved RAM mappings plus known flash backing,
not a fresh runtime code dump. It proves these mapped ranges for this snapshot,
not arbitrary later modification. It does not independently establish the
loader's reason for placing the affected page in RAM. The script rejects unknown
physical backing and the possible MCPX overlay page rather than assuming its
contents. It handles present 4 KiB and supported 4 MiB mappings, and rejects
unsupported extended large-page addresses. Flash offsets use the pinned 512 KiB
mirror period across the high physical ROM region, as xemu's `xbox_flash_init`
configures. For example, virtual code page `0x84001000` maps to `0xff023000`.

The xemu flash region uses `memory_region_init_rom`, which allocates RAM backing
and marks it read-only. `cputlb.c` obtains a direct host-memory addend for this
RAM-backed region; read-only treatment affects writes. Therefore readonly ROM
mapping alone does not imply MMIO reads or establish a slower read path. This
source check does not measure actual TLB misses, watchpoints, translated-block
lookup behavior, host caches, or elapsed access costs. It provides no evidence
that ROM mapping explains the observed long-gap timing difference.

`source-provenance.json` records the owned and xemu source hashes and locations.
The scripts have no external dependencies beyond Python and emit no RAM or code
bytes. Supply the three authorized private input files in this order:

```sh
python3 check_code_identity.py RAM_SNAPSHOT BASELINE_FLASH OWNED_UNSTRIPPED_PE --output scalar-code-identity.json
python3 -m unittest discover -p 'test_*.py'
```

Eight synthetic tests cover small and large page translation, nonpresent and
out-of-range tables, flash mirrors, overlay rejection, unknown backing, page
crossings, RAM reads, malformed image headers and pinned-input rejection. All
pass. This investigation made no host calls, build changes or firmware edits.
