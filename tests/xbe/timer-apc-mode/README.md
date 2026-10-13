# Timer APC mode contract

The synthetic guest arms a 50 ms timer, waits on an unsignaled event with a
500 ms timeout, and observes the public API status and callback effects.
It does not inspect proprietary code or depend on wall-clock thresholds.

Cases:

- UserMode APC during an alertable wait: STATUS_USER_APC, exactly one callback.
- UserMode APC during a nonalertable wait: STATUS_TIMEOUT and no callback;
  a following zero-time alertable wait dispatches it and returns STATUS_USER_APC.
- Cancel a queued UserMode timer APC before entering an alertable wait: no callback
  and STATUS_TIMEOUT from the following zero-time wait.
- KernelMode APC during an alertable wait: callback runs, but the event wait
  completes with STATUS_TIMEOUT.

Delivered callbacks must receive the original context and execute on the setting
thread. Elapsed milliseconds are diagnostic only. The TAP stream includes all
assertions, a plan, and the failure count before shutdown.

Build with the pinned nxdk fixture or an existing nxdk checkout:

```sh
PATH=/home/codex/src/nxdk/bin:$PATH make NXDK_DIR=/home/codex/src/nxdk
```

Output: `timer-apc-mode.iso` and `bin/default.xbe`.
