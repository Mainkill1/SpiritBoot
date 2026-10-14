# Public process/thread contract

This nxdk guest reads only the published `KPROCESS`, `KTHREAD`, and `ETHREAD`
ABI. It creates both `PsCreateSystemThreadEx` and five-argument
`PsCreateSystemThread` workers, including a suspended thread with zero TLS.

The guest checks membership and inherited priority in creation callbacks and
before the worker starts, observes a +2 per-thread base increment across a
process priority change, and checks removal from the process list after a
thread signals while a reference keeps the object alive. Exit callbacks must
still observe membership. Every process priority change stays inside 1..15.

Build using the pinned nxdk container in `sources/firmware-lock.json`:

```sh
make NXDK_DIR=/usr/src/nxdk
```

Run `process-thread-contract-v6.iso` from a cold boot on the reference and candidate firmware.
Record the TAP output and the input ROM/ISO hashes. The plan contains 197
checks; there are no TODOs or skips. List enumeration runs at DPC level and
checks reciprocal links and a bounded traversal.

The product copy is also exported into the patched Roswell source through
`0119a-native-process-thread-contract.patch`. No proprietary firmware binary,
source, disassembly, or key material is included.

Version 6 adds positive/negative saturation and process moves across dynamic
and real-time priority classes. See the saturation provenance note.
