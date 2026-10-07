"""Pinned open-firmware build and execution helpers (no external Python packages)."""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOCK = ROOT / "sources/firmware-lock.json"
FLASH_SIZES = {"release": 256 * 1024, "debug": 512 * 1024}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def load_lock(path=DEFAULT_LOCK):
    try:
        value = json.loads(Path(path).read_text())
        if value["schema"] != 1:
            raise ValueError("unsupported schema")
        for name in ("roswell", "xemu"):
            repository = value["repositories"][name]
            if not re.fullmatch(r"[0-9a-f]{40}", repository["revision"]):
                raise ValueError("expected full lowercase Git revision")
            if not repository["url"].startswith("https://github.com/"):
                raise ValueError("expected public GitHub HTTPS URL")
        return value
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ValueError(f"invalid firmware lock: {error}") from error


def checked_output(command):
    return subprocess.check_output(command, text=True, stderr=subprocess.STDOUT).strip()


def build_firmware(source, output, variant="release", lock_path=DEFAULT_LOCK):
    source, output = Path(source).resolve(), Path(output).resolve()
    if variant not in ("release", "debug"):
        raise ValueError("variant must be release or debug")
    if output == source or source.is_relative_to(output) or output.is_relative_to(source):
        raise ValueError("source and output directories must not overlap")
    output.mkdir(parents=True, exist_ok=True)
    published = output / "flash.bin"
    published.unlink(missing_ok=True)
    manifest = {"schema": 1, "status": "failed", "variant": variant,
                "source": str(source), "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "commands": []}
    started = time.monotonic()
    try:
        lock = load_lock(lock_path)
        revision = checked_output(["git", "-C", str(source), "rev-parse", "HEAD"])
        if revision != lock["repositories"]["roswell"]["revision"]:
            raise ValueError(f"source revision {revision} differs from firmware lock")
        if checked_output(["git", "-C", str(source), "status", "--porcelain"]):
            raise ValueError("dirty Roswell source: commit and pin patches before building")
        manifest.update(source_revision=revision, repositories=lock["repositories"],
                        lock_sha256=sha256(lock_path), tool_versions={})
        epoch = checked_output(["git", "-C", str(source), "show", "-s", "--format=%ct", "HEAD"])
        manifest["source_date_epoch"] = epoch
        build_env = dict(os.environ, SOURCE_DATE_EPOCH=epoch)
        for tool in ("cmake", "ninja", "i686-w64-mingw32-gcc", "i686-w64-mingw32-g++", "gcc", "git", "python3"):
            manifest["tool_versions"][tool] = checked_output([tool, "--version"]).splitlines()[0]
        # A new configure tree prevents undeclared CMake cache options or
        # compiler paths from contaminating the attributed build. Keep previous
        # trees as evidence; never delete an arbitrary existing work directory.
        work = Path(tempfile.mkdtemp(prefix="work-", dir=output))
        manifest["build_directory"] = str(work)
        commands = [
            ["cmake", "-G", "Ninja", "-S", str(source), "-B", str(work),
             f"-DCMAKE_TOOLCHAIN_FILE={source / 'toolchain-gcc.cmake'}",
             "-DCMAKE_BUILD_TYPE=Release", f"-DDBG={int(variant == 'debug')}",
             "-DKDBG=FALSE"],
            ["cmake", "--build", str(work), "--clean-first", "--target", "flash", "--parallel", "4"],
        ]
        with (output / "build.log").open("w") as log:
            for command in commands:
                manifest["commands"].append(command)
                log.write(json.dumps(command) + "\n")
                log.flush()
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, env=build_env)
        image = work / "flash.bin"
        if image.stat().st_size != FLASH_SIZES[variant]:
            raise ValueError(f"invalid flash size: expected {FLASH_SIZES[variant]} bytes")
        shutil.copyfile(image, published)
        manifest.update(status="built", flash_size=published.stat().st_size,
                        flash_sha256=sha256(published))
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        published.unlink(missing_ok=True)
        manifest["error"] = str(error)
        raise
    finally:
        manifest["elapsed_seconds"] = round(time.monotonic() - started, 3)
        write_json(output / "build.json", manifest)
    return manifest


def grade_tap(text):
    """Grade one complete, numbered TAP stream; retain TODO and SKIP counts."""
    lines = text.splitlines()
    versions = [line for line in lines if line.startswith("TAP version")]
    plans = [re.fullmatch(r"1\.\.(\d+)", line.strip()) for line in lines if line.startswith("1..")]
    results = []
    result_positions = []
    errors = []
    for position, line in enumerate(lines):
        if line.startswith("Bail out!"):
            errors.append("TAP bailout")
        if re.match(r"^(?:not[ \t]+ok|ok)\b", line):
            match = re.fullmatch(r"(not[ \t]+ok|ok)[ \t]+(\d+)(?:[ \t]+.*)?", line)
            if not match:
                errors.append("malformed test result")
                continue
            results.append((int(match[2]), " ".join(match[1].split()), line))
            result_positions.append(position)
    if len(versions) != 1 or versions[0] not in ("TAP version 13", "TAP version 14"):
        errors.append("expected exactly one TAP version 13 or 14 stream")
    if len(plans) != 1 or plans[0] is None or int(plans[0][1]) <= 0:
        errors.append("expected one nonempty test plan")
        plan = 0
    else:
        plan = int(plans[0][1])
    if len(results) != plan or any(number != i for i, (number, _, _) in enumerate(results, 1)):
        errors.append("test numbers do not match complete plan")
    plan_positions = [i for i, line in enumerate(lines) if line.startswith("1..")]
    version_positions = [i for i, line in enumerate(lines) if line.startswith("TAP version")]
    if result_positions and len(plan_positions) == 1:
        if result_positions[0] < plan_positions[0] < result_positions[-1]:
            errors.append("test plan must precede or follow all results")
    if len(version_positions) == 1 and result_positions + plan_positions:
        if version_positions[0] > min(result_positions + plan_positions):
            errors.append("TAP version must precede its plan and results")
    counts = {"ok": 0, "failed": 0, "todo": 0, "skipped": 0}
    for _, state, line in results:
        if re.search(r"#\s*TODO\b", line, re.IGNORECASE):
            counts["todo"] += 1
        elif state == "ok" and re.search(r"#\s*SKIP\b", line, re.IGNORECASE):
            counts["skipped"] += 1
        else:
            counts["ok" if state == "ok" else "failed"] += 1
    return {"passed": not errors and counts["failed"] == 0, "plan": plan,
            "ran": len(results), "errors": errors, **counts}


def run_firmware(xemu, flash, hdd, dvd, output, timeout=240, tap=False, preserve_hdd=False):
    """Capture an open-firmware run. A deadline never becomes a passing test."""
    if not isinstance(timeout, (int, float)) or not 0 < timeout <= 86400:
        raise ValueError("timeout must be between 0 and 86400 seconds")
    paths = {"xemu": Path(xemu).resolve(), "flash": Path(flash).resolve(),
             "hdd": Path(hdd).resolve()}
    if dvd is not None:
        paths["dvd"] = Path(dvd).resolve()
    for name, path in paths.items():
        if not path.is_file():
            raise ValueError(f"missing {name} input: {path}")
    if not os.access(paths["xemu"], os.X_OK):
        raise ValueError("xemu is not executable")
    if paths["flash"].stat().st_size not in FLASH_SIZES.values():
        raise ValueError("flash size must be 262144 (release) or 524288 (debug) bytes")
    output = Path(output).resolve()
    # Exclusive directory creation preserves previous captures and input files.
    output.mkdir(parents=True, exist_ok=False)
    runtime_hdd = paths["hdd"]
    if preserve_hdd:
        runtime_hdd = output / "private-hdd.qcow2"
        # Flatten backing chains and external data files without modifying the
        # supplied disk. A byte copy can relocate relative backing references
        # or leave guest writes targeting a shared external data file.
        try:
            checked_output(["qemu-img", "convert", "-O", "qcow2",
                            str(paths["hdd"]), str(runtime_hdd)])
        except subprocess.CalledProcessError as error:
            raise ValueError(f"private HDD conversion failed: {error.output}") from error
    config = output / "xemu.toml"
    config.write_text("[general]\nshow_welcome = false\nskip_boot_anim = true\n"
                      "[sys]\nmem_limit = '128'\n[sys.files]\n" + "\n".join(
                          f"{name}_path = {json.dumps(value, ensure_ascii=False)}" for name, value in
                          [("bootrom", ""), ("flashrom", str(paths["flash"])),
                           ("eeprom", ""), ("hdd", str(runtime_hdd))] +
                          ([("dvd", str(paths["dvd"]))] if dvd is not None else [])) + "\n")
    serial = output / "serial.log"
    serial.touch()
    command = [str(paths["xemu"]), "-config_path", str(config)]
    if not preserve_hdd:
        command.append("-snapshot")
    command.extend(["-device", "lpc47m157", "-serial", f"file:{serial}"])
    manifest = {"schema": 1, "status": "launch_failed", "command": command,
                "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "timeout_seconds": timeout, "memory_mib": 128,
                "boot_mode": "open-direct", "snapshot": not preserve_hdd, "expect_tap": tap,
                "assets": {name: {"path": str(path), "sha256": sha256(path),
                                  "size": path.stat().st_size} for name, path in paths.items()}}
    if preserve_hdd:
        manifest["runtime_hdd"] = {"path": str(runtime_hdd),
                                   "initial_sha256": sha256(runtime_hdd)}
    started = time.monotonic()
    process = None
    try:
        with (output / "emulator.log").open("wb") as log:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                       start_new_session=True)
            try:
                returncode = process.wait(timeout=timeout)
                manifest.update(returncode=returncode,
                                status="captured" if returncode == 0 else "emulator_failed")
            except subprocess.TimeoutExpired:
                manifest["status"] = "timeout"
            finally:
                # Kill descendants too: AppImage wrappers and render helpers may
                # outlive the leader. Always reap the process we started.
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
                manifest.setdefault("returncode", process.returncode)
        if tap:
            manifest["tap"] = grade_tap(serial.read_text(errors="replace"))
            if manifest["status"] == "captured":
                manifest["status"] = "passed" if manifest["tap"]["passed"] else "test_failed"
    except OSError as error:
        manifest["error"] = str(error)
    finally:
        manifest["elapsed_seconds"] = round(time.monotonic() - started, 3)
        if preserve_hdd:
            manifest["runtime_hdd"].update(sha256=sha256(runtime_hdd),
                                           size=runtime_hdd.stat().st_size)
        write_json(output / "run.json", manifest)
    return manifest
