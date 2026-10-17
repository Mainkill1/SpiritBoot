# ATA/PATA hot-path behavioral specification

## Scope and provenance

This specification is based only on the current SpiritBoot-owned integration,
its public request contracts, the final release-i386 objects, and the measured
Forza function census. No prohibited ClassPnP, Disk, or nxcdrom implementation
body was inspected. The retained MIT ATA/PATA source is treated as compatible
current source; this optimization does not import another implementation.

## Observed cost

The release Forza census executes one ATA start, one PATA start, and one ATA
completion for each of 1,024 reads. The cache-publication adapter currently
constructs an empty writer and then calls the general writer-definition routine
again for every ordinary read. Completion converts and copies a cache result for
every ordinary read even though only a successfully started IDENTIFY writer can
publish it. This bookkeeping precedes all queue retirement and is not involved
in READ10 status, DMA ownership, IRQ delivery, or successor admission.

## Required behavior

1. Request storage reuse establishes an all-zero, unstarted cache writer before
   translation.
2. Ordinary ATA requests whose final command is neither IDENTIFY DEVICE (0xec)
   nor IDENTIFY PACKET (0xa1) retain that zero writer. They do not invoke the
   general cache-writer definition routine.
3. An IDENTIFY command still classifies cached, local, or other destination and
   exact 512-byte extent through the existing independent definition primitive.
4. Actual-start generation invalidation remains immediately before the external
   controller start and under the existing interrupt serialization boundary.
5. Completion captures raw status and byte count only when a translation
   callback or internal worker can consume the result. An ordinary read has no
   such consumer and leaves old result storage unobserved. A consumer always
   receives an explicit current result, including Started=0, so stale request
   storage cannot qualify a changed or failed command.
6. Internal IDENTIFY completion still publishes its value copy before request
   storage reuse. Runtime IDENTIFY completion still supplies the translation
   callback before a successor starts.
7. SG/MDL release, port-slot and device-tag release, queue freeze/requeue rules,
   successor-before-parent-completion ordering, NT/SRB status translation, and
   IRQ/polling behavior remain source-equivalent outside the cache bookkeeping
   guard.
8. PATA device selection, status waits, DMA programming, and interrupt-mode
   transitions remain unchanged because the exact release path performs
   hardware-visible operations and no redundant compiler helper was found.
9. The portable request engine's enter/leave callback ABI remains unchanged.
   The release port-leave body is already one state load plus the required
   kernel unlock call; assembly cannot remove a required ABI or lock operation.

## Acceptance checks

- A host oracle poisons writer/result storage and covers ordinary, IDENTIFY
  cached/local, invalid-length, and started/not-started completion cases.
- Existing lower-cache, ATA retained-SG, native adapter, async I/O, and DMA
  lifetime suites pass under sanitizers where available.
- Exact release-i386 disassembly demonstrates fewer instructions/calls on the
  ordinary start and completion paths and no new division/compiler helper.
- A release firmware build succeeds. Native performance qualification is left
  to the final assembled batch because this isolated patch does not alter the
  controller, queue, or IRQ contracts.
