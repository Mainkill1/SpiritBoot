# Recompute the two-campaign results

The evidence includes both campaigns' raw serial logs and result/launch metadata, the guest fixture source, and four frozen synthetic test ISO images. It includes no firmware, EEPROM, HDD or game image.

From this evidence directory, using Python 3.11+ and the standard archive tools:

```sh
unzip -q campaign1/results.zip -d campaign1/results
unzip -q campaign2/results.zip -d campaign2/results
tar -xzf campaign1/fixture-sources.tar.gz -C campaign1
unzip -q probe-images.zip -d campaign1
ln -s ../campaign1/fixtures campaign2/fixtures
ln -s ../campaign1/stream-timing.iso campaign2/stream-timing.iso
ln -s ../campaign1/sync-cost.iso campaign2/sync-cost.iso
python average.py --first campaign1 --second campaign2 --output recomputed
```

Each campaign analyzer verifies fixture bytes against launch hashes, BIOS/executable hashes, interactive session, exact enabled/skip sets, complete TAP endings, and each leaf result. The averaging script invokes both analyzers before reading derived CSVs, verifies all 42 unique supplementary trials per campaign, all 40 kernel workloads with expected sample counts and matching semantic checksums, both streaming phases, and all synchronization modes/samples. It checks the identical skip manifests and excludes any leaf failing in either campaign.

The primary arithmetic average takes each campaign's mean over seven measured leaf trials and then averages the two means equally. This equals the pooled fourteen-trial mean because sample counts match. Per-campaign medians and their equal-weight average are also recorded. Supplementary averages use the two campaign medians; timing ratios divide averaged times rather than average ratios.

`run-one.ps1`, `leaf-paired.ps1`, and `paired.ps1` in each campaign directory record how the Windows interactive user-space tests ran. Their lab paths point to the corresponding original stage directories. BIOS order alternates; leaf pair 0 is discarded as pilot/warmup, while all seven supplementary pairs are measured. To rerun elsewhere, supply the separately owned ROMs/MCPX/HDD/EEPROM and update those paths while preserving the recorded 64 MiB/Vulkan configuration, workload images, exclusions, and sequential ordering.
