# Initial kernel export snapshot

Source revisions:
- Roswell: `1569e2e89fb47cc72b9c704a8884f98200432bd4`
- Cxbx-Reloaded: `585c49a50af1255ab155099e06f24505f9c5a800`

## Export-table coverage

| State | Slots |
| --- | ---: |
| Mapped to a Roswell symbol | 360 |
| Generated Roswell stub | 8 |
| Data scaffold/constant | 3 |
| Missing from Roswell export definition | 7 |
| Reserved slot 0 | 1 |
| **Total** | **379** |

"Mapped" only means the export resolves to a Roswell symbol. It is **not** evidence that the implementation is Xbox-correct.

## Generated stubs

- 7: `DbgLoadImageSymbols`
- 10: `DbgPrompt`
- 11: `DbgUnLoadImageSymbols`
- 374: `MmDbgAllocateMemory`
- 375: `MmDbgFreeMemory`
- 376: `MmDbgQueryAvailablePages`
- 377: `MmDbgReleaseAddress`
- 378: `MmDbgWriteCheck`

These are dominated by debugger/devkit-facing functionality and should be triaged by observed retail use rather than implemented blindly.

## Data scaffolds

- 40: `HalDiskCachePartitionCount` -> `=3`
- 88: `KdDebuggerEnabled` -> `=1`
- 89: `KdDebuggerNotPresent` -> `=1`

These are deliberate data values/scaffolds, not ordinary function implementations.

## Missing Roswell export definitions

- 367: `UnknownAPI367`
- 368: `UnknownAPI368`
- 369: `UnknownAPI369`
- 370: `XProfpControl`
- 371: `XProfpGetData`
- 372: `IrtClientInitFast`
- 373: `IrtSweep`

Ordinals 370-373 are profiling-related in Cxbx-Reloaded. 367-369 remain named as unknown APIs there. These are not automatically first-priority retail blockers.

## Interpretation

The immediate problem is unlikely to be "implement hundreds of absent exports." The larger unknown is behavioral conformance of the 360 mapped slots, especially scheduler/dispatcher, memory management, I/O, object lifetime, timing, and HAL-facing behavior.

The next inventory pass should correlate `hardware_test` against xbox_kernel_test_suite and attach Roswell/Cxbx implementation locations.
