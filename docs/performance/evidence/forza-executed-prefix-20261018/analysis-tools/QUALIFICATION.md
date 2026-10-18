# Frozen v2 native cohort qualification

`qualify.py` qualifies a complete bounded recorder cohort before its counts
are used for analysis. It does not modify the parser or join tool.

The required configuration is version 2, handle `0x42c`, max/admitted/returned
calls all 64, admission closed, and exactly these half-open owned ranges:

- `.text`: `84001000` through `84055400`.
- `PAGE`: `84069000` through `84069b08`.

The strict prefix parser must accept all health and count records. The strict
identity parser and analyzer must establish 64 distinct complete native calls
inside the receipt interval. Each call must return success or pending and
have exactly one successful callback whose byte count equals that call's
requested size. Every callback must also be inside the receipt interval.
Callback ownership uses the live IOSB generation, not the active-call label;
a callback before native return and IOSB reuse after a callback are allowed.
Unknown or duplicate callbacks reject until all 64 calls have begun, returned,
and completed successfully. That event defines the selected drain boundary.
After it, the recorder may still observe callbacks for unadmitted reads,
including reused IOSBs; these are counted as `unassigned_post_drain` without
claiming ownership or selected-call correctness. All later event kinds are
counted separately. Identity issues and open tracked state through the selected
drain reject qualification. Every admitted
call must have prefix observations, and every owned, excluded, or translation
reference must resolve inside its admitted active-call interval.

Example (paths supplied by the capture owner):

```sh
python3 qualify.py --prefix PREFIX.log --identity IDENTITY.log \
  --receipts RECEIPTS.jsonl --identity-tools IDENTITY_TOOLS_DIR \
  --output UNIQUE_QUALIFICATION.json
```

Use a unique output path for each capture and require a zero process exit.
An invalid cohort raises an error and does not write a new qualification.
Successful output includes source-input and tool hashes, exact admission and
range metadata, recorder health, per-call lifecycle sequence IDs, callback
count, and owned/excluded instruction-start totals.

This checks observed accounting and callback/status/length lifetimes, not
payload bytes, timing correctness, runtime byte identity, or performance.
Declared ranges must still be independently bound to the intended loaded
image before static symbol attribution is treated as image-specific.

Tests were written before implementation. `qualify-red.log` preserves failures
against the non-qualifying stub. `qualify-full-green.log` records full discovery:
94 tests pass, including 20 qualifier tests. Synthetic cases cover configuration
drift, truncated/overflowed input, incomplete admission, handle mismatch,
receipt cuts, missing/duplicate/unknown/failed/short callbacks, failed native
returns, unresolved identity/open lifetimes, missing or invalid prefix
references, valid callback-before-return and IOSB reuse, and CLI hash binding.

The post-drain rule was added test-first after inspecting the owned numeric
v2 capture. `qualify-drain-red.log` preserves the failing prior behavior.
The added tests require explicit counting of later callbacks, reject any
unknown/duplicate callback before full drain, require all 64 native returns
as well as callbacks, and reject missing selected callbacks.

Offline review of the existing v2 capture produced
`../capture/qualification.json`: 64 selected calls and successful
callbacks, drain sequence 666, 269 unassigned later callbacks, and no open
selected lifetimes. Instruction starts total 617376 (611862 owned, 5514
excluded). This review result remains subject to the parent's independent
acceptance; it is not a performance claim. Raw capture inputs were unchanged.
