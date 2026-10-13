# Public thread identity evidence

These are public-API standalone XBE receipts on the original uninstrumented
xemu binary. `launch.json` pins BIOS, emulator and fixture SHA256 values;
`serial.log` contains all assertions. A process exit code alone is insufficient.
No proprietary binary, code or disassembly is included.

`wait-v4-oracle-complex-*` intentionally preserves an invalid fixture: it
expected APC_LEVEL for a user APC kernel routine and passed NULL for the
required public wait-block array. Complex runs both user APC routines at
PASSIVE_LEVEL; NULL blocks bugcheck. Corrected captures are separate.

`wait-v4-corrected-prototype3-*` is a valid failing v3 control: exactly 20
assertions reject abandoned-result block fields and callback-time native
pointers. Complex and v4 pass all 295 checks. `wait-v4-mixed-*` also includes
a held public self-thread in the wait array and WaitNext before user APC.

The async2 cost control deliberately fails only the aggregate public thread
identity/exit assertion. Its timing and page measurements are still reported,
with that expected failure made explicit. Both v4 runs pass all 139 checks.
Performance values are within-boot medians of three rounds; the four boots
run A/B/B/A. No traces, HDD throttle or diagnostic ROM instrumentation is used.

The authoritative narrative and limitations are in
[PUBLIC_THREAD_IDENTITY.md](../../PUBLIC_THREAD_IDENTITY.md).

Committed Windows text copies normalize CRLF to LF and trim CPU-brand padding
in emulator stderr; the failed bugcheck capture also trims trailing blank lines.
The normalization manifest
records original and normalized SHA256 values; original captures remain retained
in the qualification workspace. No assertion text or measurements were edited.
