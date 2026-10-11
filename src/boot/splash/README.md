# SpiritBoot splash asset

`spiritboot-splash.png` is the cleaned transparent source used for the static
boot logo. The checked-in Roswell patch carries a 256x256, 16-color bitmap for
the existing bootvid renderer. Regenerate that bitmap with:

```sh
python3 tools/build_boot_splash.py \
  src/boot/splash/spiritboot-splash.png \
  reconstruction/work-*/source/ntoskrnl/inbv/resources/spiritboot.bmp
```

The renderer and asset are separate from the three-second settings deadline,
controller discovery, and EEPROM transaction. A later animation can use a
small sequence of indexed frames without changing those contracts. Text is the
fallback path if the image cannot be displayed.

## Measured storage

The checked-in transparent 256x256 PNG is 45,819 bytes. The deterministic
bootvid conversion is a 32,886-byte, 4-bit indexed Windows bitmap. In the exact
64 MiB release build, adding this bitmap increased the compressed kernel by
4,168 bytes. The resource lives in the discardable `.rsrc`/INIT span, so it does
not add title-time resident RAM.

The indexed bitmap is the compatibility fallback for the first release. A
future NV2A presentation experiment should compare it at the actual boot-screen
size against both of these candidates:

- a compact triangle mesh using vertex colors for the fox, eyes and cyan rim,
  with a small texture only if the measured result needs it;
- DXT5 texture data, which occupies 16 KiB at 128x128 or 64 KiB at 256x256,
  before container and command data.

That comparison must include ROM bytes, temporary RAM, render setup, visual
quality and teardown. Original Xbox shaders cannot consume a modern procedural
GLSL implementation directly. Keep the artwork in ROM and reclaim every
temporary rendering allocation before title launch.
