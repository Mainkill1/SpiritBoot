# Reset and optical-media lifetime repair

## Failure

Halo could remain black after another title or disc had run in the same xemu
machine. Two firmware lifetime errors could reproduce that symptom, and a third
request-ownership error could affect a fresh boot.

SpiritBoot published the `MmPersistContiguousMemory` bitmap for every SMC reset.
Only a quick title launch creates a launch-data handoff, but ordinary reboot and
passive-level crash recovery still restored the old title's selected physical
pages as live allocations. A later title consequently started with less memory.
This is material for Halo: the earlier controlled 64 MiB investigation found
that 22 pages separated its failure and progress cases.

XDVDFS also accepted every `IRP_MN_VERIFY_VOLUME` without contacting the optical
stack. It retained the first disc's root-table sector, size, and serial, so an
ISO replacement could resolve names and issue reads using the previous disc's
geometry.

Finally, native optical control requests found any inactive request envelope by
scanning the array, while data reads acquired envelopes from a free list. The
control path did not remove its envelope from that list. A pending media check
and a data read could therefore own the same child IRP and control buffer, and
completion could insert the same envelope into the free list twice.

The first repair candidate also issued `IOCTL_CDROM_CHECK_VERIFY` while mounting
the initial disc. A matched Halo cold-boot A/B showed that this otherwise
unnecessary TEST UNIT READY changed observable game behavior: the Multiplayer
menu texture became stable multicolor noise. Removing only the cold-mount
request restored the row. DVD read totals remained identical, and a follow-up
candidate stayed correct despite reading less from HDD, so aggregate I/O volume
was not the cause.

## Repair

The reset path now uses a one-shot quick-launch request. The XBE reentry path
arms it only for `XeFwQuickReboot`, after the filesystem shutdown flush. The HAL
consumes it after shutdown callbacks and publishes persistent allocation state
only when the hardware action is reset and that request was armed. An unarmed
ordinary reboot, power-cycle, power-off, and passive-level crash recovery
invalidate the handoff. Physical RAM bytes do not need a blanket scrub: normal VM commit
already zeroes pages, while `MEM_NOZERO` and explicit persistence retain their
documented content semantics. A matched Complex reference also retains the old
bytes when the same physical range is returned by a later contiguous
allocation, so the compatibility requirement is allocation ownership rather
than clearing every DRAM byte.

On `IRP_MN_VERIFY_VOLUME`, XDVDFS now sends `IOCTL_CDROM_CHECK_VERIFY` to the
lower optical device. It does not issue that command during the initial mount;
the first real verify establishes the generation lazily. An unchanged nonzero
media generation is then the fast path. Otherwise it re-reads the complete
XDVDFS descriptor at LBA 32 and compares both magic fields, root-table sector
and size, the full filetime identity, and a fingerprint over all 2,048
descriptor bytes. The same disc reinserted with a new generation remains
mounted. Missing, malformed, or different media marks the old VCB unmounted and
returns `STATUS_WRONG_VOLUME`, which lets the I/O manager allocate a new VPB and
mount the replacement. All operations that can use an old FCB now reject the
unmounted VCB before consulting cached sectors.

Control and data I/O now acquire from the same envelope free list under the
adapter lock. A pending control request therefore owns its child IRP and buffer
until the existing single release path returns that lease.

## Regression coverage

The host reset fixture distinguishes unarmed ordinary reset from an armed quick
launch, proves the one-shot request is consumed, and retains the existing
persistent-page and shutdown-order checks. The quick-launch source check pins
the required order: filesystem flush, persistence arm, HAL handoff.

The release guest ordinary-reset probe allocates a fixed contiguous range,
marks it persistent, invokes the public `HalReturnToFirmware(HalRebootRoutine)`
entry point, and then proves that the old ownership is gone and the range is
available to the next title. Reallocated byte contents are diagnostic only:
the matched Complex run retained all marker bytes, and the contiguous API does
not promise zero-filled memory.

A second 64 MiB mixed probe distinguishes physical contents from API exposure.
After the same ordinary reset, all eight former contiguous PFNs lost ownership,
ordinary VM commit reclaimed all eight, and all 48 MiB returned through normal
VM allocation were zero-filled. The underlying marker bytes had survived until
that commit. This proves that title ownership and normal VM zeroing are reset
without paying for an unnecessary whole-RAM scrub.

The native adapter suite adds a two-slot optical case that holds CHECK_VERIFY
and one read pending. A second read must fail with
`STATUS_INSUFFICIENT_RESOURCES`; plain and ASan/UBSan builds exercise the exact
production adapter.

The XDVDFS verify check compiles the production identity predicate, mutates each
identity field independently, requires the lower media-control call and
descriptor read, forbids media-control traffic during cold mount, and checks
that every old-handle dispatch rejects an unmounted VCB. Firmware CI runs this
check from the exact assembled source tree.

Halo cold-boot qualification used the same release xemu, ISO, 64 MiB profile,
EEPROM seed, fresh HDD overlays, and 12/30/60-second captures. Pre-repair and
reset-plus-native builds rendered Multiplayer correctly; the candidate with
cold-mount TEST UNIT READY corrupted it at both 30 and 60 seconds; the build
that removed only that request rendered it correctly at both checkpoints.

## Limits

An SMC reset preserves DRAM bytes by design. This repair resets ownership for a
new title lifetime; it does not promise that APIs explicitly requesting
uninitialized memory observe zeros. The fixed Xbox optical topology does not
exercise complete PnP device removal and re-enumeration, which remains a
separate lifecycle improvement rather than part of the disc-swap path. The
current wrong-volume path leaves the retired volume device and VPB allocated;
old handles are safely rejected, but repeated disc replacement can consume a
small amount of kernel memory until the emulator restarts. Safe last-reference
teardown requires its own removal and concurrency contract.
