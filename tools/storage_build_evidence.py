"""Bind the storage preflight to real source, COFF, map and flash artifacts.

The result is reproducible engineering evidence, not a source-rights verdict.
PE/COFF layout follows the public Microsoft PE-format specification. Link map
records follow GNU ld; missing transient LTO objects remain explicit limitations.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import struct
import subprocess


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(source, *args, input=None):
    try:
        return subprocess.check_output(
            ["git", "-c", f"safe.directory={source}", "-C", str(source), *args],
            stderr=subprocess.PIPE, input=input)
    except subprocess.CalledProcessError as error:
        raise ValueError("cannot validate assembled Git source identity") from error


def verify_source(source, expected, expected_worktree=None):
    """Verify canonical Git identity and separately hash exact checkout bytes."""
    source = Path(source).resolve()
    if not re.fullmatch(r"[0-9a-f]{40}", str(expected)):
        raise ValueError("missing source tree identity")
    if Path(git(source, "rev-parse", "--show-toplevel").decode().strip()).resolve() != source:
        raise ValueError("source_directory must be the assembled repository root")
    if git(source, "write-tree").decode().strip() != expected:
        raise ValueError("assembled indexed source tree differs from build evidence")
    count = 0
    raw_tree = hashlib.sha256()
    normalized = []
    for record in git(source, "ls-files", "--stage", "-z").split(b"\0"):
        if not record:
            continue
        header, relative = record.split(b"\t", 1)
        mode, oid, stage = header.split()
        if stage != b"0" or mode not in (b"100644", b"100755", b"120000"):
            raise ValueError("unsupported or conflicted source index entry")
        file = source / os.fsdecode(relative)
        if mode == b"120000":
            if not file.is_symlink() or not file.resolve().is_relative_to(source):
                raise ValueError("source link escapes assembled source")
            data = os.fsencode(os.readlink(file))
        else:
            if file.is_symlink():
                raise ValueError("tracked regular source was replaced by a link")
            data = file.read_bytes()
        actual = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        if actual != oid.decode():
            # Git's explicit eol attributes legitimately produce CRLF bytes
            # from LF indexed blobs. Validate their canonical object as well
            # as preserving the exact bytes that the compiler saw.
            if b'\n' in relative or b'\r' in relative or mode == b'120000':
                raise ValueError("unsupported source normalization/path")
            normalized.append((relative, oid))
        raw_tree.update(mode + b'\0' + relative + b'\0' + str(len(data)).encode() + b'\0')
        raw_tree.update(hashlib.sha256(data).digest())
        count += 1
    if normalized:
        hashes = git(source, "hash-object", "--stdin-paths",
                     input=b'\n'.join(path for path, _ in normalized)+b'\n').splitlines()
        if len(hashes) != len(normalized):
            raise ValueError("cannot normalize all indexed source inputs")
        for actual, (path, expected_oid) in zip(hashes, normalized):
            if actual != expected_oid:
                raise ValueError(f"tracked source differs from build tree: {os.fsdecode(path)}")
    if not count:
        raise ValueError("empty tracked source tree")
    value = raw_tree.hexdigest()
    if expected_worktree is not None and expected_worktree != value:
        raise ValueError("exact source checkout bytes differ from build evidence")
    return {"tracked_source_files_verified": count, "worktree_sha256": value}


def file_record(record, label):
    if not isinstance(record, dict) or set(record) != {"path", "sha256"}:
        raise ValueError(f"missing actual {label} file/hash record")
    path = Path(record["path"]).resolve()
    if not re.fullmatch(r"[0-9a-f]{64}", str(record["sha256"])) or digest(path) != record["sha256"]:
        raise ValueError(f"{label} hash differs from build evidence")
    return path


def coff_symbols(path):
    """Read real defined COFF symbol addresses from an unstripped i386 PE32."""
    data = Path(path).read_bytes()
    try:
        if len(data) < 64 or data[:2] != b"MZ":
            raise ValueError("kernel is not a PE image")
        pe = struct.unpack_from("<I", data, 60)[0]
        if data[pe:pe+4] != b"PE\0\0":
            raise ValueError("invalid kernel PE header")
        machine, sections, _, pointer, count, optional_size, _ = struct.unpack_from("<HHIIIHH", data, pe+4)
        optional = pe+24
        section_start = optional+optional_size
        if (machine != 0x14c or not sections or optional_size < 96
                or section_start+sections*40 > len(data)
                or struct.unpack_from("<H", data, optional)[0] != 0x10b):
            raise ValueError("requires complete i386 PE32 headers")
        image_base = struct.unpack_from("<I", data, optional+28)[0]
        virtual = [struct.unpack_from("<II", data, section_start+i*40+8) for i in range(sections)]
        if not count or pointer < section_start+sections*40 or pointer+count*18+4 > len(data):
            raise ValueError("require an actual unstripped COFF symbol table")
        strings_start = pointer+count*18
        strings_size = struct.unpack_from("<I", data, strings_start)[0]
        if strings_size < 4 or strings_start+strings_size > len(data):
            raise ValueError("truncated COFF string table")
        records = set()
        index = 0
        while index < count:
            offset = pointer+index*18
            name_field = data[offset:offset+8]
            value, section, _, _, auxiliary = struct.unpack_from("<IhHBB", data, offset+8)
            if index+auxiliary >= count:
                raise ValueError("truncated COFF auxiliary entries")
            if name_field[:4] == b"\0"*4:
                string_offset = struct.unpack_from("<I", name_field, 4)[0]
                if not 4 <= string_offset < strings_size:
                    raise ValueError("invalid COFF name offset")
                start = strings_start+string_offset
                end = data.find(b"\0", start, strings_start+strings_size)
                if end < 0:
                    raise ValueError("unterminated COFF name")
                name = data[start:end].decode("ascii")
            else:
                name = name_field.rstrip(b"\0").decode("ascii")
            if 0 < section <= sections:
                size, rva = virtual[section-1]
                if value > size:
                    raise ValueError("COFF symbol outside its section")
                records.add((image_base+rva+value, name))
            elif section == -1:
                records.add((value, name))
            index += auxiliary+1
        if not records:
            raise ValueError("kernel has no defined symbols")
        return records
    except (struct.error, UnicodeError) as error:
        raise ValueError("malformed/truncated kernel COFF table") from error


def resolved_inputs(map_path, build_directory):
    """Hash real LOAD inputs, including archives hidden by response/scripts."""
    inputs, transient, synthetic = [], [], []
    for line in Path(map_path).read_text(encoding="utf-8").splitlines():
        if not line.startswith("LOAD "):
            continue
        name = line[5:].strip()
        path = Path(name)
        path = (Path(build_directory)/path if not path.is_absolute() else path).resolve()
        if not path.is_file():
            if name == "dll stuff":
                # GNU ld's PE backend creates this BFD input in memory; it
                # is not a library pathname. Keep it visible in the receipt.
                synthetic.append("gnu-ld-pe:dll stuff")
                continue
            if re.fullmatch(r"cc[A-Za-z0-9_]+\.ltrans\d+\.ltrans\.o", path.name):
                transient.append(str(path))
                continue
            raise ValueError(f"resolved linker input is missing: {path}")
        inputs.append({"path": str(path), "sha256": digest(path)})
    if not inputs:
        raise ValueError("linker map has no resolved LOAD inputs")
    return inputs, transient, synthetic


def pe_sections(path):
    """Return loaded section bytes; post-strip header/flag changes are separate."""
    data = Path(path).read_bytes()
    try:
        if len(data) < 64 or data[:2] != b"MZ":
            raise ValueError("invalid packed kernel PE")
        pe = struct.unpack_from("<I", data, 60)[0]
        if data[pe:pe+4] != b"PE\0\0":
            raise ValueError("invalid packed kernel PE signature")
        machine, count, _, symbols, symbol_count, optional_size, _ = struct.unpack_from("<HHIIIHH", data, pe+4)
        optional = pe+24
        start = optional+optional_size
        if (machine != 0x14c or optional_size < 96 or not count
                or start+40*count > len(data)
                or struct.unpack_from("<H", data, optional)[0] != 0x10b):
            raise ValueError("invalid packed i386 PE32 layout")
        image_base = struct.unpack_from("<I", data, optional+28)[0]
        strings = symbols+symbol_count*18
        result = {}
        for index in range(count):
            offset = start+index*40
            raw_name = data[offset:offset+8].rstrip(b"\0")
            if raw_name.startswith(b"/"):
                name_offset = strings+int(raw_name[1:])
                end = data.find(b"\0", name_offset)
                if not symbols or end < name_offset:
                    raise ValueError("invalid long PE section name")
                name = data[name_offset:end].decode("ascii")
            else:
                name = raw_name.decode("ascii")
            size, rva, raw_size, raw_offset = struct.unpack_from("<IIII", data, offset+8)
            flags = struct.unpack_from("<I", data, offset+36)[0]
            if name in result or (raw_size and (raw_offset < start+40*count or raw_offset+raw_size > len(data))):
                raise ValueError("duplicate/truncated PE section")
            if name.startswith(".debug_") and not flags & 0x20000000:
                continue
            content = data[raw_offset:raw_offset+min(size, raw_size)] if raw_size else b""
            result[name] = (image_base+rva, size, hashlib.sha256(content).hexdigest(), len(content))
        return result
    except (struct.error, UnicodeError) as error:
        raise ValueError("malformed packed kernel PE") from error


def verify_build_identity(source, manifest, nm_table, link_command):
    worktree = manifest.get("source_worktree_sha256")
    if not re.fullmatch(r"[0-9a-f]{64}", str(worktree)):
        raise ValueError("missing exact source checkout identity")
    source_identity = verify_source(source, manifest.get("source_tree"), worktree)
    kernel = file_record(manifest.get("kernel_unstripped"), "unstripped kernel")
    final = file_record(manifest.get("kernel_final"), "packed kernel")
    map_path = file_record(manifest.get("linker_map"), "linker map")
    output = Path(manifest.get("output_directory", "")).resolve()
    flash = file_record({"path": str(output/"flash.bin"), "sha256": manifest.get("flash_sha256")}, "flash")
    build = Path(manifest.get("build_directory", "")).resolve()
    if not kernel.is_relative_to(build) or not final.is_relative_to(build) or not map_path.is_relative_to(build):
        raise ValueError("kernel/map are outside the recorded build directory")
    command_file = file_record(manifest.get("storage_link_command"), "recorded linker invocation")
    symbols_file = file_record(manifest.get("storage_symbols"), "recorded symbol listing")
    if not command_file.is_relative_to(build) or not symbols_file.is_relative_to(build):
        raise ValueError("link/symbol records are outside the recorded build directory")
    if command_file.read_text(encoding="utf-8") != link_command:
        raise ValueError("supplied link command differs from exact recorded build")
    if symbols_file.read_text(encoding="utf-8") != nm_table:
        raise ValueError("supplied nm listing differs from exact recorded build")
    records = coff_symbols(kernel)
    supplied_records = set()
    for line in nm_table.splitlines():
        if line.strip():
            address, _, name = line.split()
            if (int(address, 16), name) not in records:
                raise ValueError("nm listing does not match the actual unstripped PE")
            supplied_records.add((int(address, 16), name))
    if supplied_records != records:
        raise ValueError("nm listing is incomplete for the actual unstripped PE")
    if pe_sections(kernel) != pe_sections(final):
        raise ValueError("packed kernel sections differ from recorded unstripped PE")
    outputs = re.findall(r"^OUTPUT\((.+)\s+[A-Za-z0-9_-]+\)\s*$",
                         map_path.read_text(encoding="utf-8"), re.MULTILINE)
    if len(outputs) != 1:
        raise ValueError("linker map must identify exactly one output")
    actual_output = Path(outputs[0])
    actual_output = (build/actual_output if not actual_output.is_absolute() else actual_output).resolve()
    if actual_output != final:
        raise ValueError("linker map OUTPUT differs from the recorded packed kernel")
    inputs, transient, synthetic = resolved_inputs(map_path, build)
    run_path = file_record(manifest.get("storage_link_run"), "executed linker record")
    if not run_path.is_relative_to(build):
        raise ValueError("executed link record is outside the build directory")
    execution = json.loads(run_path.read_text(encoding="utf-8"))
    if (execution.get("schema") != 1 or execution.get("exit_code") != 0
            or Path(execution.get("cwd", "")).resolve() != build
            or Path(execution.get("source_directory", "")).resolve() != Path(source).resolve()
            or execution.get("source_tree") != manifest["source_tree"]
            or execution.get("source_worktree_sha256") != worktree
            or Path(execution.get("output_path", "")).resolve() != final
            or execution.get("linker_map") != manifest["linker_map"]
            or execution.get("expanded_argv") != shlex.split(link_command)):
        raise ValueError("executed linker record differs from exact build identity")
    for key in ("response_files", "direct_inputs", "resolved_inputs", "transient_lto_inputs", "synthetic_inputs"):
        if not isinstance(execution.get(key), list):
            raise ValueError("executed link record lacks complete input fields")
    for record in execution["response_files"] + execution["direct_inputs"] + execution["resolved_inputs"]:
        file_record(record, "executed linker input")
    if (execution["resolved_inputs"] != inputs or execution["transient_lto_inputs"] != transient
            or execution["synthetic_inputs"] != synthetic):
        raise ValueError("current resolved inputs differ from executed linker inputs")
    linked = file_record(execution.get("linked_output"), "original linked kernel")
    if not linked.is_relative_to(build):
        raise ValueError("original linked kernel is outside the build directory")
    linked_records = coff_symbols(linked)
    # The existing post-link pipeline removes the .reloc section. Its section
    # symbol may disappear; no other defined identity may be renamed/deleted.
    if {record for record in linked_records if record[1] != '.reloc'} != records:
        raise ValueError("original linked COFF identities differ from unstripped export")
    post_path = file_record(manifest.get("storage_postprocess_run"), "executed postprocessing record")
    pack_path = file_record(manifest.get("storage_pack_run"), "executed flash packaging record")
    stages = []
    for path, kind in ((post_path, "postprocess"), (pack_path, "pack")):
        if not path.is_relative_to(build):
            raise ValueError("artifact pipeline record is outside the build directory")
        stage = json.loads(path.read_text(encoding="utf-8"))
        if (stage.get("schema") != 1 or stage.get("exit_code") != 0 or stage.get("kind") != kind
                or Path(stage.get("source_directory", "")).resolve() != Path(source).resolve()
                or stage.get("source_tree") != manifest["source_tree"]
                or stage.get("source_worktree_sha256") != worktree
                or not isinstance(stage.get("inputs"), list) or not stage["inputs"]
                or not isinstance(stage.get("tools"), list) or not stage["tools"]
                or not isinstance(stage.get("commands"), list) or not stage["commands"]):
            raise ValueError("artifact pipeline does not identify a successful exact-source execution")
        for record in stage["inputs"] + stage["tools"]:
            file_record(record, "artifact pipeline input/tool")
        stages.append(stage)
    post, pack = stages
    before = file_record(post.get("before_kernel"), "pre-fixup kernel")
    after = file_record(post.get("after_kernel"), "post-fixup kernel")
    if (not before.is_relative_to(build) or not after.is_relative_to(build)
            or pe_sections(linked) != pe_sections(before) or coff_symbols(linked) != coff_symbols(before)
            or digest(after) != digest(kernel)
            or post.get("output") != {"path": str(final), "sha256": digest(after)}):
        raise ValueError("executed kernel fixups differ from original link or unstripped copy")
    if pack.get("kernel") != manifest["kernel_final"]:
        raise ValueError("packaged kernel differs from the recorded final PE")
    packed_flash = file_record(pack.get("flash"), "executed packed flash")
    if digest(packed_flash) != digest(flash) or pack.get("output") != pack.get("flash"):
        raise ValueError("published flash differs from the executed packaging result")
    libraries = set()
    for item in inputs:
        match = re.fullmatch(r"lib([A-Za-z0-9_+.-]+)\.a", Path(item["path"]).name)
        if match:
            libraries.add(match[1])
    if not libraries:
        raise ValueError("linker map contains no resolved archives")
    return {"tracked_source_files_verified": source_identity["tracked_source_files_verified"],
            "source_worktree_sha256": worktree,
            "kernel_unstripped": {"path": str(kernel), "sha256": digest(kernel)},
            "kernel_final": {"path": str(final), "sha256": digest(final)},
            "linker_map": {"path": str(map_path), "sha256": digest(map_path)},
            "storage_link_run": {"path": str(run_path), "sha256": digest(run_path)},
            "storage_postprocess_run": {"path": str(post_path), "sha256": digest(post_path)},
            "storage_pack_run": {"path": str(pack_path), "sha256": digest(pack_path)},
            "flash_file": {"path": str(flash), "sha256": digest(flash)},
            "resolved_inputs": inputs, "transient_lto_inputs": transient,
            "synthetic_inputs": synthetic,
            "actual_symbol_names": [name for _, name in sorted(records | linked_records)],
            "linked_libraries": sorted(libraries)}


def capture_build_evidence(manifest):
    """Export the executed link record and matching GNU nm after a real build."""
    build = Path(manifest["build_directory"]).resolve()
    kernel = build/"ntoskrnl/xboxkrnl.unstripped.exe"
    final = build/"ntoskrnl/xboxkrnl.exe"
    map_path = build/"ntoskrnl/storage-kernel.map"
    run_path = build/"ntoskrnl/storage-link-run.json"
    post_path = build/"ntoskrnl/storage-postprocess-run.json"
    pack_path = build/"storage-pack-run.json"
    execution = json.loads(run_path.read_text(encoding="utf-8"))
    if execution.get("exit_code") != 0 or not execution.get("expanded_argv"):
        raise ValueError("no successful executed kernel link record")
    command = shlex.join(execution["expanded_argv"]) + "\n"
    symbols = subprocess.check_output(
        ["i686-w64-mingw32-nm", "-n", "--defined-only", str(kernel)], text=True)
    command_file = build/"ntoskrnl/storage-link-command.txt"
    symbols_file = build/"ntoskrnl/storage-symbols.txt"
    command_file.write_text(command, encoding="utf-8")
    symbols_file.write_text(symbols, encoding="utf-8")
    for key, path in (("kernel_unstripped", kernel), ("kernel_final", final), ("linker_map", map_path),
                      ("storage_link_run", run_path), ("storage_link_command", command_file),
                      ("storage_postprocess_run", post_path), ("storage_pack_run", pack_path),
                      ("storage_symbols", symbols_file)):
        manifest[key] = {"path": str(path), "sha256": digest(path)}
    # Do not turn a capture failure into a successful build identity.
    return verify_build_identity(Path(manifest["source_directory"]), manifest, symbols, command)
