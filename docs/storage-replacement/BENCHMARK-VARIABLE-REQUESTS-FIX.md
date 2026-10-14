# Preserve exact variable request lengths in performance decisions

The public FATX replay issues unequal read lengths. The analyzer previously
required one integer `bytes_per_operation` and calculated the total by
multiplication. A sequence whose total is not divisible by its request count
cannot satisfy that schema without changing its workload or rounding its bytes.

The case schema now accepts either the existing uniform size or an exact
`operation_bytes` list, with one positive integer per scheduled operation. It
rejects both fields being present. Variable results must provide the actual
completed IOSB byte counts in issue order. The analyzer checks every length and
their exact total; exchanging bytes between requests cannot pass by preserving
the total. Small HDD cases also check that every length matches `request_bytes`.

Four independent host regressions failed on the original analyzer and pass
with this change: a non-divisible variable sequence, equal totals with changed
request lengths, missing evidence/ambiguous specification, and contradictory
actual lengths explicitly supplied for a uniform case. Known evidence cannot
be ignored simply because a case uses the old uniform schema. These fixtures
are invented for validation; they are not measured firmware timings. No
previous frozen schedule or native result has been rewritten, and P1 performance
qualification remains unfinished.

Validation: all 28 comparator host tests passed in 36.896 seconds. The retained
log is `.scratch/pr248-native-baseline/variable-request-host-tests.log` in the
workbench. Firmware measurements and source provenance are separate evidence.
