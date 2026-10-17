# SPDX-License-Identifier: GPL-2.0-only
"""Xbox NtReleaseSemaphore returns its documented overflow error without a halt."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / 'tools/check_kernel_semaphore_overflow.py'


class KernelSemaphoreOverflowTests(unittest.TestCase):
    def check_platform(self, platform):
        subprocess.run([sys.executable, '-B', str(TOOL), '--platform', platform], check=True)

    def test_xbox_overflow_returns_status_and_preserves_atomic_release(self):
        self.check_platform('xbox')

    def test_non_xbox_exception_and_status_behavior_is_preserved(self):
        self.check_platform('nt')
