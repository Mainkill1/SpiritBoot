# Exposure and validation

Author: isolated implementer agent `pr248_sense_normalizer`, 2026-10-14.
Strict third-party clean-room profile applied. I did not inspect assembled
Roswell, classpnp/disk implementation, history, helpers, disassembly, native packet
headers, or an unfiltered repository. Work is confined to this owned directory.

Inputs read:

- `oss-clean-room/SKILL.md` and `references/separation-profiles.md` (workflow).
- Approved `clean-room-inputs/CONTRACT.md` and `PUBLIC-REFERENCES.md`.
- Filtered `scsi-interface-only.h`, SHA-256
  `002f04c8ecd5437e23e7c143c431e65805fded9167047874d333bfb34787446c`:
  sense-related public constants and declarations, with search context only.
- Root's behavior-only handoff: independently reviewed Seagate Rev M section 2.4,
  Tables 12/27, and owned copied-buffer facts (96-byte limit, count, provenance).
  The manual was not fetched by this implementer. Approved reference:
  https://knowledge.seagate.com/files/staticfiles/support/docs/manual/Interface%20manuals/100293068m.pdf

No third-party function bodies or tests were read. SPEC.md was written before
implementation. The four literal byte vectors and tests were independently
written here. Necessary convergence is limited to public wire offsets, masks,
response codes, and the supplied owned copy bound. Repository naming conventions
were not inspected; portable C uses an independently chosen Sb prefix and normal
indented braces. This artifact is unlinked: no native build or driver integration
has been performed. Readability of nonnull caller memory is a caller precondition;
a portable C function cannot probe arbitrary pointers.

The stub compiled but failed the first unavailable-reason assertion (exit 134).
The actual production function then passed both commands below, each printing
`sense_header: all tests passed` with exit 0:

```
cc -std=c99 -Wall -Wextra -Werror -pedantic sense_header.c sense_header_test.c -o sense_header_test
./sense_header_test
cc -std=c99 -Wall -Wextra -Werror -pedantic -g -fsanitize=address,undefined -fno-omit-frame-pointer sense_header.c sense_header_test.c -o sense_header_test_san
./sense_header_test_san
```

Coverage: all four formats/timings; every prefix of each independent vector;
exact heap bounds under ASan; declared lengths 8 through 263; fixed tuple absent
from declared extent despite present copied bytes; usable tuple with missing
tail; both extents short; invalid count/capacity and maximum size_t; null storage;
absent autosense without dereferencing storage; every unsupported response byte;
ignored high response/key bits; unchanged input and canaries; returned facts
checked after source poisoning and freeing. Arbitrary descriptor-tail bytes
intentionally demonstrate that tuple availability is not record validation.
No allocation or external calls are used by the production implementation.

Packaging follow-up: original authored code now carries SPDX GPL-2.0-only.
`0135-independent-sense-header-primitive.patch` adds only the two production
files and `tests/host/nxstorage-sense/{sense_header_test.c,check.py}`. No native
build integration is included. The runner resolves production files relative to
its repository location, honors CC, and runs plain plus ASan/UBSan builds.
It passed using default cc in an owned synthetic layout and CC=clang after the
patch was applied to a fresh owned empty directory with `patch -p1`.

Target portability check passed:

```
clang -target i386-unknown-none-elf -std=c99 -Wall -Wextra -Werror -pedantic -ffreestanding -fno-builtin -O2 -c sense_header.c -o sense_header-i386.o
nm -u sense_header-i386.o
```

The undefined-symbol listing was empty: no allocator or libc imports. This is a
freestanding compile check, not a native kernel link or runtime qualification.
