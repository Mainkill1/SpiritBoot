# FATX asynchronous-read lifetime regression

This standalone nxdk XBE creates its own 8 MiB patterned file at
`\Device\Harddisk0\Partition4\async-life.bin`. Run it only with a disposable HDD
overlay containing a formatted Partition4 and a separate EEPROM copy. The test
creates, truncates and deletes that path. It requires no game assets.

```sh
make NXDK_DIR=/path/to/nxdk
```

Boot `async-qualification.iso` on 64 MiB xemu with
`-device lpc47m157 -serial file:serial.log`, a QMP endpoint, and `-S`.
Before continuing the VM, apply a 2 MiB/s HDD read limit through QMP:

```sh
python3 throttle.py QMP_PORT 2097152 qmp-throttle.json
```

The script requires exactly one inserted disk whose filename ends in
`hdd.qcow2`, records the QMP exchanges, applies `block_set_io_throttle`, and
continues the VM. The throttle creates real pending I/O for lifetime checks;
these runs do not measure product performance. No IDE callback is replaced.

A passing capture contains 7,833 consecutive TAP assertions, a matching plan,
`failures=0`, and normal guest-initiated shutdown. Allow 120 seconds. Retain BIOS,
emulator and fixture hashes, complete serial output and the QMP transcript.

The checks cover four concurrent issuers through one asynchronous handle;
exact data, buffer/IOSB guards and APC identity; explicit-offset file-position
preservation; repeated-read page/pool stability; issuer termination; and reads
pending when another thread closes, truncates or deletes the file. An EOF read
after truncation must preserve its buffer, and a new generation must read back
correctly. Termination provides the public cancellation/rundown path: the Xbox
export set has no standalone NtCancelIoFile or IoCancelIrp.

Thread ID/exit-code wrapper values are retained as diagnostics. Earlier
SpiritBoot builds have a separate public thread-object layout discrepancy;
storage assertions therefore use opaque public thread identity, signaled waits
and the worker's explicit result. Complex accepts those same checks. This test
does not instrument the filesystem's internal fast-path selection.
