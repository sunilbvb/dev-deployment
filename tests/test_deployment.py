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
        # Valid prod store deploy commands (legacy text form - backward compat)
        self.assertTrue(commands._is_prod_store_deploy("bash run_build.sh deployIPA app1 prod"))
        self.assertTrue(commands._is_prod_store_deploy("bash run_build.sh uploadAAB app1 prod"))
        self.assertTrue(commands._is_prod_store_deploy("bash run_build.sh deployBothPlatforms app1 prod"))

        # Non-prod commands (legacy form)
        self.assertFalse(commands._is_prod_store_deploy("bash run_build.sh deployIPA app1 dev"))
        self.assertFalse(commands._is_prod_store_deploy("bash run_build.sh buildIPA app1 prod"))

        # Bypass attempts with trailing characters or command chaining (legacy form)
        self.assertTrue(commands._is_prod_store_deploy("bash run_build.sh deployIPA app1 prod ; echo pwned"))
        self.assertTrue(commands._is_prod_store_deploy("bash run_build.sh deployIPA app1 prod # trailing comment"))

    def test_is_prod_store_deploy_explicit_form(self):
        """A1 fix: explicit template_id + flavor form works correctly for all scenarios."""
        # Explicit prod flavor + store template → True
        self.assertTrue(commands._is_prod_store_deploy(template_id="upload_ipa", flavor="prod"))
        self.assertTrue(commands._is_prod_store_deploy(template_id="upload_aab", flavor="prod"))
        self.assertTrue(commands._is_prod_store_deploy(template_id="deploy_ipa", flavor="prod"))
        self.assertTrue(commands._is_prod_store_deploy(template_id="deploy_aab", flavor="prod"))
        self.assertTrue(commands._is_prod_store_deploy(template_id="deploy_both", flavor="prod"))

        # Single-app (no-flavor) = "default" → must ALSO require confirmation
        self.assertTrue(commands._is_prod_store_deploy(template_id="upload_ipa", flavor="default"))
        self.assertTrue(commands._is_prod_store_deploy(template_id="upload_aab", flavor="default"))
        self.assertTrue(commands._is_prod_store_deploy(template_id="upload_aab", flavor=""))

        # Build templates (not store-shipping) → False even with prod flavor
        self.assertFalse(commands._is_prod_store_deploy(template_id="build_ipa", flavor="prod"))
        self.assertFalse(commands._is_prod_store_deploy(template_id="build_aab", flavor="prod"))

        # DEV flavor store template → False
        self.assertFalse(commands._is_prod_store_deploy(template_id="upload_ipa", flavor="dev"))
        self.assertFalse(commands._is_prod_store_deploy(template_id="upload_aab", flavor="qa"))

    def test_scan_android_segment_matching(self):
        """B1 fix: com.devstudio.app must NOT match 'dev'; com.app.dev must match 'dev'."""
        import tempfile, pathlib
        with tempfile.TemporaryDirectory() as td:
            app_path = pathlib.Path(td)
            android_app = app_path / "android" / "app"
            android_app.mkdir(parents=True)

            # 'devstudio' has 'dev' as a substring but NOT as a whole segment → should NOT match dev
            (android_app / "build.gradle").write_text(
                'android {\n  defaultConfig {\n    applicationId "com.devstudio.myapp"\n  }\n}\n',
                encoding="utf-8",
            )
            result = config._scan_android_app_ids(app_path)
            # Should fall through to prod (the base package), NOT android_id_dev
            self.assertNotIn("android_id_dev", result)
            self.assertEqual(result.get("android_package"), "com.devstudio.myapp")

        with tempfile.TemporaryDirectory() as td:
            app_path = pathlib.Path(td)
            android_app = app_path / "android" / "app"
            android_app.mkdir(parents=True)

            # 'com.example.dev' — "dev" IS a whole segment after the last dot → should match dev
            (android_app / "build.gradle").write_text(
                'android {\n  defaultConfig {\n    applicationId "com.example.dev"\n  }\n}\n',
                encoding="utf-8",
            )
            result2 = config._scan_android_app_ids(app_path)
            self.assertIn("android_id_dev", result2)
            self.assertEqual(result2["android_id_dev"], "com.example.dev")

    def test_scan_xcconfig_segment_matching(self):
        """B2 fix: 'devstudio.xcconfig' must NOT match 'dev' flavor; 'Debug-dev.xcconfig' must match."""
        import tempfile, pathlib
        with tempfile.TemporaryDirectory() as td:
            app_path = pathlib.Path(td)
            xcconfig_dir = app_path / "ios" / "Flutter"
            xcconfig_dir.mkdir(parents=True)

            # 'devstudio' contains 'dev' as substring but not whole segment → no flavor match
            (xcconfig_dir / "devstudio.xcconfig").write_text(
                "PRODUCT_BUNDLE_IDENTIFIER = com.example.myapp\n", encoding="utf-8"
            )
            result = config._scan_xcconfig_bundle_ids(app_path)
            # No flavor-suffixed key; just plain bundle_id
            self.assertNotIn("bundle_id_dev", result)
            self.assertEqual(result.get("bundle_id"), "com.example.myapp")

        with tempfile.TemporaryDirectory() as td:
            app_path = pathlib.Path(td)
            xcconfig_dir = app_path / "ios" / "Flutter"
            xcconfig_dir.mkdir(parents=True)

            # 'Debug-dev' — "dev" is a whole segment → should match dev flavor
            (xcconfig_dir / "Debug-dev.xcconfig").write_text(
                "PRODUCT_BUNDLE_IDENTIFIER = com.example.myapp.dev\n", encoding="utf-8"
            )
            result2 = config._scan_xcconfig_bundle_ids(app_path)
            self.assertIn("bundle_id_dev", result2)
            self.assertEqual(result2["bundle_id_dev"], "com.example.myapp.dev")

    def test_detect_app_in_dir_empty_returns_none(self):
        """C1 fix: empty directory must return None, not a generic dict."""
        import tempfile, pathlib
        with tempfile.TemporaryDirectory() as td:
            empty_dir = pathlib.Path(td) / "random_folder"
            empty_dir.mkdir()
            result = config._detect_app_in_dir(empty_dir)
            self.assertIsNone(result, "Empty directory should return None, not a generic app dict")

    def test_detect_app_flutter_package_vs_app(self):
        """C2 fix: Flutter package (no android/ios/main.dart) should be is_package=True.
           Flutter app (has android/ or ios/ or lib/main.dart) should be is_package=False."""
        import tempfile, pathlib
        # Pure package — has pubspec.yaml but no android/, ios/, or lib/main.dart
        with tempfile.TemporaryDirectory() as td:
            pkg_dir = pathlib.Path(td) / "my_utils"
            pkg_dir.mkdir()
            (pkg_dir / "pubspec.yaml").write_text(
                "name: my_utils\nversion: 1.0.0\ndescription: A Dart utility package\n"
                "environment:\n  sdk: '>=3.0.0 <4.0.0'\n",
                encoding="utf-8",
            )
            (pkg_dir / "lib").mkdir()
            (pkg_dir / "lib" / "my_utils.dart").write_text("// library", encoding="utf-8")
            result = config._detect_app_in_dir(pkg_dir)
            self.assertIsNotNone(result)
            self.assertTrue(result["is_package"], "Flutter package without android/ios/main.dart must be is_package=True")

        # App — has pubspec.yaml + android/
        with tempfile.TemporaryDirectory() as td:
            app_dir = pathlib.Path(td) / "my_app"
            (app_dir / "android").mkdir(parents=True)
            (app_dir / "pubspec.yaml").write_text(
                "name: my_app\nversion: 1.0.0\nflutter:\n  uses-material-design: true\n",
                encoding="utf-8",
            )
            result2 = config._detect_app_in_dir(app_dir)
            self.assertIsNotNone(result2)
            self.assertFalse(result2["is_package"], "Flutter app with android/ must be is_package=False")

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

        # A1: store upload commands with "default" flavor must report needsConfirmation
        upload_aab_cmd = next((c for c in cmds if c["templateId"] == "upload_aab"), None)
        if upload_aab_cmd:
            self.assertEqual(upload_aab_cmd["flavor"], "default")
            self.assertTrue(
                commands._is_prod_store_deploy(template_id="upload_aab", flavor=upload_aab_cmd["flavor"]),
                "Single-app store upload (flavor=default) must trigger prod confirmation"
            )

    def test_b5_product_flavors_parsing(self):
        """B5 fix: real productFlavors block in build.gradle is parsed, not random src/ subfolders."""
        import tempfile, pathlib
        with tempfile.TemporaryDirectory() as td:
            app_dir = pathlib.Path(td)
            gradle_file = app_dir / "android" / "app" / "build.gradle"
            gradle_file.parent.mkdir(parents=True)
            gradle_file.write_text(
                'android {\n'
                '    flavorDimensions "default"\n'
                '    productFlavors {\n'
                '        dev {\n'
                '            dimension "default"\n'
                '            applicationIdSuffix ".dev"\n'
                '        }\n'
                '        staging {\n'
                '            dimension "default"\n'
                '        }\n'
                '        prod {\n'
                '            dimension "default"\n'
                '        }\n'
                '    }\n'
                '}\n',
                encoding="utf-8",
            )
            # Create a random subfolder that is NOT in productFlavors
            (app_dir / "android" / "app" / "src" / "not_a_flavor").mkdir(parents=True)

            flavors = config._detect_app_flavors_from_dir(app_dir)
            self.assertIn("dev", flavors)
            self.assertIn("staging", flavors)
            self.assertIn("prod", flavors)
            self.assertNotIn("not_a_flavor", flavors, "Directories in src/ not in productFlavors should be ignored")

    def test_b3_scan_diff_and_force(self):
        """B3 fix: scan_app_config returns diff of old vs new values, and supports force=True."""
        res = config.scan_app_config("dummy_app_alpha", force=True)
        self.assertTrue(res["success"])
        self.assertIn("diff", res)
        self.assertTrue(res["force"])

    def test_b4_rescan_workspace(self):
        """B4 fix: rescan_workspace clears cache and rediscovers workspace apps."""
        res = config.rescan_workspace()
        self.assertTrue(res["success"])
        self.assertIsInstance(res["apps"], list)

    def test_c10_allow_workspace(self):
        """C10 fix: allow_workspace adds a valid directory to workspaces_list.json."""
        import tempfile, pathlib
        with tempfile.TemporaryDirectory() as td:
            res = config.allow_workspace(td)
            self.assertTrue(res["success"])
            self.assertEqual(res["path"], str(pathlib.Path(td).resolve()))

        # Non-existent path fails
        res_bad = config.allow_workspace("/path/that/definitely/does/not/exist_12345")
        self.assertFalse(res_bad["success"])

    def test_c11_template_stack_filtering(self):
        """C11 fix: Flutter templates are skipped for apps with stack='node' or 'react-native'."""
        # Flutter app gets build_aab
        cmds_flutter = commands._build_commands_from_templates("app1", "", False, [], app_stack="flutter")
        self.assertTrue(any(c["templateId"] == "build_aab" for c in cmds_flutter))

        # Node app does NOT get build_aab (it's tagged stacks: ['flutter'])
        cmds_node = commands._build_commands_from_templates("app1", "", False, [], app_stack="node")
        self.assertFalse(any(c["templateId"] == "build_aab" for c in cmds_node))
        # But generic/release templates (like release_preview) are still present
        self.assertTrue(any(c["templateId"] == "release_preview" for c in cmds_node))


if __name__ == "__main__":
    unittest.main()

