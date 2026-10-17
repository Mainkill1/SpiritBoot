# Final broad XISO release sweep

The exact release64 BIOS `00aa2536dbda14ee851665be98e903c32c9705996832b335bbab72ab81c8ead6` completed two independent Steam Deck OpenGL runs of the frozen 144-leaf, five-group suite. Both runs passed all 149 same-host records with no fixed-field mismatches, no applicable oracle failures, and no functional-hash differences from the prior candidate. Two S3TC metadata records per run remain explicitly non-applicable. The runner's 55 framebuffer mismatches compare Steam Deck OpenGL against a historical Windows reference; the same-host policy records them as informational.

The sum of the 144 two-run leaf means changed from 31544807.372 us to 28992555.945 us, or -8.09%. This is a descriptive whole-suite result rather than attribution to a BIOS path.

The initial short sweep placed one sub-millisecond leaf above the 20% review threshold: `report_query.dma_target_switch`, 625.000 us to 866.375 us. The required follow-up used an ABBA order, 64 warmups, 4,096x fixed work, 16,384 iterations, and about 15.4 to 16.1 seconds of measured work per run. All four outcomes passed. Its prior two-run mean was 948.875 us and its current mean was 967.375 us, a 1.95% change. The original >20% signal is closed as short-sample noise; no leaf remains above the threshold after the sustained check.

`leaf-comparison.csv` preserves every leaf and both raw run means. The evaluation, request, sustained receipt, and sustained request JSON files bind the BIOS, emulator, XISO, fixed plan, host, and run identities.
