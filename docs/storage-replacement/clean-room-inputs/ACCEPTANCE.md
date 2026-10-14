# Independently authored acceptance scenarios

These scenarios are written from public request semantics and caller requirements. They contain no implementation template. Host checks must execute candidate production code, not an extracted baseline routine. Keep source provenance and results separate; no result is currently claimed as run.

| ID | Input / lower-device observation | Required visible outcome |
| --- | --- | --- |
| A01 | aligned one-sector HDD read; lower returns matching patterned bytes | one parent completion, exact bytes/count, one eligible data command, caller MDL remains owned by caller |
| A02 | aligned HDD write then flush; lower records write and cache-sync outcomes | data before synchronization; final flush reports real lower status, no success-only SRB substitute |
| A03 | lower completes synchronously before submission returns, for success and failure | no later access to reclaimed request state; exactly one parent result |
| A04 | lower returns pending and completes later | parent dispatch/pending flag/IOSB/event/APC agree; actual bytes copied once |
| A05 | request spans multiple adapter-limited transfers, all complete inline | correct offset/count/checksum, bounded call stack, no unbounded recursion |
| A06 | mid-request short transfer/error | bytes equal verified completed data; later segments are not incorrectly issued as success; no fabricated full count |
| A07 | each candidate allocation/mapping site fails | bounded correct failure, zero leaked objects, no completion duplication, existing queued work progresses |
| A08 | parent canceled before admission and while lower owns pages | no DMA into released pages; one result; cleanup occurs only after lower ownership ends |
| A09 | issuing thread exits or file closes/truncates/deletes during pending FATX I/O | upper lease and original MDL remain valid to lower terminal completion |
| A10 | lower internally requeues same SRB/IRP pointer before completing | no premature release or accounting of a terminal result; finite class retry policy |
| A11 | terminal failure reports QUEUE_FROZEN, later HDD and DVD work is queued | recovery releases relevant queue condition or fails work within a declared bound; no stuck unrelated I/O |
| A12 | pool exhausted during frozen-queue recovery | bounded reserve/recovery outcome, forward progress, no allocation-dependent infinite loop |
| A13 | invalid negative/overflowing/alignment/range requests and zero length | rejected requests cause no lower data command; zero length has explicit zero-byte result |
| A14 | odd-address buffer and fragmented MDL; adapter byte/page/alignment limits | valid target buffer behavior; correct DMA/PIO fallback and checksum; no PRD assertion |
| A15 | timeout or reset during a write with unknown physical completion | no unconditional unsafe write retry; error/durability state is explicit |
| A16 | required IOCTL with 0, one-byte-short, exact minimum, and oversized output | correct status/Information, no out-of-bounds access, initialized returned bytes |
| A17 | optical TOC lower returns fewer than 804 bytes with DATA_OVERRUN | success with actual reply bytes, untouched tail not claimed as returned |
| A18 | optical read of final sector, page-sized read crossing end, start-at-end, absent media | aligned crossing request reaches lower; preserve measured bytes/errors; no invented padded success |
| A19 | optical writes, negative and misaligned reads | specified write-protected/invalid-parameter rejection and no lower data command |
| A20 | valid, truncated, absent and malformed autosense; no-disc, spin-up, unit attention | bounded parse, explicit documented mapping; no read beyond supplied sense length |
| A21 | boot driver creation, AddDevice, Start, BusRelations and partition starts | expected namespace and ordering; optical uses XDVDFS; HDD partition offset added once |
| A22 | boot initialization ends and INIT memory is reclaimed | no resident callback enters INIT; late PnP produces bounded invalid-request result |
| A23 | repeated healthy QD1/QD4/QD12 mixed reads, writes and real flushes | no extra compulsory worker or lost lower concurrency; stable pool/MDL high-water and measured consumer-visible latency |
| A24 | cache enabled/disabled/flush-unsupported and flush device failure | capability branch is visible; enabled-cache unsupported flush is a qualification failure; errors reach caller |

Freeze exact candidate policy for unknown statuses/partial-failure byte counts before declaring tests passed. Record operation/device, offset/length/flags, dispatch return, terminal IOSB, lower command and completion bytes, checksums, callback/event order, pool deltas, and all input/build hashes. Independently run raw-device/native observations to resolve baseline unknowns, then qualify exact candidate firmware. Existing open-XBE storage and FATX lifetime tests are permitted observations, but their historical check counts are not a candidate result.
