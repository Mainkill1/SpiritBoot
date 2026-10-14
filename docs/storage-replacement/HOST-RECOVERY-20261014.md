# Native host recovery — 2026-10-14

The operator authorized clearing old xemu test files and repairing the desktop runner. Normal test execution continues through the runner HTTP API; remote shell access is limited to this operator recovery.

## Windows desktop runner

TCP/9368 timed out while SSH was reachable. The current `XemuTestRunnerBoundary3aa5e059` scheduled task was stopped, no runner or xemu process remained, and the task reported result 267014 (terminated). Its execution limit was `PT72H`. The last retained runner log showed idle with no queued or active job. These observations are consistent with the task lifetime limit; no independent Task Scheduler event-log cause was available. This was not a DNS lookup failure.

Recovery preserved the task XML and previous log under `C:/xemu-lab/incoming/runner-boundary-3aa5e059/recovery-20261014`, changed the task lifetime limit to `PT0S`, and started that same interactive Codex task. The executable, configuration, job queues and desktop launch mechanism were unchanged. Recovery inspected ordinary queue entries while preserving the runner's hidden metadata directories and lock file.

Direct HTTP returned the original `0.2.0+3aa5e059d52339bf4b14725260e124322c30beca` identity and idle state. The runner executes in desktop session 1. The first frozen V362 functional case then completed 1,024 reads / 4,096 checks with zero failures. Its actual receipts verified the Codex USER named-pipe launch, `WinSta0/Default`, PowerShell 5.1, exact input binding and owned process exit. The remaining functional cases were started only after inspecting that first result.

See [recovery receipt](WINDOWS-RUNNER-RECOVERY.json). Functional results do not establish timing acceptance, physical durability, a complete replacement, or licensing closure. The original stopped Deck calibration and its failures remain preserved.

## Windows functional completion and separate paused-start failure

The complete frozen V362 matrix finished: **36/36 cases**, **36,864 operations**, **795,975,680 bytes**, and **188,416 assertions**, with **zero failures**. All four fixed-wrapper DVD cases passed native PowerShell media/desktop/route checks. See [the full result and run identities](WINDOWS-V362-RESULT.json).

A separate explicitly diagnostic StartPaused probe then reproduced a runner defect before guest workload execution. Run `20261014-232002940-6dd1b2f44cad4e32a7d3e9eac5850b35` was preserved as `control_error`. The runner reported `Paused=false`, while read-only operator recovery inspection of the uniquely owned QMP listener returned `status=prelaunch, running=false` for the selected desktop guest. The deployed `RefreshPauseStateAsync` recognizes only the string `paused`, so it rejects this valid stopped launch. The managed diagnostic API could not inspect the state because initialization failed before diagnostic-context attachment; its 409 response is retained. Root then quit the exact owned target through the HTTP API and collected the failed attempt. No GDB server or allocator tracing ran, and this failure is not counted as a functional-suite failure or pass.

The minimal correction is [runner PR #109](https://github.com/Mainkill1/Xemu-Test-Runner/pull/109), stacked on the already deployed benchmark-boundary PR #106. It validates typed QMP state/running fields and recognizes stopped prelaunch without changing cached waiters on malformed or contradictory replies. Independent review found no critical or important issues; focused checks pass 27/27 and the full runner/API host checks pass.

The exact reviewed Windows Release (`baf56ca5164ab477cf7bc3c424705577df0100f5`) is [deployed](WINDOWS-RUNNER-DEPLOYMENT.json) through the same interactive desktop task, with its unlimited lifetime and configuration retained. Four existing helpers were copied byte-for-byte and verified. The prior task XML and binary remain available for rollback. A [new native probe](WINDOWS-STARTPAUSED-QUALIFIED.json) completed initial `prelaunch/running=false`, ownership/desktop checks, managed resume, guest END with zero failures, and private-disk cleanup. The [original failed probe](WINDOWS-STARTPAUSED-FAILURE.json) remains recorded separately. Neither run is BIOS performance or licensing acceptance.

## Deck space recovery

The operator-approved cleanup retired exactly **275 obsolete finalized executable copies**. Each file was rechecked against the explicit inventory, its terminal result and metadata, and a retained byte-identical canonical executable. Root verified the deletion receipt contained exactly the planned paths, all direct archived `Queue/Tested/<package>/xemu` files and none from V352.

Measured free space rose from **984,719,360 to 15,222,976,512 bytes**, reclaiming **14,238,257,152 physical bytes**. Logical retired bytes were larger because some copies shared filesystem storage. All four retained canonical executable hashes, the clean disk seed, all 89 current V352 executable paths and 99 protected media files were verified afterward. Games, HDD/EEPROM state, disk assets, ISOs, results, evidence, queue definitions and settings were untouched. The Deck HTTP runner remained idle with no pending or active jobs.

See [the sealed cleanup receipt](DECK-CLEANUP-20261014.json) for exact inventory/deletion-log hashes and retained canonical locations. This cleanup does not resume or qualify the stopped V352 campaign. A fresh method diagnostic must use new identities and record any future housekeeping outside measured pairs.

## Allocation diagnostic follow-on

Fresh allocation run `20261014-233932868-ebea89c151b845a28985f009be7229ea` passed both native ownership guards and attached its owned debugger. It observed 443 complete issue-to-verified-consumer pairs before an ambiguous repeated free-entry identity stopped collection. The full failed attempt and partial trace are retained; allocation counts, physical peak, and full counter qualification remain unknown. An identical repeated entry is not sufficient evidence of a BIOS double-free or leak. Collector breakpoint handling requires investigation before a new capture.
