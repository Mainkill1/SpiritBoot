# Post-END storage context

The unchanged generation2 recorder can finish its measured case before any
read-only context diagnostic starts. The declared runner plan waits for the
successful END, queries the owned VM state and boot-media route, captures the
owned process and clock construction context, then quits that job. The
`-no-shutdown` argument keeps the process available after guest poweroff; a
post-END `shutdown` state does not establish a pause during measurement.
No new fixture, BIOS tracing, global controls, or host setting changes are used.

V343 completed this bounded method on Deck: run
`20261014-213910930-b9f1bd2d20eb42d1bf47b4b897d381a5`, exit0,
1,024 small-HDD reads and 4,096 checks without a fixture failure. The complete
END/EOF read preceded all heavy process/file hashing. The post snapshot was
`running`; the declared final job-owned quit completed and cleanup confirmed
the process stopped. Its clock-context errors were empty. See the
[portable receipt](storage-post-END-native-receipt.json) for the exact freeze,
raw artifact hashes, namespace/file observations, runner assessment and
preserved failed predecessors. This method pilot remains ineligible for A/A.

V341 completed all 1,024 small-HDD reads and 4,096 checks with zero fixture
failures, then failed context qualification. Run
`20261014-213106178-1e2f549e737b49f4a3e6a17801519b6c` and its failed ledger remain
preserved. V342, run `20261014-213506063-103342cf649b4171ae9158621301d58a`,
repeated that observation with additional failed-check receipts. Both plans
stopped on failure; neither supplies accepted timing input.

V342 observed `/usr/lib/libc.so.6` in five mappings with device `00:1a` and
inode `102507`. Both opened-file stats reported device `00:1b`, inode `102507`,
and unchanged size/timestamps. All five `map_files` links named that exact
path. The deepest covering mount was the Btrfs root, device `0:26`,
`subvolid=5`. The readable file SHA256 was
`5f3a99ecdb915ebac00eac33b3e465893948a9d4a974290f1e5bcc24f31dc7ef`.

Linux's maps implementation reads the backing inode's superblock device,
while Btrfs getattr reports its root's anonymous device. These interfaces can
therefore report different devices for this file. The observer checks
the exact Btrfs root mount/device, matching inode, every mapped-file link,
and unchanged regular opened file, retaining both devices. Other filesystem
or unexplained identity mismatches fail. See the primary
[maps implementation](https://github.com/torvalds/linux/blob/v6.12/fs/proc/task_mmu.c#L315)
and [Btrfs getattr](https://github.com/torvalds/linux/blob/v6.12/fs/btrfs/inode.c#L7362).

The receipt also records successful host monotonic reads, observer/target
boot and time namespace identity, target Seccomp status, presence-only
`LD_PRELOAD`/`LD_AUDIT`, the readable libc hash, and actual vDSO mapping metadata.
The target vDSO bytes and constructor branch are not directly observed.
Trusted kernel/libc behavior and no unrecorded intervention remain explicit
controlled-lab construction assumptions. Post observations do not supply
continuous running/media proof or absolute host-clock accuracy. Raw runner
intervention and cache limitations remain unchanged. A fresh predeclared A/A
schedule and reviewed importer are required for conditional relative timing;
P1, private structural counters and physical durability remain unqualified.
