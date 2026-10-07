# Final independent-kernel qualification evidence

These files are exact copies from final local builds and direct xemu captures,
with checksummed identities in `final-verification.json`. Build manifests retain
original `/work` container paths. `release` means DBG=0; `checked` means DBG=1,
KDBG=FALSE. Both use the reviewed patched source tree. Guest compilation happened
after source-tree attribution and created only separate build outputs.

Each API/contracts/warm capture has its original run manifest, serial TAP,
emulator log and configuration. Full XISO captures additionally retain byte-exact
JSON results, guest configuration and COMPLETE receipts. Verification reports
check all catalog IDs/revisions/kinds, counts, outcomes, applicable oracles and
clean exits. Complete pinned hash-comparison reports show all 253 eligible hashes.
Non-applicable S3TC diagnostic counts remain visible. Historical red captures
are labeled `baseline-red-corrected`, `pre-review-red` and `pre-review-warm-red`;
they are not results for the final BIOS.

`grade_xiso.py` is the original host analysis used on extracted private HDDs.
Its baseline defaults refer to the original workspace; supply a matched
`--baseline-root` elsewhere. It launches no test runner. Original private QCOW2
and sparse raw images remain ignored local artifacts. Their identities are in
capture manifests. No game or community firmware bytes are included here.

See [the report](../../provenance/CLEAN_ROOM_XEMU_BASELINE.md) for reproduction,
source separation, reviewed fixes, scope and limitations. The evidence does not
establish retail gameplay, hardware support or measured performance.
