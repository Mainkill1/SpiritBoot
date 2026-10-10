# Exact-image kernel page report

`tools/kernel_page_atlas.py` joins the existing compiler extent inventory with
the bounded TB-frequency capture from `tools/profiling/tb_frequency.c`. It is
offline diagnostic tooling: it changes no kernel code, ROM placement, emulator
configuration or release instrumentation. Related investigation: #136.

```sh
python3 tools/kernel_page_atlas.py \
  --inventory inventory.json --build build.json \
  --kernel xboxkrnl.unstripped.exe --flash flash.bin \
  --capture capture-identity.json --output page-atlas.json
```

Repeat `--capture` for independent recordings. Omit it for a static report.
Output creation is exclusive; an earlier report is never overwritten.

## Inputs and identity

The completed firmware build manifest supplies `source_tree`, `flash_sha256`
and `status`. The tool hashes the supplied PE and flash, rejects a different
flash from that build, and requires the inventory and every recording sidecar
to match the same source tree, PE and flash. It validates section addresses and
virtual sizes against the actual PE32 section table.

The schema2 inventory supplies `sections`, `functions_and_input_extents` and
`sizeof_proved_tables`. Section records contain `name`, `start`, `virtual_bytes`,
`flags`, `executable` and `discardable`. Extent records contain `name`, `symbols`,
`section`, `va`, `extent_end`, `bytes`, and either a certified
`compiler_extent_bytes` with `length_kind: COFF compiler input-section extent`,
or independently established `sizeof_bytes`. Source candidates and confidence
remain optional provenance. This consumes the supplied compiler ledger; it does
not recompile source or independently prove every ledger claim. Next-symbol
intervals are rejected as certified function sizes.

The load ledger determines included sections and final section attributes;
unstripped debug sections are not automatically treated as runtime allocations.
It must come from the same shipped image. Read-only section flags establish
only a placement candidate, never safe ROM execution or actual physical backing.

A capture sidecar is JSON:

```json
{
  "schema": 1,
  "source_tree": "<40 lowercase hex>",
  "pe_sha256": "<64 lowercase hex>",
  "flash_sha256": "<64 lowercase hex>",
  "xemu_sha256": "<64 lowercase hex>",
  "capture": "tb-frequency.ndjson",
  "capture_sha256": "<64 lowercase hex>",
  "phase": "whole-process",
  "window": { "kind": "whole-process" }
}
```

The capture path is relative to its sidecar. Captures require the existing
producer's successful completion footer. Duplicate capture hashes are rejected.
The existing producer records **whole-process** weights. A sidecar cannot relabel
those as title or boot weights. A future qualified producer may declare an
explicit `boot` or `title` phase and matching `window` in its capture header,
using `kind: bounded-recording`, named `start`/`end` boundaries and an
`evidence_sha256`. Both header and sidecar must agree. This tool implements no
new recording capability, and a declaration alone is not guest-progress proof.

## Report meaning

Each included 4 KiB page reports RVA, section, supplied extent owners and aliases,
source confidence, overlap bytes, union bytes, unknown content, tail padding,
phase weights and placement status. Overlapping/identical extents are grouped or
unioned: their individual overlap counts must not be summed as physical bytes.
Zero-length labels can name an existing extent but claim no additional storage.
Known union + unknown content + tail padding always accounts for4096 bytes.

Physical backing is explicitly `unknown`: static addresses and section flags do
not establish RAM versus ROM. Discardable and writable pages are not selected
for resident ROM placement. Other pages require ownership/access qualification.
Removing one extent from a mixed page does not imply reclaiming that page.

TB instructions × executions are entry-page weights, not function-call counts,
exclusive CPU time, retired instructions or the byte coverage of every page a
TB spans. Outside-image and dropped/untracked weights remain visible. Only an
explicit bounded title capture can nominate an observed hot page. Zero observed
work never proves a safe cold page: the report retains `candidate_cold_page: null`
and explains the confidence gap. There is no gameplay/FPS claim.

Run the maintained host suite with:

```sh
python3 -m unittest discover -s tests/host -v
```
