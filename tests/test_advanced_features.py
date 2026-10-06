"""Unit tests for the 5 advanced automation and diagnostic features:
1. Deep Link & Universal Link Validator
2. Store Metadata & Release Notes Previewer
3. Crash Symbol Vault (dSYM & ProGuard Mappings)
4. Semantic Version Bumper & Conventional Commit Changelog
5. Mobile Security & Dangerous Permissions Inspector

Pure Python standard library only.
"""

import http.client
import json
import os
import plistlib
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

# Setup sys.path
BACKEND_DIR = Path(__file__).resolve().parents[1] / "features" / "deployment" / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import config
import doctor
import metadata
import artifacts
import automation
import router
import server

from _isolation import isolate_dashboard_config, restore_dashboard_config


def setUpModule():
    isolate_dashboard_config()


def tearDownModule():
    restore_dashboard_config()


class TestDeepLinkValidator(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.app_dir = Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_extract_android_domains(self):
        manifest_dir = self.app_dir / "android" / "app" / "src" / "main"
        manifest_dir.mkdir(parents=True)
        manifest_xml = """<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.example.app">
    <application>
        <activity android:name=".MainActivity">
            <intent-filter android:autoVerify="true">
                <action android:name="android.intent.action.VIEW"/>
                <category android:name="android.intent.category.BROWSABLE"/>
                <data android:scheme="https" android:host="app.acme.com"/>
                <data android:scheme="https" android:host="links.acme.com"/>
            </intent-filter>
        </activity>
    </application>
</manifest>"""
        (manifest_dir / "AndroidManifest.xml").write_text(manifest_xml, encoding="utf-8")

        domains = doctor.extract_android_domains(self.app_dir)
        self.assertIn("app.acme.com", domains)
        self.assertIn("links.acme.com", domains)
        self.assertEqual(len(domains), 2)

    def test_extract_ios_domains(self):
        ios_dir = self.app_dir / "ios" / "Runner"
        ios_dir.mkdir(parents=True)
        entitlements_xml = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.developer.associated-domains</key>
    <array>
        <string>applinks:app.acme.com</string>
        <string>applinks:mobile.acme.com</string>
    </array>
</dict>
</plist>"""
        (ios_dir / "Runner.entitlements").write_text(entitlements_xml, encoding="utf-8")

        domains = doctor.extract_ios_domains(self.app_dir)
        self.assertIn("app.acme.com", domains)
        self.assertIn("mobile.acme.com", domains)
        self.assertEqual(len(domains), 2)

    @patch("doctor.deep_links.fetch_url_json")
    def test_verify_android_assetlinks_valid(self, mock_fetch):
        mock_fetch.return_value = ([
            {
                "relation": ["delegate_permission/common.handle_all_urls"],
                "target": {
                    "namespace": "android_app",
                    "package_name": "com.example.app",
                    "sha256_cert_fingerprints": [
                        "AA:BB:CC:DD:EE:FF:11:22:33:44:55:66:77:88:99:00:AA:BB:CC:DD:EE:FF:11:22:33:44:55:66:77:88:99:00"
                    ]
                }
            }
        ], None)

        res = doctor.verify_android_assetlinks(
            "app.acme.com",
            package_name="com.example.app",
            expected_fingerprint="aabbccddeeff11223344556677889900aabbccddeeff11223344556677889900"
        )
        self.assertEqual(res["status"], "valid")
        self.assertTrue(res["packageMatched"])
        self.assertTrue(res["fingerprintMatched"])

    @patch("doctor.deep_links.fetch_url_json")
    def test_verify_apple_aasa_valid(self, mock_fetch):
        mock_fetch.return_value = ({
            "applinks": {
                "apps": [],
                "details": [
                    {
                        "appID": "TEAM12345.com.example.app",
                        "paths": ["/open/*", "/products/*"]
                    }
                ]
            }
        }, None)

        res = doctor.verify_apple_aasa("app.acme.com", team_id="TEAM12345", bundle_id="com.example.app")
        self.assertEqual(res["status"], "valid")
        self.assertTrue(res["teamMatched"])
        self.assertTrue(res["bundleMatched"])


class TestStoreMetadata(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.orig_ws = config.WORKSPACE_ROOT
        config.WORKSPACE_ROOT = Path(self.tmp_dir.name)
        self.app_dir = config.WORKSPACE_ROOT / "apps" / "my_app"
        self.app_dir.mkdir(parents=True)

    def tearDown(self):
        config.WORKSPACE_ROOT = self.orig_ws
        self.tmp_dir.cleanup()

    def test_save_and_get_store_metadata(self):
        save_res = metadata.save_store_metadata(
            app_id="my_app",
            platform="android",
            locale="en-US",
            release_notes="New fast checkout and bug fixes.",
            title="My Acme App",
            short_description="Best shopping experience",
            description="Detailed app description here.",
        )
        self.assertTrue(save_res["success"])

        data = metadata.get_store_metadata("my_app")
        self.assertTrue(data["success"])
        android_en = data["android"]["locales"].get("en-US")
        self.assertIsNotNone(android_en)
        self.assertEqual(android_en["changelog"], "New fast checkout and bug fixes.")
        self.assertEqual(android_en["title"], "My Acme App")
        self.assertFalse(android_en["changelogExceeds"])

        # Test preview card
        card = metadata.preview_store_card("my_app", platform="android", locale="en-US")
        self.assertTrue(card["success"])
        self.assertEqual(card["appTitle"], "My Acme App")
        self.assertEqual(card["whatsNew"], "New fast checkout and bug fixes.")

    def test_changelog_character_limit_exceeded(self):
        long_notes = "A" * 550
        metadata.save_store_metadata(
            app_id="my_app",
            platform="android",
            locale="es-ES",
            release_notes=long_notes,
        )
        data = metadata.get_store_metadata("my_app")
        android_es = data["android"]["locales"].get("es-ES")
        self.assertTrue(android_es["changelogExceeds"])
        self.assertEqual(android_es["changelogLength"], 550)


class TestCrashSymbolVault(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.orig_ws = config.WORKSPACE_ROOT
        config.WORKSPACE_ROOT = Path(self.tmp_dir.name)
        self.app_dir = config.WORKSPACE_ROOT / "apps" / "test_app"
        self.app_dir.mkdir(parents=True)

    def tearDown(self):
        config.WORKSPACE_ROOT = self.orig_ws
        self.tmp_dir.cleanup()

    def test_scan_and_package_symbols(self):
        # Create dummy mapping.txt
        mapping_dir = self.app_dir / "build" / "app" / "outputs" / "mapping" / "prodRelease"
        mapping_dir.mkdir(parents=True)
        mapping_file = mapping_dir / "mapping.txt"
        mapping_file.write_text("com.example.Foo -> a.b:\n    int x -> a\n", encoding="utf-8")

        # Create dummy dSYM folder
        dsym_dir = self.app_dir / "build" / "ios" / "iphoneos" / "Runner.app.dSYM" / "Contents"
        dsym_dir.mkdir(parents=True)
        (dsym_dir / "Info.plist").write_text("<plist></plist>", encoding="utf-8")

        res = artifacts.scan_symbols("test_app", flavor="prod")
        self.assertTrue(res["success"])
        self.assertEqual(len(res["mappings"]), 1)
        self.assertEqual(res["mappings"][0]["filename"], "mapping.txt")
        self.assertEqual(len(res["dsyms"]), 1)
        self.assertIn("Runner.app.dSYM", res["dsyms"][0]["filename"])

        # Test ZIP packaging
        zip_bytes = artifacts.package_symbols_zip("test_app", symbol_type="all", flavor="prod")
        self.assertGreater(len(zip_bytes), 50)
        self.assertTrue(zip_bytes.startswith(b"PK\x03\x04"))


class TestVersionBumperAndChangelog(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.orig_ws = config.WORKSPACE_ROOT
        config.WORKSPACE_ROOT = Path(self.tmp_dir.name)
        self.app_dir = config.WORKSPACE_ROOT / "apps" / "ver_app"
        self.app_dir.mkdir(parents=True)

    def tearDown(self):
        config.WORKSPACE_ROOT = self.orig_ws
        self.tmp_dir.cleanup()

    def test_parse_and_bump_version(self):
        pubspec = self.app_dir / "pubspec.yaml"
        pubspec.write_text("name: ver_app\nversion: 1.2.3+45\n\ndependencies:\n  flutter:\n    sdk: flutter\n", encoding="utf-8")

        info = automation.get_version_info("ver_app")
        self.assertTrue(info["success"])
        self.assertEqual(info["current"]["major"], 1)
        self.assertEqual(info["current"]["minor"], 2)
        self.assertEqual(info["current"]["patch"], 3)
        self.assertEqual(info["current"]["build"], 45)
        self.assertEqual(info["previews"]["patch"], "1.2.4+46")
        self.assertEqual(info["previews"]["minor"], "1.3.0+46")

        # Bump patch
        bump_res = automation.bump_version("ver_app", bump_type="patch")
        self.assertTrue(bump_res["success"])
        self.assertEqual(bump_res["newVersion"], "1.2.4+46")

        # Read back
        parsed_after = automation.parse_pubspec_version(pubspec)
        self.assertEqual(parsed_after["raw"], "1.2.4+46")

    def test_generate_changelog_conventional(self):
        # Mock subprocess run to simulate git log
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = (
                "a1b2c3d|||feat(auth): add biometrics login|||John Doe|||2026-10-06\n"
                "e4f5a6b|||fix(cart): resolve checkout crash on tablet|||Jane Doe|||2026-10-06\n"
                "c7d8e9f|||perf(images): compress cached avatars|||John Doe|||2026-10-06\n"
            )
            res = automation.generate_changelog("ver_app")
            self.assertTrue(res["success"])
            self.assertEqual(res["commitCount"], 3)
            self.assertIn("Features 🚀", res["markdownChangelog"])
            self.assertIn("Bug Fixes 🐛", res["markdownChangelog"])
            self.assertIn("Performance Improvements ⚡", res["markdownChangelog"])
            self.assertIn("biometrics login", res["storeNotes"])
            self.assertFalse(res["storeNotesExceedsLimit"])


class TestSecurityAndPermissionsInspector(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.orig_ws = config.WORKSPACE_ROOT
        config.WORKSPACE_ROOT = Path(self.tmp_dir.name)
        self.app_dir = config.WORKSPACE_ROOT / "apps" / "sec_app"
        self.app_dir.mkdir(parents=True)

    def tearDown(self):
        config.WORKSPACE_ROOT = self.orig_ws
        self.tmp_dir.cleanup()

    def test_inspect_android_security(self):
        manifest_dir = self.app_dir / "android" / "app" / "src" / "main"
        manifest_dir.mkdir(parents=True)
        (manifest_dir / "AndroidManifest.xml").write_text("""<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.sec.app">
    <uses-permission android:name="android.permission.INTERNET"/>
    <uses-permission android:name="android.permission.CAMERA"/>
    <uses-permission android:name="android.permission.ACCESS_BACKGROUND_LOCATION"/>
    <application android:usesCleartextTraffic="true">
        <activity android:name=".MainActivity" android:exported="true"/>
        <service android:name=".SecretService" android:exported="true"/>
    </application>
</manifest>""", encoding="utf-8")

        sec = doctor.scan_android_security(self.app_dir)
        self.assertTrue(sec["manifestFound"])
        self.assertEqual(sec["dangerousCount"], 2)  # CAMERA and ACCESS_BACKGROUND_LOCATION
        self.assertTrue(sec["usesCleartextTraffic"])
        self.assertIn("android:usesCleartextTraffic is enabled", sec["warnings"][0])

    def test_inspect_ios_security(self):
        ios_dir = self.app_dir / "ios" / "Runner"
        ios_dir.mkdir(parents=True)
        plist_data = {
            "NSCameraUsageDescription": "We use your camera to scan customer loyalty cards.",
            "NSMicrophoneUsageDescription": "TODO",
            "NSAppTransportSecurity": {
                "NSAllowsArbitraryLoads": True,
            }
        }
        with open(ios_dir / "Info.plist", "wb") as f:
            plistlib.dump(plist_data, f)

        sec = doctor.scan_ios_security(self.app_dir)
        self.assertTrue(sec["plistFound"])
        self.assertEqual(sec["configuredPrivacyCount"], 2)
        self.assertTrue(sec["allowsArbitraryLoads"])
        # Flagged suspicious description for TODO
        suspicious = [p for p in sec["configuredPrivacy"] if p["isSuspicious"]]
        self.assertEqual(len(suspicious), 1)
        self.assertEqual(suspicious[0]["key"], "NSMicrophoneUsageDescription")


class TestAdvancedEndpointsIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import http.server
        cls.orig_ws = config.WORKSPACE_ROOT
        cls.tmp_ws = tempfile.TemporaryDirectory()
        config.WORKSPACE_ROOT = Path(cls.tmp_ws.name)
        cls.app = config.WORKSPACE_ROOT / "apps" / "demo_app"
        cls.app.mkdir(parents=True)
        (cls.app / "pubspec.yaml").write_text("name: demo_app\nversion: 2.1.0+10\n", encoding="utf-8")

        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), server.DeploymentHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=1.0)
        config.WORKSPACE_ROOT = cls.orig_ws
        cls.tmp_ws.cleanup()

    def _headers(self):
        token = server._get_auth_token()
        return {"X-API-Token": token, "Content-Type": "application/json"}

    def test_version_endpoints(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        conn.request("GET", "/api/deployment/version?app=demo_app", headers=self._headers())
        res = conn.getresponse()
        self.assertEqual(res.status, 200)
        data = json.loads(res.read().decode())
        self.assertTrue(data["success"])
        self.assertEqual(data["current"]["major"], 2)

        # POST bump
        conn.request(
            "POST",
            "/api/deployment/version/bump",
            body=json.dumps({"app": "demo_app", "bumpType": "patch"}),
            headers=self._headers(),
        )
        bump_res = conn.getresponse()
        self.assertEqual(bump_res.status, 200)
        bump_data = json.loads(bump_res.read().decode())
        self.assertTrue(bump_data["success"])
        self.assertEqual(bump_data["newVersion"], "2.1.1+11")

    def test_symbols_and_download(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        conn.request("GET", "/api/deployment/symbols?app=demo_app", headers=self._headers())
        res = conn.getresponse()
        self.assertEqual(res.status, 200)
        data = json.loads(res.read().decode())
        self.assertTrue(data["success"])
        self.assertIn("downloadUrl", data)
        token = data["downloadToken"]

        # Download with scoped token
        conn.request("GET", f"/api/deployment/symbols/download?app=demo_app&token={token}")
        dl_res = conn.getresponse()
        self.assertEqual(dl_res.status, 200)
        self.assertEqual(dl_res.getheader("Content-Type"), "application/zip")
        raw_zip = dl_res.read()
        self.assertTrue(raw_zip.startswith(b"PK\x03\x04"))

    def test_security_endpoint(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        conn.request("GET", "/api/deployment/security/permissions?app=demo_app", headers=self._headers())
        res = conn.getresponse()
        self.assertEqual(res.status, 200)
        data = json.loads(res.read().decode())
        self.assertTrue(data["success"])
        self.assertIn("riskLevel", data)


if __name__ == "__main__":
    unittest.main()
