# DVD media fields in native import

The original `f63ce574` importer omits `media_sha256` from DVD rows. The frozen comparator requires that field to match each case's `iso_sha256`. The immutable first V352 cycle therefore imports 72 rows with narrow timing flags, but comparator inspection accepts 64 and retains eight DVD media-field issues, alongside 288 expected missing attempts. No completed P1 or calibration is established.

The proposed correction binds the actual verified `storage-perf.iso` and `target.iso` input rows to their separate frozen artifact roles. It also checks the hashed post-END recorder and its readonly actual DVD route. Only then does it emit `media_sha256` from the observed mounted-wrapper input. The original released ISO remains separately recorded as `original_released_iso_sha256`; `media_method` is `fixed-wrapper` and `exact_original_media_parity` stays false. Original `dvd_media` observations are preserved.

| Variant | Declared and mounted wrapper (`media_sha256`) | Original released ISO (`target.iso` provenance) |
| --- | --- | --- |
| Clean | `6b8c26ab5201eef7d213d6329b5cddc225a8c2f60c403df7ae48491ecd5d0bd7` | `8d01028844e508629d3f73481714ad46ea9931ba55f35956f28d7121f9eba475` |
| Performance | `9c3e20d49cad3886f0b341b4bfe4c4f24c5afa9c13632f09e246d0ac67d4d180` | `099d161a6010499cb86be58ccd2297a8be8802d8b8f4b97f7ef720ff5d0d6d33` |

The wrapper contains recorder `default.xbe` and the original extracted target bytes as `target.xbe`. The measured request is `\Device\CdRom0\target.xbe`. The original released ISO is provenance input; it is not the mounted image. These distinct hashes cannot establish original-media layout parity.

Tests preserve the original 72-row import and reproduce its eight actual DVD comparator issues. A helper-only diagnostic repair of copied dictionaries accepts all 72 timing shapes with 288 missing attempts still explicit. That test does not replay a changed clock verifier under the old contract and produces no accepted cohort. It rejects missing, wrong, unverified or duplicated original-input rows, coherent foreign original identities, incorrect wrapper hashes/routes, writable routes and parity claims. Two portable full-emitter tests exercise both invented DVD variants against the complete comparator interface under a matching invented future clock contract.

V352's immutable clock contract pins `f63ce574`; a corrected importer cannot reuse it. An explicit test requires the existing verifier guard to reject that reuse. The original importer, comparator, interval helper, parser and post-context observer are archived together for original-method replay. V352 stopped after 89 qualified native captures and a preserved package preflight failure before the next guest launched. The full original 90-row ledger remains intact; its importer constructor failure for the absent native run ID also remains a distinct limitation.

For future qualification, review this correction, freeze the new verifier hash and contract before a new declared cohort, and keep every native/normalization failure. Retrospective copied-row diagnostics can explain the missing field; they cannot relabel or repin V352. Physical flush, durability and private structural telemetry remain unknown. No native dispatch, production BIOS change, threshold change or candidate comparison occurs in this preparation.
