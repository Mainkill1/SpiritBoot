# Forza map-stream queue-depth correction

Forza's captured map-streaming route had 10 to 12 asynchronous HDD reads
outstanding.  The extracted native disk class in PR 248 preallocated only eight
request envelopes.  `NxNativeAdapterSubmit` therefore completed the ninth read
with `STATUS_INSUFFICIENT_RESOURCES`. The dedicated release fixture reproduced
hundreds of these failures; Forza's eventual world recovery is consistent with
later retries, though title retry logic was not inspected.

Patch `0146-forza-map-queue-depth.patch` gives the native HDD class 16 slots.
The optical class remains at eight slots.  Sixteen preserves a power-of-two
bounded pool and covers the observed 12-read burst with four slots for unrelated
I/O.  Dispatch remains allocation-free.

## TDD evidence

The host regression constructs the disk through the production
`DiskDriverEntry` and `AddDevice` path, publishes disk capacity, holds 12 4 KiB
reads pending at the lower device, then completes and verifies every parent.

Before the production change, the plain host test failed on read nine because
its dispatch returned `STATUS_INSUFFICIENT_RESOURCES` instead of
`STATUS_PENDING`.  With the HDD slot count set to 16, both checks pass:

```text
adapter-plain: 27 adapter groups, 0 failures
adapter-sanitized: 27 adapter groups, 0 failures
```

## Memory cost

The release i686 target layout was measured with the PR 248 toolchain and exact
release headers:

| Object | Target size | Added count | Added payload |
| --- | ---: | ---: | ---: |
| `nx_slot` | 256 bytes | 8 | 2,048 bytes |
| `NX_NATIVE_ENVELOPE` | 1,440 bytes | 8 | 11,520 bytes |
| fixed IRP (`IoSizeOfIrp(8)`) | 640 bytes | 8 | 5,120 bytes |
| fixed MDL (`sizeof(MDL) + 23 * sizeof(PFN_NUMBER)`) | 124 bytes | 8 | 992 bytes |
| **Total retained HDD payload** |  |  | **19,680 bytes** |

The enum constants add zero bytes of static data or BSS.  Kernel pool/lookaside
allocator bookkeeping is implementation overhead outside these object payload
sizes.  CD-ROM retains its existing eight slots, so it adds no retained memory.
