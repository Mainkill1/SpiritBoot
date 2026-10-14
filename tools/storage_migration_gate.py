#!/usr/bin/env python3
"""Read-only, deliberately incomplete preflight for the Xbox storage-class swap.

This verifies obvious build-link and source-references, not license compliance.
Run against the *assembled* Roswell source and evidence from the *exact* build.
It does not identify surviving LTO inlines, unattributed bytes or rights grants.
"""

import argparse
import json
from pathlib import Path
import re
import shlex
import sys

if __package__:
    from .storage_build_evidence import verify_build_identity
else:
    from storage_build_evidence import verify_build_identity

REQUIRED_BASELINE = frozenset({"classpnp", "disk", "nxcdrom"})
REQUIRED_CANDIDATE = frozenset({
    "nxstorage", "nxcdrom", "atapi", "pciide", "pciidex",
    "partmgr", "mountmgr", "xdvdfs", "vfatfs",
})
FORBIDDEN_CANDIDATE = frozenset({"classpnp", "disk"})
# An intentionally non-exhaustive set, from the qualified v1 release audit.
# Symbols are a smoke test only; stripped, folded and inline bodies need
# independent provenance mapping against original source revisions.
LEGACY_IDENTITIES = frozenset({
    "ClassInitialize", "ClassReadWrite", "DiskDriverEntry",
    "DiskReadWriteVerification", "SubmitTransferPacket", "TransferPktComplete",
})
OWNED_SOURCE = (
    "drivers/storage/class/nxstorage",
    "drivers/storage/class/nxcdrom/nxcdrom.c",
)
NO_PRIVATE_HEADER = re.compile(
    r'^\s*#\s*include\s*[<"](?:[^>"]*/)?(?:classpnp|classp|disk|srbhelper)\.h[>"]',
    re.MULTILINE | re.IGNORECASE,
)
NO_CLASS_CALL = re.compile(r"\bClass[A-Z]\w*\s*\(")
HASH40 = re.compile(r"[0-9a-f]{40}\Z")
HASH64 = re.compile(r"[0-9a-f]{64}\Z")


def linked_archives(command):
    """Parse an already-expanded linker invocation; fail if a response is hidden."""
    args = shlex.split(command, posix=True)
    if not args:
        raise ValueError("empty linker invocation")
    # GCC's comma forwarding and separate -Xlinker operands reach the same ld
    # option namespace. Inspect each operand, including group members.
    operands = []
    for arg in args:
        operands.extend(arg[4:].split(",") if arg.startswith("-Wl,") else [arg])
    archives = set()
    need_library = False
    for arg in operands:
        if arg.startswith("@"):
            raise ValueError("link command contains an opaque @response file: expand it first")
        if arg == "-Xlinker":
            continue
        if arg in ("-l", "--library"):
            need_library = True
            continue
        library = arg if need_library else None
        need_library = False
        if arg.startswith("--library="):
            library = arg.split("=", 1)[1]
        elif arg.startswith("-l") and len(arg) > 2 and not arg.startswith("-link"):
            library = arg[2:]
        if library is not None:
            if not library or library.startswith("-"):
                raise ValueError("missing linker library operand")
            if library.startswith(":"):
                arg = library[1:]
            else:
                archives.add(library)
        name = Path(arg.replace("\\", "/")).name
        match = re.fullmatch(r"lib([a-zA-Z0-9_+.-]+)\.a", name)
        if match:
            archives.add(match.group(1))
    if need_library:
        raise ValueError("missing linker library operand")
    return archives


def exported_names(table):
    """Validate GNU nm -n --defined-only records and normalize COFF clones."""
    names = set()
    for number, line in enumerate(table.splitlines(), 1):
        if not line.strip():
            continue
        match = re.fullmatch(r"\s*[0-9a-fA-F]{8,16}\s+[aAbBcCdDgGiInNpPrRsStTvVwW?]\s+(\S+)\s*", line)
        if not match:
            raise ValueError(f"invalid defined-only nm record at line {number}")
        raw = re.sub(r"\.(?:constprop|isra|part|lto_priv)\.\d+(?:\.[\w.]+)?$|\.cold(?:\.\d+)?$", "", match[1])
        names.add(re.sub(r"@\d+$", "", raw).lstrip("_"))
    return names


def strip_comments(source):
    # Removes comments solely to avoid false positives in the sentinel.
    # This is not a C parser or a provenance analysis.
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.DOTALL)


def candidate_source_findings(source):
    """Inspect only new/owned code, not unused archived MS-PL source."""
    root = Path(source)
    newdir = root / OWNED_SOURCE[0]
    cdrom = root / OWNED_SOURCE[1]
    problems = []
    if not newdir.is_dir() or not any(newdir.rglob("*.c")):
        problems.append("missing independently implemented nxstorage C sources")
    if not cdrom.is_file():
        problems.append("missing nxcdrom implementation")
    files = list(newdir.rglob("*.c")) + list(newdir.rglob("*.h"))
    if cdrom.is_file():
        files.append(cdrom)
    for file in files:
        try:
            source_text = strip_comments(file.read_text(encoding="utf-8"))
        except UnicodeError as error:
            problems.append(f"{file.relative_to(root)}: cannot decode: {error}")
            continue
        if NO_PRIVATE_HEADER.search(source_text):
            problems.append(f"{file.relative_to(root)}: includes legacy private storage header")
        if NO_CLASS_CALL.search(source_text):
            problems.append(f"{file.relative_to(root)}: contains a Class* direct call/declaration")
    return problems


def check(source, manifest, link_command, nm_table, mode):
    source = Path(source).resolve()
    if mode not in ("baseline", "candidate"):
        raise ValueError("mode must be baseline or candidate")
    if not source.is_dir():
        raise ValueError("assembled source directory is missing")
    if manifest.get("schema") != 1 or manifest.get("status") != "built":
        raise ValueError("expected a successful version-1 firmware build.json")
    if Path(manifest.get("source_directory", "")).resolve() != source:
        raise ValueError("manifest source_directory differs from supplied assembled source")
    if not HASH40.fullmatch(str(manifest.get("source_tree", ""))):
        raise ValueError("build manifest lacks validated assembled source_tree")
    if not HASH64.fullmatch(str(manifest.get("flash_sha256", ""))):
        raise ValueError("build manifest lacks validated flash_sha256")
    command_libraries = linked_archives(link_command)
    names = exported_names(nm_table)
    if not names:
        raise ValueError("empty symbol table; require an unstripped kernel listing")
    evidence = verify_build_identity(source, manifest, nm_table, link_command)
    libraries = set(evidence["linked_libraries"])
    # Inspect the actual PE as well: a shortened but syntactically valid nm
    # listing cannot conceal a legacy symbol present in the image.
    names.update(exported_names("\n".join(
        "00000000 T " + name for name in evidence["actual_symbol_names"])))
    findings = []
    required = REQUIRED_BASELINE if mode == "baseline" else REQUIRED_CANDIDATE
    missing = sorted(required - libraries)
    findings.append({"check": "expected_libraries", "pass": not missing, "detail": missing})
    if mode == "candidate":
        forbidden = sorted(FORBIDDEN_CANDIDATE & (libraries | command_libraries))
        present = sorted(LEGACY_IDENTITIES & names)
        source_errors = candidate_source_findings(source)
        findings.extend((
            {"check": "forbidden_libraries", "pass": not forbidden, "detail": forbidden},
            {"check": "known_legacy_symbols", "pass": not present, "detail": present},
            {"check": "owned_source_references", "pass": not source_errors, "detail": source_errors},
        ))
    return {
        "schema": 1,
        "scope": "PRECHECK_ONLY_NOT_LICENSE_CERTIFICATION",
        "mode": mode,
        "source_tree": manifest["source_tree"],
        "flash_sha256": manifest["flash_sha256"],
        "linked_libraries": sorted(libraries),
        "checks": findings,
        "build_evidence": {k: v for k, v in evidence.items()
                           if k not in ("actual_symbol_names", "linked_libraries")},
        "passed": all(item["pass"] for item in findings),
        "limitations": [
            "Build command and symbol listing must come from the same exact recorded build.",
            "Archive names and a handful of symbols cannot prove absence of copied inline, data or merged code.",
            "Independent source-provenance, SDK/DDK rights and corresponding-source review required.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("baseline", "candidate"), required=True)
    parser.add_argument("--source", type=Path, required=True,
                        help="assembled Roswell source_directory from build.json")
    parser.add_argument("--build-json", type=Path, required=True)
    parser.add_argument("--link-line", type=Path, required=True,
                        help="UTF-8 actual final expanded linker invocation; no @response files")
    parser.add_argument("--symbols", type=Path, required=True,
                        help="nm listing of matching unstripped xboxkrnl image")
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.build_json.read_text(encoding="utf-8"))
        result = check(args.source, manifest,
                       args.link_line.read_text(encoding="utf-8"),
                       args.symbols.read_text(encoding="utf-8"),
                       args.mode)
    except (ValueError, KeyError, OSError, UnicodeError, TypeError) as error:
        print(json.dumps({"schema": 1, "scope": "PRECHECK_ONLY_NOT_LICENSE_CERTIFICATION",
                          "passed": False, "error": str(error)}, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
