# Windows PowerShell5.1 pipe-receipt parsing

The Windows clock-context V3 diagnostic stopped before clock sampling because
`Read-Pr248Fields` used the ambiguous two-argument `String.Split` call.
PowerShell5.1 selected the `StringSplitOptions` overload and rejected value2;
.NET Framework exposes only None and RemoveEmptyEntries. Portable PS7 checks
had passed and did not qualify this native compatibility boundary.

The parser now finds the first equals character and takes the two substrings.
It preserves subsequent equals characters, empty values, whitespace and ordinal
key identity. Blank lines remain ignored, and missing separators or duplicate
keys retain their bounded rejection. No desktop, SID, session, ancestry, source,
hash, QMP or lifetime check is relaxed.

Focused host checks execute the production parser on command-line values with
multiple equals and malformed/duplicate records. A separate minimal Framework
overload-surface double reproduces the ambiguity; it is a diagnostic model,
not native PS5.1 execution. The shared guard's remaining clock-used helpers
were reviewed for Framework-era API availability. Actual Windows CIM/process
mapping, live handle/provider behavior and native PS5.1 qualification remain
separate evidence gates.

The retained V3 failure is run
`20261014-202610884-f91b8f8953d145b8887963388e833e1d`, with actual
PowerShell `5.1.19041.6456`. It is INCONCLUSIVE and has no clock samples.
The preceding V2 path-comparison failure is also retained. A new V4 identity
pins the corrected shared module; neither this source fix nor host checks imply
performance, physical durability or full-driver qualification.

The corrected V4 native run
`20261014-203205963-0a562225ed684a64a2d89437fa8e7fc0` completed under the same
PowerShell `5.1.19041.6456`, with the actual Codex desktop, protected receipts,
owned process/lifetime checks and both managed running-state queries. It
collected two successful QPF/QPC samples and the complete 50-sample/100-marker
fixture, then stopped and finalized complete evidence. This closes the
observed PS5.1 parser compatibility failure on that bounded route. The
[clock-context receipt](windows-clock-context-native-receipt.json) retains the
measurement limits: count quantum and conversion arithmetic are separate from
provider precision, continuous VM-state proof and performance acceptance.
