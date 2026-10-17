# Rejected QEMU plugin captures

Two read-only QEMU plugin attempts were rejected:

1. `windows-trace-v1-failed` used the documented vCPU-initialization callback
   to discover the `esp` register. The xemu process remained live but never
   exposed a usable QMP channel. It produced an empty trace and no terminal
   plugin report. The failure is bounded to plugin load/vCPU initialization;
   the retained evidence does not distinguish a loader, callback, or Windows
   plugin-integration defect.
2. `windows-trace-v2` deferred register discovery until the first instruction
   callback. It exposed QMP during startup, then became unresponsive at that
   callback and wrote zero records. QEMU documents
   `qemu_plugin_get_registers()` for the vCPU-initialization callback; calling
   it from an instruction callback made this attempt unsupported, so it cannot
   qualify or refute the guest path.

The callback would also perform many `qemu_plugin_read_memory_vaddr()` calls,
which enter QEMU's debug virtual-memory reader from translated execution and
would perturb the hot path even if the collector ran. Neither failure says
anything about SpiritBoot correctness or request eligibility. The aggregate
firmware-counter method replaced this collector for the current investigation.
