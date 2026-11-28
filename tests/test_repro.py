"""跨进程复现：调用冒烟脚本比较两个 PYTHONHASHSEED 的结果。"""

import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ReproTest(unittest.TestCase):
    def test_cross_process(self):
        cmd = [sys.executable, os.path.join(ROOT, 'scripts', 'experiment_smoke.py'),
               '--compare', '--days', '1', '--weather', 'sichuan_storm']
        out = subprocess.check_output(cmd, cwd=ROOT, env=dict(os.environ, PYTHONHASHSEED='0'))
        self.assertIn(b'cross-process equal: True', out)


if __name__ == '__main__':
    unittest.main()
