# File-backed emulator media policy

SpiritBoot's build tool defaults to `emulator-file-media` for its xemu target:

```sh
python3 scripts/build-firmware.py --source /path/to/pinned/roswell \
  --output artifacts/firmware-release --media-policy emulator-file-media
```

This selects Roswell's `XBOX_EMULATOR_FILE_MEDIA` CMake option. Roswell itself
leaves that option off by default. For the original certificate behavior:

```sh
python3 scripts/build-firmware.py --source /path/to/pinned/roswell \
  --output artifacts/firmware-strict --media-policy strict
```

Use strict builds for physical optical-device qualification. This switch does
not implement DVD authentication or make unsupported device controls succeed.

## Loaded metadata

A DVD-only XBE certificate receives the hard-disk media bit in its loaded
compatibility view (`2` becomes `3`). Other declared media types and upper flags
are preserved. This allows title initialization to treat file-backed emulator
media as a supported nonexclusive media source. It applies to the format and
profile, with no title ID checks.

The loader validates the certificate's address, declared length, mandatory key
fields, and separation from the image header before copying or changing it. It
retains the complete original certificate for provenance and derives title keys
from those original bytes. Only the allowed-media field in the loaded view is
changed; the source XBE and all other certificate bytes remain unchanged.
Allocation failure rejects the load before altering metadata or title keys.

`build.json` records `media_policy` and the explicit CMake command. Checked
firmware also reports original/effective media masks once per image load.
Existing release 0.95 remains immutable and retains its original behavior.

## Verification

The production-path host fixture compiles the actual loader policy and title-key
call boundary in both modes. It checks DVD-only and mixed media, unknown upper
flags, original-certificate ownership, original key inputs, malformed/truncated
ranges, header overlap, allocation failure, and allocation balance.

Native title startup is qualified separately. A working title on another BIOS
is not proof that a particular optical device control is supported, because that
BIOS may expose different loaded media metadata.
