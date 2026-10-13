# thread-public-identity

Standalone nxdk public-API qualification of creation/exit notification identity, current/real/pseudo-handle equivalence, pointer-consuming APIs, APC delivery/rundown, held references, terminal status and GetExitCodeThread.

Build with `make NXDK_DIR=/path/to/nxdk`. Boot the generated ISO on a disposable
64 MiB xemu instance using `-device lpc47m157 -serial file:serial.log`. No game
assets, patched emulator, trace instrumentation or HDD throttle are needed.
Expect 166 consecutive TAP assertions, a matching plan, `failures=0`, and
normal guest-initiated shutdown. Allow 120 seconds and retain BIOS/emulator/
fixture hashes with the full serial capture.

Known failing earlier-kernel controls and exact scope are documented in
[public thread identity qualification](../../../docs/provenance/PUBLIC_THREAD_IDENTITY.md).
