#!/usr/bin/env python3
"""自研工具离线回归：不连手机、不注入、不打包。"""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable


class SelfToolsTest(unittest.TestCase):
    def run_cmd(self, *args):
        return subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=30)

    def test_hook_gen_dry_run(self):
        r = self.run_cmd(PY, "scripts/hook_gen.py", "--class", "android.app.Activity",
                         "--method", "onCreate", "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("android.app.Activity.onCreate", r.stdout)

    def test_hook_gen_dry_run_rejects_run(self):
        r = self.run_cmd(PY, "scripts/hook_gen.py", "--class", "android.app.Activity",
                         "--method", "onCreate", "--dry-run", "--run", "--package", "com.example")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_dex_dump_bad_args(self):
        r = self.run_cmd(PY, "scripts/dex_dump.py", "--package", "com.example", "--rounds", "0")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        r = self.run_cmd(PY, "scripts/dex_dump.py", "--package", "com.example", "--protections", "xxx")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_dex_dump_app_detection(self):
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        import dex_dump
        raw = b"Lumito/android/minipiano/ads/Foo;"
        self.assertTrue(dex_dump._looks_like_app(raw, "umito.android.minipiano.cn"))
        self.assertFalse(dex_dump._looks_like_app(raw, "com.example.unknown"))

    def test_build_sign_help_and_missing(self):
        r = self.run_cmd("bash", "scripts/build_sign.sh", "--help")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("用法", r.stdout)
        r = self.run_cmd("bash", "scripts/build_sign.sh", "/no/such/dir")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        r = self.run_cmd("bash", "scripts/build_sign.sh")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
