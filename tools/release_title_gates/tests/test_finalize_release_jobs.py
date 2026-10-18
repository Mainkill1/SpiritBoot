import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from finalize_release_jobs import (_stage_package, build_title_job, finalize,
                                   resolve_contract)
from rclass_gate import build_forza_plan
from release_job_validator import validate_release_job


class FinalizeReleaseJobsTests(unittest.TestCase):
    def setUp(self):
        contract_path = ROOT / "contract.template.json"
        if not contract_path.is_file():
            contract_path = ROOT / "candidate-release-automation" / "contract.template.json"
        self.contract = json.loads(contract_path.read_text())
        self.contract["titles"]["halo2"]["hdd"] = {
            "id": "clean-hdd", "sha256": "a" * 64,
            "retention": "deleteAfterEvidence",
        }
        self.contract["titles"]["halo2"]["disc"] = {
            "id": "halo2-disc", "sha256": "b" * 64,
        }
        fixture = ROOT / "fixtures" / "base-job.json"
        if not fixture.is_file():
            fixture = ROOT / "packages" / "forza-rclass-gate-0168" / "job.json"
        self.base = json.loads(fixture.read_text())

    def _write_base(self, root):
        job = copy.deepcopy(self.base)
        replacements = {}
        for row in job["inputs"]:
            if row["path"] == "flash.bin":
                continue
            path = root / row["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(("fixture:" + row["path"]).encode())
            replacements[row["expectedSha256"]] = hashlib.sha256(path.read_bytes()).hexdigest()
            row["expectedSha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        encoded = json.dumps(job)
        for old, new in replacements.items():
            encoded = encoded.replace(old, new)
        job = json.loads(encoded)
        hashes = {row["path"]: row["expectedSha256"] for row in job["inputs"]}
        job["expectedExecutableSha256"] = hashes["native-launch.exe"]
        job["runtimeState"]["files"][0]["expectedSha256"] = hashes["state/eeprom.bin"]
        (root / "job.json").write_text(json.dumps(job))
        self.contract["common"]["xemu"]["sha256"] = hashes["xemu.exe"]
        self.contract["common"]["launcher"]["sha256"] = hashes["native-launch.exe"]
        self.contract["common"]["eeprom_sha256"] = hashes["state/eeprom.bin"]
        return job

    def test_resolve_contract_changes_only_firmware_fields(self):
        before = copy.deepcopy(self.contract)
        resolved = resolve_contract(self.contract, "candidate", "c" * 64)
        before["state"] = "resolved"
        before["common"]["firmware_asset"] = {
            "id": "spiritboot-release64-candidate-cccccccccccc",
            "sha256": "c" * 64,
        }
        self.assertEqual(resolved, before)

    def test_forza_job_replaces_every_old_firmware_reference(self):
        resolved = resolve_contract(self.contract, "candidate", "c" * 64)
        job, spec = build_title_job(
            self.base, resolved, "forza", "candidate",
            owned_tool_sources={
                "owned-child-actions.ps1": ROOT / "route_actions.ps1",
                "owned-child-input.cs": ROOT / "route_input.cs",
            })
        text = json.dumps(job)
        self.assertNotIn("2d43d91ca5a4474a365e308b2117a642", text)
        self.assertIn("c" * 64, text)
        self.assertEqual(job["plan"], build_forza_plan())
        self.assertEqual(validate_release_job(job, spec), [])

    def test_unresolved_halo_disc_fails_closed(self):
        contract = copy.deepcopy(self.contract)
        contract["titles"]["halo2"]["disc"] = {"id": None, "sha256": None}
        resolved = resolve_contract(contract, "candidate", "c" * 64)
        with self.assertRaisesRegex(ValueError, r"halo2-a\.disc"):
            build_title_job(self.base, resolved, "halo2-a", "candidate")

    def test_finalize_stages_verified_flash_and_all_phase_one_jobs(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            flash = td / "flash.bin"
            flash.write_bytes(b"candidate firmware")
            digest = hashlib.sha256(flash.read_bytes()).hexdigest()
            contract = td / "contract.json"
            base = td / "base"
            base.mkdir()
            self._write_base(base)
            base_input_before = (base / "owned-child-input.cs").read_bytes()
            old_input_hash = next(row["expectedSha256"] for row in
                                  json.loads((base / "job.json").read_text())["inputs"]
                                  if row["path"] == "owned-child-input.cs")
            contract.write_text(json.dumps(self.contract))
            out = td / "out"
            report = finalize(
                flash=flash,
                expected_sha256=digest,
                candidate_id="candidate",
                contract_path=contract,
                base_package=base,
                output=out,
            )
            self.assertEqual(report["firmware_sha256"], digest)
            self.assertEqual(
                set(report["ready_jobs"]),
                {"pgr2-create", "forza", "halo2-a", "halo2-b", "doa-create"},
            )
            self.assertEqual((out / "packages" / "forza" / "flash.bin").read_bytes(),
                             flash.read_bytes())
            owned_input = out / "packages" / "forza" / "owned-child-input.cs"
            self.assertEqual(owned_input.read_bytes(), (ROOT / "route_input.cs").read_bytes())
            self.assertEqual((base / "owned-child-input.cs").read_bytes(), base_input_before)
            forza_job = json.loads((out / "packages" / "forza" / "job.json").read_text())
            declared = next(row["expectedSha256"] for row in forza_job["inputs"]
                            if row["path"] == "owned-child-input.cs")
            self.assertEqual(declared, hashlib.sha256(owned_input.read_bytes()).hexdigest())
            guided = next(row for row in forza_job["diagnostics"]
                          if row["id"] == "forza-guided-route")
            self.assertGreaterEqual(guided["durationMs"], 100_000)
            self.assertIn(declared, json.dumps(guided))
            for diagnostic in forza_job["diagnostics"]:
                if diagnostic["type"] == "external":
                    command = json.dumps(diagnostic)
                    self.assertIn(declared, command)
                    self.assertNotIn(old_input_hash, command)
            self.assertNotIn("forza-A-race-confirm",
                             {row["id"] for row in forza_job["diagnostics"]})
            self.assertNotIn("forza-blockstats-race-ready",
                             {row["id"] for row in forza_job["diagnostics"]})
            phase_two = td / "phase-two"
            frozen_spec = (out / "packages" / "forza" / "validator-spec.json").read_bytes()
            _stage_package(out / "packages" / "forza", phase_two, flash,
                           forza_job, {"phase": 2})
            self.assertEqual((phase_two / "owned-child-input.cs").read_bytes(),
                             owned_input.read_bytes())
            self.assertEqual((out / "packages" / "forza" / "validator-spec.json").read_bytes(),
                             frozen_spec)
            self.assertEqual(json.loads((phase_two / "validator-spec.json").read_text()),
                             {"phase": 2})
            create_job = json.loads((out / "packages" / "pgr2-create" / "job.json").read_text())
            self.assertTrue(create_job["runtimeState"]["keepOnSuccess"])
            self.assertEqual(create_job["runtimeState"]["diskAssets"][0]["assetId"],
                             "pr256-clean-fatx-compat010-v1")
            self.assertTrue((out / "pgr2-reload.template.json").is_file())
            self.assertTrue((out / "doa-reload.template.json").is_file())


if __name__ == "__main__":
    unittest.main()
