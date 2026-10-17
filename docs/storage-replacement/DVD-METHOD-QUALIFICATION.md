# Bounded DVD method qualification

The current method boots a recorder from a fixed wrapper and reads the exact
released payload at `\Device\CdRom0\target.xbe`. The original released ISO
and the actual mounted wrapper are separate artifacts. The wrapper changes the
boot file and directory layout; exact-original-media parity remains open.
This cohort provides functional byte-fill evidence only. Every retained duration
is ineligible for P1, A/A calibration or candidate performance comparison.

The [portable receipt](dvd-method-qualification-receipt.json) pins the source,
plan, parser, caller, wrapper layouts, original payloads and raw predecessors.
It contains observations and hashes without executable or game bytes. Exact raw
artifacts remain preserved under `.scratch/pr248-native-baseline/evidence/RUN_ID`.

| Preserved attempt | Actual result | Functional observation |
| --- | --- | --- |
| V2.8.3, `20261014-191609180-76df34157ae24431957c67900197559f` | Runner completed, exit0; qualification failed | `declared-media-remount-timeout`; no META or operations. |
| V2.9, `20261014-192915457-06380a443faf4bd3a8a96b74e7f677d8` | Runner completed, exit0; raw diagnostic only | First query reported old recorder length118784; next open returned `c0000013`, then118 opens returned `80000016` (VERIFY_REQUIRED). Terminal mounted0/measurement_started0. |
| V3.0, `20261014-194653180-7efa0acf932940bb9489d31363000ba7` | Runner timeout after180s, exit137; qualification failed | Private C recorder boot reached READY. Five managed DVD operations completed; guest open never reached measured operations. |

Each predecessor has complete owned-process stop and finalized-evidence receipts.
A public dismount success did not establish successful media remount. The raw
V2.9 query records report the caller's initialized IOSB; they do not establish an
unobserved internal driver Information value. No failure or old freeze was erased.
The abandoned HDD installer and optional empty-media source are preserved locally
and excluded from the product changes. No production filesystem change was made.

The new recorder opens `target.xbe`, checks successful public file-query status,
IOSB status, complete returned count and exact file length, then performs the
unchanged generation2 verification loop. Each of1,024 reads poisons all4,096
output bytes and its IOSB before the per-operation tick, checks status/count and
compares the complete public header inside the measured interval. Queue depth1,
APCs0 and cold-ish (no intentional warmup) are frozen. Cold-ish does not establish
physical cold media. The measured loop source matches preserved V2.8.3 byte for
byte. A separately pinned20s post-END grace lets final guards observe a live child.

Fresh extraction uses the two pinned released ISOs and the exact pinned
`extract-xiso` executable. Entire opaque payloads are copied and hashed; only the
first4,096 public header bytes and XISO layout metadata are inspected. Independent
wrapper parsing verifies both complete file extents and their hashes. The clean
and performance wrappers are distinct, even though their target extents happen
to begin at sector265, matching the respective original images. This extent
observation does not make the wrapper equal to the original medium.

| Artifact | Clean | Performance |
| --- | --- | --- |
| Original released ISO SHA-256 | `8d01028844e508629d3f73481714ad46ea9931ba55f35956f28d7121f9eba475` | `099d161a6010499cb86be58ccd2297a8be8802d8b8f4b97f7ef720ff5d0d6d33` |
| Exact target XBE SHA-256 | `2b3f3b1e8689c553ee0136126b28b4bb5249e022fe215a37ccb79a24ddf30864` | `4ccfdc7bf54b5c87ec3b9f91fb39701bbbdede87a4437ce3486c3301169a1b25` |
| Mounted wrapper SHA-256 | `6b8c26ab5201eef7d213d6329b5cddc225a8c2f60c403df7ae48491ecd5d0bd7` | `9c3e20d49cad3886f0b341b4bfe4c4f24c5afa9c13632f09e246d0ac67d4d180` |

The recorder XBE is
`87eb31f8aacb5de0a5ce8d79c35b363de546a1ecd2a7c69d515705d30ae9e59b`.
Only one clean/cold pilot is frozen. It uses the unmodified published64 ROM,
original approved78af seed, fresh private HDD/EEPROM and E plan injection.
Actual prepared-HDD bytes remain separately recorded from immutable seed lineage.
All1,024 operation vectors now name `target.xbe`; the original source file remains
`default.xbe`. A revised one-leaf catalog binds this exact workload identity.

The62-entry outer manifest is
`c7e397e4f9e5ff4dbe625ed4fa339214c26faa911fbd4e6731e9a5b2453e13ec`;
plan `f4ce4562822c5e81a25d26412a6608c891530046879dcd487d8126e8afb49189`.
The typed initial/final query-block recipes and read-only guard must prove the
same unique wrapper route, exact input bytes and owned process lifetime. There
is no medium change or direct QMP client. Initial guards may overlap calibration
and reads; no claim is made that this diagnostic control is outside measurement.
Fourteen clean source host tests and the frozen inference/failure controls pass.
The parent reviewed all62 pins and executed one native pilot. Run
`20261014-201527148-70ceced74d5e4cdab8e1b48e4fb035f9` completed with exit0;
strict qualification accepted exactly1,024 ×4,096-byte successful reads, all
status/IOSB/count checks and complete header comparisons, QD1/APCs0 and the
cold-ish label. All four typed query/guard diagnostics completed. The initial
and final guards verified the same actual wrapper route and process lifetime;
owned stop and finalized evidence were complete. Serial SHA-256 is
`d4d005b0fbebb53329bebb4bae06878507c45abb0bfeafbe2c8f2b4756b130e6`.

The concatenated equality hash is explicitly inferred on the host from complete
verified header equality under the pinned fixture; it was not computed inside
the measured interval. The receipt keeps immutable78af seed lineage and actual
prepared-HDD hash separately. This single clean/cold pass establishes the
fixed-media method's bounded functionality. Performance wrapper/warm variants,
full36, Windows optical, normative clock, real flush, physical durability and
private-counter qualification remain open.
