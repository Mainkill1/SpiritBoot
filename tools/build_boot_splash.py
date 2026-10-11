#!/usr/bin/env python3
"""Convert the SpiritBoot splash PNG to bootvid's 4-bit Windows BMP."""

import argparse
from pathlib import Path
import struct

try:
    from PIL import Image
except ImportError as error:  # Asset-authoring tool; firmware builds use the checked-in BMP.
    raise SystemExit("Pillow is required to regenerate the splash bitmap") from error


def write_bmp(source: Path, output: Path, width: int, height: int) -> None:
    image = Image.open(source).convert("RGBA")
    image = image.resize((width, height), Image.Resampling.LANCZOS)
    background = Image.new("RGB", image.size, (0, 0, 0))
    background.paste(image, mask=image.getchannel("A"))
    indexed = background.quantize(
        colors=16,
        method=Image.Quantize.MAXCOVERAGE,
        dither=Image.Dither.FLOYDSTEINBERG,
    )

    palette = [tuple(indexed.getpalette()[i:i + 3]) for i in range(0, 48, 3)]
    black = min(range(16), key=lambda i: sum(component * component
                                             for component in palette[i]))
    white = min(
        (i for i in range(16) if i != black),
        key=lambda i: sum((255 - component) * (255 - component)
                          for component in palette[i]),
    )
    # bootvid's named colors are palette indices. Keep the background at 0
    # and reserve 15 for legible white text over the custom image.
    remap = [black]
    remap.extend(i for i in range(16) if i not in (black, white))
    remap.append(white)
    inverse = [0] * 16
    for new, old in enumerate(remap):
        inverse[old] = new
    palette = [palette[old] for old in remap]

    indices = indexed.tobytes()
    row_bytes = ((width + 1) // 2 + 3) & ~3
    pixels = bytearray()
    for y in range(height - 1, -1, -1):
        row = indices[y * width:(y + 1) * width]
        packed = bytearray()
        for x in range(0, width, 2):
            high = inverse[row[x]]
            low = inverse[row[x + 1]] if x + 1 < width else 0
            packed.append((high << 4) | low)
        packed.extend(b"\0" * (row_bytes - len(packed)))
        pixels.extend(packed)

    dib_size = 40
    pixel_offset = 14 + dib_size + 16 * 4
    file_size = pixel_offset + len(pixels)
    header = struct.pack("<2sIHHI", b"BM", file_size, 0, 0, pixel_offset)
    dib = struct.pack("<IiiHHIIiiII", dib_size, width, height, 1, 4, 0,
                      len(pixels), 3780, 3780, 16, 16)
    colors = b"".join(struct.pack("<BBBB", blue, green, red, 0)
                      for red, green, blue in palette)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(header + dib + colors + pixels)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--width", type=int, default=256)
    parser.add_argument("--height", type=int, default=256)
    args = parser.parse_args()
    if not (1 <= args.width <= 640 and 1 <= args.height <= 480):
        raise SystemExit("dimensions must fit the 640x480 boot surface")
    write_bmp(args.source, args.output, args.width, args.height)


if __name__ == "__main__":
    main()
