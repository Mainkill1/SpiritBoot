#!/usr/bin/env bash
set -euo pipefail
mkdir -p review/target/gcc
i686-w64-mingw32-gcc --version > review/target/gcc/compiler.txt
flags=(-DD3D_UMD_INTERFACE_VERSION=0x000C -DDBG=0 -DDLL_EXPORT_VERSION=0x502 -DDXGKDDI_INTERFACE_VERSION=0x1052 -DDriverEntry=AtapiDriverEntry -DMINGW_HAS_SECURE_API=1 -DSARCH_XBOX -DUSE_COMPILER_EXCEPTIONS -DWINVER=0x502 -DXBOX_RAM_MIB=64 -DXB_EMULATOR_FILE_MEDIA=1 -D_CRT_SUPPRESS_RESTRICT -D_GLIBCXX_HAVE_BROKEN_VSWPRINTF -D_M_IX86 -D_NEW_DELETE_OPERATORS_ -D_NTHALDLL_ -D_NTHAL_ -D_NTOSKRNL_ -D_NTSYSTEM_ -D_SETUPAPI_VER=0x502 -D_USE_32BIT_TIME_T -D_USE_PSEH3=1 -D_WIN32_IE=0x603 -D_WIN32_WINDOWS=0x502 -D_WIN32_WINNT=0x502 -D_X86_ -D__REACTOS__ -D__i386__ -Di386 -std=gnu99 -ffile-prefix-map=/baseline/source= -ffile-prefix-map=../source= -pipe -fms-extensions -fno-strict-aliasing -fno-common -fno-asynchronous-unwind-tables -fno-unwind-tables -mlong-double-64 -nostdinc -fno-aggressive-loop-optimizations -fno-builtin-acosf -fno-builtin-acosl -fno-builtin-asinf -fno-builtin-asinl -fno-builtin-atan2f -fno-builtin-atan2l -fno-builtin-atanf -fno-builtin-atanl -fno-builtin-ceilf -fno-builtin-ceill -fno-builtin-coshf -fno-builtin-coshl -fno-builtin-cosf -fno-builtin-cosl -fno-builtin-expf -fno-builtin-expl -fno-builtin-fabsf -fno-builtin-fabsl -fno-builtin-floorf -fno-builtin-floorl -fno-builtin-fmodf -fno-builtin-fmodl -fno-builtin-frexpf -fno-builtin-frexpl -fno-builtin-hypotf -fno-builtin-hypotl -fno-builtin-ldexpf -fno-builtin-ldexpl -fno-builtin-logf -fno-builtin-logl -fno-builtin-log10f -fno-builtin-log10l -fno-builtin-modff -fno-builtin-modfl -fno-builtin-powf -fno-builtin-powl -fno-builtin-sinhf -fno-builtin-sinhl -fno-builtin-sinf -fno-builtin-sinl -fno-builtin-sqrtf -fno-builtin-sqrtl -fno-builtin-tanhf -fno-builtin-tanhl -fno-builtin-tanf -fno-builtin-tanl -fno-builtin-feraiseexcept -fno-builtin-feupdateenv -fno-builtin-ceil -fno-builtin-cos -fno-builtin-floor -fno-builtin-pow -fno-builtin-sin -fno-builtin-sincos -fno-builtin-sqrt -fno-builtin-erf -fno-builtin-erff -fno-builtin-execv -fno-builtin-execve -fno-builtin-execvp -march=pentium -mtune=generic -Wall -Wpointer-arith -Wno-char-subscripts -Wno-multichar -Wno-unused-value -Wno-unused-const-variable -Wno-unused-local-typedefs -Wno-deprecated -Wno-unused-result -Wno-format -Wno-maybe-uninitialized -Wno-nonnull-compare -Wno-unknown-pragmas -Wno-unused-variable -Wno-unused-but-set-variable -Wno-unused-function -Wno-unused-label -Wno-array-bounds -Os -DNDEBUG= -ffunction-sections -flto -ffat-lto-objects -fno-optimize-sibling-calls -fno-omit-frame-pointer -mstackrealign -mpreferred-stack-boundary=3 -fno-set-stack-executable -momit-leaf-frame-pointer -fno-lto -Werror)
i686-w64-mingw32-gcc "${flags[@]}" -c inputs/declarations/native-assertions.c -o review/target/gcc/native-250.o
extra=(-std=c11 -ffreestanding -fno-builtin -Isource/tests/target/native_packet -Iinputs/declarations -Isource/drivers/storage/class/nxstorage -include source/tests/host/nxstorage/packet_native_platform.h)
i686-w64-mingw32-gcc "${flags[@]}" "${extra[@]}" -c source/tests/host/nxstorage/packet_native_assertions.c -o review/target/gcc/packet-assert.o
i686-w64-mingw32-gcc "${flags[@]}" "${extra[@]}" -c source/drivers/storage/class/nxstorage/native_packet.c -o review/target/gcc/packet.o
for object in review/target/gcc/native-250.o review/target/gcc/packet-assert.o review/target/gcc/packet.o; do
    i686-w64-mingw32-nm -u "$object" > "$object.undefined"
    i686-w64-mingw32-objdump -h "$object" > "$object.sections"
done
[ ! -s review/target/gcc/native-250.o.undefined ]
[ ! -s review/target/gcc/packet-assert.o.undefined ]
python3 - <<'CHECK'
from pathlib import Path
expected='U _IoReuseIrp@8'
actual=Path('review/target/gcc/packet.o.undefined').read_text().strip()
assert actual==expected,actual
for p in ['native-250.o','packet-assert.o']:
    lines=Path('review/target/gcc/'+p+'.sections').read_text().splitlines()
    for name in ['.text','.data','.bss']:
        sizes=[int(line.split()[2],16) for line in lines if len(line.split())>2 and line.split()[1]==name]
        assert sizes==[0],(p,name,sizes)
print('PASS unchanged 250 + measured SRB/width assertions; zero code/data/bss assertion objects; packet only imports IoReuseIrp')
CHECK
