# Conker release64 qualification result

Six uninstrumented release runs formed three alternating pairs on the Windows
runner: off/on, on/off, then off/on. Every run used the same Conker image,
private copy of the same HDD asset, 64 MiB profile, xemu executable, 60-second
CPU window, and frame/flip logger. All six processes completed normally with
complete declared evidence.

The enabled image differs from the product image only by the test-only initial
value of `NxkExperimentalFlags`; that patch forces bit 2 on so unattended runs
exercise direct XDVDFS forwarding. It is not in the firmware lock.

## Observations

The longest frame interval was frame 3 in every run. It is a stable early-boot
stall and is useful exploratory load-progress evidence:

| Pair | Off | On | Enabled difference |
| --- | ---: | ---: | ---: |
| A | 4,131.470 ms | 3,977.012 ms | -154.458 ms (-3.74%) |
| B | 4,065.954 ms | 4,039.559 ms | -26.395 ms (-0.65%) |
| C | 4,048.059 ms | 4,027.514 ms | -20.545 ms (-0.51%) |
| Mean | 4,081.828 ms | 4,014.695 ms | -67.133 ms (-1.64%) |

The enabled arm produced more frames in the first five-second flip window in
all three pairs: 47 versus 37, 43 versus 41, and 44 versus 42. The mean is
44.67 versus 40.00 (+11.67%). Total logged flip-window output was effectively
identical: 5,867.33 versus 5,866.33 frames (+0.017%).

The 60-second process CPU mean increased from 110.8125 to 112.0417 seconds
(+1.11%). That may represent ordinary host variation or slightly more guest
progress; this experiment does not attribute it. There is no material overall
frame-rate change.

## Decision

The three pairs consistently support a small improvement in the stable early
boot stall, while the CPU and whole-run frame measures are inconclusive. This
is sufficient to retain direct forwarding as an explicit advanced experiment,
because the measured request census shows that it removes a child IRP, a
duplicate MDL pin/unpin, and an internal wait from 89.98% of observed file
reads. It is not sufficient to enable the path by default or claim a general
Conker load-time percentage.

The next acceptance step is operator-controlled gameplay with the option on,
followed by a broader optical-load sample. Any data corruption, guest failure,
or repeated load regression rejects the experiment without affecting default
behavior.

`summary.json` contains the machine-readable values and exact run IDs.
`summarize.py` rebuilds it from each retained `result.json`,
`performance.json`, `guest-frames.log`, and `guest-flips.log`.
