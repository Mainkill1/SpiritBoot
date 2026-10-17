# Per-case artifact checkpoint

This checkpoint adds an opt-in schema and resolver for experiments using more
than one recorder or media image. It does not implement the native importer,
qualify native timing, change counter conversion or change paired statistics.
Without `artifact_policy`, the existing single-fixture schema and behavior apply.

The common baseline/candidate manifest keeps the existing firmware, source,
emulator, toolchain, EEPROM-source and original HDD-seed pins. In this mode it
omits `fixture_sha256` and `iso_sha256`; mixed global/per-case declarations are
rejected. Each sealed job resolves these two fields to its actual recorder XBE
and measured media image. Candidate arms retain the identical case map and
state-source pins.

`artifact_policy` has `schema_version: 1`, `mode: "per-case"`, an `artifact_set`
descriptor and `cases`, an inline map covering exactly all frozen cases. The
descriptor names a real JSON file containing `{"schema_version": 1, "cases":
<the same map>}`. Its hash is `artifact_set_sha256`, never a fixture-file hash.
Each case entry has these fields:

- `recorder_xbe`, `recorder_source`, `recorder_build`, `boot_iso` and
  `measured_media_iso`: confined file descriptors with `path`, `sha256`, `bytes`.
- `hdd_seed`: original `asset_id` and `sha256`, matching the common seed pin.
- `preparation`: explicit `prepared_xiso` or `direct_copy` mode plus `recipe`
  and `request_contract` file descriptors. The request contract names the exact
  frozen `case_sha256`; the case already includes cache preparation and requests.
- DVD entries additionally bind `original_released_iso`, `extracted_target_xbe`
  and `reference_header` descriptors, and separate `source_filename`,
  `request_filename` and `request_path`. Every case request vector must use the
  actual request filename and match its index and declared byte length.

For the fixed DVD wrapper, the original release's `default.xbe` is lineage;
the unmodified payload is wrapper `target.xbe`. The new recorder is wrapper
`default.xbe`. The boot/measured wrapper ISO is distinct from the original ISO.
Merely hashing a stale `default.xbe` request population cannot hide this mismatch.

The current per-case mode requires the existing fixture-fixed `METADATA_ONLY`
workload policy and separated public API durability policy. Their readable
contracts bind `artifact_set_sha256` and all case hashes, without inventing one
`fixture_artifact`. All 36 cases, operation/assertion counts, old healthy-path
gates and positive required physical flush counts remain mandatory. Physical
durability stays INCONCLUSIVE, including when rows supply bare true/count values.

Each row repeats the job's `artifact_set_sha256` and `case_artifact_sha256`, and
supplies `artifact_bindings` containing actual recorder/boot/measured hashes,
source seed hash/asset, preparation mode, EEPROM source hash, request/input/
preparation receipt hashes, and `prepared_image: {sha256, bytes}`. Prepared
images may vary between runs; they are never predeclared as a single output.
`prepared_xiso` outputs must be distinct from the source seed; `direct_copy`
outputs must equal it. Reports preserve available bindings for every planned
attempt, including failed and missing attempts, without inventing missing values.

**Importer gap:** `verified_by_native_importer: true` is currently a declared
integration boundary. This checkpoint checks its presence and consistency of
the supplied hash fields, but does not open/authenticate the native request,
input manifest or preparation receipt behind those hashes, nor pin a verifier.
It checks the readable frozen set and role files. Before real native calibration,
a separately reviewed, pinned importer must verify the actual receipt bytes,
actual run/request/lifetime and mounted roles, original seed lineage, prepared
`RuntimeFiles.Sha256/Bytes`, and required placement/readback facts. A boolean or
hash string alone is not native verification. Synthetic tests exercise resolver
behavior and never establish that this missing importer exists.

Recorded-RDTSC-frequency conversion remains unchanged. Source-fixed conversion
and exact endpoint decisions are the next bounded checkpoint. No A/A, provider
precision, physical durability, P1 or complete driver acceptance follows here.
