7 alternating pairs; ticks per iteration. Negative percentage means less time. All raw samples and empty-loop overhead retained; no overhead subtraction.

| Workload | Baseline median | Candidate median | Paired change | Classification |
|---|---:|---:|---:|---|
| empty | 0.748 | 0.829 | 0.28% | timing inconclusive |
| pin-1 | 833.476 | 6.067 | -99.27% | timing improvement |
| pin-16 | 870.442 | 51.436 | -93.90% | timing improvement |
| pin-64 | 1096.840 | 188.540 | -81.76% | timing improvement |
| pin-65 | 1028.170 | 928.080 | -11.28% | timing inconclusive |
| pin-256 | 1460.375 | 1432.875 | -4.84% | timing inconclusive |
| pin-4096 | 12623.750 | 11830.000 | -1.86% | timing inconclusive |
| pin-reject-0 | 397.752 | 1.910 | -99.52% | timing improvement |
| pin-reject-32 | 419.860 | 39.060 | -89.66% | timing improvement |
| pin-reject-64 | 465.060 | 75.530 | -83.76% | timing improvement |
| pin-reject-65 | 473.650 | 475.840 | -0.67% | timing inconclusive |
| pool-1 | 15.703 | 14.141 | -8.16% | timing inconclusive |
| pool-16 | 69.188 | 48.688 | -10.09% | timing inconclusive |
| pool-256 | 752.250 | 670.750 | -13.82% | timing inconclusive |
| pool-1024 | 2857.000 | 2289.000 | -17.24% | timing inconclusive |
| pool-fragmented-fail-4 | 890.812 | 479.375 | -44.45% | timing inconclusive |
| sysva-1 | 70.188 | 70.656 | 1.53% | timing inconclusive |
| sysva-16 | 217.625 | 192.625 | -6.83% | timing inconclusive |
| sysva-1024 | 11249.000 | 11861.000 | 0.41% | timing inconclusive |
| sysva-1025 | 10558.000 | 9967.000 | -1.19% | timing inconclusive |
| sysva-4096 | 50337.000 | 49648.000 | -5.23% | timing inconclusive |
| object-cold-64 | 1271.000 | 1282.000 | 0.99% | timing inconclusive |
| object-warm-1 | 7.398 | 5.963 | -11.02% | timing inconclusive |
| object-warm-8 | 46.094 | 35.719 | -22.51% | timing inconclusive |
| object-warm-64 | 372.125 | 322.625 | -17.83% | timing inconclusive |
| modexp-1-e1-odd | 145.672 | 148.094 | -4.15% | timing inconclusive |
| modexp-1-e65537-odd | 158.125 | 165.094 | 6.04% | timing inconclusive |
| modexp-2-e3-even | 348.875 | 297.875 | -17.23% | timing inconclusive |
| modexp-32-e3-odd | 8604.500 | 7432.500 | -8.44% | timing inconclusive |
| modexp-64-e65537-odd | 32763.000 | 33340.000 | -5.41% | timing inconclusive |
| modexp-512-e1-odd | 1389393.000 | 1289323.000 | -3.69% | timing inconclusive |
| sha-0 | 41.047 | 48.418 | 17.56% | timing inconclusive |
| sha-1 | 42.996 | 47.084 | 11.58% | timing inconclusive |
| sha-63 | 54.547 | 66.996 | 23.82% | timing inconclusive |
| sha-65 | 54.953 | 66.355 | 22.74% | timing inconclusive |
| sha-4096 | 941.875 | 999.750 | 6.14% | timing inconclusive |
| sha-1MiB | 281984.000 | 302719.000 | 12.03% | timing inconclusive |
| des-block | 275.570 | 293.398 | -1.96% | timing inconclusive |
| des3-block | 957.734 | 823.156 | -4.47% | timing inconclusive |
| des-cbc-4096 | 143740.000 | 134958.000 | 0.53% | timing inconclusive |
| des3-cbc-4096 | 416095.000 | 428662.000 | 3.13% | timing inconclusive |
