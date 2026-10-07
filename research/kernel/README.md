# Kernel compatibility inventory

`exports.csv` is the machine-readable 379-slot Xbox kernel export inventory covering ordinals 0-378.

The baseline names come from Cxbx-Reloaded's public kernel thunk table. Roswell's public export definition supplies ABI/type information where present, and Roswell's ordinal map supplies mapped/stub/data-scaffold state.

This is an inventory, not a correctness claim. In particular, `roswell_state=mapped` means only that the ordinal resolves to a symbol.

See `STATUS.md` for the current summary and `provenance.json` for exact source revisions.

Target columns:

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

Next pass: correlate every row with xbox_kernel_test_suite and Cxbx-Reloaded implementation locations, then assign behavioral confidence and subsystem priority.
