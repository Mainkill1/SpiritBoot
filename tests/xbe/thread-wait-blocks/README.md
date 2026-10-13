# thread-wait-blocks

Standalone nxdk public-API qualification of immediate event/abandoned waits, WaitNext, exact caller block prefixes, actual queued and immediate user APC observations, mixed thread/event objects, Count 1/2/64, callback reentrant waits, order and IRQL.

Build with `make NXDK_DIR=/path/to/nxdk`. Boot the generated ISO on a disposable
64 MiB xemu instance using `-device lpc47m157 -serial file:serial.log`. No game
assets, patched emulator, trace instrumentation or HDD throttle are needed.
Expect 295 consecutive TAP assertions, a matching plan, `failures=0`, and
normal guest-initiated shutdown. Allow 120 seconds and retain BIOS/emulator/
fixture hashes with the full serial capture.

Known failing earlier-kernel controls and exact scope are documented in
[public thread identity qualification](../../../docs/provenance/PUBLIC_THREAD_IDENTITY.md).
