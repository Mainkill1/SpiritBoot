# Windows fixed-media DVD preparation

The separately named `dvd-fixed-windows-guard.ps1` reuses the owned desktop,
pipe ancestry, process lifetime, exact argv/config/input and readonly route
checks from the reviewed Windows guard. Both observations require the same
`storage-perf.iso` wrapper. `target.iso` supplies original released-image
provenance only. The fixed variant records `fixed_media=true`,
`media_method=fixed-wrapper` and `exact_original_media_parity=false`; it does
not request or accept a managed media-change receipt.

Eight portable PowerShell7 tests pass. A fixed-media main-method test fails
against the unchanged earlier swap guard and passes against this variant.
The tests use invented process/pipe/recipe records and do not qualify native
PowerShell5.1. The short ordinary `-Command` loader hashes and executes the
same packaged source bytes, changes no execution policy and opens no QMP
socket; the runner owns typed query recipes and final quit.

The proposed Windows36 cohort keeps the qualified V27 desktop launcher,
published64 ROM, generation2 suite and fixed-wrapper DVD recorder unchanged.
The DVD control plan can overlap measurement and is functional-only. Native
Windows qualification remains pending for this new route. Actual live CWD,
NTFS file identity, driver-memory cache, original-media parity, physical
durability and private structural counts remain unproved. The existing
Windows cache report and intervention fields must remain visible; this
packet supplies no performance or P1 approval.
