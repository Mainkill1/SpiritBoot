# FATX save-path contract

Run this standalone nxdk XBE on a **fresh disposable HDD overlay per run**.
It creates `E:\SpiritBootSavePathProbe` and synthetic 11,176-byte files; it never
opens a game's save directory. Reusing an overlay would no longer demonstrate
fresh creation with the observed `FILE_OPEN_IF` disposition.

```sh
NXDK_DIR=/path/to/nxdk PATH=/path/to/nxdk/bin:$PATH make
```

Boot `save-path-probe.iso` with a 64 MB BIOS and emulator, attach an LPC47M157
serial device, and capture COM1. A successful run prints 34 passing checks,
`failures=0`, and shuts down. The same binary is run on the reference and both
SpiritBoot builds. Each run must use the same EEPROM and HDD backing image.

The public-API checks cover NtCreateFile, NtOpenFile, and IoCreateFile; canonical,
doubled, tripled, volume-root and native-device path spellings; directory-relative
controls; and synthetic save creation, write, flush, close, reopen and byte equality.
The assertions for invalid spellings come from the reference observations, not
from the candidate algorithm. Host tests separately exercise counted, non-NUL
buffers, Unicode characters, guards, and validation before mutation.

The final `survey=` lines are **observations, not passing checks**. In particular,
a trailing separator on a regular file still returns NAME_INVALID in SpiritBoot
where Complex returns NOT_A_DIRECTORY. That separate status-parity issue is not
needed to create or reload DOA's save and is not claimed fixed here.
