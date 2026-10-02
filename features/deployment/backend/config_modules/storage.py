import json
import re
from pathlib import Path
from typing import Any, Optional

try:
    from .workspace import SAFE_ID_PATTERN, TEMPLATES_FILE, _ensure_gitignore_has_dashboard, get_workspace_root
except (ImportError, ValueError):
    from config_modules.workspace import SAFE_ID_PATTERN, TEMPLATES_FILE, _ensure_gitignore_has_dashboard, get_workspace_root


def get_apps_config_file() -> Path:
    ws_root = get_workspace_root()
    _ensure_gitignore_has_dashboard(ws_root)
    target_dir = ws_root / ".dev-dashboard"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "apps_config.json"
    if not target.exists():
        target.write_text("[]", encoding="utf-8")
    return target


def get_deploy_config_file(ws_root: Optional[Path] = None) -> Path:
    root = ws_root or get_workspace_root()
    _ensure_gitignore_has_dashboard(root)
    target_dir = root / ".dev-dashboard"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "deploy_config.json"
    if not target.exists():
        target.write_text("{}", encoding="utf-8")
    return target


def get_commands_config_file() -> Path:
    ws_root = get_workspace_root()
    _ensure_gitignore_has_dashboard(ws_root)
    target_dir = ws_root / ".dev-dashboard"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "commands_config.json"
    if not target.exists():
        target.write_text("[]", encoding="utf-8")
    return target


def load_deploy_config(ws_root: Optional[Path] = None) -> dict[str, Any]:
    cfg_file = get_deploy_config_file(ws_root)
    if not cfg_file.exists():
        return {}
    try:
        content = cfg_file.read_text(encoding="utf-8").strip()
        return json.loads(content) if content else {}
    except Exception:
        return {}


def save_deploy_config(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {"success": False, "error": "Invalid deploy config format: expected JSON object"}

    apps = data.get("apps", {})
    if not isinstance(apps, dict):
        return {"success": False, "error": "Invalid 'apps' section in deploy config"}

    ALLOWED_WEBHOOK_PROVIDERS = ("auto", "slack", "discord", "teams", "google_chat", "whatsapp", "custom", "generic")

    ws_webhook_url = data.get("workspace_webhook_url")
    if ws_webhook_url is not None and ws_webhook_url != "":
        if not isinstance(ws_webhook_url, str) or not (ws_webhook_url.startswith("http://") or ws_webhook_url.startswith("https://")) or len(ws_webhook_url) > 2048:
            return {"success": False, "error": "Invalid workspace webhook URL: must start with http:// or https:// (max 2048 chars)"}

    ws_provider = data.get("workspace_webhook_provider")
    if ws_provider and str(ws_provider).lower() not in ALLOWED_WEBHOOK_PROVIDERS:
        return {"success": False, "error": f"Invalid workspace webhook provider '{ws_provider}'. Allowed: {', '.join(ALLOWED_WEBHOOK_PROVIDERS)}"}

    ws_webhooks = data.get("workspace_webhooks")
    if ws_webhooks is not None:
        if not isinstance(ws_webhooks, list):
            return {"success": False, "error": "Invalid 'workspace_webhooks': must be a list"}
        for w in ws_webhooks:
            if not isinstance(w, dict):
                return {"success": False, "error": "Each workspace webhook must be an object"}
            w_url = w.get("url")
            if not w_url or not (str(w_url).startswith("http://") or str(w_url).startswith("https://")):
                return {"success": False, "error": "Each workspace webhook must have a valid URL (http:// or https://)"}
            w_provider = w.get("provider", "auto")
            if str(w_provider).lower() not in ALLOWED_WEBHOOK_PROVIDERS:
                return {"success": False, "error": f"Invalid webhook provider '{w_provider}'. Allowed: {', '.join(ALLOWED_WEBHOOK_PROVIDERS)}"}

    for app_id, app_cfg in apps.items():
        if not isinstance(app_id, str) or not SAFE_ID_PATTERN.match(app_id):
            return {"success": False, "error": f"Invalid app ID '{app_id}'. Must match ^[A-Za-z0-9._-]+$"}
        if not isinstance(app_cfg, dict):
            continue
        for key, val in app_cfg.items():
            if val is None or val == "":
                continue
            if isinstance(val, str):
                if key == "webhook_url":
                    if not (val.startswith("http://") or val.startswith("https://")) or len(val) > 2048:
                        return {"success": False, "error": f"Invalid webhook URL for app '{app_id}': must start with http:// or https:// (max 2048 chars)"}
                    continue
                if key == "webhook_provider":
                    if val.lower() not in ALLOWED_WEBHOOK_PROVIDERS:
                        return {"success": False, "error": f"Invalid webhook provider '{val}' for app '{app_id}'. Allowed: {', '.join(ALLOWED_WEBHOOK_PROVIDERS)}"}
                    continue
                is_id_field = (
                    any(key == prefix or key.startswith(f"{prefix}_") for prefix in (
                        "bundle_id", "android_id", "android_package", "ios_bundle_id", "android_bundle_id"
                    ))
                    or key in ("apple_id", "apple_key_id", "apple_issuer_id", "team_id")
                )
                if is_id_field and not (key.startswith("google_services_") or key.startswith("google_service_")):
                    if not SAFE_ID_PATTERN.match(val):
                        return {
                            "success": False,
                            "error": f"Invalid value for '{key}' in app '{app_id}': '{val}'. Must match ^[A-Za-z0-9._-]+$",
                        }
            elif isinstance(val, list):
                if key == "flavors":
                    for f in val:
                        if not isinstance(f, str) or not SAFE_ID_PATTERN.match(f):
                            return {
                                "success": False,
                                "error": f"Invalid flavor '{f}' in app '{app_id}'. Must match ^[A-Za-z0-9._-]+$",
                            }
                elif key == "auto_release_flavors":
                    for f in val:
                        if not isinstance(f, str) or not SAFE_ID_PATTERN.match(f):
                            return {
                                "success": False,
                                "error": f"Invalid item '{f}' in list '{key}' for app '{app_id}'. Must match ^[A-Za-z0-9._-]+$",
                            }
                elif key == "webhooks":
                    if not isinstance(val, list):
                        return {"success": False, "error": f"Invalid 'webhooks' in app '{app_id}': must be a list"}
                    for w in val:
                        if not isinstance(w, dict):
                            return {"success": False, "error": f"Each webhook in app '{app_id}' must be an object"}
                        w_url = w.get("url")
                        if not w_url or not (str(w_url).startswith("http://") or str(w_url).startswith("https://")):
                            return {"success": False, "error": f"Each webhook in app '{app_id}' must have a valid URL (http:// or https://)"}
                        w_provider = w.get("provider", "auto")
                        if str(w_provider).lower() not in ALLOWED_WEBHOOK_PROVIDERS:
                            return {"success": False, "error": f"Invalid webhook provider '{w_provider}' in app '{app_id}'. Allowed: {', '.join(ALLOWED_WEBHOOK_PROVIDERS)}"}
                elif key == "pipelines":
                    if len(val) > 50:
                        return {"success": False, "error": f"Too many pipelines for app '{app_id}' (max 50)"}
                    seen_pipe_ids = set()
                    for pipe in val:
                        if not isinstance(pipe, dict):
                            return {"success": False, "error": f"Each pipeline in app '{app_id}' must be an object"}
                        p_id = pipe.get("id")
                        p_name = pipe.get("name")
                        p_flavor = pipe.get("flavor")
                        steps = pipe.get("steps")

                        if not p_id or not isinstance(p_id, str) or not re.match(r"^[a-z0-9-]+$", p_id) or len(p_id) > 60:
                            return {
                                "success": False,
                                "error": f"Invalid pipeline id '{p_id}' in app '{app_id}'. Must match ^[a-z0-9-]+$ and be 1-60 chars",
                            }
                        if p_id in seen_pipe_ids:
                            return {"success": False, "error": f"Duplicate pipeline id '{p_id}' in app '{app_id}'"}
                        seen_pipe_ids.add(p_id)

                        if not p_name or not isinstance(p_name, str) or len(p_name.strip()) == 0 or len(p_name) > 60:
                            return {"success": False, "error": f"Invalid pipeline name in app '{app_id}'. Must be 1-60 characters"}

                        if p_flavor is not None and p_flavor != "":
                            if not isinstance(p_flavor, str) or not SAFE_ID_PATTERN.match(p_flavor):
                                return {"success": False, "error": f"Invalid flavor '{p_flavor}' for pipeline '{p_id}' in app '{app_id}'"}

                        if not isinstance(steps, list) or len(steps) == 0:
                            return {"success": False, "error": f"Pipeline '{p_id}' in app '{app_id}' must contain at least 1 step"}
                        if len(steps) > 20:
                            return {"success": False, "error": f"Pipeline '{p_id}' in app '{app_id}' has {len(steps)} steps; maximum is 20"}

                        for s_idx, step in enumerate(steps):
                            if not isinstance(step, dict):
                                return {"success": False, "error": f"Step #{s_idx + 1} in pipeline '{p_id}' must be an object"}
                            t_id = step.get("templateId")
                            custom_cmd = step.get("command")
                            if not t_id and not custom_cmd:
                                return {"success": False, "error": f"Step #{s_idx + 1} in pipeline '{p_id}' must specify templateId or command"}
                            if t_id and (not isinstance(t_id, str) or not SAFE_ID_PATTERN.match(t_id)):
                                return {"success": False, "error": f"Invalid templateId '{t_id}' in pipeline '{p_id}' step #{s_idx + 1}"}
                            if custom_cmd and (not isinstance(custom_cmd, str) or len(custom_cmd.strip()) == 0 or len(custom_cmd) > 1000):
                                return {"success": False, "error": f"Invalid custom command in pipeline '{p_id}' step #{s_idx + 1}"}
                            s_flavor = step.get("flavor")
                            if s_flavor is not None and s_flavor != "":
                                if not isinstance(s_flavor, str) or not SAFE_ID_PATTERN.match(s_flavor):
                                    return {"success": False, "error": f"Invalid flavor '{s_flavor}' in pipeline '{p_id}' step #{s_idx + 1}"}

    cfg = get_deploy_config_file()
    try:
        cfg.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return {"success": True}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def load_templates() -> dict[str, list[dict[str, Any]]]:
    if not TEMPLATES_FILE.exists():
        return {}
    try:
        return json.loads(TEMPLATES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
