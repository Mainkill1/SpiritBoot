#!/usr/bin/env python3
"""Record owned kernel section metadata and reviewed permanent-MM bounds.

Run with BUILD_JSON OUTPUT_JSON. The source/build must remain present beside
the receipt. Read section headers and source only; do not copy image payloads.
"""
import hashlib
import json
from pathlib import Path
import re
import struct
import sys


receipt_path = Path(sys.argv[1]).resolve()
receipt = json.loads(receipt_path.read_text())
work = receipt_path.parent / Path(receipt["source_directory"]).parent.name
source = work / "source"
build = work / "build"
kernel_path = build / "ntoskrnl/xboxkrnl.exe"
kernel = kernel_path.read_bytes()
pe = struct.unpack_from("<I", kernel, 0x3C)[0]
assert kernel[:2] == b"MZ" and kernel[pe:pe + 4] == b"PE\0\0"
count, optional_size = struct.unpack_from("<H", kernel, pe + 6)[0], struct.unpack_from("<H", kernel, pe + 20)[0]
table = pe + 24 + optional_size
sections = []
for index in range(count):
    offset = table + index * 40
    name = kernel[offset:offset + 8].rstrip(b"\0").decode("ascii")
    virtual_size, rva, raw_size = struct.unpack_from("<III", kernel, offset + 8)
    sections.append({"name": name, "virtual_size": virtual_size,
                     "rva": rva, "raw_size": raw_size,
                     "rounded_virtual_pages": (virtual_size + 4095) // 4096})

files = ["ntoskrnl/xb/mm/pagesupply.c", "ntoskrnl/xb/mm/pool.c",
         "ntoskrnl/xb/mm/poolpages.c", "ntoskrnl/xb/mm/mm.h",
         "ntoskrnl/mm/ARM3/i386/init.c", "ntoskrnl/mm/ARM3/procsup.c",
         "ntoskrnl/ps/thread.c", "ntoskrnl/ps/kill.c", "ntoskrnl/ps/psmgr.c",
         "ntoskrnl/xb/threadview.c", "ntoskrnl/xb/procobj.c",
         "sdk/include/ndk/ketypes.h", "ntoskrnl/xb/mm/sysva.c",
         "ntoskrnl/mm/ARM3/mmsup.c", "ntoskrnl/xb/mm/iospace.c",
         "ntoskrnl/xb/mm/api.c"]
hashes = {name: hashlib.sha256((source / name).read_bytes()).hexdigest()
          for name in files}
mm = (source / "ntoskrnl/xb/mm/mm.h").read_text()
window = int(re.search(r"#define NXK_POOL_WINDOW_PAGES\s+(\d+)", mm)[1])
assert window == 4096
pool = (source / "ntoskrnl/xb/mm/pool.c").read_text()
classes = [int(value) for value in re.search(r"NxpClassSize\[\] = \{([^}]+)", pool)[1].replace(",", " ").split()]
assert classes == [32, 64, 128, 256, 272, 320, 512, 1024, 2048]
metadata = []
for ram in (64, 128):
    frames = ram * 1024 * 1024 // 4096
    for checked in (False, True):
        supply = frames * 6
        run = window * 2
        bitmap = window // 8
        attribution = window * 4 if checked else 0
        pool_bytes = run + bitmap + attribution
        metadata.append({"memory_mib": ram, "checked": checked,
                         "supply_links_owner_bytes": frames * 4,
                         "supply_pin_bytes": frames * 2,
                         "supply_pages": (supply + 4095) // 4096,
                         "pool_run_bytes": run, "pool_used_bitmap_bytes": bitmap,
                         "pool_checked_attribution_bytes": attribution,
                         "pool_metadata_pages": (pool_bytes + 4095) // 4096,
                         "total_boot_carve_pages": (supply + 4095) // 4096 + (pool_bytes + 4095) // 4096})
result = {"schema": 1, "source_tree": receipt["source_tree"],
          "release64_rom_sha256": receipt["flash_sha256"],
          "build_receipt_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
          "kernel_file_sha256": hashlib.sha256(kernel).hexdigest(),
          "pool_audit": receipt["pool_audit"], "rom_kernel": receipt["rom_kernel"],
          "scope": "Section metadata and source-derived carve bounds; not a runtime PFN census. ROM-backed sections do not each consume their rounded size in RAM.",
          "reviewed_source_sha256": hashes, "sections": sections,
          "pool_window_pages": window, "pool_classes": classes,
          "pool_page_state_image_bytes": window,
          "pool_class_map_image_bytes": 257,
          "pool_free_heads_image_bytes_shared": len(classes) * 4,
          "pool_free_heads_image_bytes_reserved": len(classes) * 8,
          "thread_registry_image_bytes": 32 * 8 + 4 + 4,
          "public_thread_view_per_native_object_bytes": 320,
          "thread_registry_link_per_native_object_bytes": 8,
          "public_process_image_bytes": 28,
          "xbox_dead_stack_cache_limit": 0,
          "arm3_pfn_alias_backing_data_pages": 1,
          "boot_carve_source_bounds": metadata}
Path(sys.argv[2]).write_text(json.dumps(result, indent=2) + "\n")
