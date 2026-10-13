# Remaining contracts and memory performance — 2026-10-13

This candidate extends PR242. It fixes the two remaining public process/thread
contracts, validates demand-mapped system addresses using their live page
mappings, removes unnecessary raw system-data clearing, adds two measured pool
size classes and reduces padded modular-arithmetic work. Large synchronous
write-gather requests can borrow pinned WB caller pages; other requests retain
the bounce path. Every implementation has a focused cause/qualification writeup.

Final native qualification is pending. No release tag or publication is
requested until the user's gameplay/save/reset checks finish. A full fixture
comparison must retain all leaf and workload results, including slower controls.

Independent reviewers have examined the pool/domain/census behavior, raw-data
PFN/PT/VM lifetime, process priority saturation and gather DMA/cache/completion
lifetimes. Production-source checks pass. Final measurements and complete
receipts will be appended before this PR is eligible to merge.
