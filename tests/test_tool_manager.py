#!/usr/bin/env python3
"""tool_manager 的离线单元测试：不联网、不下载。"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TM = ROOT / "scripts" / "tool_manager.py"
REG = ROOT / "tools" / "registry.json"


class ToolManagerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name) / "state.json"

    def tearDown(self):
        self.tmp.cleanup()

    def run_tm(self, *args):
        return subprocess.run(
            [sys.executable, str(TM), "--state", str(self.state), *args],
            cwd=ROOT, capture_output=True, text=True, timeout=30,
        )

    def test_registry_integrity(self):
        data = json.loads(REG.read_text(encoding="utf-8"))
        ids = [t["id"] for t in data["tools"]]
        self.assertEqual(len(ids), len(set(ids)), "duplicate tool id")
        self.assertEqual(data["policy"]["default_mode"], "thirdparty")
        self.assertEqual(data["policy"]["default_profile"], "minimal")
        self.assertFalse(data["policy"]["bundle_third_party_binaries"])
        for t in data["tools"]:
            self.assertIn(t["type"], {"third_party", "self"})
            self.assertTrue(t.get("license"), t["id"])
            self.assertTrue(t.get("detect"), t["id"])
            if t["type"] == "self":
                self.assertIn(t.get("completeness"), {"stable", "experimental"})

    def test_status_and_plan(self):
        r = self.run_tm("status", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertIn("tools", payload)
        r = self.run_tm("plan", "--task", "decode", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertGreater(len(payload["tools"]), 0)
        self.assertIn("estimated_mb", payload)

    def test_install_requires_yes(self):
        r = self.run_tm("install", "--task", "decode")
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertFalse(self.state.exists() and json.loads(self.state.read_text()).get("installed"))

    def test_mode_and_resolve(self):
        r = self.run_tm("mode", "thirdparty")
        self.assertEqual(r.returncode, 0, r.stderr)
        state = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertEqual(state["mode"], "thirdparty")
        r = self.run_tm("resolve", "--capability", "dynamic")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("mode=thirdparty", r.stdout)

    def test_mode_self(self):
        self.assertEqual(self.run_tm("mode", "self").returncode, 0)
        r = self.run_tm("resolve", "--capability", "dynamic")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("self-hook-gen", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
