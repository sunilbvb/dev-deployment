import sys
import tempfile
import unittest
from pathlib import Path

# Add backend directory to sys.path for importing modules
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "features" / "deployment" / "backend"))

import commands
import config
import jobs
import p8


class TestDeploymentSecurityAndLogic(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._orig_ws = config.WORKSPACE_ROOT
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.temp_path = Path(cls.temp_dir.name).resolve()
        config.WORKSPACE_ROOT = cls.temp_path

        # Build fake Flutter app dummy_app_alpha
        cls.app_dir = cls.temp_path / "dummy_app_alpha"
        (cls.app_dir / "android" / "app").mkdir(parents=True, exist_ok=True)
        (cls.app_dir / "ios" / "Runner").mkdir(parents=True, exist_ok=True)

        (cls.app_dir / "pubspec.yaml").write_text(
            "name: dummy_app_alpha\n"
            "description: Fake flutter app for tests\n"
            "version: 1.0.0+1\n"
            "flutter:\n"
            "  uses-material-design: true\n",
            encoding="utf-8",
        )
        (cls.app_dir / "android" / "app" / "build.gradle").write_text(
            'android {\n    defaultConfig {\n        applicationId "com.example.dummy_app_alpha"\n    }\n}\n',
            encoding="utf-8",
        )
        (cls.app_dir / "ios" / "Runner" / "Info.plist").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
            '<plist version="1.0">\n'
            '<dict>\n'
            '    <key>CFBundleIdentifier</key>\n'
            '    <string>com.example.dummyAppAlpha</string>\n'
            '</dict>\n'
            '</plist>\n',
            encoding="utf-8",
        )

    @classmethod
    def tearDownClass(cls):
        config.WORKSPACE_ROOT = cls._orig_ws
        cls.temp_dir.cleanup()

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

    def test_app_busy_lock_elapsed_time(self):
        import time
        with jobs._JOBS_LOCK:
            jobs._APP_LOCKS["test_app_lock"] = {
                "job_id": "job_123",
                "flavor": "qa",
                "command": "bash test.sh",
                "started_at": time.time() - 150,
            }
        try:
            res = jobs.execute_command("test_app_lock", "bash test.sh", flavor="qa")
            self.assertFalse(res["success"])
            self.assertEqual(res["code"], "APP_BUSY")
            self.assertIn("running for 2m 30s", res["error"])
            self.assertIn("check the History tab", res["error"])
            self.assertEqual(res["runningJob"]["elapsedSeconds"], 150)
        finally:
            with jobs._JOBS_LOCK:
                jobs._APP_LOCKS.pop("test_app_lock", None)

    def test_scan_app_config_dummy_alpha(self):
        # dummy_app_alpha exists in /home/sunil-bakale/IdeaProjects/dummy_flutter_apps/dummy_app_alpha
        res = config.scan_app_config("dummy_app_alpha")
        self.assertTrue(res["success"])
        self.assertIn("discovered", res)
        d = res["discovered"]
        self.assertEqual(d.get("bundle_id"), "com.example.dummyAppAlpha")
        self.assertEqual(d.get("android_package"), "com.example.dummy_app_alpha")
        self.assertFalse(res["has_flavors"])

    def test_inspect_workspace_path_detection(self):
        res = config.inspect_workspace_path(str(self.app_dir))
        self.assertTrue(res["success"])
        self.assertTrue(res["exists"])
        self.assertIsNotNone(res.get("detectedApp"))
        self.assertEqual(res["detectedApp"]["id"], "dummy_app_alpha")
        self.assertEqual(res["detectedApp"]["stack"], "flutter")

    def test_unflavored_single_app_commands(self):
        # Single app without flavors generates unflavored commands without --flavor
        deploy_cfg = {
            "apps": {
                "dummy_app_alpha": {
                    "flavors": [],
                    "bundle_id": "com.example.dummyAppAlpha",
                    "android_package": "com.example.dummy_app_alpha"
                }
            }
        }
        cmds = commands._build_commands_from_templates("dummy_app_alpha", "", False, [], deploy_cfg)
        aab_cmd = next((c for c in cmds if c["templateId"] == "build_aab"), None)
        self.assertIsNotNone(aab_cmd)
        self.assertEqual(aab_cmd["command"], "flutter build appbundle --release")
        self.assertEqual(aab_cmd["name"], "Build AAB")

        ipa_cmd = next((c for c in cmds if c["templateId"] == "build_ipa"), None)
        self.assertIsNotNone(ipa_cmd)
        self.assertEqual(ipa_cmd["command"], "flutter build ipa --release")
        self.assertEqual(ipa_cmd["name"], "Build IPA")


if __name__ == "__main__":
    unittest.main()
