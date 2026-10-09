# Optional upper RAM reservation

Build a 128-MiB RAM image with `--memory-mib 128 --reserve-upper-ram`.
The default remains OFF. The profile requires NXK_MM_PHYS, NXK_MM_POOL,
NXK_MM_POOLPAGES and NXK_MM_VM; unsupported combinations fail configuration.

The profile reserves physical RAM `[0x04000000, 0x08000000)` for firmware's
generic allocations, private pool data, page tables and scheduler-managed
execution stacks. Those paths fail on exhaustion rather than taking lower RAM.
Explicit title data uses only lower RAM: public pool ordinals, title virtual
commits, public system memory including its pool fallback, public contiguous
allocation, the exported explicit stack-buffer allocator, and dedicated title
TLS buffers. Low contiguous relocation counts and chooses only eligible lower
replacement frames. Public and private pool buckets cannot reuse each other's
backing; headers, sizes, tags, free/query behavior and TLS alignment are preserved.

Public memory statistics report the real total of 32768 pages. AvailablePages
reports only free lower pages and is at most 16384. Other committed counters
continue to report their actual backing. Total minus available includes upper
reserved capacity; it does not mean all upper RAM is actively allocated.

Scheduler-created execution stacks (including initial and spawned title
threads), thread objects and their kernel metadata remain firmware allocations
in upper RAM. Hardware-facing contiguous/DMA buffers and bootstrap/PCR state
retain their required lower placements. Thus this is an allocation policy for
the listed routes, not a claim that every address a title can access is below
64 MiB. Physical address queries remain truthful. The profile neither hides
128-MiB hardware nor provides a security boundary; a title can still choose a
128-MiB mode based on total memory. No FPS improvement is claimed.

The source patch includes focused component and actual CMake gates under
`tests/host/upper-ram-reservation/`. Native guest and retail game qualification
are separate from those gates and from a successful firmware build.
