# Task 2 integration report

Status: IMPLEMENTED, ready for independent review. Product working tree is clean.
Runtime qualification, seven formal controller pairs, final analyzer execution,
new CI execution and BIOS publication remain controller acceptance work. No
speedup or new runtime/CI pass is claimed by this implementer. No Docker/emulator,
push/publish, source-kernel mutation, reference clone mutation or BIOS write was
performed. No subagent was used and no forbidden repository was inspected.

## Commits and files

- `f1a53ef4e564c314b294dd9590ba7e2cb0af33f3`: exact approved optimization
  patch and ordered lock entry. Controller was notified immediately after commit
  so its sequential build could begin.
- `df5fb616750b286b7e669c847920cc4a192a677f`: analyzer, synthetic contract tests,
  actual-source host and performance correctness CI, integration guide and
  copied source work evidence.

Changed product files: `patches/roswell/0002-kernel-call-optimization.patch`,
`sources/firmware-lock.json`, `.github/workflows/firmware.yml`,
`tools/kernel_performance.py`, `scripts/analyze-kernel-performance.py`,
`tests/host/test_kernel_performance.py`,
`docs/optimization/2026-10-07/{README.md,integration-and-measurement.md,host-work.json}`.
The preexisting audit JSON/CSV remain unchanged, each with 371 rows.
Neither `tools/firmware.py` nor any build script was changed.

## Source applicability and preserved identities

Read Task 1 approved source record before mutation: specification PASS,
quality PASS; commit `87aba89a6ba9b2a58f2edd6e52d5e3aa1e8649d7`, tree
`f7adb302a762ed1945cc07d9c2ff428c643ba959`. Public source status was clean.
Generated the new patch exactly using:

```sh
git -C /workspace/SpiritBoot-optimization-kernel diff --binary \
  291ad9759f7993cb1f96d73bfa1c6f333c2bef34 \
  87aba89a6ba9b2a58f2edd6e52d5e3aa1e8649d7 \
  > patches/roswell/0002-kernel-call-optimization.patch
```

Existing firmware preparation is inline in `build_firmware`, rather than a
`prepare_source` helper. The controller clarified that no refactor should be
made. Host-only applicability proof used the same `load_lock()`/`patch_inputs()`
input validation and isolated clone/index application sequence, without a build:

```python
import subprocess, tempfile
from pathlib import Path
from tools.firmware import load_lock, patch_inputs
root = Path.cwd()
lock = load_lock()
inputs = patch_inputs(lock['repositories']['roswell']['patches'])
with tempfile.TemporaryDirectory(prefix='optimization-prepare-') as td:
    output = Path(td)
    source = output / 'source'
    subprocess.run(['git', 'clone', '--quiet', '--no-hardlinks', '--dissociate',
                    '--no-checkout', str(root / '.reference/roswell'), str(source)], check=True)
    subprocess.run(['git', '-C', str(source), 'checkout', '--quiet', '--detach',
                    lock['repositories']['roswell']['revision']], check=True)
    for number, data in enumerate(inputs):
        patch = output / f'{number}.patch'
        patch.write_bytes(data)
        for args in (['apply', '--check', '--index'], ['apply', '--index']):
            subprocess.run(['git', '-C', str(source)] + args + [str(patch)], check=True)
    tree = subprocess.check_output(['git', '-C', str(source), 'write-tree'], text=True).strip()
    assert tree == 'f7adb302a762ed1945cc07d9c2ff428c643ba959'
```

Result: both patches apply cleanly to public base
`1569e2e89fb47cc72b9c704a8884f98200432bd4`; prepared tree equals approved
source tree exactly. Temporary source was removed by TemporaryDirectory;
reference clone was read only.

| Retained/new input | SHA256 | Bytes |
|---|---|---:|
| Existing 0001 patch | `747a5974ac714bcf76a6516fc1ed3ced148880907bd41a3f3f62fbd3d60b168f` | unchanged |
| New 0002 patch | `0e8147f370fc591c1f6b440344d1271aa5d040291e54a15fba650a88ad8ff1f7` | source diff |
| Historical release BIOS | `154276a142c7df727ea46f1a35ee9a896f7369221f10d07f21757a61bc8e6d60` | 262144 |
| Historical checked BIOS | `7f7cb55be972308b570415863222ff8285e0f4de2d324a12425ee5e33c568ceb` | 524288 |
| Copied host work JSON | `ecdb801312c07ef01cbc69ef9ad4b945ca6e457bef53b375f47eb101f69290d7` | exact copy |

Prior patch and BIOS hashes were verified directly. Host work JSON is copied
byte-for-byte from controller `artifacts/optimization/host-work.json`; it has
source operation counts and differential state hashes, no guest timing.

## Validation commands and results

From `/workspace/SpiritBoot-cleanroom`:

```sh
python3 -m unittest discover -s tests/host -v
python3 -m unittest discover -s tests/host -p test_kernel_performance.py -v
PYTHONPYCACHEPREFIX=/tmp/spiritboot-integration-pycache python3 -m py_compile \
  tools/kernel_performance.py scripts/analyze-kernel-performance.py \
  tests/host/test_kernel_performance.py
git diff --check
```

Initial packaging host run: 42 tests, 41 pass plus one root-only skip.
Final full suite: 63 tests, 62 pass plus the same documented
`requires root CI ownership fixture` skip; zero failures/errors. New analyzer
suite: 21/21 tests pass. Coverage includes valid seven pairs and deterministic
improvement/regression/inconclusive outcomes; noisy sample variation and only
five improving pairs cannot claim speedup; same flash/mismatched ISO/local DVD
bytes, failed driver/TAP/TODO/SKIP, terminal loss, malformed/incorrect/overflow
samples, missing/duplicate workloads, missing/nonalternating/overlapping
execution logs and bad runtime configuration are refused. CLI generates JSON
and Markdown for valid fixtures and refuses an explicitly wrong candidate hash.

Python compilation and whitespace checks pass. Initial default py_compile
could not write a preexisting root-owned `tools/__pycache__`; rerunning with
an isolated pycache prefix above passed without changing ownership or files.

Workflow structural validation ran:

```python
import ast, re, subprocess, yaml
from pathlib import Path
workflow = yaml.safe_load(Path('.github/workflows/firmware.yml').read_text())
for job in workflow['jobs'].values():
    for step in job['steps']:
        if 'run' not in step:
            continue
        script = step['run'].replace('${{ matrix.variant }}', 'release')
        subprocess.run(['bash', '-n'], input=script, text=True, check=True)
        for inner in re.findall("sh -ec '([\\s\\S]*?)'", script):
            subprocess.run(['sh', '-n'], input=inner, text=True, check=True)
        for body in re.findall("python3 - <<'PY'\\n([\\s\\S]*?)\\nPY", script):
            ast.parse(body)
```

Result: YAML parses; nine shell blocks, nested container shell bodies and Python
heredocs pass syntax validation. This is not an execution claim. The workflow
runs actual-source clean-room checks, `check.py --optimized`, pin ordinary and
opt-in diagnostics inside the pinned toolchain after build. It verifies the
actual indexed source tree, builds four guests from manifest source_directory,
retains existing direct checks, and adds strict 42/42 performance smoke with
zero TODO/SKIP/errors and validated PERF records. Source host logs/work.json and
guest capture directories are uploaded. No HTTP runner is added and CI does not
interpret a single runtime as paired performance evidence.

## Analyzer command and dataset contract

Controller-provided runtime records: existing `baseline_release`, `xemu`,
`api_seed` plus appended `benchmark_dvd` and `candidate_release`; each has
sha256/bytes, candidate additionally the approved source_tree. Optional
candidate build manifest validates built release status, size, source tree and
output hash. Both fixed baseline and explicit candidate hashes are enforced:

```sh
python3 scripts/analyze-kernel-performance.py artifacts/optimization/pairs.json \
  --runtime-inputs artifacts/optimization/runtime-inputs.json \
  --candidate-build artifacts/optimization/final-release-v1/build.json \
  --baseline-hash 154276a142c7df727ea46f1a35ee9a896f7369221f10d07f21757a61bc8e6d60 \
  --candidate-hash CANDIDATE_RELEASE_SHA256 \
  --output artifacts/optimization/performance-report.json \
  --markdown artifacts/optimization/performance-report.md
```

Requires >=7 ordered baseline/candidate capture pairs, one unique capture per
run and exact microsecond UTC `execution_log` alternating each pair order. It
proves log nonoverlap, checks driver coarse starts with one-second quantization
allowance and verifies elapsed durations against precise controller intervals.
Paths are absolute or relative to pairs.json. Explicit `asset_path_map` provides
controller mount mappings; no `/work` mapping is guessed. Literal accessible
local assets are verified byte-for-byte against hashes; unavailable files retain
record identities. xemu/HDD/DVD identities must match across every capture and
runtime inputs. Baseline release is fixed; candidate release must differ, match
runtime/build records and be 262144 bytes.

All samples are retained. Contract checks enforce 41 workloads/42 positive TAP
records, fixed workload order and iterations, samples 0..2 except single cold
sample 0, one positive clock frequency, correctness 1, matching checksums,
terminal PASS and zero-failure summary. The guest independently supplies KAT
and lifecycle correctness. The analyzer does not invent correctness or subtract
overhead. Report stores input/code hashes, controller provenance, asset records,
raw samples, normalized ranges, trial median arrays, min/max/median, paired
absolute/percentage differences and classification.

Improvement needs positive overall median reduction greater than maximum
observed variant range including raw normalized samples, and >=6/7 improving
pairs (ceil(6*N/7) for larger datasets). Symmetric consistent negative change is
regression; other timing is inconclusive. No aggregate FPS or gameplay claim.

## Self-review and remaining concerns

Reviewed requirements, product diff, source identity, analyzer validation and
false-claim threshold, CI source_directory use, hashes and audit row coverage.
Public guide documents all seven changes, nonwrapping registry count proof,
diagnostic opt-in, 41-workload/42-TAP limits, pin crossover cost, stub/correctness
deferrals and pending runtime qualification. Source host evidence is attributed
to its implementer/controller and is not relabeled as guest evidence.

Pending: independent Task 2 review; controller candidate builds and direct/API/
contracts/warm/XISO regressions; seven alternating immutable-ISO pairs; formal
analyzer command with actual candidate hash; acceptance of the 64-page pin
threshold; remote CI execution; final qualification and BIOS publication. The
integration code deliberately rejects datasets from an unapproved source tree
or different guest version rather than guessing compatibility. No critical or
important issue is known from self-review.

## Fix round 1/5 — review Important I1 exact timing arithmetic

Review basis: full `task-2-review.md`, finding I1; fix base
`df5fb616750b286b7e669c847920cc4a192a677f`. Implemented in commit
`0cd16fbe1e828f77d6ffb320c7574bf10792640b`. Only
`tools/kernel_performance.py` and `tests/host/test_kernel_performance.py` changed.
Product working tree is clean. Kernel, firmware helper, patches, BIOS and CI
are unchanged. No Docker/emulator, source fixture, original fixture-mapped path,
push or publication was used. Actual paired captures were not modified or
reanalyzed by this implementer; controller performs the final actual analysis.

Verified the technical finding through new real-parser synthetic capture tests:
permitted uint64 values were rounded before normalization-derived classification,
erasing 1023 ticks of raw variation and reporting 2048 rather than 1 tick of
median change. Before implementation, the focused command was:

```sh
python3 -m unittest discover -s tests/host -p test_kernel_performance.py -k uint64 -v
```

Output (exit 1):

```text
Ran 3 tests in 0.083s
FAILED (failures=5)
```

The exact reviewer workload `sysva-4096` repeated in seven pairs:
baseline `[9223372036854776833, 9223372036854776833, 9223372036854776833]`,
candidate `[9223372036854775809, 9223372036854776832, 9223372036854776832]`.
The red run classified the forward case as `timing improvement` and reverse
case as `timing regression`, rather than required inconclusive. The matched
constant definite change reported +/-2048 instead of +/-1024. The corresponding
1000-iteration boundary lost its real 1/1000 normalized median difference.

The fix reconstructs exact `Fraction(ticks, iterations)` normalized samples
from retained raw uint64 fields. Trial and overall medians, per-variant raw and
intertrial ranges, paired differences, sign consistency, strict thresholds and
percentage changes remain exact until after classifications. The consistency
count uses exact integer ceiling `(6*N+6)//7`. Capture normalized floats remain
presentation fields and are never read by the decision path. Numeric report
fields convert only after decisions; `exact_decision` retains numerator and
denominator for both variant medians, median difference, maximum observed
range and all paired differences. `decision_arithmetic` labels this distinction.
The full uint64 parser contract remains permitted without an arbitrary cap.

New tests prove the exact reviewer case remains inconclusive in both directions
with delta +/-1 and range 1023; definite constant cases classify improvement /
regression with exact +/-1024 and zero variation. A 1000-iteration version
requires inconclusive delta 1/1000 and range 1023/1000, checks exact rational
records and successful JSON serialization. Existing definite, noisy-positive,
weak-positive and five-of-seven cases remain covered.

Final validation commands and actual output:

```sh
python3 -m unittest discover -s tests/host -p test_kernel_performance.py -v
```

```text
Ran 24 tests in 0.803s
OK
```

```sh
python3 -m unittest discover -s tests/host -v
```

```text
Ran 66 tests in 5.547s
OK (skipped=1)
```

There are 65 passing tests and the unchanged root-only ownership fixture skip.
Both commands exited 0; the full suite includes the CLI JSON/Markdown output
check. Additional commands exited 0 with no diagnostics:

```sh
PYTHONPYCACHEPREFIX=/tmp/spiritboot-integration-pycache python3 -m py_compile \
  tools/kernel_performance.py tests/host/test_kernel_performance.py
git diff --check
```

Self-review confirms no classification input comes from rounded presentation
fields, and symmetric regression and positive-threshold decisions use the same
exact values. Pending scoped independent re-review of
`df5fb616..0cd16fbe` and controller actual-data report regeneration. No new
runtime/CI qualification or performance conclusion is claimed by this fix.
