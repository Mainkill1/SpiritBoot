# Test strategy

SpiritBoot uses four layers of testing.

## 1. Kernel API conformance

Primary input: Cxbx-Reloaded xbox_kernel_test_suite.

Normalize each result:

```json
{
  "ordinal": 159,
  "name": "KeWaitForSingleObject",
  "environment": "retail-1.6",
  "implementation": "hardware",
  "test_revision": "<sha>",
  "result": "pass",
  "observations": {}
}
```

Capture return values and side effects when possible instead of reducing behavior to PASS/FAIL.

## 2. Differential traces

Normalize kernel-facing events across original hardware/reference kernel, SpiritBoot/Roswell on xemu, and Cxbx-Reloaded where equivalent tracing exists.

Suggested fields:
- event id
- guest timestamp
- thread id
- ordinal/name
- normalized arguments
- status/result
- relevant before/after object state
- optional MMIO/hardware consequence

Reports should identify the first meaningful divergence.

## 3. Boot/compatibility state machine

```text
RESET
BOOTROM_ENTERED
FLASH_ENTERED
KERNEL_ENTRY
KERNEL_READY
XBE_MAPPED
XBE_ENTRY
FIRST_RENDER
MENU_REACHED
SCRIPTED_SCENE
CLEAN_EXIT_OR_REBOOT
```

Every run reports the last confirmed marker.

## 4. Performance

Kernel microbenchmarks may record:
- guest instruction count
- TB execution/dispatch count
- TLB invalidations
- PTE/protection updates
- MMIO accesses
- allocations/frees
- wait/wakeup counts
- I/O operations and bytes

Title performance remains bound to exact xemu, SpiritBoot, test/XISO, settings, host hardware/OS/driver, and scene/start-state proof.

Do not attribute whole-title performance to a kernel change without measuring the changed path directly.
