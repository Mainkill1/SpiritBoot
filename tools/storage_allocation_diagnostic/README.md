# Owned allocation diagnostic

This GPL-2.0-only first-party tool records allocator/free entry and normal-return lifetimes while the selected owned fixture executes 1,024 synchronous 4 KB reads. It preserves unknown ownership, incomplete inventory, capture loss and requested-byte versus physical-charge distinctions. It does not launch xemu or qualify performance/private pool counters.

Generate selected bindings locally from explicit inputs:

```sh
python3 tools/storage_allocation_diagnostic/prepare_kernel_binding.py "$PR248_UNSTRIPPED" "$PR248_FINAL_KERNEL" tools/storage_allocation_diagnostic/rsp_transport.py > selected-binding.json
python3 tools/storage_allocation_diagnostic/prepare_fixture_binding.py "$PR248_OWNED_XBE" "$PR248_OWNED_OBJECT" > fixture-binding.json
```

These generators reject different selected image hashes. Keep generated code-byte profiles in the frozen native job package, outside source control and replacement-driver author inputs. The collector takes explicit binding, fixture, context, transport, port and new output-directory arguments; it has no automatic target selection.

Use the existing supported HTTP runner with the Windows USER desktop native-launch wrapper, its reviewed configuration and a fresh owned job ID. Set StartPaused through the job field, then use typed QMP query-status, the before-gdb ownership guard, typed QMP human-monitor-command to open the declared loopback GDB port, another typed status query and the capture guard. The observer checks actual process/image/start/session/desktop/argv/config and listener ownership before the first RSP packet. No manual -S, remote-shell launch or unguarded attachment is supported.

The existing tests/xbe/storage-perf/dvd-route-windows-guard.ps1 and windows-launch.c are project dependencies. Freeze all uploaded source/profile/input hashes and observe the actual Python executable before submission. The expected JSON for the small recipe builder contains expected_config_sha256, expected_flash_sha256, expected_iso_sha256, expected_job, expected_launcher_sha256, expected_package, expected_xemu_sha256, gdb_port, kernel_sha256, python_executable and source_pins. The source_pins map contains the five runtime Python modules, both generated bindings and both PowerShell guards. Every hash is explicit; package and Python paths are literal observed Windows paths. Metadata alone does not authenticate these declarations.

```sh
python3 tests/xbe/storage-perf/make-windows-allocation-guard-command.py --expected frozen-expectations.json --stage before-gdb > before-recipe.json
python3 tests/xbe/storage-perf/make-windows-allocation-guard-command.py --expected frozen-expectations.json --stage capture > capture-recipe.json
python3 -m unittest discover -s tests/host -p 'test_storage_allocation*.py' -v
```

The builder emits only external diagnostic recipe JSON; the operator inserts it into the reviewed native job and submits through HTTP. Raw trace files belong to that result, alongside guard and cleanup receipts. Offline analysis is available with allocation_ledger.py events.jsonl. The historical v4 native receipt covers the earlier frozen source bundle; this rehomed bundle needs its own source/request review and runtime binding.

See docs/storage-replacement/ALLOCATION-DIAGNOSTIC.md for the duplicate-stop fix, observed native scope and remaining gates. Python dependencies are standard-library modules only. Host fixtures use invented bindings; none establishes native execution or desktop ownership.
