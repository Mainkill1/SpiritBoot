# Public IRP thread identity

Build with nxdk using `make NXDK_DIR=/path/to/nxdk`. This standalone public API
fixture uses its own title device and shuts down after a TAP plan.

The exact fixture passed 77/77 on Complex, v5 release64 and v5 checked64. It
checks public thread identity in all three IRP builders, queue/list/header
invariance, inline and pending completion from another thread, exact IOSB,
all StartIo entry paths, retained completion (`MORE_PROCESSING_REQUIRED`),
caller reinitialization/requeue, and native I/O manager dispatch to the title
driver with exact returned data. It uses only published public structures and
APIs; no proprietary executable source is inspected.

The title driver grants its requested read access through `IoSetShareAccess`
and reports the actual read length. Earlier expanded fixtures omitted that
access setup and overreported a buffered transfer; those receipts are excluded
and retained in the provenance evidence. Native→title→native forwarding and
free-in-callback cases additionally run in the actual-source host suite.

See `docs/provenance/PUBLIC_THREAD_IDENTITY.md` for exact firmware identities,
receipts, and scope limits. This fixture does not claim that the public thread
view mirrors native intrusive lists or live scheduler fields.
