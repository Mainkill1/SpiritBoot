# Saturated title thread base increments

Independent review of `df1d380ea45cf2c526d1cfd52f9bed52e78c92cd` found that the
public process setter reconstructed every thread increment from its clamped
base. Setting a thread increment to +16 at process base 8 yields base 15 and a
saturated query of +16. Moving the process to 9 cleared native `Saturation` and
changed that query to +6. Negative saturation was also lost: base 1 became 2,
and the query became -7. This violates the pinned native scheduler's explicit
same-class saturation policy.

The actual-source 32-bit ASan/UBSan test first reproduced both failures.
Follow-up patch `0119b` preserves saturated threads, including their current
quantum and decrement state, during moves within a priority class. Crossing
between dynamic priorities (1..15) and real-time priorities (16..31) reapplies
the existing native saturated increment, placing the thread at the new class
minimum or maximum. The existing base setter handles normalization. Process
moves now cover 1..31; raw field stores outside that range retain their previous
behavior. No thread structure, permanent allocation, or pool allocation grows.

The v6 public nxdk guest adds 138 checks to the existing 59-check fixture. It
sets two workers to +16 and -16, then moves the process through its original
base plus two, 16, 20, 31, 15, 2, and its original base plus one. It checks the
process setter result, saturated thread bases, and both saturated queries at
each move. It then creates normal and suspended zero-TLS title workers at process bases
16, 31, and 1, checking creation notification, membership, suspended inheritance,
first entry, termination ordering, and referenced terminal queries. Both title
initialization hooks now restore inherited priorities across 1..31, while the
native system process base and worker quantum remain unchanged.

The new inheritance source case first failed at process base 16 before the
two initialization guards were extended. Source regression: nine cases pass. Product host suite: 134 tests run: 131 pass, with the
same three environment skips (root foreign-owner CI, and two QEMU-header
requirements). Source arithmetic follows the pinned GPL-compatible native
scheduler. Reference kernel behavior is obtained only from public guest calls;
no proprietary source, disassembly, or decompilation is used.

Native v6 qualification confirms 197/197 on Complex, release64 and debug64.
The raw receipts and strict identity/TAP/input validation manifest are retained
in `evidence/process-thread-saturation-20261013/native` and `native-report.json`.

The first v5 reference run identified an observer lifetime bug: it retained
retired case IDs and scanned beyond a matching active case, allowing an ID
reused by the reference allocator to select a stale later slot. This produced
six missing callback assertions for three suspended probes. The fixture now
clears retired IDs after all terminal checks and stops at the first current
match. Every callback ordering assertion remains enabled. The v5 release and
debug candidates passed all 197 checks; final v6 qualification supersedes
that faulty reference receipt.

Final v6 validation checks exact ROM/ISO/executable hashes, interactive session,
64 MiB configuration, unchanged recorded HDD/EEPROM/boot-ROM seeds, and all
197 ordinary assertions without skips or TODOs. It supersedes the v5 observer
false failures. No reference mismatch remains in the qualified priority,
membership, creation, notification, retirement and terminal-query contracts.
