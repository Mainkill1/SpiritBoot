# Storage medium of the sampled world resource

The preserved Spirit snapshot resolves world handle `0x42c` to a file on
`HarddiskVolume3`, whose mounted filesystem is `Vfatfs` with FATX16 metadata.
This is a hard-disk FATX resource. Its drive letter has not been established.
The generated `E:` fixture therefore matches the broad Spirit medium/filesystem
class, not a verified partition, cache state, file placement or complete workload.
Complex handle `0x1f8` remains of unknown medium.

Spirit's native FILE_OBJECT flags are `0x00040008`: the public
`FO_NO_INTERMEDIATE_BUFFERING` bit is set; `FO_SYNCHRONOUS_IO` and
`FO_ALERTABLE_IO` are clear. Its published flag byte `0x24` independently has
no-intermediate-buffering and opened set, with synchronous/alertable clear.
The sampled handle is therefore asynchronous and requests noncached I/O,
matching the generated fixture's no-intermediate-buffering mode. Other flag
bits are not interpreted. These flags do not establish identical lower caching
or media timing.

The independently written [reader](read_spirit_medium.py) follows only object
metadata using the owned baseline's symbols and structure layouts. Its
[scalar result](spirit-world-medium.json) records these checks:

* The handle entry resolves to an object whose type equals `IoFileObjectType`.
* The file's device equals its VPB's real device, named `HarddiskVolume3`,
  with disk device type and `partmgr` driver.
* The VPB's mounted device has disk-filesystem type and `Vfatfs` driver.
* The mounted extension's volume/storage pointers independently match those
  VPB links. Both sector-size fields are 512; FAT type is 4 (FATX16); volume
  flags are `0x14` (FATX and good).

The reader accepts only the recorded 64 MiB RAM SHA256 and rejects unmapped,
out-of-range or structurally inconsistent metadata. [Provenance](medium-provenance.json)
records the exact owned header/kernel hashes and layout facts; the headers and
binary are not included. [Snapshot metadata](snapshot-metadata.json) separately
records the preserved qcow2 SHA256 and identity reported by the coordinating
agent. RAM, game payloads and firmware bytes remain private and excluded.

Reproduce from the authorized private RAM file:

```sh
python read_spirit_medium.py /private/path/missing-world.bin
python -m unittest test_spirit_medium.py
```

The existing v5 logs provide no nonempty object-name fields or open/create
records that identify the Complex volume. A file-object address, where present,
would not establish the medium without corresponding metadata and an appropriate
layout. Spirit layout offsets were not applied to Complex. No new live capture
or proprietary BIOS disassembly was used for this determination.
