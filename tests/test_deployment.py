import json
import os
import sys
import unittest
from pathlib import Path

# Add backend directory to sys.path for importing modules
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "features" / "deployment" / "backend"))

import config
import commands
import jobs
import p8
import router


class TestDeploymentSecurityAndLogic(unittest.TestCase):

    def test_is_prod_store_deploy(self):
        # Valid prod store deploy commands
        self.assertTrue(commands._is_prod_store_deploy("bash run_build.sh deployIPA app1 prod"))
        self.assertTrue(commands._is_prod_store_deploy("bash run_build.sh uploadAAB app1 prod"))
        self.assertTrue(commands._is_prod_store_deploy("bash run_build.sh deployBothPlatforms app1 prod"))

        # Non-prod commands
        self.assertFalse(commands._is_prod_store_deploy("bash run_build.sh deployIPA app1 dev"))
        self.assertFalse(commands._is_prod_store_deploy("bash run_build.sh buildIPA app1 prod"))

        # Bypass attempts with trailing characters or command chaining
        self.assertTrue(commands._is_prod_store_deploy("bash run_build.sh deployIPA app1 prod ; echo pwned"))
        self.assertTrue(commands._is_prod_store_deploy("bash run_build.sh deployIPA app1 prod # trailing comment"))

    def test_path_traversal_protection(self):
        # inspect_workspace_path outside WORKSPACE_ROOT
        res = config.inspect_workspace_path("../../")
        self.assertFalse(res.get("success", True))
        self.assertIn("Path traversal restriction", res.get("error", ""))

    def test_p8_upload_sanitization(self):
        # Invalid AuthKey filename missing Key ID
        res = p8.upload_p8_key("testapp", "invalid_file.p8", b"dummy")
        self.assertFalse(res["success"])
        self.assertIn("Cannot extract Key ID", res["error"])

        # Valid AuthKey filename with path traversal in filename parameter
        res_safe = p8.upload_p8_key("testapp", "../../AuthKey_1234567890.p8", b"dummy_content")
        self.assertTrue(res_safe["success"])
        self.assertEqual(res_safe["key_id"], "1234567890")

    def test_get_commands(self):
        res = commands.get_commands("app1")
        self.assertTrue(res["success"])
        self.assertIsInstance(res["commands"], list)


if __name__ == "__main__":
    unittest.main()
