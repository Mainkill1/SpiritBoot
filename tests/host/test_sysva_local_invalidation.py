#!/usr/bin/env python3
"""Lock the bounded SYSVA invalidation candidate and its production fixture."""
import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
PATCH_PATH = "patches/roswell/0154-system-va-local-invalidation.patch"


class SysVaLocalInvalidationTests(unittest.TestCase):
    def test_candidate_is_last_and_hash_locked(self):
        lock = json.loads((ROOT / "sources/firmware-lock.json").read_text())
        entry = lock["repositories"]["roswell"]["patches"][-1]
        self.assertEqual(entry["path"], PATCH_PATH)
        self.assertEqual(
            hashlib.sha256((ROOT / PATCH_PATH).read_bytes()).hexdigest(),
            entry["sha256"],
        )

    def test_small_ranges_use_local_invalidation(self):
        patch = (ROOT / PATCH_PATH).read_text()
        self.assertIn("#define NXK_SYSVA_LOCAL_TLB_MAX 4", patch)
        self.assertIn("if (Pages <= NXK_SYSVA_LOCAL_TLB_MAX)", patch)
        self.assertIn("if (Pages > NXK_SYSVA_LOCAL_TLB_MAX)", patch)
        self.assertIn("__invlpg((PVOID)(Va + ((ULONG_PTR)i << PAGE_SHIFT)))", patch)

    def test_free_invalidates_before_returning_the_frame(self):
        patch = (ROOT / PATCH_PATH).read_text()
        clear_at = patch.index("Pte[Idx] = 0;", patch.index("NxkSysVaFree"))
        invalidate_at = patch.index("__invlpg", clear_at)
        return_at = patch.index("NxkPageSupplyReturn", clear_at)
        self.assertLess(clear_at, invalidate_at)
        self.assertLess(invalidate_at, return_at)

    def test_production_body_fixture_covers_small_and_large_policy(self):
        patch = (ROOT / PATCH_PATH).read_text()
        for token in (
            "small SYSVA allocation avoids a global TLB flush",
            "small SYSVA free invalidates each cleared VA before reuse",
            "large SYSVA allocation uses one global TLB flush",
            "large SYSVA free uses one additional global TLB flush",
        ):
            self.assertIn(token, patch)


if __name__ == "__main__":
    unittest.main()
