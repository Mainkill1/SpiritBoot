#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
output=${1:?pass an isolated output directory}
mkdir -p "$output"
cc -std=c11 -D_GNU_SOURCE -Wall -Wextra -Wno-pointer-to-int-cast \
   -I"$root/include" "$root/persistence.c" -o "$output/persistence-host"
"$output/persistence-host"
cc -std=c11 -Wall -Wextra -I"$root/include" "$root/shutdown.c" -o "$output/shutdown-host"
"$output/shutdown-host"

source_root=$(CDPATH= cd -- "$root/../../.." && pwd)
cc -std=c11 -D_GNU_SOURCE -Wall -Wextra -I"$root/include/ide" -I"$source_root/sdk/include" \
   "$root/ide.c" -o "$output/ide-host"
"$output/ide-host"
cc -std=c11 -Wall -Wextra -I"$root/include" -I"$root/include/ide" \
   "$root/power.c" -o "$output/power-host"
"$output/power-host"
python3 "$root/extract-pins.py" "$output/pins-actual.inc"
cc -std=c11 -Wall -Wextra -I"$root/include" -I"$output" -I"$source_root/ntoskrnl/xb/mm" \
   "$root/pins.c" -o "$output/pins-host"
"$output/pins-host"
