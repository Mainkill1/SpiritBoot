"""Keep published firmware CI on the independently owned storage backend."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class CandidateReleasePolicyTests(unittest.TestCase):
    def test_firmware_workflow_builds_only_complete_candidate_products(self):
        workflow = (ROOT / ".github/workflows/firmware.yml").read_text(
            encoding="utf-8")
        self.assertNotIn("--storage-backend legacy-reference", workflow)
        self.assertEqual(workflow.count("--storage-backend complete-candidate"), 4)
        self.assertNotIn("storage-completion/check.py", workflow)
        self.assertIn(
            'NXK_STORAGE_BACKEND:STRING=//p\' "$GUEST_BUILD/CMakeCache.txt")" '
            '= complete-candidate', workflow)

    def test_runtime_and_performance_qualification_runs_only_on_release(self):
        workflow = (ROOT / ".github/workflows/firmware.yml").read_text(
            encoding="utf-8")
        for step in (
                "Check the built source identity and actual kernel work",
                "Prepare pinned open runtime fixtures",
                "Build guests from the tested patched source",
                "Run API, contracts, warm reboot, and performance correctness guests"):
            self.assertIn(
                f"- name: {step}\n        if: matrix.variant == 'release'",
                workflow)

    def test_release_guest_artifact_copy_translates_the_container_work_path(self):
        workflow = (ROOT / ".github/workflows/firmware.yml").read_text(
            encoding="utf-8")
        self.assertIn(
            'guest_source_host="$PWD/${guest_source#/work/}"', workflow)
        self.assertIn(
            'cp "$guest_source_host/tests/xbe/cold-storage-persistence/'
            'cold-storage-persistence.iso"', workflow)
        self.assertNotIn(
            'cp "$guest_source/tests/xbe/cold-storage-persistence/'
            'cold-storage-persistence.iso"', workflow)


if __name__ == "__main__":
    unittest.main()
