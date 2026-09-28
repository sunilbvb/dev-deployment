#!/usr/bin/env python3
import argparse
import hmac
import http.server
import hashlib
import io
import json
import os
import sys
from email.parser import BytesFeedParser
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import router

FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
SHARED_FRONTEND_DIR = Path(__file__).resolve().parents[3] / "frontend"
SHARED_ASSET_PREFIXES = ("css/", "js/", "assets/")


def _get_auth_token() -> str:
    token = os.environ.get("DEPLOYMENT_AUTH_TOKEN", "").strip()
    if not token:
        token_file = router.WORKSPACE_ROOT / ".dev-dashboard" / "auth_token.txt"
        if token_file.exists():
            try:
                token = token_file.read_text(encoding="utf-8").strip()
            except Exception:
                pass
    return token


def _content_type(path: Path) -> str:
    if path.suffix == ".css":
        return "text/css; charset=utf-8"
    if path.suffix == ".js":
        return "application/javascript; charset=utf-8"
    if path.suffix == ".png":
        return "image/png"
    if path.suffix in (".jpg", ".jpeg"):
        return "image/jpeg"
    if path.suffix == ".webp":
        return "image/webp"
    if path.suffix == ".svg":
        return "image/svg+xml"
    return "application/octet-stream"


class DeploymentHandler(http.server.SimpleHTTPRequestHandler):
    def _is_allowed_origin(self, origin: str) -> bool:
        if not origin:
            return True
        parsed = urlparse(origin)
        host_header = self.headers.get("Host", "")
        # Allow localhost and 127.0.0.1 or exact Host match
        if parsed.hostname in ("localhost", "127.0.0.1", "0.0.0.0"):
            return True
        if host_header and (parsed.netloc == host_header or parsed.hostname == host_header.split(":")[0]):
            return True
        return False

    def end_headers(self) -> None:
        origin = self.headers.get("Origin", "")
        if origin and self._is_allowed_origin(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-API-Token, X-Webhook-Secret, X-Hub-Signature-256")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        origin = self.headers.get("Origin", "")
        if origin and not self._is_allowed_origin(origin):
            self.send_response(403)
            self.end_headers()
            return
        self.send_response(204)
        self.end_headers()

    def _verify_auth(self) -> bool:
        expected_token = _get_auth_token()
        if not expected_token:
            return True  # If no auth token configured, fallback to standard origin/CSRF checks

        token = self.headers.get("X-API-Token", "").strip()
        if not token:
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            token = query.get("token", [""])[0].strip()

        return hmac.compare_digest(token, expected_token)

    def do_GET(self) -> None:
        origin = self.headers.get("Origin", "")
        if origin and not self._is_allowed_origin(origin):
            self.send_error(403, "Cross-origin request rejected")
            return

        parsed = urlparse(self.path)
        if parsed.path == "/api/deployment/workspaces":
            self.write_json(router.get_workspaces_list())
            return
        if parsed.path == "/api/deployment/inspect-path":
            query = parse_qs(parsed.query)
            self.write_json(router.inspect_workspace_path(query.get("path", [""])[0]))
            return
        if parsed.path == "/api/deployment/apps":
            self.write_json(router.get_apps())
            return
        if parsed.path == "/api/deployment/commands":
            query = parse_qs(parsed.query)
            self.write_json(router.get_commands(query.get("app", [""])[0]))
            return
        if parsed.path == "/api/deployment/deploy-config":
            self.write_json({"success": True, "config": router.load_deploy_config()})
            return
        if parsed.path == "/api/deployment/templates":
            self.write_json({"success": True, "templates": router.load_templates()})
            return
        if parsed.path == "/api/deployment/scan-config":
            query = parse_qs(parsed.query)
            self.write_json(router.scan_app_config(query.get("app", [""])[0]))
            return
        if parsed.path == "/api/app-icon":
            query = parse_qs(parsed.query)
            self.serve_app_icon(query.get("url", [""])[0])
            return
        if parsed.path == "/api/deployment/job":
            query = parse_qs(parsed.query)
            self.write_json(router.get_job(query.get("id", [None])[0]))
            return
        if parsed.path == "/api/deployment/history":
            query = parse_qs(parsed.query)
            try:
                limit = int(query.get("limit", ["50"])[0])
            except (TypeError, ValueError):
                limit = 50
            self.write_json(router.get_deployment_history(
                limit=limit,
                app=query.get("app", [""])[0],
                flavor=query.get("flavor", [""])[0],
                status=query.get("status", [""])[0],
            ))
            return
        if parsed.path == "/api/deployment/ios-cert-check":
            query = parse_qs(parsed.query)
            self.write_json(router.check_ios_expiry(
                query.get("app", [""])[0],
                query.get("flavor", ["prod"])[0],
            ))
            return
        if parsed.path == "/api/deployment/batch-plan":
            query = parse_qs(parsed.query)
            self.write_json(router.get_batch_deploy_plan(
                query.get("flavor", [""])[0],
                query.get("templateId", ["auto"])[0],
            ))
            return
        if parsed.path.startswith("/api/"):
            self.write_json({"success": False, "error": f"Unknown endpoint: {parsed.path}"}, status=404)
            return
        if parsed.path == "/dashboard.html":
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()
            return
        if parsed.path in ("", "/"):
            self.path = "/index.html"
        if not self._is_safe_static_path(self.path):
            self.send_error(403, "Forbidden")
            return
        return super().do_GET()

    def _is_safe_static_path(self, path: str) -> bool:
        parsed = urlparse(path)
        relative = parsed.path.lstrip("/") or "index.html"
        base_dir = SHARED_FRONTEND_DIR if relative.startswith(SHARED_ASSET_PREFIXES) else FRONTEND_DIR
        candidate = (base_dir / relative).resolve()
        return candidate == base_dir or base_dir in candidate.parents

    def do_POST(self) -> None:
        origin = self.headers.get("Origin", "")
        if origin and not self._is_allowed_origin(origin):
            self.send_error(403, "Cross-origin request rejected")
            return

        parsed = urlparse(self.path)
        content_type_header = self.headers.get("Content-Type", "")

        try:
            length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(length) if length else b""
        except Exception:
            raw_body = b""

        # --- Multipart upload routes ---
        if parsed.path == "/api/deployment/p8/upload" and content_type_header.startswith("multipart/form-data"):
            if not self._verify_auth():
                self.write_json({"success": False, "error": "Unauthorized API token"}, status=401)
                return

            mime_header = f"Content-Type: {content_type_header}\r\n\r\n".encode()
            parser = BytesFeedParser()
            parser.feed(mime_header)
            parser.feed(raw_body)
            msg = parser.close()

            fields: dict[str, str] = {}
            file_content: bytes | None = None
            file_name: str = "AuthKey.p8"

            for part in msg.get_payload():
                disposition = part.get("Content-Disposition", "")
                name = ""
                for seg in disposition.split(";"):
                    seg = seg.strip()
                    if seg.startswith("name="):
                        name = seg[5:].strip().strip('"')
                    elif seg.startswith("filename="):
                        file_name = seg[9:].strip().strip('"')
                payload = part.get_payload(decode=True) or b""
                if name == "file":
                    file_content = payload
                else:
                    fields[name] = payload.decode("utf-8", errors="replace")

            app_id = fields.get("app_id", "")
            issuer_id = fields.get("issuer_id", "")
            if not file_content or not app_id:
                self.write_json({"success": False, "error": "Missing 'app_id' or 'file' field."}, status=400)
                return
            self.write_json(router.upload_p8_key(app_id, file_name, file_content, issuer_id))
            return

        # Enforce strict application/json content type for API POST requests
        if not content_type_header.startswith("application/json"):
            self.write_json({"success": False, "error": "Content-Type must be application/json"}, status=415)
            return

        if parsed.path != "/api/deployment/webhook" and not self._verify_auth():
            self.write_json({"success": False, "error": "Unauthorized API token"}, status=401)
            return

        try:
            data = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        except Exception:
            data = {}

        if parsed.path == "/api/deployment/execute":
            app_id = str(data.get("app") or "")
            req_cmd = str(data.get("command") or "")
            req_runner = str(data.get("runner") or "make")
            req_template_id = str(data.get("templateId") or "")
            req_flavor = str(data.get("flavor") or "")

            # Security: lookup server-registered template command to avoid raw command injection
            allowed_cmds = router.get_commands(app_id).get("commands", [])
            target_cmd = None
            for c in allowed_cmds:
                if req_template_id and c.get("templateId") == req_template_id and (c.get("flavor") == req_flavor or c.get("flavor") == "any"):
                    target_cmd = c
                    break
                elif c.get("key") == req_cmd:
                    target_cmd = c
                    break

            if not target_cmd and req_cmd:
                # If command doesn't match a server-generated template, check if runner is custom and block arbitrary command
                self.write_json({"success": False, "error": "Custom arbitrary command execution is disabled. Select a valid template."}, status=400)
                return

            exec_cmd = target_cmd.get("key") if target_cmd else req_cmd
            exec_runner = target_cmd.get("runner") if target_cmd else req_runner

            self.write_json(router.execute_command(
                app_id,
                exec_cmd,
                exec_runner,
                str(data.get("env") or ""),
                req_template_id or (target_cmd.get("templateId") if target_cmd else ""),
                req_flavor or (target_cmd.get("flavor") if target_cmd else ""),
                bool(data.get("confirmed") or False),
            ))
            return
        if parsed.path == "/api/deployment/job/stop":
            self.write_json(router.stop_job(data.get("jobId")))
            return
        if parsed.path == "/api/deployment/deploy-config/save":
            self.write_json(router.save_deploy_config(data))
            return
        if parsed.path == "/api/deployment/regenerate-commands":
            self.write_json(router.regenerate_commands())
            return
        if parsed.path == "/api/deployment/scan-all":
            self.write_json(router.scan_all_apps_config())
            return
        if parsed.path in ("/api/deployment/apps/save", "/api/deployment/apps"):
            self.write_json(router.add_app(data))
            return
        if parsed.path == "/api/deployment/workspace/select":
            self.write_json(router.set_active_workspace(str(data.get("path") or "")))
            return
        if parsed.path == "/api/deployment/p8/upload":
            import base64 as _b64
            filename = str(data.get("filename") or "AuthKey.p8")
            app_id = str(data.get("app_id") or "")
            issuer_id = str(data.get("issuer_id") or "")
            b64 = str(data.get("content_base64") or "")
            if not app_id or not b64:
                self.write_json({"success": False, "error": "Missing 'app_id' or 'content_base64'."}, status=400)
                return
            try:
                content_bytes = _b64.b64decode(b64)
            except Exception as exc:
                self.write_json({"success": False, "error": f"Invalid base64: {exc}"}, status=400)
                return
            self.write_json(router.upload_p8_key(app_id, filename, content_bytes, issuer_id))
            return
        if parsed.path == "/api/deployment/webhook":
            # Webhook HMAC / Shared secret authentication
            webhook_secret = os.environ.get("WEBHOOK_SECRET", "").strip()
            if webhook_secret:
                provided_secret = self.headers.get("X-Webhook-Secret", "").strip()
                signature_header = self.headers.get("X-Hub-Signature-256", "").strip()
                valid = False
                if provided_secret and hmac.compare_digest(provided_secret, webhook_secret):
                    valid = True
                elif signature_header and signature_header.startswith("sha256="):
                    expected_sig = hmac.new(webhook_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
                    valid = hmac.compare_digest(signature_header[7:], expected_sig)

                if not valid:
                    self.write_json({"success": False, "error": "Invalid webhook secret or HMAC signature"}, status=401)
                    return

            app_id = str(data.get("app") or "")
            flavor = str(data.get("flavor") or "prod")
            template_id = str(data.get("templateId") or "build_aab")
            cmds = router.get_commands(app_id).get("commands", [])
            target_cmd = None
            for c in cmds:
                if c.get("templateId") == template_id and (c.get("flavor") == flavor or c.get("flavor") == "any"):
                    target_cmd = c
                    break
            if not target_cmd:
                self.write_json({"success": False, "error": f"No matching command found for app '{app_id}', template '{template_id}', flavor '{flavor}'"}, status=400)
                return
            self.write_json(router.execute_command(
                app_id,
                target_cmd.get("command", ""),
                target_cmd.get("runner", "custom"),
                flavor,
                template_id,
                flavor,
                bool(data.get("confirmed") or False),
            ))
            return
        self.write_json({"success": False, "error": "Unknown endpoint"}, status=404)

    def translate_path(self, path: str) -> str:
        parsed = urlparse(path)
        relative = parsed.path.lstrip("/") or "index.html"

        if relative.startswith(SHARED_ASSET_PREFIXES):
            return str((SHARED_FRONTEND_DIR / relative).resolve())

        return str((FRONTEND_DIR / relative).resolve())

    def serve_app_icon(self, raw_url: str) -> None:
        if not raw_url or raw_url.startswith(("http://", "https://")):
            self.send_error(404, "Icon not available locally")
            return

        candidates = []
        raw_path = Path(raw_url)
        if raw_path.is_absolute():
            candidates.append(raw_path)
        else:
            candidates.append(router.WORKSPACE_ROOT / raw_url)
            candidates.append(SHARED_FRONTEND_DIR / raw_url)
            candidates.append(Path(__file__).resolve().parents[3] / raw_url)

        for candidate in candidates:
            resolved = candidate.resolve()
            allowed_roots = [router.WORKSPACE_ROOT.resolve(), SHARED_FRONTEND_DIR.resolve()]
            if not any(resolved == root or root in resolved.parents for root in allowed_roots):
                continue
            if resolved.exists() and resolved.is_file():
                body = resolved.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", _content_type(resolved))
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

        self.send_error(404, "Icon not found")

    def write_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    parser = argparse.ArgumentParser(description="Deployment Console web app")
    parser.add_argument("--port", type=int, default=18112)
    parser.add_argument("--host", default="localhost", help="Bind address (default: localhost)")
    args = parser.parse_args()

    token = _get_auth_token()
    if token:
        print(f"🔑 Auth Token Active: {token[:4]}...{token[-4:]}")

    server = http.server.ThreadingHTTPServer((args.host, args.port), DeploymentHandler)
    print(f"Deployment app: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
