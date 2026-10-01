#!/usr/bin/env python3
import argparse
import base64
import hashlib
import hmac
import http.server
import json
import logging
import os
import secrets
import sys
from email.parser import BytesFeedParser
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

import router

FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
SHARED_FRONTEND_DIR = Path(__file__).resolve().parents[3] / "frontend"
SHARED_ASSET_PREFIXES = ("css/", "js/", "assets/")

_SERVER_AUTH_TOKEN = ""


def _get_auth_token_file() -> Path:
    token_dir = Path.home() / ".config" / "dev-deployment"
    try:
        token_dir.mkdir(parents=True, exist_ok=True)
        token_dir.chmod(0o700)
    except Exception:
        logging.exception("Failed to create or set permissions on auth token directory")
    return token_dir / "auth_token.txt"


def _get_auth_token() -> str:
    global _SERVER_AUTH_TOKEN
    if _SERVER_AUTH_TOKEN:
        return _SERVER_AUTH_TOKEN

    token = os.environ.get("DEPLOYMENT_AUTH_TOKEN", "").strip()
    token_file = _get_auth_token_file()

    if not token and token_file.exists():
        try:
            token = token_file.read_text(encoding="utf-8").strip()
        except Exception:
            logging.exception("Failed to read auth token file")

    # Fallback check for legacy token location if user previously ran it
    if not token:
        legacy_file = router.get_workspace_root() / ".dev-dashboard" / "auth_token.txt"
        if legacy_file.exists():
            try:
                token = legacy_file.read_text(encoding="utf-8").strip()
                if token:
                    # Migrate to ~/.config and delete legacy file
                    token_file.write_text(token, encoding="utf-8")
                    token_file.chmod(0o600)
                    legacy_file.unlink(missing_ok=True)
            except Exception:
                logging.exception("Failed to migrate legacy auth token file")

    if not token:
        token = secrets.token_hex(16)
        try:
            token_file.write_text(token, encoding="utf-8")
            token_file.chmod(0o600)
        except Exception:
            logging.exception("Failed to write new auth token file")

    os.environ["DEPLOYMENT_AUTH_TOKEN"] = token
    _SERVER_AUTH_TOKEN = token
    return _SERVER_AUTH_TOKEN


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
    def _is_allowed_host(self) -> bool:
        host_header = self.headers.get("Host", "").strip()
        if not host_header:
            return False
        host_name = host_header.split(":")[0].lower()
        allowed_hosts = {"localhost", "127.0.0.1"}
        bind_host = getattr(self.server, "server_name", None) or getattr(self.server, "server_address", [None])[0]
        if bind_host and isinstance(bind_host, str):
            allowed_hosts.add(bind_host.lower())
        return host_name in allowed_hosts

    def _is_allowed_origin(self, origin: str) -> bool:
        if not origin:
            return True
        parsed = urlparse(origin)
        hostname = (parsed.hostname or "").lower()
        allowed_hosts = {"localhost", "127.0.0.1"}
        bind_host = getattr(self.server, "server_name", None) or getattr(self.server, "server_address", [None])[0]
        if bind_host and isinstance(bind_host, str):
            allowed_hosts.add(bind_host.lower())
        return hostname in allowed_hosts

    def end_headers(self) -> None:
        origin = self.headers.get("Origin", "")
        if origin and self._is_allowed_origin(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-API-Token, X-Webhook-Secret, X-Hub-Signature-256")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline' https://unpkg.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'self';"
        )
        super().end_headers()

    def do_OPTIONS(self) -> None:
        if not self._is_allowed_host():
            self.send_error(403, "Invalid Host header: DNS rebinding rejected")
            return
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
            return False
        token = self.headers.get("X-API-Token", "").strip()
        if not token:
            return False
        return hmac.compare_digest(token, expected_token)

    def _extract_request_workspace(self, parsed_query: Optional[dict[str, list[str]]] = None) -> Any:
        ws_val = self.headers.get("X-Workspace", "").strip()
        if not ws_val and parsed_query:
            ws_val = parsed_query.get("ws", parsed_query.get("workspace", [""]))[0].strip()
        if ws_val:
            cand = Path(ws_val).resolve()
            if cand.is_dir():
                allowed_roots = router.config._get_allowed_workspace_roots()
                if any(cand == a or a in cand.parents for a in allowed_roots):
                    return router.config.set_request_workspace(cand)
        return None

    def do_GET(self) -> None:
        if not self._is_allowed_host():
            self.send_error(403, "Invalid Host header: DNS rebinding rejected")
            return

        origin = self.headers.get("Origin", "")
        if origin and not self._is_allowed_origin(origin):
            self.send_error(403, "Cross-origin request rejected")
            return

        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        ws_token = self._extract_request_workspace(query)
        try:
            # Enforce API authentication on all GET endpoints
            if parsed.path.startswith("/api/"):
                if not self._verify_auth():
                    self.write_json({"success": False, "error": "Unauthorized: valid X-API-Token header required"}, status=401)
                    return

            if parsed.path == "/api/deployment/running-jobs":
                self.write_json({"success": True, "runningJobs": router.get_running_jobs()})
                return
            if parsed.path == "/api/deployment/workspaces":
                self.write_json(router.get_workspaces_list())
                return
            if parsed.path == "/api/deployment/inspect-path":
                self.write_json(router.inspect_workspace_path(query.get("path", [""])[0]))
                return
            if parsed.path == "/api/deployment/health":
                self.write_json(router.check_system_health())
                return
            if parsed.path == "/api/deployment/apps":
                self.write_json(router.get_apps())
                return
            if parsed.path == "/api/deployment/commands":
                self.write_json(router.get_commands(query.get("app", [""])[0]))
                return
            if parsed.path == "/api/deployment/deploy-config":
                self.write_json({"success": True, "config": router.load_deploy_config()})
                return
            if parsed.path == "/api/deployment/credentials":
                self.write_json(router.get_credentials_status(query.get("app", [""])[0]))
                return
            if parsed.path == "/api/deployment/templates":
                self.write_json({"success": True, "templates": router.load_templates()})
                return
            if parsed.path == "/api/deployment/scan-config":
                self.write_json(router.scan_app_config(query.get("app", [""])[0]))
                return
            if parsed.path == "/api/app-icon":
                self.serve_app_icon(query.get("url", [""])[0])
                return
            if parsed.path == "/api/deployment/job":
                self.write_json(router.get_job(query.get("id", [None])[0]))
                return
            if parsed.path == "/api/deployment/history":
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
                self.write_json(router.check_ios_expiry(
                    query.get("app", [""])[0],
                    query.get("flavor", ["prod"])[0],
                ))
                return
            if parsed.path.startswith("/api/"):
                self.write_json({"success": False, "error": f"Unknown endpoint: {parsed.path}"}, status=404)
                return
        finally:
            if ws_token is not None:
                router.config.reset_request_workspace(ws_token)
        if parsed.path == "/dashboard.html":
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()
            return

        # Serve index.html with injected auth token for the legitimate dashboard
        if parsed.path in ("", "/", "/index.html"):
            index_path = FRONTEND_DIR / "index.html"
            if index_path.exists():
                html = index_path.read_text(encoding="utf-8")
                token = _get_auth_token()
                injected = f'<script>window.__DEPLOYMENT_TOKEN__ = "{token}";</script>'
                if "<head>" in html:
                    html = html.replace("<head>", f"<head>\n    {injected}", 1)
                else:
                    html = f"{injected}\n{html}"
                body = html.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

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
        if not self._is_allowed_host():
            self.send_error(403, "Invalid Host header: DNS rebinding rejected")
            return

        origin = self.headers.get("Origin", "")
        if origin and not self._is_allowed_origin(origin):
            self.send_error(403, "Cross-origin request rejected")
            return

        parsed = urlparse(self.path)
        content_type_header = self.headers.get("Content-Type", "")

        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > 1024 * 1024:
                self.send_error(413, "Payload Too Large: Request body exceeds 1 MB limit")
                return
            raw_body = self.rfile.read(length) if length else b""
        except Exception:
            logging.exception("Failed to read POST request body")
            raw_body = b""

        ws_token = self._extract_request_workspace()
        try:
            # --- Webhook endpoint (authenticated via HMAC / shared secret) ---
            if parsed.path == "/api/deployment/webhook":
                webhook_secret = os.environ.get("WEBHOOK_SECRET", "").strip()
                if not webhook_secret:
                    self.write_json({
                        "success": False,
                        "error": "Webhook integration disabled: WEBHOOK_SECRET environment variable is not configured on the server."
                    }, status=503)
                    return

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

                try:
                    data = json.loads(raw_body.decode("utf-8")) if raw_body else {}
                except Exception:
                    logging.exception("Failed to parse webhook JSON payload")
                    data = {}

                app_id = str(data.get("app") or "")
                flavor = str(data.get("flavor") or "prod")
                template_id = str(data.get("templateId") or "build_aab")
                cmds = router.get_commands(app_id).get("commands", [])
                target_cmd = None
                for c in cmds:
                    if c.get("templateId") == template_id and (c.get("flavor") in (flavor, "any", "default")):
                        target_cmd = c
                        break
                if not target_cmd:
                    self.write_json({"success": False, "error": f"No matching command found for app '{app_id}', template '{template_id}', flavor '{flavor}'"}, status=400)
                    return

                self.write_json(router.execute_command(
                    app_id,
                    target_cmd.get("key", ""),
                    target_cmd.get("runner", "custom"),
                    flavor,
                    template_id,
                    flavor,
                    bool(data.get("confirmed") or False),
                ))
                return

            # --- Multipart upload routes ---
            if parsed.path == "/api/deployment/p8/upload" and content_type_header.startswith("multipart/form-data"):
                if not self._verify_auth():
                    self.write_json({"success": False, "error": "Unauthorized: valid X-API-Token header required"}, status=401)
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

            # All other API POST requests require X-API-Token
            if not self._verify_auth():
                self.write_json({"success": False, "error": "Unauthorized: valid X-API-Token header required"}, status=401)
                return

            try:
                data = json.loads(raw_body.decode("utf-8")) if raw_body else {}
            except Exception:
                logging.exception("Failed to parse POST JSON payload")
                data = {}

            if parsed.path == "/api/deployment/pick":
                self.write_json(router.pick_path(
                    str(data.get("kind") or "folder"),
                    str(data.get("prompt") or ""),
                    str(data.get("start") or ""),
                    data.get("extensions") if isinstance(data.get("extensions"), list) else None,
                ))
                return
            if parsed.path == "/api/deployment/credentials/scan":
                self.write_json(router.scan_credentials(str(data.get("folder") or "")))
                return
            if parsed.path == "/api/deployment/credentials/import":
                self.write_json(router.import_credential_path(
                    str(data.get("path") or ""),
                    app_id=str(data.get("app") or ""),
                    flavor=str(data.get("flavor") or ""),
                    issuer_id=str(data.get("issuerId") or ""),
                ))
                return
            if parsed.path == "/api/deployment/credentials/upload":
                try:
                    content = base64.b64decode(str(data.get("contentBase64") or ""), validate=True)
                except Exception:
                    self.write_json({"success": False, "error": "contentBase64 is not valid base64"}, status=400)
                    return
                self.write_json(router.import_credential_bytes(
                    Path(str(data.get("filename") or "")).name,
                    content,
                    app_id=str(data.get("app") or ""),
                    flavor=str(data.get("flavor") or ""),
                    issuer_id=str(data.get("issuerId") or ""),
                ))
                return
            if parsed.path == "/api/deployment/credentials/remove":
                self.write_json(router.remove_credential(str(data.get("kind") or ""), str(data.get("app") or "")))
                return

            if parsed.path == "/api/deployment/execute":
                app_id = str(data.get("app") or "")
                req_cmd = str(data.get("command") or "")
                req_runner = str(data.get("runner") or "make")
                req_template_id = str(data.get("templateId") or "")
                req_flavor = str(data.get("flavor") or "")

                allowed_cmds = router.get_commands(app_id).get("commands", [])
                target_cmd = None
                for c in allowed_cmds:
                    if req_template_id and c.get("templateId") == req_template_id and (c.get("flavor") == req_flavor or c.get("flavor") == "any"):
                        target_cmd = c
                        break
                    if not req_template_id and c.get("key") == req_cmd:
                        target_cmd = c
                        break

                if not target_cmd and allowed_cmds:
                    for c in allowed_cmds:
                        if c.get("templateId") == req_template_id:
                            target_cmd = c
                            break

                if not target_cmd:
                    self.write_json({
                        "success": False,
                        "error": f"Unauthorized command for app '{app_id}'. Command not found in configured templates."
                    }, status=403)
                    return

                res = router.execute_command(
                    app_id,
                    target_cmd["key"],
                    runner=target_cmd.get("runner", req_runner),
                    env=req_flavor or target_cmd.get("flavor", "dev"),
                    template_id=target_cmd.get("templateId", req_template_id),
                    flavor=target_cmd.get("flavor", req_flavor),
                    confirmed=bool(data.get("confirmed") or False),
                )
                self.write_json(res)
                return

            if parsed.path in ("/api/deployment/stop", "/api/deployment/job/stop"):
                self.write_json(router.stop_job(str(data.get("jobId") or data.get("job_id") or "")))
                return
            if parsed.path == "/api/deployment/deploy-config/save":
                self.write_json(router.save_deploy_config(data))
                return
            if parsed.path in ("/api/deployment/regenerate", "/api/deployment/regenerate-commands"):
                self.write_json(router.regenerate_commands())
                return
            if parsed.path == "/api/deployment/scan-all":
                force_mode = bool(data.get("force") or False)
                self.write_json(router.scan_all_apps_config(force=force_mode))
                return
            if parsed.path == "/api/deployment/rescan-workspace":
                self.write_json(router.rescan_workspace())
                return
            if parsed.path == "/api/deployment/workspace/remove":
                path = str(data.get("path") or "")
                resolved = str(Path(path).resolve()) if path else ""
                busy = [j for j in router.get_running_jobs()
                        if j.get("workspace") and str(Path(j["workspace"]).resolve()) == resolved]
                if busy:
                    self.write_json({"success": False, "error": f"A build is running in this project ({busy[0].get('app')}). Stop it first."}, status=409)
                    return
                self.write_json(router.remove_workspace(path))
                return
            if parsed.path == "/api/deployment/workspace/allow":
                self.write_json(router.allow_workspace(str(data.get("path") or "")))
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

            self.write_json({"success": False, "error": "Unknown endpoint"}, status=404)
        finally:
            if ws_token is not None:
                router.config.reset_request_workspace(ws_token)

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
        ws_root = router.get_workspace_root()
        if raw_path.is_absolute():
            candidates.append(raw_path)
        else:
            candidates.append(ws_root / raw_url)
            candidates.append(SHARED_FRONTEND_DIR / raw_url)
            candidates.append(Path(__file__).resolve().parents[3] / raw_url)

        for candidate in candidates:
            resolved = candidate.resolve()
            allowed_roots = [ws_root.resolve(), SHARED_FRONTEND_DIR.resolve()]
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

    try:
        router.credentials.migrate_inline_p8()
    except Exception:
        logging.exception("Failed to migrate inline .p8 keys out of deploy_config.json")

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
