# Windows native qualification

The secondary host is the user-approved Ryzen 9 6900HX at `10.0.7.1`.
Graphical fixtures run through the protected PowerShell pipe in the logged-in
Codex desktop. HTTP controls the existing runner; SSH was used for the separate
archive maintenance operation only.

## Capacity recovery

Completed V1 packages exhausted the test volume. Before new fixtures, a reviewed
operator script verified 624 immutable archived files and replaced 622 identical
`xemu.exe`/`storage-perf.iso` copies with hard links to two existing anchors.
Every original path and byte remained present. Mutable disk images, EEPROM,
results, reference files, firmware, configuration and launchers were excluded.

The operation recovered **15,427,457,024 bytes**, increasing free capacity from
1,075,003,392 to 16,502,460,416 bytes. The isolated PowerShell process used
`RemoteSigned`; all five persistent policy scopes were `Undefined` before and
after. No emulator was started or stopped and no test guard changed.

| Evidence | SHA256 |
| --- | --- |
| Reviewed operator script | `026d5b0c5fd609e11873727146660e218abaf803496c53e41958114d83af2d13` |
| Exact archive plan | `932b29ae047757aaf02de2ed73405211e4bfdab4509a8501b5714fbbeeb31802` |
| Full 626-row apply log | `7fc6ab5fd42b4903eddb5679a7c1acb7a4cf978a178e9664355716fdf9568a2e` |
| Bounded recovery summary | `463c73d2f0232ae7cbcbc217e1e9599518d825125a160b3cf542047dbb6dfead` |

The local apply log is preserved at
`.scratch/pr248-operator-recovery/win-apply.jsonl` in the workbench.
This maintenance evidence establishes available capacity; it provides no
firmware correctness or performance qualification.

## Frozen V23 test scope

The separately reviewed parent caller uses the original V23 plan, parser,
launcher, requests and evidence grading without changing their bytes. It binds
the completed recovery receipt before submitting any Windows fixture through
the normal HTTP runner. Each declared job has private HDD/EEPROM state.

| Input | SHA256 |
| --- | --- |
| V23 plan | `968253699409067adb9414de3c7cdeecdd3353269f7f394dbe2b2a495b498511` |
| V23 77-file manifest | `2d5761b35ccd45b53e80135903e7f83542e539ba3e2ed83eb78b5da76cbc0a7e` |
| V23 parser | `8bd1794f7102ba18a9db17db6c4226f51b3b08a5761c70be1c0cdc271272b742` |
| Desktop pipe launcher | `366531cbfcdc4d2f81b4033a6d56c669b5ff1d051c0177fc826b444655ff090f` |
| Exact published reference flash | `c630d22f2353d3898024d510f0b402b64bccdb331781fe7885389f73d6200853` |

The four declared jobs cover poison-verified small reads, the public query
matrix, an internal owned graphical-child timeout, and normal reads after that
timeout. The original results are retained in the
[V23 native receipt](windows-v23-native-receipt.json):

| Job | Actual run | Outcome |
| --- | --- | --- |
| Normal small reads | `20261014-162149765-b17ace18274047d88559b943e6b6e47a` | 1,024 exact poison-verified reads, 4 MiB, 4,096 assertions; bounded integrity PASS |
| Public queries | `20261014-162251572-a7fa3cb5a2dd4e35b056ed44c6d9cf7b` | 210 calls; complete public observations, not normative parity |
| Owned timeout | `20261014-162325708-a52e392832b24f58ae9aaee08b090691` | Qualification FAILED: deadline reason lost; original failed result preserved |
| Reads after timeout | No V23 run | Stopped after the failure |

The timeout must report the
specific server deadline and prove the owned job has no remaining children;
arbitrary crashes or outer runner termination cannot qualify it. The failure
led to a [client EOF correction](WINDOWS-PIPE-EOF-FIX.md); its new V27 tests use
fresh identities and keep the original strict grading.

## Corrected V27 native results

The [independent caller review](windows-v27-caller-review.json) verified the
43-file freeze and clean launcher build. All four new jobs passed their declared
bounded scope. Full raw outcomes were written before grading and remain archived.
The [native receipt](windows-v27-native-receipt.json) binds their actual inputs,
serial results and cleanup evidence.

| Job | Actual run | Outcome |
| --- | --- | --- |
| Normal small reads | `20261014-164514066-8083861d1f224f40bcefa285c873ac81` | 1,024 exact reads/4 MiB, 4,096 assertions; integrity PASS |
| Public queries | `20261014-164525285-17dfb7728e96485d82abf5238c672c29` | All 210 calls observed |
| Owned timeout | `20261014-164534904-a0eb64328b094dbeb127b56168c7fd39` | Exact 120-second deadline preserved, failed runner outcome/exit 1 retained, zero owned descendants |
| Reads after timeout | `20261014-164741936-bbc6a31c90d64dddaba121e161e6ffd6` | Another 1,024 exact reads/4 MiB; recovery PASS |

All runs verified the logged-in Codex/session 1/WinSta0/Default desktop pipe.
The V27 plan SHA256 is
`49b242c305dddf50fa1746a56957026cd49ce422a61036b5b3d037969e0fc13b`;
manifest `75a8bd4a2d2c0e1ab5846a899cdadc87fb62dfa64c060973ec63af35c60cc8d2`;
launcher `a61757b17e2da594607e82d3f8595b1faba61c3ed4d1b6276373e39b15613b79`.

These are integrity, public-observation and lifetime checks. P1 timing,
controlled-cache comparisons, actual device flush/persistence and the full
replacement class driver remain separate unfinished gates.
