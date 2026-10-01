import json
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
import pipelines


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

    def test_other_p8_keys_are_listed_but_not_importable(self):
        (self.downloads / "SubscriptionKey_VSN447PHNL.p8").write_bytes(P8_PEM)
        kinds = [f["kind"] for f in self.cred.scan_credentials(str(self.downloads))["found"]]
        self.assertIn("apple_other_p8", kinds)
        res = self.cred.import_credential_path(str(self.downloads / "SubscriptionKey_VSN447PHNL.p8"))
        self.assertFalse(res["success"])

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



