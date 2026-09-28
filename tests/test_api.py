import json
import os
import sys
import unittest
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "features" / "deployment" / "backend"))

import config
import router


class TestAPIRoutesAndHealth(unittest.TestCase):

    def test_system_health(self):
        health = config.check_system_health()
        self.assertTrue(health["success"])
        self.assertIn("tools", health)
        self.assertIn("python", health["tools"])
        self.assertTrue(health["tools"]["python"]["available"])
        self.assertTrue(health["tools"]["git"]["available"])
        self.assertTrue(health["tools"]["bash"]["available"])

    def test_router_exports(self):
        self.assertTrue(callable(router.check_system_health))
        self.assertTrue(callable(router.get_workspaces_list))
        self.assertTrue(callable(router.get_apps))
        self.assertTrue(callable(router.execute_command))

    def test_workspaces_list(self):
        res = router.get_workspaces_list()
        self.assertTrue(res["success"])
        self.assertIn("active", res)
        self.assertIn("workspaces", res)


if __name__ == "__main__":
    unittest.main()
