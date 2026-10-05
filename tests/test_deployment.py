import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add backend directory to sys.path for importing modules
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "features" / "deployment" / "backend"))

import commands
import config
import jobs
import notifications
import p8
import pipelines

from _isolation import isolate_dashboard_config, restore_dashboard_config


def setUpModule():
    isolate_dashboard_config()


def tearDownModule():
    restore_dashboard_config()


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
        import tempfile
        import pathlib
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
        import tempfile
        import pathlib
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
        import tempfile
        import pathlib
        with tempfile.TemporaryDirectory() as td:
            empty_dir = pathlib.Path(td) / "random_folder"
            empty_dir.mkdir()
            result = config._detect_app_in_dir(empty_dir)
            self.assertIsNone(result, "Empty directory should return None, not a generic app dict")

    def test_detect_app_flutter_package_vs_app(self):
        """C2 fix: Flutter package (no android/ios/main.dart) should be is_package=True.
           Flutter app (has android/ or ios/ or lib/main.dart) should be is_package=False."""
        import tempfile
        import pathlib
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
        import tempfile
        import pathlib
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
        import tempfile
        import pathlib
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

    def test_b7_gitignore_auto_added(self):
        """B7 fix: .dev-dashboard/ is auto-added to workspace .gitignore."""
        import tempfile
        import pathlib
        with tempfile.TemporaryDirectory() as td:
            ws = pathlib.Path(td)
            gitignore = ws / ".gitignore"
            gitignore.write_text("node_modules/\n", encoding="utf-8")
            config._ensure_gitignore_has_dashboard(ws)
            content = gitignore.read_text(encoding="utf-8")
            self.assertIn(".dev-dashboard/", content)

    def test_b8_apple_credentials_required(self):
        """B8 fix: iOS upload/deploy commands require Apple ID or key configured."""
        deploy_cfg = {
            "apps": {
                "test_app": {
                    "bundle_id": "com.example.test",
                    # No apple_id or apple_key_id!
                }
            }
        }
        cmds = commands._build_commands_from_templates("test_app", "", False, ["prod"], deploy_cfg)
        upload_cmd = next(c for c in cmds if c["templateId"] == "upload_ipa")
        self.assertFalse(upload_cmd["configured"], "upload_ipa must be marked unconfigured when Apple credentials missing")

        # Now configure apple_id
        deploy_cfg["apps"]["test_app"]["apple_id"] = "dev@example.com"
        cmds2 = commands._build_commands_from_templates("test_app", "", False, ["prod"], deploy_cfg)
        upload_cmd2 = next(c for c in cmds2 if c["templateId"] == "upload_ipa")
        self.assertTrue(upload_cmd2["configured"], "upload_ipa must be marked configured when apple_id present")

    def test_c3_dart_pub_workspace(self):
        """C3 fix: Dart 3.5+ / Melos 7 pub workspaces (workspace: in pubspec.yaml) are discovered."""
        import tempfile
        import pathlib
        with tempfile.TemporaryDirectory() as td:
            ws = pathlib.Path(td)
            (ws / "pubspec.yaml").write_text(
                "name: my_workspace\n"
                "workspace:\n"
                "  - packages/pkg_a\n"
                "  - packages/pkg_b\n",
                encoding="utf-8"
            )
            for pkg in ("pkg_a", "pkg_b"):
                p_dir = ws / "packages" / pkg
                (p_dir / "lib").mkdir(parents=True)
                (p_dir / "lib" / "main.dart").write_text("// main", encoding="utf-8")
                (p_dir / "pubspec.yaml").write_text(f"name: {pkg}\nversion: 1.0.0\n", encoding="utf-8")

            apps, is_mono, _ = config._discover_apps_in_workspace(ws)
            self.assertTrue(is_mono)
            self.assertEqual(len(apps), 2)
            app_ids = [a["id"] for a in apps]
            self.assertIn("pkg_a", app_ids)
            self.assertIn("pkg_b", app_ids)

    def test_c4_melos_globs_and_ignore(self):
        """C4 fix: Melos parser expands globs (apps/**) and respects ignore patterns."""
        import tempfile
        import pathlib
        with tempfile.TemporaryDirectory() as td:
            ws = pathlib.Path(td)
            (ws / "melos.yaml").write_text(
                "name: my_melos\n"
                "packages:\n"
                "  - 'apps/**'\n"
                "ignore:\n"
                "  - '**/example/**'\n",
                encoding="utf-8"
            )
            # Create nested app at apps/client/mobile
            nested_app = ws / "apps" / "client" / "mobile"
            (nested_app / "lib").mkdir(parents=True)
            (nested_app / "lib" / "main.dart").write_text("// main", encoding="utf-8")
            (nested_app / "pubspec.yaml").write_text("name: mobile_client\nversion: 1.0.0\n", encoding="utf-8")

            # Create ignored app in example
            ignored_app = ws / "apps" / "example" / "sample"
            (ignored_app / "lib").mkdir(parents=True)
            (ignored_app / "lib" / "main.dart").write_text("// main", encoding="utf-8")
            (ignored_app / "pubspec.yaml").write_text("name: sample_example\nversion: 1.0.0\n", encoding="utf-8")

            apps, is_mono, has_melos = config._discover_apps_in_workspace(ws)
            self.assertTrue(is_mono)
            self.assertTrue(has_melos)
            app_ids = [a["id"] for a in apps]
            self.assertIn("mobile", app_ids)
            self.assertNotIn("sample", app_ids, "Ignored example app should not be discovered")

    def test_c5_multilevel_discovery(self):
        """C5 fix: multi-level discovery finds apps up to 3 levels deep."""
        import tempfile
        import pathlib
        with tempfile.TemporaryDirectory() as td:
            ws = pathlib.Path(td)
            # App at level 2: repo/mobile/app
            app_dir = ws / "subfolder" / "deep_app"
            (app_dir / "lib").mkdir(parents=True)
            (app_dir / "lib" / "main.dart").write_text("// main", encoding="utf-8")
            (app_dir / "pubspec.yaml").write_text("name: deep_app\nversion: 1.0.0\n", encoding="utf-8")

            apps, _, _ = config._discover_apps_in_workspace(ws)
            self.assertEqual(len(apps), 1)
            self.assertEqual(apps[0]["id"], "deep_app")

    def test_c6_duplicate_app_ids_disambiguated(self):
        """C6 fix: duplicate app IDs are disambiguated with path info instead of dropped."""
        import tempfile
        import pathlib
        with tempfile.TemporaryDirectory() as td:
            ws = pathlib.Path(td)
            for parent in ("apps", "packages"):
                p_dir = ws / parent / "core"
                (p_dir / "lib").mkdir(parents=True)
                (p_dir / "lib" / "main.dart").write_text("// main", encoding="utf-8")
                (p_dir / "pubspec.yaml").write_text("name: core\nversion: 1.0.0\n", encoding="utf-8")

            apps, _, _ = config._discover_apps_in_workspace(ws)
            self.assertEqual(len(apps), 2, "Both core projects should be discovered")
            app_ids = [a["id"] for a in apps]
            self.assertNotEqual(app_ids[0], app_ids[1], "IDs must be disambiguated")

    def test_c7_app_lock_scoped_to_workspace(self):
        """C7 fix: app locks are workspace-scoped."""
        import tempfile
        import pathlib
        with tempfile.TemporaryDirectory() as td1, tempfile.TemporaryDirectory() as td2:
            ws1 = pathlib.Path(td1)
            ws2 = pathlib.Path(td2)

            token1 = config.set_request_workspace(ws1)
            try:
                # Lock app in workspace 1
                lock_k1 = f"{ws1.resolve()}:my_app"
                with jobs._JOBS_LOCK:
                    jobs._APP_LOCKS[lock_k1] = {
                        "job_id": "job_1",
                        "flavor": "dev",
                        "command": "echo 1",
                        "started_at": 1000,
                        "workspace": str(ws1.resolve()),
                        "app": "my_app",
                    }
            finally:
                config.reset_request_workspace(token1)

            # In workspace 2, the same app name is NOT locked
            token2 = config.set_request_workspace(ws2)
            try:
                ws_now = config.get_workspace_root()
                self.assertEqual(ws_now, ws2)
                lock_k2 = f"{ws2.resolve()}:my_app"
                self.assertNotIn(lock_k2, jobs._APP_LOCKS)
            finally:
                config.reset_request_workspace(token2)
                with jobs._JOBS_LOCK:
                    jobs._APP_LOCKS.pop(lock_k1, None)

    def test_c8_get_running_jobs(self):
        """C8 fix: get_running_jobs returns jobs across all workspaces."""
        with jobs._JOBS_LOCK:
            jobs._APP_LOCKS["dummy_ws:dummy_app"] = {
                "job_id": "job_999",
                "app": "dummy_app",
                "flavor": "prod",
                "command": "flutter build",
                "started_at": 100,
                "workspace": "/dummy_ws",
            }
        try:
            running = jobs.get_running_jobs()
            found = any(j.get("jobId") == "job_999" for j in running)
            self.assertTrue(found)
        finally:
            with jobs._JOBS_LOCK:
                jobs._APP_LOCKS.pop("dummy_ws:dummy_app", None)

    def test_c9_request_scoped_workspace(self):
        """C9 fix: request-scoped workspace via set_request_workspace works without race conditions."""
        import tempfile
        import pathlib
        with tempfile.TemporaryDirectory() as td:
            custom_ws = pathlib.Path(td)
            self.assertNotEqual(config.get_workspace_root(), custom_ws)
            token = config.set_request_workspace(custom_ws)
            try:
                self.assertEqual(config.get_workspace_root(), custom_ws)
            finally:
                config.reset_request_workspace(token)
            self.assertNotEqual(config.get_workspace_root(), custom_ws)

    def test_c12_workspace_missing_flag(self):
        """C12 fix: get_workspaces_list reports workspaceMissing when active workspace was not found."""
        config.WORKSPACE_MISSING = "/nonexistent/path/for/test"
        try:
            res = config.get_workspaces_list()
            self.assertEqual(res.get("workspaceMissing"), "/nonexistent/path/for/test")
        finally:
            config.WORKSPACE_MISSING = None

    def test_history_entry_enrichment(self):
        """Verify _record_history_entry populates completedAt, durationSeconds, errorExcerpt, outputExcerpt, and flavor."""
        test_job_id = "job_test_enrichment_123"
        with jobs._JOBS_LOCK:
            jobs._JOBS[test_job_id] = {
                "id": test_job_id,
                "app": "dummy_app_alpha",
                "command": "make test",
                "status": "success",
                "return_code": 0,
                "started_at": 1000.0,
                "finished_at": 1015.0,
                "env": "prod",
                "flavor": "prod",
                "template_id": "deploy_aab",
                "error": "line 1\nline 2\nwarning: something minor",
                "output": "step 1\nstep 2\nSUCCESS: uploaded AAB",
            }
        try:
            jobs._record_history_entry(test_job_id, chained_job_id="job_parent_001")
            history = jobs.get_deployment_history(limit=5, app="dummy_app_alpha", flavor="prod")
            self.assertTrue(history.get("success"))
            entries = [e for e in history.get("entries", []) if e.get("id") == test_job_id]
            self.assertTrue(len(entries) > 0)
            entry = entries[0]
            self.assertEqual(entry.get("completedAt"), 1015000)
            self.assertEqual(entry.get("durationSeconds"), 15)
            self.assertEqual(entry.get("chainedJobId"), "job_parent_001")
            self.assertIn("uploaded AAB", entry.get("outputExcerpt", ""))
            self.assertIn("something minor", entry.get("errorExcerpt", ""))
        finally:
            with jobs._JOBS_LOCK:
                jobs._JOBS.pop(test_job_id, None)

    def test_check_ios_expiry_timezone(self):
        """Verify check_ios_expiry generates ISO 8601 UTC timestamp cleanly."""
        res = jobs.check_ios_expiry("dummy_app_alpha", flavor="prod")
        self.assertTrue(res.get("success"))
        checked_at = res.get("checkedAt")
        self.assertIsNotNone(checked_at)
        self.assertTrue(checked_at.endswith("+00:00") or checked_at.endswith("Z"))


if __name__ == "__main__":
    unittest.main()



def _flutter_app(path: Path, name: str, entry: str = "main.dart") -> None:
    (path / "lib").mkdir(parents=True, exist_ok=True)
    (path / "lib" / entry).write_text("void main() {}\n", encoding="utf-8")
    (path / "android" / "app").mkdir(parents=True, exist_ok=True)
    (path / "ios" / "Runner.xcodeproj").mkdir(parents=True, exist_ok=True)
    (path / "pubspec.yaml").write_text(f"name: {name}\nversion: 1.0.0+1\n", encoding="utf-8")


def _flutter_package(path: Path, name: str, plugin: bool = False) -> None:
    (path / "lib").mkdir(parents=True, exist_ok=True)
    (path / "lib" / f"{name}.dart").write_text("library;\n", encoding="utf-8")
    text = f"name: {name}\nversion: 0.1.0\n"
    if plugin:
        (path / "android").mkdir(exist_ok=True)
        (path / "ios").mkdir(exist_ok=True)
        text += "flutter:\n  plugin:\n    platforms:\n      android:\n        package: x\n"
    (path / "pubspec.yaml").write_text(text, encoding="utf-8")


class TestWorkspaceLayouts(unittest.TestCase):

    def _discover(self, ws: Path) -> dict[str, bool]:
        apps, _, _ = config._discover_apps_in_workspace(ws)
        return {a["id"]: a["is_package"] for a in apps}

    def test_melos_pub_workspace_with_nested_packages_and_plugin(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            (ws / "pubspec.yaml").write_text(
                "name: ws\nworkspace:\n  - apps/shop\n  - packages/profile\n"
                "  - packages/profile/profile_logic\n  - packages/tracker\n"
                "melos:\n  scripts: {}\n", encoding="utf-8")
            _flutter_app(ws / "apps" / "shop", "shop")
            _flutter_package(ws / "packages" / "profile", "profile")
            _flutter_package(ws / "packages" / "profile" / "profile_logic", "profile_logic")
            _flutter_package(ws / "packages" / "tracker", "tracker", plugin=True)
            _flutter_app(ws / "packages" / "tracker" / "example", "tracker_example")
            found = self._discover(ws)
            self.assertEqual(found, {"shop": False, "profile": True, "profile_logic": True, "tracker": True})

    def test_melos_yaml_glob_does_not_pick_platform_folders(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            (ws / "melos.yaml").write_text("name: m\npackages:\n  - apps/**\n  - packages/*\n", encoding="utf-8")
            _flutter_app(ws / "apps" / "a1", "a1")
            _flutter_package(ws / "packages" / "core", "core")
            self.assertEqual(self._discover(ws), {"a1": False, "core": True})

    def test_single_flutter_project(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            _flutter_app(ws, "solo", entry="main_dev.dart")
            self.assertEqual(self._discover(ws), {ws.name.lower(): False})

    def test_single_project_with_local_packages(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            _flutter_app(ws, "solo")
            _flutter_package(ws / "packages" / "ui_kit", "ui_kit")
            self.assertEqual(self._discover(ws), {ws.name.lower(): False, "ui_kit": True})

    def test_folder_of_independent_apps(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            _flutter_app(ws / "app_one", "app_one")
            _flutter_app(ws / "app_two", "app_two")
            self.assertEqual(self._discover(ws), {"app_one": False, "app_two": False})

    def test_folders_with_shared_packages_without_melos(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            _flutter_app(ws / "mobile" / "customer", "customer")
            _flutter_app(ws / "mobile" / "driver", "driver")
            _flutter_package(ws / "shared" / "api_client", "api_client")
            _flutter_package(ws / "shared" / "design", "design")
            self.assertEqual(self._discover(ws), {
                "customer": False, "driver": False, "api_client": True, "design": True})


P8_PEM = b"-----BEGIN PRIVATE KEY-----\nMIGTAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBHkwdwIBAQQg\n-----END PRIVATE KEY-----\n"
SERVICE_ACCOUNT = (
    b'{"type": "service_account", "project_id": "demo-proj", "private_key": "-----BEGIN PRIVATE KEY-----\\nX\\n-----END PRIVATE KEY-----\\n",'
    b' "client_email": "deployer@demo-proj.iam.gserviceaccount.com"}'
)


class TestCredentials(unittest.TestCase):

    def setUp(self):
        import credentials
        self.cred = credentials
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name).resolve()
        self.ws = base / "ws"
        self.home = base / "home"
        self._saved = (credentials.CONFIG_DIR, credentials.KEYS_DIR, credentials.STORE_FILE,
                       credentials.APPLE_KEYS_DIR, config.WORKSPACE_ROOT)
        credentials.CONFIG_DIR = self.home / "cfg"
        credentials.KEYS_DIR = self.home / "cfg" / "keys"
        credentials.STORE_FILE = self.home / "cfg" / "credentials.json"
        credentials.APPLE_KEYS_DIR = self.home / "apple"
        config.WORKSPACE_ROOT = self.ws
        app = self.ws / "apps" / "shop"
        (app / "lib").mkdir(parents=True)
        (app / "lib" / "main.dart").write_text("void main() {}\n", encoding="utf-8")
        (app / "pubspec.yaml").write_text("name: shop\n", encoding="utf-8")
        (app / "android" / "app").mkdir(parents=True)
        (app / "android" / "app" / "build.gradle").write_text(
            'android { defaultConfig { applicationId "com.acme.shop" } }\n', encoding="utf-8")
        self.downloads = base / "Downloads"
        (self.downloads / "nested").mkdir(parents=True)
        (self.downloads / "nested" / "random-name.json").write_bytes(SERVICE_ACCOUNT)
        (self.downloads / "AuthKey_ABCDE12345.p8").write_bytes(P8_PEM)
        (self.downloads / "google-services.json").write_text(
            '{"project_info": {"project_id": "demo"}, "client": [{"client_info": {"android_client_info": {"package_name": "com.acme.shop"}}}]}',
            encoding="utf-8")
        (self.downloads / "package.json").write_text('{"name": "not-a-key"}', encoding="utf-8")

    def tearDown(self):
        c = self.cred
        c.CONFIG_DIR, c.KEYS_DIR, c.STORE_FILE, c.APPLE_KEYS_DIR, config.WORKSPACE_ROOT = self._saved
        self.tmp.cleanup()

    def test_scan_identifies_keys_by_content_and_matches_apps(self):
        res = self.cred.scan_credentials(str(self.downloads))
        self.assertTrue(res["success"])
        kinds = {f["kind"]: f for f in res["found"]}
        self.assertEqual(set(kinds), {"play_service_account", "apple_p8", "firebase_android"})
        self.assertEqual(kinds["play_service_account"]["client_email"], "deployer@demo-proj.iam.gserviceaccount.com")
        self.assertEqual(kinds["apple_p8"]["key_id"], "ABCDE12345")
        self.assertIn({"app": "shop", "flavor": "default"}, kinds["firebase_android"]["matches"])
        self.assertNotIn("private_key", json.dumps(res))

    def test_import_play_key_is_private_and_reaches_job_env(self):
        res = self.cred.import_credential_path(str(self.downloads / "nested" / "random-name.json"))
        self.assertTrue(res["success"], res)
        stored = Path(res["stored_path"])
        self.assertTrue(str(stored).startswith(str(self.home)))
        self.assertEqual(stored.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.cred.job_env("shop")["SERVICE_ACCOUNT_JSON"], str(stored))
        self.assertFalse(any(self.ws.rglob("*play-*.json")), "key must not be copied into the workspace")

    def test_app_level_p8_overrides_workspace_and_sets_apple_env(self):
        self.cred.import_credential_path(str(self.downloads / "AuthKey_ABCDE12345.p8"),
                                         issuer_id="11111111-2222-3333-4444-555555555555")
        other = self.downloads / "AuthKey_ZZZZZ99999.p8"
        other.write_bytes(P8_PEM)
        self.cred.import_credential_path(str(other), app_id="shop")
        env = self.cred.job_env("shop")
        self.assertEqual(env["APPLE_API_KEY"], "ZZZZZ99999")
        self.assertEqual(env["APPLE_API_ISSUER"], "11111111-2222-3333-4444-555555555555")
        self.assertTrue(Path(env["APPLE_API_KEY_PATH"]).is_file())

    def test_rejects_non_keys_and_bad_input(self):
        self.assertFalse(self.cred.import_credential_path(str(self.downloads / "package.json"))["success"])
        self.assertFalse(self.cred.import_credential_bytes("AuthKey_ABCDE12345.p8", b"not a key")["success"])
        self.assertFalse(self.cred.import_credential_bytes("key.p8", P8_PEM)["success"], "key id required")
        self.assertFalse(self.cred.import_credential_bytes("x.json", SERVICE_ACCOUNT, app_id="../evil")["success"])
        res = p8.upload_p8_key("shop", "../../AuthKey_ABCDE12345.p8", P8_PEM)
        self.assertTrue(res["success"])
        self.assertEqual(Path(res["stored_path"]).parent, self.cred.APPLE_KEYS_DIR)

    def test_inline_p8_is_migrated_out_of_deploy_config(self):
        import base64
        cfg_file = config.get_deploy_config_file()
        cfg_file.write_text(json.dumps({"apps": {"shop": {
            "apple_key_id": "ABCDE12345", "apple_p8_base64": base64.b64encode(P8_PEM).decode()}}}), encoding="utf-8")
        self.cred.migrate_inline_p8()
        self.assertNotIn("apple_p8_base64", cfg_file.read_text(encoding="utf-8"))
        self.assertEqual(self.cred.job_env("shop")["APPLE_API_KEY"], "ABCDE12345")

    def test_other_p8_keys_are_hidden_and_not_importable(self):
        (self.downloads / "SubscriptionKey_VSN447PHNL.p8").write_bytes(P8_PEM)
        res = self.cred.scan_credentials(str(self.downloads))
        self.assertNotIn("apple_other_p8", [f["kind"] for f in res["found"]])
        self.assertEqual(res["hidden_other_p8"], 1)
        res = self.cred.import_credential_path(str(self.downloads / "SubscriptionKey_VSN447PHNL.p8"))
        self.assertFalse(res["success"])

    def test_scan_dedupes_identical_copies_and_reports_usage(self):
        (self.downloads / "copy").mkdir()
        (self.downloads / "copy" / "AuthKey_ABCDE12345.p8").write_bytes(P8_PEM)
        self.cred.import_credential_path(str(self.downloads / "AuthKey_ABCDE12345.p8"), app_id="shop")
        p8s = [f for f in self.cred.scan_credentials(str(self.downloads))["found"] if f["kind"] == "apple_p8"]
        self.assertEqual(len(p8s), 1)
        self.assertEqual(len(p8s[0]["paths"]), 2)
        self.assertEqual(p8s[0]["in_use_by"], ["shop"])

    def test_env_file_apple_key_is_flavor_specific_and_unlocks_ios_upload(self):
        import commands
        app = self.ws / "apps" / "shop"
        (app / "env").mkdir()
        (app / "env" / "dev.json").write_text('{"APPLE_API_KEY": "DEVKEY1234", "APPLE_API_ISSUER": "i"}', encoding="utf-8")
        (app / "env" / "qa.json").write_text('{"APPLE_API_KEY": "QAKEY12345", "APPLE_API_ISSUER": "i"}', encoding="utf-8")
        self.cred.APPLE_KEYS_DIR.mkdir(parents=True)
        (self.cred.APPLE_KEYS_DIR / "AuthKey_QAKEY12345.p8").write_bytes(P8_PEM)
        self.assertEqual(self.cred.get_credentials_status("shop", "qa")["apple"]["source"], "env file (qa.json)")
        self.assertEqual(self.cred.get_credentials_status("shop", "dev")["apple"]["key_id"], "DEVKEY1234")
        cfg = {"apps": {"shop": {"bundle_id": "com.acme.shop"}}}
        self.assertTrue(commands._is_flavor_configured("shop", "qa", "deploy_ipa", deploy_cfg=cfg))
        # dev's key file is missing, so dev iOS uploads stay locked
        self.assertFalse(commands._is_flavor_configured("shop", "dev", "deploy_ipa", deploy_cfg=cfg))

    def test_conventional_play_key_is_auto_detected(self):
        (self.ws / "private_keys").mkdir()
        (self.ws / "private_keys" / "play-store-deployer.json").write_bytes(SERVICE_ACCOUNT)
        status = self.cred.get_credentials_status("shop")
        self.assertEqual(status["play"]["source"], "auto")
        self.assertTrue(status["play"]["valid"])
        self.assertIn("SERVICE_ACCOUNT_JSON", self.cred.job_env("shop"))


class TestNativePicker(unittest.TestCase):

    def test_applescript_quotes_are_escaped(self):
        import picker
        cmd = picker._mac_command("file", 'Pick "x" \\ now', "", ["p8"])
        self.assertEqual(cmd[:2], ["osascript", "-e"])
        self.assertIn('with prompt "Pick \\"x\\" \\\\ now"', cmd[2])
        self.assertIn('of type {"p8"}', cmd[2])

    def test_rejects_unknown_kind(self):
        import picker
        self.assertFalse(picker.pick_path("anything")["success"])


class TestImportLayouts(unittest.TestCase):
    """Import Project must classify every supported folder layout."""

    def _inspect(self, ws: Path) -> dict:
        import picker
        picker._PICKED_PATHS.add(str(ws.resolve()))
        return config.inspect_workspace_path(str(ws))

    def test_all_layouts(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td).resolve()
            _flutter_app(base / "c1" / "app_a", "app_a")
            _flutter_app(base / "c1" / "app_b", "app_b")
            _flutter_app(base / "c2" / "app_a", "app_a")
            _flutter_package(base / "c2" / "packages" / "core", "core")
            _flutter_app(base / "c3" / "apps" / "app_a", "app_a")
            _flutter_package(base / "c3" / "packages" / "core", "core")
            (base / "c3" / "melos.yaml").write_text("name: ws\npackages:\n  - apps/*\n  - packages/*\n", encoding="utf-8")
            _flutter_app(base / "c4" / "mobile" / "app_a", "app_a")
            _flutter_package(base / "c4" / "shared" / "ui", "ui")
            _flutter_app(base / "c5", "solo")
            _flutter_package(base / "c5" / "packages" / "ui", "ui")
            expected = {
                "c1": ("Multiple apps (no packages, no Melos)", 2, 0),
                "c2": ("Multiple apps with shared packages (no Melos)", 1, 1),
                "c3": ("Melos monorepo (apps + packages)", 1, 1),
                "c4": ("Multiple apps with shared packages (no Melos)", 1, 1),
                "c5": ("Single app with local packages", 1, 1),
            }
            for name, (layout, n_apps, n_pkgs) in expected.items():
                res = self._inspect(base / name)
                self.assertTrue(res["success"], res)
                self.assertEqual((res["layout"], res["appCount"], res["packageCount"]), (layout, n_apps, n_pkgs), name)

    def test_unpicked_folder_outside_roots_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            res = config.inspect_workspace_path(td)
            self.assertFalse(res["success"])


class TestPerTabWorkspace(unittest.TestCase):

    def test_job_threads_keep_the_request_workspace(self):
        import threading
        with tempfile.TemporaryDirectory() as td:
            seen = {}
            done = threading.Event()

            def record():
                seen["root"] = config.get_workspace_root()
                done.set()

            token = config.set_request_workspace(Path(td))
            try:
                jobs._start_in_context(record)
            finally:
                config.reset_request_workspace(token)
            self.assertTrue(done.wait(5))
            self.assertEqual(seen["root"], Path(td))


class TestAutoRelease(unittest.TestCase):

    def _decide(self, app_cfg, env):
        with tempfile.TemporaryDirectory() as td:
            token = config.set_request_workspace(Path(td))
            try:
                config.get_deploy_config_file().write_text(json.dumps({"apps": {"shop": app_cfg}}), encoding="utf-8")
                return jobs._release_auto_chain_configured("shop", env)
            finally:
                config.reset_request_workspace(token)

    def test_uses_the_settings_saved_by_the_release_tab(self):
        cfg = {"auto_release_on_success": True, "auto_release_action": "release_tag", "auto_release_flavors": ["qa"]}
        self.assertEqual(self._decide(cfg, "qa"), (True, "release_tag"))
        self.assertEqual(self._decide(cfg, "prod"), (False, ""))
        self.assertEqual(self._decide({"auto_release_on_success": False}, "prod"), (False, ""))

    def test_defaults_and_flavorless_apps(self):
        self.assertEqual(self._decide({"auto_release_on_success": True}, "default"), (True, "release_push"))
        self.assertEqual(self._decide({"auto_release_tag": True}, "prod"), (True, "release_push"))
        self.assertEqual(self._decide({"auto_release_on_success": True, "auto_release_action": "build_aab"}, "prod"), (False, ""))


class TestRemoveWorkspace(unittest.TestCase):

    def test_remove_only_drops_the_list_entry(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td).resolve()
            (base / "config").mkdir()
            project = base / "proj"
            _flutter_app(project, "proj")
            saved_root, saved_ws = config.DASHBOARD_ROOT, config.WORKSPACE_ROOT
            config.DASHBOARD_ROOT, config.WORKSPACE_ROOT = base, base / "default"
            (base / "default").mkdir()
            try:
                self.assertTrue(config.allow_workspace(str(project))["success"])
                listed = [w["path"] for w in config.get_workspaces_list()["workspaces"]]
                self.assertIn(str(project), listed)
                self.assertTrue(config.remove_workspace(str(project))["success"])
                listed = config.get_workspaces_list()["workspaces"]
                self.assertNotIn(str(project), [w["path"] for w in listed])
                self.assertTrue(project.is_dir(), "the folder itself must stay")
                self.assertTrue(all(w["isDefault"] for w in listed))
                self.assertFalse(config.remove_workspace(str(base / "default"))["success"])
                self.assertFalse(config.remove_workspace(str(project))["success"])
            finally:
                config.DASHBOARD_ROOT, config.WORKSPACE_ROOT = saved_root, saved_ws


class TestPipelines(unittest.TestCase):

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.base = Path(self.td.name).resolve()
        self.orig_ws = config.WORKSPACE_ROOT
        config.WORKSPACE_ROOT = self.base

        # Create mock app
        self.app_dir = self.base / "app_alpha"
        self.app_dir.mkdir(parents=True)
        (self.app_dir / "pubspec.yaml").write_text("name: app_alpha\nversion: 1.0.0+1\n", encoding="utf-8")
        (self.app_dir / "android" / "app").mkdir(parents=True)
        (self.app_dir / "android" / "app" / "build.gradle").write_text('android { defaultConfig { applicationId "com.example.alpha" } }', encoding="utf-8")

        # Create basic deploy_config.json
        cfg_dir = self.base / ".dev-dashboard"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        self.cfg_file = cfg_dir / "deploy_config.json"
        self.cfg_file.write_text(json.dumps({
            "apps": {
                "app_alpha": {
                    "flavors": ["dev", "qa", "prod"],
                    "bundle_id": "com.example.alpha",
                    "android_package": "com.example.alpha",
                }
            }
        }), encoding="utf-8")

    def tearDown(self):
        config.WORKSPACE_ROOT = self.orig_ws
        self.td.cleanup()

    def test_pipeline_schema_validation(self):
        # 1. Valid pipeline saves
        valid_cfg = {
            "apps": {
                "app_alpha": {
                    "pipelines": [
                        {
                            "id": "qa-workflow",
                            "name": "QA Workflow",
                            "flavor": "qa",
                            "steps": [
                                {"templateId": "pub_get"},
                                {"templateId": "clean", "continueOnFailure": True},
                            ]
                        }
                    ]
                }
            }
        }
        res = config.save_deploy_config(valid_cfg)
        self.assertTrue(res.get("success"), res.get("error"))

        # 2. Invalid ID (uppercase / spaces)
        bad_id_cfg = json.loads(json.dumps(valid_cfg))
        bad_id_cfg["apps"]["app_alpha"]["pipelines"][0]["id"] = "QA Workflow Invalid"
        self.assertFalse(config.save_deploy_config(bad_id_cfg)["success"])

        # 3. Duplicate IDs
        dup_cfg = json.loads(json.dumps(valid_cfg))
        dup_cfg["apps"]["app_alpha"]["pipelines"].append({
            "id": "qa-workflow",
            "name": "Another Workflow",
            "steps": [{"templateId": "pub_get"}],
        })
        self.assertFalse(config.save_deploy_config(dup_cfg)["success"])

        # 4. Empty steps
        empty_steps_cfg = json.loads(json.dumps(valid_cfg))
        empty_steps_cfg["apps"]["app_alpha"]["pipelines"][0]["steps"] = []
        self.assertFalse(config.save_deploy_config(empty_steps_cfg)["success"])

        # 5. Over 20 steps
        too_many_cfg = json.loads(json.dumps(valid_cfg))
        too_many_cfg["apps"]["app_alpha"]["pipelines"][0]["steps"] = [{"templateId": "pub_get"}] * 21
        self.assertFalse(config.save_deploy_config(too_many_cfg)["success"])

    def test_pipeline_resolution_and_confirmation(self):
        cfg = {
            "apps": {
                "app_alpha": {
                    "flavors": ["dev", "prod"],
                    "bundle_id": "com.example.alpha",
                    "android_package": "com.example.alpha",
                    "pipelines": [
                        {
                            "id": "dev-build",
                            "name": "Dev Build",
                            "flavor": "dev",
                            "steps": [
                                {"templateId": "pub_get"},
                                {"templateId": "build_apk"},
                            ]
                        },
                        {
                            "id": "prod-release",
                            "name": "Prod Release",
                            "flavor": "prod",
                            "steps": [
                                {"templateId": "pub_get"},
                                {"templateId": "deploy_aab"},
                            ]
                        },
                        {
                            "id": "custom-pipe",
                            "name": "Custom Pipeline",
                            "flavor": "dev",
                            "steps": [
                                {"command": "echo test custom step", "name": "Echo step"},
                            ]
                        }
                    ]
                }
            }
        }
        config.save_deploy_config(cfg)

        # Non-prod build pipeline should not need confirmation
        dev_res = pipelines.resolve_pipeline("app_alpha", "dev-build")
        self.assertTrue(dev_res.get("success"), dev_res.get("error"))
        self.assertFalse(dev_res.get("needsConfirmation"))
        self.assertEqual(len(dev_res.get("steps", [])), 2)

        # Prod store deploy pipeline must need confirmation
        prod_res = pipelines.resolve_pipeline("app_alpha", "prod-release")
        self.assertTrue(prod_res.get("success"))
        self.assertTrue(prod_res.get("needsConfirmation"))

        # Custom shell step must always require confirmation
        custom_res = pipelines.resolve_pipeline("app_alpha", "custom-pipe")
        self.assertTrue(custom_res.get("success"))
        self.assertTrue(custom_res.get("needsConfirmation"))
        self.assertTrue(custom_res["steps"][0]["isCustom"])

    def test_pipeline_execution_happy_path(self):
        cfg = {
            "apps": {
                "app_alpha": {
                    "bundle_id": "com.example.alpha",
                    "android_package": "com.example.alpha",
                    "pipelines": [
                        {
                            "id": "fast-seq",
                            "name": "Fast Sequence",
                            "steps": [
                                {"command": "echo 'step 1 output'"},
                                {"command": "echo 'step 2 output'"},
                                {"command": "echo 'step 3 output'"},
                            ]
                        }
                    ]
                }
            }
        }
        config.save_deploy_config(cfg)

        # Requires confirmation because of custom commands
        unconfirmed = pipelines.run_pipeline("app_alpha", "fast-seq", confirmed=False)
        self.assertFalse(unconfirmed.get("success"))
        self.assertTrue(unconfirmed.get("needsConfirmation"))

        # Run with confirmation
        run_res = pipelines.run_pipeline("app_alpha", "fast-seq", confirmed=True)
        self.assertTrue(run_res.get("success"), run_res.get("error"))
        run_id = run_res["runId"]

        # Wait for pipeline to finish
        import time
        for _ in range(50):
            status_res = pipelines.get_pipeline_run(run_id)
            self.assertTrue(status_res.get("success"))
            if status_res["run"]["status"] in ("success", "error", "stopped"):
                break
            time.sleep(0.1)

        final_run = pipelines.get_pipeline_run(run_id)["run"]
        self.assertEqual(final_run["status"], "success")
        self.assertEqual(len(final_run["steps"]), 3)
        self.assertTrue(all(s["status"] == "success" for s in final_run["steps"]))

        # Verify deployment history contains pipeline run
        history = jobs.get_deployment_history(app="app_alpha")
        self.assertTrue(history.get("success"))
        pipe_entries = [e for e in history.get("entries", []) if e.get("type") == "pipeline" and e.get("id") == run_id]
        self.assertEqual(len(pipe_entries), 1)
        self.assertEqual(pipe_entries[0]["status"], "success")

    def test_pipeline_execution_stop_on_failure(self):
        cfg = {
            "apps": {
                "app_alpha": {
                    "bundle_id": "com.example.alpha",
                    "android_package": "com.example.alpha",
                    "pipelines": [
                        {
                            "id": "failing-seq",
                            "name": "Failing Sequence",
                            "steps": [
                                {"command": "echo 'step 1'"},
                                {"command": "exit 1"},
                                {"command": "echo 'step 3'"},
                            ]
                        }
                    ]
                }
            }
        }
        config.save_deploy_config(cfg)

        run_res = pipelines.run_pipeline("app_alpha", "failing-seq", confirmed=True)
        self.assertTrue(run_res.get("success"))
        run_id = run_res["runId"]

        import time
        for _ in range(50):
            status_res = pipelines.get_pipeline_run(run_id)
            if status_res["run"]["status"] in ("success", "error", "stopped"):
                break
            time.sleep(0.1)

        final_run = pipelines.get_pipeline_run(run_id)["run"]
        self.assertEqual(final_run["status"], "error")
        self.assertEqual(final_run["failedStep"], 2)
        self.assertEqual(final_run["steps"][0]["status"], "success")
        self.assertEqual(final_run["steps"][1]["status"], "error")
        self.assertEqual(final_run["steps"][2]["status"], "skipped")

    def test_pipeline_execution_continue_on_failure(self):
        cfg = {
            "apps": {
                "app_alpha": {
                    "bundle_id": "com.example.alpha",
                    "android_package": "com.example.alpha",
                    "pipelines": [
                        {
                            "id": "continue-seq",
                            "name": "Continue Sequence",
                            "steps": [
                                {"command": "echo 'step 1'"},
                                {"command": "exit 1", "continueOnFailure": True},
                                {"command": "echo 'step 3'"},
                            ]
                        }
                    ]
                }
            }
        }
        config.save_deploy_config(cfg)

        run_res = pipelines.run_pipeline("app_alpha", "continue-seq", confirmed=True)
        self.assertTrue(run_res.get("success"))
        run_id = run_res["runId"]

        import time
        for _ in range(50):
            status_res = pipelines.get_pipeline_run(run_id)
            if status_res["run"]["status"] in ("success", "error", "stopped"):
                break
            time.sleep(0.1)

        final_run = pipelines.get_pipeline_run(run_id)["run"]
        self.assertEqual(final_run["status"], "success")
        self.assertEqual(final_run["steps"][0]["status"], "success")
        self.assertEqual(final_run["steps"][1]["status"], "error")
        self.assertEqual(final_run["steps"][2]["status"], "success")

    def test_pipeline_app_lock_exclusive(self):
        cfg = {
            "apps": {
                "app_alpha": {
                    "bundle_id": "com.example.alpha",
                    "android_package": "com.example.alpha",
                    "pipelines": [
                        {
                            "id": "long-pipe",
                            "name": "Long Pipeline",
                            "steps": [
                                {"command": "sleep 1"},
                            ]
                        }
                    ]
                }
            }
        }
        config.save_deploy_config(cfg)

        run_res = pipelines.run_pipeline("app_alpha", "long-pipe", confirmed=True)
        self.assertTrue(run_res.get("success"))
        run_id = run_res["runId"]

        # Attempt to run another command on app_alpha while pipeline is running
        busy_res = jobs.execute_command("app_alpha", "echo busy test")
        self.assertFalse(busy_res.get("success"))
        self.assertEqual(busy_res.get("code"), "APP_BUSY")

        # Stop pipeline
        stop_res = pipelines.stop_pipeline_run(run_id)
        self.assertTrue(stop_res.get("success"))

    def test_pipeline_history_recording(self):
        cfg = {
            "apps": {
                "app_alpha": {
                    "bundle_id": "com.example.alpha",
                    "android_package": "com.example.alpha",
                    "pipelines": [
                        {
                            "id": "hist-pipe",
                            "name": "History Pipeline",
                            "steps": [
                                {"command": "echo 'hist step 1'"},
                            ]
                        }
                    ]
                }
            }
        }
        config.save_deploy_config(cfg)

        run_res = pipelines.run_pipeline("app_alpha", "hist-pipe", confirmed=True)
        self.assertTrue(run_res.get("success"))
        run_id = run_res["runId"]

        import time
        for _ in range(50):
            status_res = pipelines.get_pipeline_run(run_id)
            if status_res["run"]["status"] in ("success", "error", "stopped"):
                break
            time.sleep(0.1)

        history_file = self.base / ".dev-dashboard" / "deployment_history.jsonl"
        self.assertTrue(history_file.exists())
        lines = history_file.read_text(encoding="utf-8").strip().split("\n")
        parsed = [json.loads(line) for line in lines if line.strip()]
        pipe_entries = [p for p in parsed if p.get("type") == "pipeline"]
        self.assertGreaterEqual(len(pipe_entries), 1)
        entry = pipe_entries[-1]
        self.assertEqual(entry["id"], run_id)
        self.assertEqual(entry["name"], "History Pipeline")
        self.assertEqual(entry["status"], "success")
        self.assertEqual(len(entry["steps"]), 1)
        self.assertEqual(entry["steps"][0]["status"], "success")


class TestAppDoctor(unittest.TestCase):

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.base = Path(self.td.name).resolve()
        self.orig_ws = config.WORKSPACE_ROOT
        config.WORKSPACE_ROOT = self.base

        # Create mock Flutter app
        self.app_dir = self.base / "app_alpha"
        self.app_dir.mkdir(parents=True)
        (self.app_dir / "pubspec.yaml").write_text("name: app_alpha\nversion: 2.1.0+33\n", encoding="utf-8")
        (self.app_dir / "pubspec.lock").write_text("# lock\n", encoding="utf-8")
        (self.app_dir / "android").mkdir(parents=True)
        gradlew = self.app_dir / "android" / "gradlew"
        gradlew.write_text("#!/bin/sh\necho gradle\n", encoding="utf-8")
        gradlew.chmod(0o755)

        cfg_dir = self.base / ".dev-dashboard"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        (cfg_dir / "deploy_config.json").write_text(json.dumps({
            "apps": {
                "app_alpha": {
                    "android_package": "com.example.alpha",
                    "bundle_id": "com.example.alpha",
                }
            }
        }), encoding="utf-8")

    def tearDown(self):
        config.WORKSPACE_ROOT = self.orig_ws
        self.td.cleanup()

    def test_diagnose_app_success(self):
        import doctor
        res = doctor.diagnose_app("app_alpha")
        self.assertTrue(res["success"])
        self.assertEqual(res["app"], "app_alpha")
        self.assertIn(res["overallStatus"], ("pass", "warn", "fail"))
        self.assertGreater(len(res["checks"]), 0)
        self.assertIn("App Doctor Diagnostic Report", res["reportMarkdown"])

        # Check pubspec check
        pub_check = next((c for c in res["checks"] if c["id"] == "pubspec_yaml"), None)
        self.assertIsNotNone(pub_check)
        self.assertEqual(pub_check["status"], "pass")
        self.assertEqual(pub_check["version"], "2.1.0+33")

        # Check gradlew check
        gw_check = next((c for c in res["checks"] if c["id"] == "android_gradlew"), None)
        self.assertIsNotNone(gw_check)
        self.assertEqual(gw_check["status"], "pass")

    def test_diagnose_app_unexecutable_gradlew(self):
        import doctor
        gradlew = self.app_dir / "android" / "gradlew"
        gradlew.chmod(0o644)  # remove execute permissions

        res = doctor.diagnose_app("app_alpha")
        self.assertTrue(res["success"])
        gw_check = next((c for c in res["checks"] if c["id"] == "android_gradlew"), None)
        self.assertIsNotNone(gw_check)
        self.assertEqual(gw_check["status"], "fail")
        self.assertIn("chmod +x", gw_check["hint"])

    def test_diagnose_app_missing_pubspec_lock(self):
        import doctor
        (self.app_dir / "pubspec.lock").unlink()

        res = doctor.diagnose_app("app_alpha")
        self.assertTrue(res["success"])
        lock_check = next((c for c in res["checks"] if c["id"] == "pubspec_lock"), None)
        self.assertIsNotNone(lock_check)
        self.assertEqual(lock_check["status"], "warn")
        self.assertIn("flutter pub get", lock_check["hint"])

    def test_server_doctor_endpoint(self):
        import http.client
        import http.server
        import threading
        import server

        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), server.DeploymentHandler)
        port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever)
        t.daemon = True
        t.start()

        try:
            token = server._get_auth_token()
            conn = http.client.HTTPConnection("127.0.0.1", port)
            headers = {"X-API-Token": token}
            conn.request("GET", "/api/deployment/doctor?app=app_alpha", headers=headers)
            res = conn.getresponse()
            self.assertEqual(res.status, 200)
            data = json.loads(res.read().decode("utf-8"))
            self.assertTrue(data.get("success"))
            self.assertEqual(data.get("app"), "app_alpha")
        finally:
            httpd.shutdown()
            httpd.server_close()


class TestApkHostingAndQr(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.ws_dir = Path(self.tmp_dir.name)
        self.app_dir = self.ws_dir / "apps" / "test_apk_app"
        self.apk_dir = self.app_dir / "build" / "app" / "outputs" / "flutter-apk"
        self.apk_dir.mkdir(parents=True, exist_ok=True)
        self.apk_file = self.apk_dir / "app-release.apk"
        self.apk_content = b"PK\x03\x04mock_android_apk_binary_payload"
        self.apk_file.write_bytes(self.apk_content)

        # Mock deploy config
        deploy_cfg = {
            "version": 1,
            "apps": {
                "test_apk_app": {
                    "name": "Test APK App",
                    "path": "apps/test_apk_app",
                }
            }
        }
        (self.ws_dir / "deploy_config.json").write_text(json.dumps(deploy_cfg), encoding="utf-8")

        import config
        self.orig_ws = config.WORKSPACE_ROOT
        config.WORKSPACE_ROOT = self.ws_dir

    def tearDown(self):
        import config
        config.WORKSPACE_ROOT = self.orig_ws
        self.tmp_dir.cleanup()

    def test_qr_format_and_version_info_at_spec_positions(self):
        # Read format info back from ISO 18004 positions ([row][col]); a transposed
        # placement made every generated QR unreadable.
        from qr import matrix as M
        for text, ec in (("HELLO", "L"), ("x" * 160, "L"), ("x" * 150, "M")):
            g = M.generate_qr_matrix(text, ec)
            q = [row[4:-4] for row in g[4:-4]]  # strip quiet zone
            n = len(q)
            a = [q[i][8] for i in range(6)] + [q[7][8], q[8][8], q[8][7]] + [q[8][14 - i] for i in range(9, 15)]
            b = [q[8][n - 1 - i] for i in range(8)] + [q[n - 15 + i][8] for i in range(8, 15)]
            fa = sum(int(v) << i for i, v in enumerate(a))
            fb = sum(int(v) << i for i, v in enumerate(b))
            self.assertEqual(fa, fb)
            ec_bits = 1 if ec == "L" else 0
            self.assertIn(fa, [M._format_info_bits(ec_bits, m) for m in range(8)])
            self.assertTrue(q[n - 8][8], "dark module")
            version = (n - 17) // 4
            if version >= 7:
                bits = sum(int(q[i // 3][n - 11 + i % 3]) << i for i in range(18))
                self.assertEqual(bits, M._version_info_bits(version))

    def test_download_tokens_are_scoped_to_target_and_purpose(self):
        from artifacts import download_tokens as dt
        tok = dt.issue("job_1", {"apk"})
        self.assertTrue(dt.check(tok, "job_1", "apk"))
        self.assertFalse(dt.check(tok, "job_2", "apk"))
        self.assertFalse(dt.check(tok, "job_1", "ipa"))
        self.assertFalse(dt.check("not-a-token", "job_1", "apk"))
        saved = dt.DOWNLOAD_TOKEN_TTL
        dt.DOWNLOAD_TOKEN_TTL = -1
        try:
            self.assertFalse(dt.check(dt.issue("job_1", {"apk"}), "job_1", "apk"))
        finally:
            dt.DOWNLOAD_TOKEN_TTL = saved

    def test_clean_build_default_is_on_for_prod_only(self):
        import jobs
        self.assertEqual(jobs.clean_build_env_value(None, "prod"), "true")
        self.assertEqual(jobs.clean_build_env_value(None, ""), "true")
        self.assertEqual(jobs.clean_build_env_value(None, "qa"), "false")
        self.assertEqual(jobs.clean_build_env_value(True, "qa"), "true")
        self.assertEqual(jobs.clean_build_env_value(False, "prod"), "false")

    def test_no_qr_for_aab_job(self):
        import artifacts
        import jobs
        aab = self.app_dir / "app-qa-release.aab"
        aab.write_bytes(b"PK\x03\x04aab")
        with jobs._JOBS_LOCK:
            jobs._JOBS["job_aab_1"] = {"id": "job_aab_1", "app": "test_apk_app", "flavor": "qa",
                                      "status": "success", "artifact": {"path": str(aab), "type": "AAB"}}
        try:
            info = artifacts.get_apk_download_info(job_id="job_aab_1")
            self.assertFalse(info["hasApk"])
            self.assertNotIn("downloadUrl", info)
        finally:
            with jobs._JOBS_LOCK:
                jobs._JOBS.pop("job_aab_1", None)

    def test_qr_generation(self):
        import qr
        url = "http://192.168.1.100:18112/api/deployment/download/job_12345?token=abcdef"

        # Test QR Matrix
        matrix = qr.generate_qr(url)
        self.assertGreaterEqual(len(matrix), 21)
        self.assertEqual(len(matrix), len(matrix[0]))

        # Test QR SVG
        svg = qr.qr_svg(url, box_size=6)
        self.assertIn("<svg", svg)
        self.assertIn("xmlns=\"http://www.w3.org/2000/svg\"", svg)
        self.assertIn("viewBox=", svg)
        self.assertIn("<rect", svg)

        # Test QR ASCII
        ascii_art = qr.qr_ascii(url)
        self.assertTrue(len(ascii_art) > 50)
        self.assertTrue(any(c in ascii_art for c in ("█", "▀", "▄")))

    def test_lan_ip_discovery(self):
        import artifacts
        lan_ip = artifacts.get_lan_ip()
        self.assertIsInstance(lan_ip, str)
        # Should be a valid IPv4 address
        parts = lan_ip.split(".")
        self.assertEqual(len(parts), 4)
        for p in parts:
            val = int(p)
            self.assertTrue(0 <= val <= 255)

    def test_is_lan_host_validation(self):
        import server
        self.assertTrue(server._is_lan_host("127.0.0.1"))
        self.assertTrue(server._is_lan_host("192.168.1.18"))
        self.assertTrue(server._is_lan_host("10.0.0.1"))
        self.assertTrue(server._is_lan_host("172.20.0.1"))
        self.assertTrue(server._is_lan_host("phone.local"))
        self.assertFalse(server._is_lan_host("8.8.8.8"))
        self.assertFalse(server._is_lan_host("evil.attacker.com"))
        self.assertFalse(server._is_lan_host(""))

    def test_find_apk_artifact(self):
        import artifacts
        art = artifacts.find_apk_artifact("test_apk_app")
        self.assertIsNotNone(art)
        self.assertEqual(art["filename"], "app-release.apk")
        self.assertEqual(art["sizeBytes"], len(self.apk_content))
        self.assertTrue(Path(art["path"]).is_file())

    def test_resolve_safe_apk_path(self):
        import artifacts
        resolved = artifacts.resolve_safe_apk_path("test_apk_app")
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.resolve(), self.apk_file.resolve())

        # Path traversal rejection
        self.assertIsNone(artifacts.resolve_safe_apk_path("../etc/passwd"))
        self.assertIsNone(artifacts.resolve_safe_apk_path("../../app.apk"))
        self.assertIsNone(artifacts.resolve_safe_apk_path("non_existent_app"))

    def test_server_apk_download_and_info(self):
        import http.client
        import http.server
        import server
        import threading

        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), server.DeploymentHandler)
        port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever)
        t.daemon = True
        t.start()

        try:
            token = server._get_auth_token()

            # 1. Test /api/deployment/apk-info
            conn = http.client.HTTPConnection("127.0.0.1", port)
            conn.request("GET", "/api/deployment/apk-info?app=test_apk_app", headers={"X-API-Token": token})
            res = conn.getresponse()
            self.assertEqual(res.status, 200)
            data = json.loads(res.read().decode("utf-8"))
            self.assertTrue(data.get("success"))
            self.assertTrue(data.get("hasApk"))
            self.assertEqual(data.get("filename"), "app-release.apk")
            self.assertIn("downloadUrl", data)
            self.assertIn("qrSvg", data)
            self.assertIn("qrAscii", data)
            # The phone link carries a scoped download token, never the master token
            self.assertNotIn(token, data["downloadUrl"])
            dl_path = data["downloadUrl"].split(f":{port}", 1)[1] if f":{port}" in data["downloadUrl"] else \
                "/api/deployment/download/" + data["downloadUrl"].split("/api/deployment/download/", 1)[1]
            conn_dl = http.client.HTTPConnection("127.0.0.1", port)
            conn_dl.request("GET", dl_path)
            res_dl = conn_dl.getresponse()
            self.assertEqual(res_dl.status, 200)
            self.assertEqual(res_dl.read(), self.apk_content)
            scoped = dl_path.split("token=", 1)[1]
            conn_other = http.client.HTTPConnection("127.0.0.1", port)
            conn_other.request("GET", f"/api/deployment/download/other_app?token={scoped}")
            self.assertEqual(conn_other.getresponse().status, 401)

            # 2. Test /api/deployment/download/<target>?token=<token> (Phone camera flow)
            conn2 = http.client.HTTPConnection("127.0.0.1", port)
            conn2.request("GET", f"/api/deployment/download/test_apk_app?token={token}")
            res2 = conn2.getresponse()
            self.assertEqual(res2.status, 200)
            self.assertEqual(res2.getheader("Content-Type"), "application/vnd.android.package-archive")
            self.assertIn("app-release.apk", res2.getheader("Content-Disposition", ""))
            body = res2.read()
            self.assertEqual(body, self.apk_content)

            # 3. Test Unauthorized download (no token)
            conn3 = http.client.HTTPConnection("127.0.0.1", port)
            conn3.request("GET", "/api/deployment/download/test_apk_app")
            res3 = conn3.getresponse()
            self.assertEqual(res3.status, 401)

            # 4. Test /api/deployment/qr endpoint
            conn4 = http.client.HTTPConnection("127.0.0.1", port)
            conn4.request("GET", f"/api/deployment/qr?text=http://test.url&token={token}")
            res4 = conn4.getresponse()
            self.assertEqual(res4.status, 200)
            self.assertEqual(res4.getheader("Content-Type"), "image/svg+xml")
            qr_body = res4.read().decode("utf-8")
            self.assertIn("<svg", qr_body)
        finally:
            httpd.shutdown()
            httpd.server_close()


class TestOutgoingWebhooks(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.ws_root = Path(self.tmp_dir.name)
        (self.ws_root / ".dev-dashboard").mkdir(parents=True, exist_ok=True)
        (self.ws_root / "pubspec.yaml").write_text("name: webhook_test_app\nversion: 2.1.0+42\n", encoding="utf-8")
        self.token = config.set_request_workspace(self.ws_root)

    def tearDown(self):
        config.reset_request_workspace(self.token)
        self.tmp_dir.cleanup()

    def test_detect_webhook_provider(self):
        import notifications

        # Auto-detection from URL
        self.assertEqual(notifications.detect_webhook_provider("https://hooks.slack.com/services/T00/B00/X123"), "slack")
        self.assertEqual(notifications.detect_webhook_provider("https://discord.com/api/webhooks/12345/abcdef"), "discord")
        self.assertEqual(notifications.detect_webhook_provider("https://discordapp.com/api/webhooks/12345/abcdef"), "discord")
        self.assertEqual(notifications.detect_webhook_provider("https://myorg.webhook.office.com/webhookb2/guid"), "teams")
        self.assertEqual(notifications.detect_webhook_provider("https://api.mycompany.com/webhook/receiver"), "generic")

        # Overrides
        self.assertEqual(notifications.detect_webhook_provider("https://api.mycompany.com/custom", override="slack"), "slack")
        self.assertEqual(notifications.detect_webhook_provider("https://api.mycompany.com/custom", override="discord"), "discord")
        self.assertEqual(notifications.detect_webhook_provider("https://api.mycompany.com/custom", override="teams"), "teams")
        self.assertEqual(notifications.detect_webhook_provider("https://hooks.slack.com/services/x", override="generic"), "generic")

    def test_format_duration(self):
        import notifications

        self.assertEqual(notifications.format_duration(0), "0s")
        self.assertEqual(notifications.format_duration(42), "42s")
        self.assertEqual(notifications.format_duration(60), "1m")
        self.assertEqual(notifications.format_duration(84), "1m 24s")
        self.assertEqual(notifications.format_duration(125), "2m 5s")
        self.assertEqual(notifications.format_duration(None), "unknown")

    def test_get_git_commit_summary(self):
        import notifications

        # For the real repository root
        summary = notifications.get_git_commit_summary(Path(__file__).resolve().parents[1])
        self.assertIsInstance(summary, dict)
        self.assertIn("hash", summary)
        self.assertIn("subject", summary)
        self.assertIn("author", summary)
        # Verify valid non-empty values
        self.assertTrue(len(summary["hash"]) > 0)
        self.assertTrue(len(summary["subject"]) > 0)

    def test_build_webhook_payloads(self):
        import notifications

        sample_event = {
            "app": "my_app",
            "appName": "My Super App",
            "flavor": "prod",
            "platform": "Android (APK)",
            "version": "2.1.0 (42)",
            "status": "success",
            "durationSeconds": 84,
            "durationFormatted": "1m 24s",
            "commit": {"hash": "abc1234", "subject": "fix: release build", "author": "QA"},
            "downloadUrl": "http://192.168.1.10:18112/api/deployment/download/my_app",
            "track": "Internal Testing",
        }

        # 1. Slack payload
        slack = notifications.build_slack_payload(sample_event)
        self.assertIn("text", slack)
        self.assertIn("blocks", slack)
        self.assertTrue(any(b.get("type") == "header" and "SUCCEEDED" in b.get("text", {}).get("text", "").upper() for b in slack["blocks"]))
        # Should have download APK action button
        action_blocks = [b for b in slack["blocks"] if b.get("type") == "actions"]
        self.assertTrue(len(action_blocks) > 0)
        self.assertEqual(action_blocks[0]["elements"][0]["url"], sample_event["downloadUrl"])

        # 2. Discord payload
        discord = notifications.build_discord_payload(sample_event)
        self.assertIn("embeds", discord)
        embed = discord["embeds"][0]
        self.assertEqual(embed["color"], 0x10B981)
        self.assertIn("SUCCEEDED", embed["title"].upper())
        self.assertTrue(any(f["name"] == "App" and f["value"] == "My Super App" for f in embed["fields"]))
        self.assertTrue(any("Download APK" in f["value"] for f in embed["fields"]))

        # 3. Microsoft Teams payload
        teams = notifications.build_teams_payload(sample_event)
        self.assertEqual(teams.get("@type"), "MessageCard")
        self.assertEqual(teams.get("themeColor"), "10B981")
        self.assertIn("potentialAction", teams)
        self.assertEqual(teams["potentialAction"][0]["targets"][0]["uri"], sample_event["downloadUrl"])

        # 4. Generic payload
        generic = notifications.build_generic_payload(sample_event)
        self.assertEqual(generic.get("event"), "deployment_finished")
        self.assertEqual(generic.get("app"), "my_app")
        self.assertEqual(generic.get("version"), "2.1.0 (42)")

    def test_send_outgoing_webhook_http_mock(self):
        import http.server
        import notifications
        import threading

        received_requests = []

        class MockWebhookHandler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                received_requests.append({
                    "path": self.path,
                    "content_type": self.headers.get("Content-Type"),
                    "body": json.loads(body.decode("utf-8")),
                })
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"ok": true}')

            def log_message(self, format, *args):
                pass

        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), MockWebhookHandler)
        port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever)
        t.daemon = True
        t.start()

        try:
            url = f"http://127.0.0.1:{port}/slack-webhook"
            payload = {"text": "Hello Slack"}
            res = notifications.send_outgoing_webhook(url, payload)
            self.assertTrue(res.get("success"))
            self.assertEqual(res.get("statusCode"), 200)
            self.assertEqual(len(received_requests), 1)
            self.assertEqual(received_requests[0]["body"], payload)
            self.assertIn("application/json", received_requests[0]["content_type"])

            # Test invalid URL
            invalid_res = notifications.send_outgoing_webhook("ftp://invalid.com", payload)
            self.assertFalse(invalid_res.get("success"))
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_save_deploy_config_validation(self):
        # 1. Valid webhook config
        valid_cfg = {
            "workspace_webhook_url": "https://hooks.slack.com/services/ABC",
            "workspace_webhook_provider": "slack",
            "apps": {
                "test_app": {
                    "webhook_url": "https://discord.com/api/webhooks/123/xyz",
                    "webhook_provider": "discord",
                    "webhook_enabled": True,
                    "notify_on_success": True,
                    "notify_on_failure": True,
                },
            },
        }
        res = config.save_deploy_config(valid_cfg)
        self.assertTrue(res.get("success"), res.get("error"))

        # 2. Invalid app webhook URL
        invalid_app_cfg = {
            "apps": {
                "test_app": {
                    "webhook_url": "ftp://not-an-http-url",
                },
            },
        }
        res2 = config.save_deploy_config(invalid_app_cfg)
        self.assertFalse(res2.get("success"))
        self.assertIn("must start with http:// or https://", res2.get("error"))

        # 3. Invalid workspace webhook URL
        invalid_ws_cfg = {
            "workspace_webhook_url": "invalid://url",
            "apps": {},
        }
        res3 = config.save_deploy_config(invalid_ws_cfg)
        self.assertFalse(res3.get("success"))
        self.assertIn("must start with http:// or https://", res3.get("error"))

        # 4. Invalid provider
        invalid_prov_cfg = {
            "apps": {
                "test_app": {
                    "webhook_provider": "telegram_not_supported",
                },
            },
        }
        res4 = config.save_deploy_config(invalid_prov_cfg)
        self.assertFalse(res4.get("success"))
        self.assertIn("Invalid webhook provider", res4.get("error"))

    def test_notify_job_finished_and_pipeline(self):
        import http.server
        import notifications
        import threading
        import time

        received = []

        class MockWebhookHandler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                received.append(json.loads(body.decode("utf-8")))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"ok": true}')

            def log_message(self, format, *args):
                pass

        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), MockWebhookHandler)
        port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever)
        t.daemon = True
        t.start()

        try:
            webhook_url = f"http://127.0.0.1:{port}/notify"
            # Configure app webhook
            config.save_deploy_config({
                "apps": {
                    "app_notify": {
                        "webhook_url": webhook_url,
                        "webhook_provider": "generic",
                        "webhook_enabled": True,
                        "notify_on_success": True,
                        "notify_on_failure": True,
                    }
                }
            })

            # 1. Normal job finish notification
            job = {
                "id": "job_123",
                "app": "app_notify",
                "status": "success",
                "started_at": time.time() - 15,
                "finished_at": time.time(),
                "flavor": "prod",
                "command": "flutter build apk --release",
            }
            notifications.notify_job_finished(job, ws_root=self.ws_root)
            time.sleep(0.3)
            self.assertEqual(len(received), 1)
            self.assertEqual(received[0]["event"], "deployment_finished")
            self.assertEqual(received[0]["status"], "success")

            # 2. Pipeline step job (should be suppressed)
            job_step = {
                "id": "job_step_456",
                "app": "app_notify",
                "status": "success",
                "is_pipeline_step": True,
            }
            notifications.notify_job_finished(job_step, ws_root=self.ws_root)
            time.sleep(0.2)
            self.assertEqual(len(received), 1)  # Still 1, no duplicate sent

            # 3. Pipeline completed notification
            pipe_run = {
                "id": "pipe_run_789",
                "name": "Full Release Pipeline",
                "app": "app_notify",
                "flavor": "prod",
                "status": "success",
                "startedAt": time.time() - 50,
                "finishedAt": time.time(),
                "durationSeconds": 50,
                "steps": [{"name": "Build APK"}, {"name": "Upload"}],
            }
            notifications.notify_pipeline_finished(pipe_run, ws_root=self.ws_root)
            time.sleep(0.3)
            self.assertEqual(len(received), 2)
            self.assertEqual(received[1]["event"], "deployment_finished")
            self.assertIn("Pipeline", received[1]["command"])

            # 4. Test Webhook endpoint directly
            test_res = notifications.test_webhook(webhook_url, provider="generic", app_id="app_notify", ws_root=self.ws_root)
            time.sleep(0.2)
            self.assertTrue(test_res.get("success"))
            self.assertEqual(len(received), 3)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_server_notifications_test_endpoint(self):
        import http.client
        import http.server
        import server
        import threading

        # Start mock target receiver
        receiver_data = []

        class MockReceiver(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                receiver_data.append(json.loads(body.decode("utf-8")))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"status": "ok"}')

            def log_message(self, format, *args):
                pass

        receiver_httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), MockReceiver)
        receiver_port = receiver_httpd.server_address[1]
        t_receiver = threading.Thread(target=receiver_httpd.serve_forever, daemon=True)
        t_receiver.start()

        # Start deployment console server
        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), server.DeploymentHandler)
        port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()

        try:
            token = server._get_auth_token()
            conn = http.client.HTTPConnection("127.0.0.1", port)
            req_payload = json.dumps({
                "url": f"http://127.0.0.1:{receiver_port}/webhook",
                "provider": "slack",
                "app": "webhook_test_app",
            }).encode("utf-8")
            conn.request(
                "POST",
                "/api/deployment/notifications/test",
                body=req_payload,
                headers={"Content-Type": "application/json", "X-API-Token": token},
            )
            res = conn.getresponse()
            self.assertEqual(res.status, 200)
            data = json.loads(res.read().decode("utf-8"))
            self.assertTrue(data.get("success"))
            self.assertEqual(data.get("provider"), "slack")
            self.assertEqual(len(receiver_data), 1)
            self.assertIn("blocks", receiver_data[0])
        finally:
            httpd.shutdown()
            httpd.server_close()
            receiver_httpd.shutdown()
            receiver_httpd.server_close()


class TestCertificateAndKeystoreSentinel(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.ws_root = Path(self.temp_dir.name).resolve()
        self._orig_ws = config.WORKSPACE_ROOT
        config.WORKSPACE_ROOT = self.ws_root

        self.app_dir = self.ws_root / "test_app"
        self.app_dir.mkdir(parents=True, exist_ok=True)
        (self.app_dir / "android" / "app").mkdir(parents=True, exist_ok=True)
        (self.app_dir / "ios" / "Runner").mkdir(parents=True, exist_ok=True)

        # Register app in apps_config.json and apps.json
        cfg_dir = self.ws_root / ".dev-dashboard"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        apps_data = json.dumps([{"id": "test_app", "name": "Test App", "path": str(self.app_dir)}])
        (cfg_dir / "apps_config.json").write_text(apps_data, encoding="utf-8")
        (cfg_dir / "apps.json").write_text(apps_data, encoding="utf-8")

    def tearDown(self):
        config.WORKSPACE_ROOT = self._orig_ws
        self.temp_dir.cleanup()

    def test_asn1_validity_extraction(self):
        import sentinel

        # Construct raw byte sequence containing ASN.1 validity structure
        # Validity sequence: 0x30, len=0x20, UTCTime(0x17, 0x0d, "240101000000Z"), UTCTime(0x17, 0x0d, "350101000000Z")
        raw = b"PREFIX_PADDING\x30\x20\x17\x0d240101000000Z\x17\x0d350101000000ZSUFFIX_PADDING"
        extracted = sentinel.extract_validity_from_keystore_bytes(raw)
        self.assertEqual(len(extracted), 1)
        self.assertEqual(extracted[0], ("2024-01-01", "2035-01-01"))

        # GeneralizedTime format: 0x18, len=0x0f, "20240101000000Z"
        raw_gen = b"\x30\x24\x18\x0f20240101000000Z\x18\x0f20380101000000Z"
        extracted_gen = sentinel.extract_validity_from_keystore_bytes(raw_gen)
        self.assertEqual(len(extracted_gen), 1)
        self.assertEqual(extracted_gen[0], ("2024-01-01", "2038-01-01"))

    def test_android_keystore_expiry_detection(self):
        import sentinel

        # 1. When no keystore exists
        res = sentinel.check_android_keystore_expiry("test_app", ws_root=self.ws_root)
        self.assertTrue(res["applicable"])
        self.assertEqual(res["status"], "missing")

        # 2. Keystore with future expiration date via ASN.1 fallback
        ks_file = self.app_dir / "android" / "app" / "upload-keystore.jks"
        raw = b"\x30\x20\x17\x0d240101000000Z\x17\x0d400101000000Z"  # Expires in 2040
        ks_file.write_bytes(raw)

        res_future = sentinel.check_android_keystore_expiry("test_app", ws_root=self.ws_root)
        self.assertTrue(res_future["applicable"])
        self.assertEqual(res_future["status"], "ok")
        self.assertEqual(res_future["validTo"], "2040-01-01")
        self.assertEqual(len(res_future["alerts"]), 0)

        # 3. Keystore expired in past
        raw_expired = b"\x30\x20\x17\x0d200101000000Z\x17\x0d220101000000Z"  # Expired in 2022
        ks_file.write_bytes(raw_expired)

        res_expired = sentinel.check_android_keystore_expiry("test_app", ws_root=self.ws_root)
        self.assertEqual(res_expired["status"], "critical")
        self.assertTrue(any(a["severity"] == "critical" and "Expired" in a["title"] for a in res_expired["alerts"]))

    def test_apple_expiry_detection(self):
        import unittest.mock as mock
        from datetime import datetime, timedelta
        import sentinel

        # 1. No Apple files -> applicable is True (searches for profiles/keys)
        res = sentinel.check_apple_expiry("test_app", ws_root=self.ws_root)
        self.assertTrue(res["applicable"])

        # 2. Mock p8 with expiring metadata
        soon_date = (datetime.now() + timedelta(days=15)).strftime("%Y-%m-%d")
        mock_p8_info = {
            "key_id": "ABC1234567",
            "p8_path": str(self.app_dir / "AuthKey_ABC1234567.p8"),
            "expires_at": soon_date,
        }
        (self.app_dir / "AuthKey_ABC1234567.p8").write_text("-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----")

        with mock.patch("sentinel._inspect_p8_key", return_value=mock_p8_info):
            res_apple = sentinel.check_apple_expiry("test_app", ws_root=self.ws_root)
            self.assertEqual(res_apple["status"], "warning")
            self.assertTrue(any(a["id"] == "apple_api_key_expiring" for a in res_apple["alerts"]))

    def test_firebase_project_id_mismatch(self):
        import sentinel

        # 1. Android google-services.json
        android_fb = self.app_dir / "android" / "app" / "google-services.json"
        android_fb.write_text(json.dumps({
            "project_info": {"project_id": "my-cool-app-prod", "project_number": "12345"},
            "client": [{"client_info": {"android_client_info": {"package_name": "com.example.test_app"}}}],
        }), encoding="utf-8")

        # iOS GoogleService-Info.plist matching
        ios_fb = self.app_dir / "ios" / "Runner" / "GoogleService-Info.plist"
        ios_fb.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>PROJECT_ID</key>
    <string>my-cool-app-prod</string>
    <key>BUNDLE_ID</key>
    <string>com.example.test_app</string>
</dict>
</plist>""", encoding="utf-8")

        res_match = sentinel.check_firebase_mismatch("test_app", flavor="prod", ws_root=self.ws_root)
        self.assertEqual(res_match["status"], "ok")
        self.assertEqual(len(res_match["alerts"]), 0)

        # 2. Cross-platform Mismatch (Android points to dev, iOS points to prod)
        ios_fb.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>PROJECT_ID</key>
    <string>different-project-id</string>
</dict>
</plist>""", encoding="utf-8")

        res_mismatch = sentinel.check_firebase_mismatch("test_app", flavor="prod", ws_root=self.ws_root)
        self.assertEqual(res_mismatch["status"], "critical")
        self.assertTrue(any(a["id"] == "firebase_project_mismatch" for a in res_mismatch["alerts"]))

        # 3. Production flavor using dev project ID
        android_fb.write_text(json.dumps({
            "project_info": {"project_id": "my-cool-app-dev"},
        }), encoding="utf-8")
        ios_fb.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>PROJECT_ID</key>
    <string>my-cool-app-dev</string>
</dict>
</plist>""", encoding="utf-8")

        res_dev_in_prod = sentinel.check_firebase_mismatch("test_app", flavor="prod", ws_root=self.ws_root)
        self.assertEqual(res_dev_in_prod["status"], "warning")
        self.assertTrue(any("Production Flavor using Non-Prod Firebase" in a["title"] for a in res_dev_in_prod["alerts"]))

    def test_app_and_workspace_sentinel_aggregation(self):
        import sentinel

        res = sentinel.check_app_sentinel("test_app", ws_root=self.ws_root)
        self.assertTrue(res["success"])
        self.assertIn("badge", res)
        self.assertIn("checks", res)

        ws_res = sentinel.check_workspace_sentinel(ws_root=self.ws_root)
        self.assertTrue(ws_res["success"])
        self.assertIn("badge", ws_res)
        self.assertIn("apps", ws_res)
        self.assertIn("test_app", ws_res["apps"])

    def test_doctor_integration_sentinel(self):
        import doctor

        diag = doctor.diagnose_app(app_id="test_app", flavor="prod", ws_root=self.ws_root)
        self.assertTrue(diag["success"])
        # Should have sentinel-integrated checks in credentials category
        check_names = [c["name"] for c in diag["checks"]]
        self.assertTrue(any("Sentinel" in name or "Upload Key" in name or "Expiry" in name for name in check_names))

    def test_server_sentinel_endpoint(self):
        import http.client
        import http.server
        import server
        import threading

        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), server.DeploymentHandler)
        port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()

        try:
            token = server._get_auth_token()
            conn = http.client.HTTPConnection("127.0.0.1", port)

            # 1. Test workspace sentinel
            conn.request("GET", "/api/deployment/sentinel", headers={"X-API-Token": token})
            res = conn.getresponse()
            self.assertEqual(res.status, 200)
            data = json.loads(res.read().decode("utf-8"))
            self.assertTrue(data.get("success"))
            self.assertIn("badge", data)

            # 2. Test app-specific sentinel
            conn.request("GET", "/api/deployment/sentinel?app=test_app&flavor=prod", headers={"X-API-Token": token})
            res2 = conn.getresponse()
            self.assertEqual(res2.status, 200)
            data2 = json.loads(res2.read().decode("utf-8"))
            self.assertTrue(data2.get("success"))
            self.assertEqual(data2.get("app"), "test_app")
            self.assertIn("checks", data2)
        finally:
            httpd.shutdown()
            httpd.server_close()


class TestBuildSizeInspectorAndDiff(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.ws_root = Path(self.temp_dir.name).resolve()
        self._orig_ws = config.WORKSPACE_ROOT
        config.WORKSPACE_ROOT = self.ws_root

        self.app_dir = self.ws_root / "test_app"
        self.app_dir.mkdir(parents=True, exist_ok=True)
        self.bundle_dir = self.app_dir / "build" / "app" / "outputs" / "bundle" / "prodRelease"
        self.bundle_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        config.WORKSPACE_ROOT = self._orig_ws
        self.temp_dir.cleanup()

    def test_formatting_utilities(self):
        import build_size

        self.assertEqual(build_size.format_bytes(0), "0 B")
        self.assertEqual(build_size.format_bytes(1024), "1.0 KB")
        self.assertEqual(build_size.format_bytes(25375539), "24.2 MB")
        self.assertEqual(build_size.format_bytes(1073741824), "1.00 GB")

        self.assertEqual(build_size.format_delta_bytes(0), "0 B")
        self.assertEqual(build_size.format_delta_bytes(3984588), "+3.8 MB")
        self.assertEqual(build_size.format_delta_bytes(-1048576), "-1.0 MB")

        self.assertEqual(build_size.format_delta_percent(18.0), "+18.0%")
        self.assertEqual(build_size.format_delta_percent(-5.5), "-5.5%")
        self.assertEqual(build_size.format_delta_percent(0.0), "0%")

    def test_archive_contents_inspection_and_uncompressed_warning(self):
        import zipfile
        import build_size

        archive_path = self.bundle_dir / "app-prod-release.aab"
        with zipfile.ZipFile(archive_path, "w") as zf:
            # 1. Deflated standard code
            zf.writestr(
                zipfile.ZipInfo("base/dex/classes.dex"),
                b"x" * 20000,
                compress_type=zipfile.ZIP_DEFLATED,
            )
            # 2. Huge uncompressed asset (STORED >= 500 KB)
            zf.writestr(
                zipfile.ZipInfo("base/assets/intro_video.mp4"),
                b"v" * 600000,
                compress_type=zipfile.ZIP_STORED,
            )
            # 3. Deflated image
            zf.writestr(
                zipfile.ZipInfo("base/res/drawable/logo.png"),
                b"p" * 15000,
                compress_type=zipfile.ZIP_DEFLATED,
            )

        inspection = build_size.inspect_archive_contents(archive_path)
        self.assertEqual(inspection["fileCount"], 3)
        self.assertTrue(inspection["hasUncompressedWarnings"])
        self.assertEqual(len(inspection["uncompressedAssets"]), 1)
        self.assertEqual(inspection["uncompressedAssets"][0]["name"], "base/assets/intro_video.mp4")
        self.assertIn("STORED", inspection["uncompressedAssets"][0]["warning"])
        self.assertGreater(inspection["compressionRatio"], 0)
        self.assertGreater(len(inspection["largestFiles"]), 0)

    def test_compare_build_size_baseline_and_warning_threshold(self):
        import build_size

        # 1. Baseline Run
        art1 = {
            "path": str(self.bundle_dir / "app-prod-release.aab"),
            "filename": "app-prod-release.aab",
            "type": "AAB",
            "sizeBytes": 20 * 1024 * 1024,
            "sizeFormatted": "20.0 MB",
        }
        res_baseline = build_size.compare_build_size(
            app_id="test_app",
            flavor="prod",
            current_artifact=art1,
            ws_root=self.ws_root,
        )
        self.assertTrue(res_baseline["success"])
        self.assertFalse(res_baseline["hasBaseline"])
        self.assertIn("first baseline", res_baseline["summary"])

        # Record baseline in history JSONL file
        history_dir = self.ws_root / ".dev-dashboard"
        history_dir.mkdir(parents=True, exist_ok=True)
        history_file = history_dir / "deployment_history.jsonl"
        history_file.write_text(json.dumps({
            "id": "job_001",
            "app": "test_app",
            "flavor": "prod",
            "status": "success",
            "completedAt": "2026-10-01T12:00:00Z",
            "artifact": art1,
        }) + "\n", encoding="utf-8")

        # 2. Second Run: +3.8 MB, +18.0% increase -> triggers Warning ⚠️
        art2 = {
            "path": str(self.bundle_dir / "app-prod-release.aab"),
            "filename": "app-prod-release.aab",
            "type": "AAB",
            "sizeBytes": int(23.6 * 1024 * 1024),
            "sizeFormatted": "23.6 MB",
        }
        res_growth = build_size.compare_build_size(
            app_id="test_app",
            flavor="prod",
            current_artifact=art2,
            current_job_id="job_002",
            ws_root=self.ws_root,
        )
        self.assertTrue(res_growth["success"])
        self.assertTrue(res_growth["hasBaseline"])
        self.assertEqual(res_growth["severity"], "warning")
        self.assertEqual(res_growth["badgeVariant"], "warning")
        self.assertIn("⚠️", res_growth["summary"])
        self.assertIn("+3.6 MB", res_growth["summary"])
        self.assertIn("+18.0%", res_growth["summary"])

    def test_archive_entry_diff(self):
        import zipfile
        import build_size

        prev_zip = self.bundle_dir / "prev.aab"
        curr_zip = self.bundle_dir / "curr.aab"

        with zipfile.ZipFile(prev_zip, "w") as zf:
            zf.writestr("lib/arm64-v8a/libapp.so", b"a" * 100000)
            zf.writestr("assets/deprecated_asset.png", b"b" * 50000)

        with zipfile.ZipFile(curr_zip, "w") as zf:
            zf.writestr("lib/arm64-v8a/libapp.so", b"a" * 150000)  # +50 KB
            zf.writestr("assets/new_feature_video.mp4", b"c" * 80000)  # Added

        diff = build_size._compute_archive_diff(str(prev_zip), str(curr_zip))
        self.assertTrue(diff["hasDiff"])
        self.assertEqual(diff["addedCount"], 1)
        self.assertEqual(diff["addedAssets"][0]["name"], "assets/new_feature_video.mp4")
        self.assertEqual(diff["removedCount"], 1)
        self.assertEqual(diff["removedAssets"][0]["name"], "assets/deprecated_asset.png")
        self.assertEqual(diff["grownCount"], 1)
        self.assertEqual(diff["grownAssets"][0]["name"], "lib/arm64-v8a/libapp.so")
        self.assertEqual(diff["grownAssets"][0]["deltaBytes"], 50000)

    def test_inspect_and_diff_job_integration(self):
        import zipfile
        import build_size

        aab_file = self.bundle_dir / "app-prod-release.aab"
        with zipfile.ZipFile(aab_file, "w") as zf:
            zf.writestr("base/dex/classes.dex", b"test" * 500)

        job = {
            "id": "job_inspect_test",
            "app": "test_app",
            "flavor": "prod",
            "status": "success",
            "started_at": 1000.0,
        }

        res = build_size.inspect_and_diff_job(job, ws_root=self.ws_root)
        self.assertIsNotNone(res)
        self.assertIn("buildSize", job)
        self.assertIn("artifact", job)
        self.assertEqual(job["buildSize"]["currentFilename"], "app-prod-release.aab")

    def test_server_build_size_endpoint(self):
        import http.client
        import http.server
        import zipfile
        import server
        import threading

        aab_file = self.bundle_dir / "app-prod-release.aab"
        with zipfile.ZipFile(aab_file, "w") as zf:
            zf.writestr("base/dex/classes.dex", b"test" * 500)

        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), server.DeploymentHandler)
        port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()

        try:
            token = server._get_auth_token()
            conn = http.client.HTTPConnection("127.0.0.1", port)

            conn.request("GET", "/api/deployment/build-size?app=test_app&flavor=prod", headers={"X-API-Token": token})
            res = conn.getresponse()
            self.assertEqual(res.status, 200)
            data = json.loads(res.read().decode("utf-8"))
            self.assertTrue(data.get("success"))
            self.assertIn("buildSize", data)
            self.assertEqual(data["buildSize"]["currentFilename"], "app-prod-release.aab")
        finally:
            httpd.shutdown()
            httpd.server_close()


class TestDocumentationAndServerStatus(unittest.TestCase):

    def test_list_available_docs(self):
        import docs_provider

        docs = docs_provider.list_available_docs()
        self.assertIsInstance(docs, list)
        doc_ids = [d["id"] for d in docs]
        self.assertIn("overview", doc_ids)
        self.assertIn("readme", doc_ids)
        self.assertIn("architecture", doc_ids)
        self.assertIn("faq", doc_ids)
        self.assertIn("api", doc_ids)

    def test_get_overview_doc(self):
        import docs_provider

        res = docs_provider.get_doc_content("overview")
        self.assertTrue(res["success"])
        self.assertEqual(res["doc"], "overview")
        self.assertIn("Dev Deployment Console", res["content"])
        self.assertIn("Saved Pipelines", res["content"])
        self.assertIn("App Doctor", res["content"])

    def test_get_repository_markdown_docs(self):
        import docs_provider

        res = docs_provider.get_doc_content("readme")
        self.assertTrue(res["success"])
        self.assertEqual(res["filename"], "README.md")
        self.assertGreater(len(res["content"]), 50)

        res_arch = docs_provider.get_doc_content("architecture")
        self.assertTrue(res_arch["success"])
        self.assertEqual(res_arch["filename"], "ARCHITECTURE.md")

        res_faq = docs_provider.get_doc_content("faq")
        self.assertTrue(res_faq["success"])
        self.assertEqual(res_faq["filename"], "FAQ.md")

    def test_unknown_and_traversal_safety(self):
        import docs_provider

        res_unknown = docs_provider.get_doc_content("non_existent_doc_id_xyz")
        self.assertFalse(res_unknown["success"])
        self.assertIn("Unknown document", res_unknown["error"])

        res_traversal = docs_provider.get_doc_content("../../etc/passwd")
        self.assertFalse(res_traversal["success"])

    def test_server_status_info(self):
        import docs_provider

        info = docs_provider.get_server_status_info(port=18112)
        self.assertTrue(info["success"])
        self.assertEqual(info["status"], "online")
        self.assertEqual(info["port"], 18112)
        self.assertIn("./start.sh", info["commandToStart"])
        self.assertIsNotNone(info["pid"])

    def test_http_server_status_and_docs_endpoints(self):
        import http.client
        import http.server
        import server
        import threading

        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), server.DeploymentHandler)
        port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()

        try:
            conn = http.client.HTTPConnection("127.0.0.1", port)

            # 1. Unauthenticated heartbeat endpoint allows frontend health detection
            conn.request("GET", "/api/deployment/server-status")
            res_status = conn.getresponse()
            self.assertEqual(res_status.status, 200)
            data_status = json.loads(res_status.read().decode("utf-8"))
            self.assertTrue(data_status["success"])
            self.assertEqual(data_status["status"], "online")
            self.assertEqual(data_status["port"], port)

            # 2. Authenticated docs list endpoint
            token = server._get_auth_token()
            conn.request("GET", "/api/deployment/docs/list", headers={"X-API-Token": token})
            res_list = conn.getresponse()
            self.assertEqual(res_list.status, 200)
            data_list = json.loads(res_list.read().decode("utf-8"))
            self.assertTrue(data_list["success"])
            self.assertIn("docs", data_list)

            # 3. Authenticated doc content endpoint
            conn.request("GET", "/api/deployment/docs?doc=overview", headers={"X-API-Token": token})
            res_doc = conn.getresponse()
            self.assertEqual(res_doc.status, 200)
            data_doc = json.loads(res_doc.read().decode("utf-8"))
            self.assertTrue(data_doc["success"])
            self.assertEqual(data_doc["doc"], "overview")
            self.assertIn("Dev Deployment Console", data_doc["content"])
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_server_manager_functions(self):
        import server_manager

        # 1. Desktop launcher installation
        res_launcher = server_manager.install_desktop_launcher()
        self.assertTrue(res_launcher["success"])
        self.assertIn("message", res_launcher)

        # 2. Service status query
        status = server_manager.get_service_status()
        self.assertIn("installed", status)
        self.assertIn("running", status)
        self.assertIn("enabled", status)

    def test_server_lifecycle_http_endpoints(self):
        import http.client
        import http.server
        import server
        import threading

        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), server.DeploymentHandler)
        port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()

        try:
            conn = http.client.HTTPConnection("127.0.0.1", port)
            token = server._get_auth_token()

            # GET /api/deployment/server/status
            conn.request("GET", "/api/deployment/server/status")
            res_status = conn.getresponse()
            self.assertEqual(res_status.status, 200)
            data_status = json.loads(res_status.read().decode("utf-8"))
            self.assertTrue(data_status["success"])
            self.assertEqual(data_status["status"], "online")

            # GET /api/deployment/server/service-status
            conn.request("GET", "/api/deployment/server/service-status")
            res_svc = conn.getresponse()
            self.assertEqual(res_svc.status, 200)
            data_svc = json.loads(res_svc.read().decode("utf-8"))
            self.assertIn("installed", data_svc)

            # POST /api/deployment/server/install-desktop (requires auth)
            conn.request(
                "POST",
                "/api/deployment/server/install-desktop",
                body=json.dumps({}),
                headers={"Content-Type": "application/json", "X-API-Token": token}
            )
            res_desk = conn.getresponse()
            self.assertEqual(res_desk.status, 200)
            data_desk = json.loads(res_desk.read().decode("utf-8"))
            self.assertTrue(data_desk["success"])
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_google_chat_webhook_payload_and_detection(self):
        import notifications

        # 1. Detection
        url = "https://chat.googleapis.com/v1/spaces/AAAA1234/messages?key=AIzaSy&token=abc"
        self.assertEqual(notifications.detect_webhook_provider(url), "google_chat")

        # 2. Card v2 Payload
        event_data = {
            "app": "test_app",
            "appName": "Test App",
            "flavor": "prod",
            "platform": "Android (AAB)",
            "version": "1.2.0",
            "status": "success",
            "durationFormatted": "1m 12s",
            "commit": {"hash": "abcd123", "subject": "fix: bug", "author": "dev"},
            "downloadUrl": "https://example.com/dl/app.apk",
            "track": "Production",
            "buildSizeSummary": "21.5 MB (+0.8 MB)",
        }
        payload = notifications.build_webhook_payload("google_chat", event_data)
        self.assertIn("cardsV2", payload)
        self.assertIn("text", payload)
        card = payload["cardsV2"][0]["card"]
        self.assertIn("SUCCEEDED", card["header"]["title"])
        self.assertIn("Test App", card["header"]["title"])
        sections = card["sections"]
        self.assertTrue(len(sections) > 0)
        widgets = sections[0]["widgets"]
        # Verify app, platform, track, and download button are present
        has_app_widget = any("Test App" in str(w) for w in widgets)
        has_track_widget = any("Production" in str(w) for w in widgets)
        has_btn_widget = any("Download APK" in str(w) for w in widgets)
        self.assertTrue(has_app_widget)
        self.assertTrue(has_track_widget)
        self.assertTrue(has_btn_widget)

    def test_pipeline_save_delete_and_api_endpoints(self):
        import pipelines
        import http.server
        import server
        import threading

        # 1. Backend save & delete functions
        pipe_data = {
            "name": "Full Release Flow",
            "flavor": "prod",
            "steps": [
                {"name": "Build AAB", "templateId": "build_aab", "continueOnFailure": False},
                {"name": "Custom Test", "command": "flutter test", "continueOnFailure": True},
            ],
        }
        save_res = pipelines.save_pipeline("test_app", pipe_data)
        self.assertTrue(save_res["success"])
        saved_id = save_res["pipeline"]["id"]
        self.assertTrue(saved_id.startswith("full-release-flow"))

        # Verify pipeline is in get_pipelines
        all_pipes = pipelines.get_pipelines("test_app")["pipelines"]
        self.assertTrue(any(p["id"] == saved_id for p in all_pipes))

        # 2. Server API endpoints
        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), server.DeploymentHandler)
        port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()

        try:
            conn = http.client.HTTPConnection("127.0.0.1", port)
            token = server._get_auth_token()

            # Save via POST /api/deployment/pipelines/save
            save_payload = {
                "app": "test_app",
                "pipeline": {
                    "id": "ci-flow-test",
                    "name": "CI Flow Test",
                    "steps": [{"name": "Build APK", "templateId": "build_apk"}],
                }
            }
            conn.request(
                "POST",
                "/api/deployment/pipelines/save",
                body=json.dumps(save_payload),
                headers={"Content-Type": "application/json", "X-API-Token": token},
            )
            res_save = conn.getresponse()
            self.assertEqual(res_save.status, 200)
            data_save = json.loads(res_save.read().decode("utf-8"))
            self.assertTrue(data_save["success"])
            self.assertEqual(data_save["pipeline"]["id"], "ci-flow-test")

            # Delete via POST /api/deployment/pipelines/delete
            del_payload = {"app": "test_app", "pipelineId": "ci-flow-test"}
            conn.request(
                "POST",
                "/api/deployment/pipelines/delete",
                body=json.dumps(del_payload),
                headers={"Content-Type": "application/json", "X-API-Token": token},
            )
            res_del = conn.getresponse()
            self.assertEqual(res_del.status, 200)
            data_del = json.loads(res_del.read().decode("utf-8"))
            self.assertTrue(data_del["success"])
            self.assertEqual(data_del["deletedId"], "ci-flow-test")
        finally:
            httpd.shutdown()
            httpd.server_close()

        # Clean up backend saved pipeline
        pipelines.delete_pipeline("test_app", saved_id)

    def test_whatsapp_webhook_payload(self):
        """Test WhatsApp provider payload generation."""
        event = {
            "app_name": "whatsapp_test_app",
            "version": "3.2.1",
            "build_number": "100",
            "flavor": "prod",
            "status": "success",
            "duration": "1m 15s",
            "download_url": "https://download.example.com/app.apk",
            "platform": "Android",
        }
        # Direct WhatsApp payload
        payload = notifications.build_webhook_payload("whatsapp", event, phone="+1234567890")
        self.assertEqual(payload.get("messaging_product"), "whatsapp")
        self.assertEqual(payload.get("to"), "+1234567890")
        self.assertIn("whatsapp_test_app", payload.get("text", {}).get("body", ""))
        self.assertIn("SUCCEEDED", payload.get("text", {}).get("body", ""))

        # Provider detection
        self.assertEqual(notifications.detect_webhook_provider("https://graph.facebook.com/v18.0/123/messages"), "whatsapp")
        self.assertEqual(notifications.detect_webhook_provider("https://api.twilio.com/2010-04-01/Accounts/AC/Messages.json"), "whatsapp")

    def test_custom_template_payload(self):
        """Test custom template JSON and text engine."""
        event = {
            "app_name": "custom_app",
            "version": "1.0.0",
            "build_number": "5",
            "flavor": "beta",
            "status": "success",
            "duration": "45s",
            "download_url": "https://example.com/build.ipa",
        }
        # JSON template
        json_template = '{"channel": "#ops", "msg": "Deploy for {appName} v{version} was a {status} in {duration}"}'
        payload = notifications.build_webhook_payload("custom", event, custom_template=json_template)
        self.assertEqual(payload.get("channel"), "#ops")
        self.assertEqual(payload.get("msg"), "Deploy for custom_app v1.0.0 was a success in 45s")

        # Plain text template
        text_template = "Notification: {appName} ({flavor}) status={status} download={downloadUrl}"
        text_payload = notifications.build_webhook_payload("custom", event, custom_template=text_template)
        self.assertIn("custom_app", text_payload.get("text", ""))
        self.assertIn("https://example.com/build.ipa", text_payload.get("text", ""))

    def test_multi_channel_resolution_and_dispatch(self):
        """Test resolving multiple webhook channels and dispatching notifications."""
        app_config = {
            "webhooks": [
                {
                    "name": "Slack Alert",
                    "url": "https://hooks.slack.com/services/T1/B1/X1",
                    "provider": "slack",
                    "enabled": True,
                    "notify_on_success": True,
                },
                {
                    "name": "WhatsApp Dev",
                    "url": "https://graph.facebook.com/v18.0/123/messages",
                    "provider": "whatsapp",
                    "phone": "+1234567890",
                    "enabled": True,
                    "notify_on_success": False,
                    "notify_on_failure": True,
                },
            ]
        }
        with tempfile.TemporaryDirectory() as td:
            ws_root = Path(td)
            cfg_dir = ws_root / ".dev-dashboard"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            (cfg_dir / "deploy_config.json").write_text(json.dumps({
                "apps": {
                    "multi_app": app_config
                },
                "workspace_webhooks": [
                    {
                        "name": "Fallback Discord",
                        "url": "https://discord.com/api/webhooks/999/xyz",
                        "provider": "discord",
                        "enabled": True,
                    }
                ]
            }), encoding="utf-8")

            channels = notifications.get_webhook_channels_for_app("multi_app", ws_root=ws_root)
            self.assertEqual(len(channels), 3)
            self.assertEqual(channels[0]["name"], "Slack Alert")
            self.assertEqual(channels[1]["name"], "WhatsApp Dev")
            self.assertEqual(channels[2]["name"], "Fallback Discord")

    def test_incoming_webhook_endpoints(self):
        """Test universal incoming webhook ingestion for GitHub ping, commands, and pipelines."""
        import http.client
        import http.server
        import server
        import threading

        port = 8783
        server._SERVER_AUTH_TOKEN = "test_auth_secret_incoming"
        old_secret = os.environ.get("WEBHOOK_SECRET")
        os.environ["WEBHOOK_SECRET"] = "webhook_unit_secret_999"

        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), server.DeploymentHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()

        try:
            conn = http.client.HTTPConnection("127.0.0.1", port)

            # 1. GitHub ping event
            conn.request(
                "POST",
                "/api/deployment/webhook/incoming/github",
                body=b"{}",
                headers={
                    "Host": f"localhost:{port}",
                    "Content-Type": "application/json",
                    "X-Webhook-Secret": "webhook_unit_secret_999",
                    "X-GitHub-Event": "ping",
                },
            )
            res_ping = conn.getresponse()
            self.assertEqual(res_ping.status, 200)
            data_ping = json.loads(res_ping.read().decode("utf-8"))
            self.assertTrue(data_ping["success"])
            self.assertIn("Pong", data_ping["message"])

            # 2. GitLab / Generic trigger with Bearer token
            conn.request(
                "POST",
                "/api/deployment/webhook/incoming",
                body=json.dumps({"app": "test_app", "flavor": "prod", "templateId": "build_aab"}),
                headers={
                    "Host": f"localhost:{port}",
                    "Content-Type": "application/json",
                    "Authorization": "Bearer webhook_unit_secret_999",
                },
            )
            res_cmd = conn.getresponse()
            self.assertEqual(res_cmd.status, 200)
            data_cmd = json.loads(res_cmd.read().decode("utf-8"))
            self.assertTrue(data_cmd.get("success") or "started" in data_cmd.get("message", "").lower())

            # 3. Slack slash command urlencoded form
            slack_body = "command=%2Fdeploy&text=test_slack_app+prod+build_aab&user_name=alice"
            conn.request(
                "POST",
                "/api/deployment/webhook/incoming/slack",
                body=slack_body.encode("utf-8"),
                headers={
                    "Host": f"localhost:{port}",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Webhook-Secret": "webhook_unit_secret_999",
                },
            )
            res_slack = conn.getresponse()
            self.assertEqual(res_slack.status, 200)
            data_slack = json.loads(res_slack.read().decode("utf-8"))
            self.assertEqual(data_slack.get("response_type"), "in_channel")
            self.assertIn("🚀", data_slack.get("text", ""))
        finally:
            httpd.shutdown()
            httpd.server_close()
            if old_secret is not None:
                os.environ["WEBHOOK_SECRET"] = old_secret
            else:
                os.environ.pop("WEBHOOK_SECRET", None)

    def test_github_actions_workflow_template_and_install(self):
        import github_actions
        import tempfile
        tmpl = github_actions.get_android_workflow_template()
        self.assertIn("workflow_dispatch:", tmpl)
        self.assertIn("flutter build apk", tmpl)
        self.assertIn("flutter build appbundle", tmpl)

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            ok, msg = github_actions.install_workflow_template(td_path)
            self.assertTrue(ok)
            installed_file = td_path / ".github" / "workflows" / "deploy-android.yml"
            self.assertTrue(installed_file.exists())
            content = installed_file.read_text(encoding="utf-8")
            self.assertIn("name: Build & Package Android", content)

    def test_github_token_and_repo_storage(self):
        import github_actions
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            orig_cfg = github_actions._CONFIG_DIR
            orig_tok = github_actions._GITHUB_TOKEN_FILE
            orig_rep = github_actions._GITHUB_REPO_OVERRIDE_FILE
            try:
                github_actions._CONFIG_DIR = Path(td)
                github_actions._GITHUB_TOKEN_FILE = Path(td) / "github_token.txt"
                github_actions._GITHUB_REPO_OVERRIDE_FILE = Path(td) / "github_repo.txt"

                saved = github_actions.save_github_token("ghp_test_token_1234567890")
                self.assertTrue(saved)
                self.assertEqual(github_actions.get_stored_github_token(), "ghp_test_token_1234567890")

                saved_repo = github_actions.save_repo_override("my-org/my-app")
                self.assertTrue(saved_repo)
                self.assertEqual(github_actions.get_stored_repo_override(), "my-org/my-app")
                self.assertEqual(github_actions.detect_github_repo(), "my-org/my-app")
            finally:
                github_actions._CONFIG_DIR = orig_cfg
                github_actions._GITHUB_TOKEN_FILE = orig_tok
                github_actions._GITHUB_REPO_OVERRIDE_FILE = orig_rep

    def test_cloud_runner_parallel_lock_separation(self):
        """Verify local build locks and cloud runner locks do NOT block each other."""
        import jobs
        import time
        from config import get_workspace_root

        ws_root = get_workspace_root()
        local_lock = f"{ws_root.resolve()}:app_hybrid_test"
        cloud_lock = f"{ws_root.resolve()}:app_hybrid_test:cloud"

        with jobs._JOBS_LOCK:
            # Simulate a local iOS build currently running
            jobs._APP_LOCKS[local_lock] = {
                "job_id": "job_local_123",
                "flavor": "prod",
                "command": "flutter build ipa",
                "started_at": time.time(),
                "workspace": str(ws_root.resolve()),
                "app": "app_hybrid_test",
                "runner": "custom",
            }

        try:
            # Disallow second local build for the same app
            busy_res = jobs.execute_command(
                app="app_hybrid_test",
                command="flutter build ipa",
                flavor="prod",
                runner="custom",
            )
            self.assertFalse(busy_res["success"])
            self.assertEqual(busy_res.get("code"), "APP_BUSY")
            self.assertIn("A deployment job is already running", busy_res.get("error", ""))

            # A cloud GitHub Actions run uses cloud lock and is NOT blocked by the local lock
            cloud_res = jobs.execute_command(
                app="app_hybrid_test",
                command="github-actions build",
                flavor="prod",
                runner="github_actions",
            )
            # Cloud run starts successfully despite local build running simultaneously!
            self.assertTrue(cloud_res["success"])
            self.assertIn("jobId", cloud_res)

            # Stopping cloud job
            stop_res = jobs.stop_job(cloud_res["jobId"])
            self.assertTrue(stop_res["success"])
        finally:
            with jobs._JOBS_LOCK:
                jobs._APP_LOCKS.pop(local_lock, None)
                jobs._APP_LOCKS.pop(cloud_lock, None)

    def test_github_actions_api_routes(self):
        """Test GET and POST GitHub Actions endpoints on backend server."""
        import http.client
        import http.server
        import json
        import threading
        import server
        from server import _get_auth_token

        handler = server.DeploymentHandler
        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()

        token = _get_auth_token()
        headers = {
            "Host": f"localhost:{port}",
            "X-API-Token": token,
            "Content-Type": "application/json",
        }

        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)

            # 1. GET /api/deployment/github/status
            conn.request("GET", "/api/deployment/github/status", headers=headers)
            res_status = conn.getresponse()
            self.assertEqual(res_status.status, 200)
            data_status = json.loads(res_status.read().decode("utf-8"))
            self.assertTrue(data_status.get("success"))
            self.assertIn("workflowFile", data_status)

            # 2. GET /api/deployment/github/template
            conn.request("GET", "/api/deployment/github/template", headers=headers)
            res_tmpl = conn.getresponse()
            self.assertEqual(res_tmpl.status, 200)
            data_tmpl = json.loads(res_tmpl.read().decode("utf-8"))
            self.assertTrue(data_tmpl.get("success"))
            self.assertIn("workflow_dispatch:", data_tmpl.get("template", ""))

            # 3. POST /api/deployment/github/config
            body_cfg = json.dumps({"token": "ghp_api_test_tok_99", "repo": "test-org/test-repo"})
            conn.request("POST", "/api/deployment/github/config", body=body_cfg.encode("utf-8"), headers=headers)
            res_cfg = conn.getresponse()
            self.assertEqual(res_cfg.status, 200)
            data_cfg = json.loads(res_cfg.read().decode("utf-8"))
            self.assertTrue(data_cfg.get("success"))

            # 4. POST /api/deployment/github/install-template
            conn.request("POST", "/api/deployment/github/install-template", body=b"{}", headers=headers)
            res_inst = conn.getresponse()
            self.assertEqual(res_inst.status, 200)
            data_inst = json.loads(res_inst.read().decode("utf-8"))
            self.assertTrue(data_inst.get("success"))
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_ios_ota_manifest_and_download_endpoints(self):
        """Test Task 1: iOS OTA manifest plist generation and streaming endpoints."""
        import artifacts
        import http.client
        import http.server
        import server
        import threading
        from server import _get_auth_token

        # 1. Manifest generation test
        manifest_xml = artifacts.generate_ota_manifest_plist(
            ipa_download_url="https://192.168.1.100:18112/api/deployment/download-ipa/test_app",
            bundle_id="com.company.testapp",
            version="2.0.1",
            title="Test App",
        )
        self.assertIn("software-package", manifest_xml)
        self.assertIn("com.company.testapp", manifest_xml)
        self.assertIn("https://192.168.1.100:18112/api/deployment/download-ipa/test_app", manifest_xml)

        # 2. Server API routes test
        handler = server.DeploymentHandler
        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()

        token = _get_auth_token()
        headers = {"Host": f"localhost:{port}", "X-API-Token": token}

        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)

            # GET /api/deployment/ipa-info
            conn.request("GET", "/api/deployment/ipa-info?app=test_app", headers=headers)
            res_info = conn.getresponse()
            self.assertEqual(res_info.status, 200)
            data_info = json.loads(res_info.read().decode("utf-8"))
            self.assertTrue(data_info.get("success"))

            # Unauthorized IPA download without token should return 401
            conn.request("GET", "/api/deployment/download-ipa/test_app", headers={"Host": f"localhost:{port}"})
            res_unauth = conn.getresponse()
            self.assertEqual(res_unauth.status, 401)
            res_unauth.read()
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_wireless_adb_manager_and_endpoints(self):
        """Test Task 2: Wireless ADB discovery, connect, and parallel push."""
        import adb_manager
        import http.client
        import http.server
        import server
        import threading
        from server import _get_auth_token

        # 1. Device discovery (handles both when adb is available or not without crashing)
        devices_res = adb_manager.get_adb_devices()
        self.assertTrue(devices_res.get("success"))
        self.assertIn("devices", devices_res)

        # 2. Server endpoints
        handler = server.DeploymentHandler
        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()

        token = _get_auth_token()
        headers = {"Host": f"localhost:{port}", "X-API-Token": token, "Content-Type": "application/json"}

        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)

            # GET /api/deployment/adb/devices
            conn.request("GET", "/api/deployment/adb/devices", headers=headers)
            res_dev = conn.getresponse()
            self.assertEqual(res_dev.status, 200)
            data_dev = json.loads(res_dev.read().decode("utf-8"))
            self.assertTrue(data_dev.get("success"))

            # POST /api/deployment/adb/connect
            conn.request("POST", "/api/deployment/adb/connect", body=json.dumps({"address": "127.0.0.1:5555"}), headers=headers)
            res_conn = conn.getresponse()
            self.assertEqual(res_conn.status, 200)
            data_conn = json.loads(res_conn.read().decode("utf-8"))
            self.assertIn("success", data_conn)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_chatops_two_way_bot_response_url(self):
        """Test Task 3: Two-way ChatOps callback using response_url."""
        import jobs
        import notifications

        # 1. Verify execute_command stores response_url
        res = jobs.execute_command(
            app="test_chatops_app",
            command="echo 'chatops test'",
            runner="custom",
            response_url="https://hooks.slack.com/commands/123/456/mock-response-url",
        )
        self.assertTrue(res.get("success"))
        job_id = res.get("jobId")
        stored_job = jobs.get_job(job_id).get("job")
        self.assertEqual(stored_job.get("response_url"), "https://hooks.slack.com/commands/123/456/mock-response-url")

        # 2. Verify Slack payload includes action buttons and OTA/QR
        event_data = {
            "app": "test_app",
            "flavor": "prod",
            "status": "success",
            "downloadUrl": "https://example.com/dl/app.ipa",
            "itmsUrl": "itms-services://?action=download-manifest&url=https://example.com/manifest.plist",
            "qrUrl": "https://example.com/qr",
            "durationFormatted": "45s",
        }
        slack_payload = notifications.build_slack_payload(event_data)
        self.assertIn("blocks", slack_payload)
        has_ota_btn = False
        for b in slack_payload["blocks"]:
            if b.get("type") == "actions":
                for elem in b.get("elements", []):
                    if "OTA" in elem.get("text", {}).get("text", ""):
                        has_ota_btn = True
        self.assertTrue(has_ota_btn)

    def test_build_time_profiler_and_bottleneck_heatmap(self):
        """Test Task 4: Compilation timing breakdown and bottleneck detection."""
        import build_profiler
        import http.client
        import http.server
        import server
        import threading
        from server import _get_auth_token

        mock_log = """
> Task :app:preBuild (0.4s)
> Task :app:compileFlutterBuildDebug (14.5s)
> Task :app:processDebugResources (6.2s)
> Task :app:mergeDebugNativeLibs (1.8s)
> Task :app:packageDebug (3.1s)
> Task :app:validateSigningDebug (0.5s)
        """
        profile = build_profiler.profile_build_log(mock_log, total_duration_sec=26.5)
        self.assertTrue(profile["success"])
        self.assertGreaterEqual(len(profile["phases"]), 6)

        # Verify compilation phase was detected as top contributor
        comp_phase = next(p for p in profile["phases"] if p["id"] == "compilation")
        self.assertGreater(comp_phase["percentage"], 40.0)
        self.assertTrue(profile["hasBottlenecks"])
        self.assertEqual(profile["bottlenecks"][0]["phaseId"], "compilation")

        # Test server endpoint
        handler = server.DeploymentHandler
        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()

        token = _get_auth_token()
        headers = {"Host": f"localhost:{port}", "X-API-Token": token}

        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("GET", "/api/deployment/build-profile", headers=headers)
            res_bp = conn.getresponse()
            self.assertEqual(res_bp.status, 200)
            data_bp = json.loads(res_bp.read().decode("utf-8"))
            self.assertIn("success", data_bp)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_smart_silent_cache_warmer(self):
        """Test Task 5: Smart silent cache warmer status, trigger, and daemon."""
        import cache_warmer
        import http.client
        import http.server
        import server
        import threading
        from server import _get_auth_token

        # Status check
        status = cache_warmer.get_cache_warmer_status()
        self.assertTrue(status.get("success"))
        self.assertIn("status", status)

        # Trigger warm check
        warm_res = cache_warmer.trigger_cache_warm(force=False)
        self.assertTrue(warm_res.get("success"))

        # Test daemon start and stop
        cache_warmer.start_cache_warmer_daemon()
        st_after = cache_warmer.get_cache_warmer_status()
        self.assertTrue(st_after.get("isWatching"))
        cache_warmer.stop_cache_warmer_daemon()

        # Test server endpoints
        handler = server.DeploymentHandler
        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()

        token = _get_auth_token()
        headers = {"Host": f"localhost:{port}", "X-API-Token": token, "Content-Type": "application/json"}

        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)

            # GET /api/deployment/cache-warmer/status
            conn.request("GET", "/api/deployment/cache-warmer/status", headers=headers)
            res_st = conn.getresponse()
            self.assertEqual(res_st.status, 200)
            data_st = json.loads(res_st.read().decode("utf-8"))
            self.assertTrue(data_st.get("success"))

            # POST /api/deployment/cache-warmer/warm
            conn.request("POST", "/api/deployment/cache-warmer/warm", body=json.dumps({"force": False}), headers=headers)
            res_warm = conn.getresponse()
            self.assertEqual(res_warm.status, 200)
            data_warm = json.loads(res_warm.read().decode("utf-8"))
            self.assertTrue(data_warm.get("success"))
        finally:
            httpd.shutdown()
            httpd.server_close()




