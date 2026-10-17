# Rejected release trace collector

This collector is retained as failure evidence and must not be used for the
current xemu build. Version 1 blocked runner control during plugin/vCPU
initialization. Version 2 moved register discovery into an instruction
callback, where QEMU does not support `qemu_plugin_get_registers()`, and then
stalled at the first likely callback. See `RESULTS.md`. The accepted
observation method is the diagnostic release firmware under
`../diagnostic-counter/`.

The rejected DLL is identified by the retained job input manifests but is not
stored in the repository. The independently authored source and runner remain
available for auditing; a future collector must first restore documented
vCPU-initialization register discovery and pass an isolated plugin smoke test.

`xdvdfs_trace_plugin.c` is a diagnostic QEMU plugin which transcribes the
scalar request facts frozen in `../rust-model/CAPTURE-SPEC.md`. It contains no
eligibility or completion policy. The Rust model remains the decision
authority.

The plugin installs one callback at the exact supplied
`XdvdDispatchRead` address, reads the current x86 `esp`, follows only the
bound structure fields, and writes the strict 16-column TSV accepted by
`analyze-trace`. Any failed memory read or structure relation increments the
rejected count. A nonzero rejected count makes the capture incomplete.

Required plugin arguments:

```text
output=PATH,report=PATH,pc=0x8404840c
```

The selected PC must be taken from the exact release map and paired with an
external exact-kernel/entry-byte binding. The runner package must retain the
plugin source, binary, release BIOS, final kernel hash, map hash, request, and
result hashes.

The collector runs only on a diagnostic release workload. Its callback cost
invalidates elapsed-time performance measurements from the same run; the
result establishes request shape only. Timing acceptance requires a separate
uninstrumented release A/B.
