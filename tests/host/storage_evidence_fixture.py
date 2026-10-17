"""Small real Git/COFF/file fixtures for migration evidence validation."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import shlex
import sys
from tools.storage_build_evidence import verify_source


def hash_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pe_image(symbols):
    # The synthetic .text has space for the hand-selected fixture addresses.
    # These are format fixtures, never runnable firmware or provenance proof.
    data = bytearray(768)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 60, 128)
    data[128:132] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", data, 132, 0x14c, 1, 0, 768, len(symbols), 224, 0x102)
    struct.pack_into("<H", data, 152, 0x10b)
    struct.pack_into("<III", data, 180, 0x84000000, 4096, 512)
    struct.pack_into("<II", data, 208, 8192, 512)
    data[376:384] = b".text\0\0\0"
    struct.pack_into("<IIII", data, 384, 256, 0x1000, 256, 512)
    struct.pack_into("<I", data, 412, 0x60000020)
    strings = bytearray(b"\0" * 4)
    for address, name in symbols:
        encoded = name.encode("ascii")
        if len(encoded) > 8:
            field = struct.pack("<II", 0, len(strings))
            strings += encoded + b"\0"
        else:
            field = encoded.ljust(8, b"\0")
        data += field + struct.pack("<IhHBB", address - 0x84001000, 1, 32, 2, 0)
    struct.pack_into("<I", strings, 0, len(strings))
    return bytes(data + strings)


def capture_fixture(root, source, manifest, link, symbols):
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "add", "."], check=True)
    manifest["source_tree"] = subprocess.check_output(
        ["git", "-C", str(source), "write-tree"], text=True).strip()
    manifest["source_worktree_sha256"] = verify_source(source, manifest["source_tree"])["worktree_sha256"]
    kernel = root / "xboxkrnl.unstripped.exe"
    records = []
    for line in symbols.splitlines():
        fields = line.split()
        if len(fields) == 3 and len(fields[1]) == 1:
            try:
                records.append((int(fields[0], 16), fields[2]))
            except ValueError:
                pass
    kernel.write_bytes(pe_image(records or [(0x84001000, "_NxDiskDriverEntry@8")]))
    final = root / "xboxkrnl.exe"
    stripped = bytearray(kernel.read_bytes()[:768])
    struct.pack_into("<II", stripped, 140, 0, 0)
    final.write_bytes(stripped)
    flash = root / "flash.bin"
    flash.write_bytes(b"fixture flash bytes, not executable firmware")
    libraries = [token[3:-2] for token in link.split()
                 if token.startswith("lib") and token.endswith(".a")]
    inputs = []
    for name in libraries:
        path = root / ("lib" + name + ".a")
        path.write_bytes(b"!<arch>\n")
        inputs.append("LOAD " + str(path))
    linker_map = root / "storage-kernel.map"
    linker_map.write_text("\n".join(inputs) + "\nOUTPUT(" + str(final) + " pei-i386)\n")
    command_file = root / "link-evidence.txt"
    command_file.write_text(link)
    symbols_file = root / "symbols-evidence.txt"
    symbols_file.write_text(symbols)
    snapshot = root / "storage-linked.exe"
    snapshot.write_bytes(kernel.read_bytes())
    run = root / "storage-link-run.json"
    run.write_text(json.dumps({
        "schema": 1, "exit_code": 0, "cwd": str(root),
        "source_directory": str(source), "source_tree": manifest["source_tree"],
        "source_worktree_sha256": manifest["source_worktree_sha256"],
        "argv": shlex.split(link), "expanded_argv": shlex.split(link),
        "response_files": [], "direct_inputs": [], "output_path": str(final),
        "linked_output": {"path": str(snapshot), "sha256": hash_file(snapshot)},
        "linker_map": {"path": str(linker_map), "sha256": hash_file(linker_map)},
        "resolved_inputs": [{"path": str(root / ("lib" + name + ".a")),
                             "sha256": hash_file(root / ("lib" + name + ".a"))} for name in libraries],
        "transient_lto_inputs": [],
        "synthetic_inputs": [],
    }))
    common = {"schema": 1, "exit_code": 0, "source_directory": str(source),
              "source_tree": manifest["source_tree"],
              "source_worktree_sha256": manifest["source_worktree_sha256"],
              "tools": [{"path": str(Path(sys.executable).resolve()),
                         "sha256": hash_file(sys.executable)}],
              "commands": [["own synthetic format fixture, not an executed production pipeline"]]}
    post = root / "storage-postprocess-run.json"
    post.write_text(json.dumps(dict(common, kind="postprocess",
        inputs=[{"path": str(snapshot), "sha256": hash_file(snapshot)}],
        before_kernel={"path": str(snapshot), "sha256": hash_file(snapshot)},
        after_kernel={"path": str(kernel), "sha256": hash_file(kernel)},
        output={"path": str(final), "sha256": hash_file(kernel)})))
    pack = root / "storage-pack-run.json"
    pack.write_text(json.dumps(dict(common, kind="pack",
        inputs=[{"path": str(final), "sha256": hash_file(final)}],
        kernel={"path": str(final), "sha256": hash_file(final)},
        flash={"path": str(flash), "sha256": hash_file(flash)},
        output={"path": str(flash), "sha256": hash_file(flash)})))
    manifest.update(output_directory=str(root), build_directory=str(root),
                    flash_sha256=hash_file(flash),
                    kernel_unstripped={"path": str(kernel), "sha256": hash_file(kernel)},
                    kernel_final={"path": str(final), "sha256": hash_file(final)},
                    linker_map={"path": str(linker_map), "sha256": hash_file(linker_map)},
                    storage_link_command={"path": str(command_file), "sha256": hash_file(command_file)},
                    storage_link_run={"path": str(run), "sha256": hash_file(run)},
                    storage_postprocess_run={"path": str(post), "sha256": hash_file(post)},
                    storage_pack_run={"path": str(pack), "sha256": hash_file(pack)},
                    storage_symbols={"path": str(symbols_file), "sha256": hash_file(symbols_file)})
    return kernel, flash, linker_map
