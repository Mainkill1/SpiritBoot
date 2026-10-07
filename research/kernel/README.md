# Kernel compatibility inventory

`exports.csv` is the machine-readable 379-slot Xbox kernel export inventory covering ordinals 0-378.

The baseline names come from Cxbx-Reloaded's public kernel thunk table. Roswell's public export definition supplies ABI/type information where present, and Roswell's ordinal map supplies mapped/stub/data-scaffold state.

This is an inventory, not a correctness claim. In particular, `roswell_state=mapped` means only that the ordinal resolves to a symbol.

See `STATUS.md` for export-table status, `CORRELATION.md` for behavioral-test coverage, `FIRST_WAVE.md` for the dependency-first work order, and `provenance.json` for exact source revisions.

Current research artifacts:

- `exports.csv` — ABI/export baseline.
- `correlation.csv` — test state, subsystem, source hints, evidence level, complexity/relevance and dependency metadata.
- `correlation-summary.json` — machine-readable aggregate counts and heuristic queue.
- `FIRST_WAVE.csv` / `FIRST_WAVE.md` — curated dependency-first attack plan.
- `hardware-results/` — normalized hardware evidence imported from kernel-test logs.

Correlation columns include:

- `ordinal`
- `name`
- `kind`
- `stack_bytes`
- `abi_style`
- `roswell_state`
- `roswell_symbol`
- `hardware_test`
- `hardware_status`
- `cxbx_reference`
- `confidence`
- `complexity`
- `notes`

Run `scripts/correlate-kernel.ps1` after fetching references to replace source hints with local `git grep` candidates and fold in any imported hardware results. The next evidence task is to implement/run the first-wave behavioral tests, not to fill low-value export slots by count.
