import contextvars
import json
import logging
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional

FEATURE_DIR = Path(__file__).resolve().parents[2]
DASHBOARD_ROOT = FEATURE_DIR.parents[1]

# Track if configured workspace root was missing on disk
WORKSPACE_MISSING: Optional[str] = None


def _resolve_workspace_root() -> Path:
    global WORKSPACE_MISSING
    ws_env = os.environ.get("WORKSPACE_ROOT")
    if ws_env:
        candidate_env = Path(ws_env)
        if candidate_env.is_dir():
            return candidate_env
        WORKSPACE_MISSING = ws_env

    active_ws_file = DASHBOARD_ROOT / "config" / "active_workspace.txt"
    if active_ws_file.exists():
        candidate = active_ws_file.read_text(encoding="utf-8").strip()
        if candidate:
            cand_path = Path(candidate)
            if cand_path.is_dir():
                return cand_path
            WORKSPACE_MISSING = candidate

    return DASHBOARD_ROOT


WORKSPACE_ROOT = _resolve_workspace_root()
TMP_DIR = Path(os.environ.get("DEPLOYMENT_TMP_DIR", str(Path(tempfile.gettempdir()) / "deployment_dashboard_tmp")))
TEMPLATES_FILE = DASHBOARD_ROOT / "config" / "deployment_templates.json"
SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")

# ContextVar to allow request-scoped workspace without overriding other tabs
_REQUEST_WORKSPACE: contextvars.ContextVar[Optional[Path]] = contextvars.ContextVar("request_workspace", default=None)


def set_request_workspace(ws: Optional[Path]) -> contextvars.Token:
    return _REQUEST_WORKSPACE.set(ws)


def reset_request_workspace(token: contextvars.Token) -> None:
    _REQUEST_WORKSPACE.reset(token)


def get_workspace_root() -> Path:
    req_ws = _REQUEST_WORKSPACE.get()
    if req_ws is not None:
        return req_ws
    cfg = sys.modules.get("config")
    if cfg is not None and hasattr(cfg, "WORKSPACE_ROOT"):
        return cfg.WORKSPACE_ROOT
    return WORKSPACE_ROOT


def _get_allowed_workspace_roots() -> list[Path]:
    allowed = [DASHBOARD_ROOT.resolve()]
    curr_ws = get_workspace_root().resolve()
    if curr_ws not in allowed:
        allowed.append(curr_ws)
    for filename in ("workspaces_list.json", "workspaces_list.example.json"):
        ws_file = DASHBOARD_ROOT / "config" / filename
        if ws_file.exists():
            try:
                data = json.loads(ws_file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get("path"):
                            p = Path(item["path"]).resolve()
                            if p not in allowed:
                                allowed.append(p)
            except Exception:
                logging.exception("Failed to parse allowed workspaces list file %s", ws_file)
    return allowed


def _ensure_gitignore_has_dashboard(ws_root: Path) -> None:
    """Auto-add .dev-dashboard/ to .gitignore in the user's workspace."""
    try:
        gitignore = ws_root / ".gitignore"
        if gitignore.exists():
            content = gitignore.read_text(encoding="utf-8", errors="replace")
            if ".dev-dashboard" not in content:
                suffix = "\n" if not content.endswith("\n") else ""
                gitignore.write_text(content + suffix + "# Dev Deployment Dashboard config\n.dev-dashboard/\n", encoding="utf-8")
        elif (ws_root / ".git").exists():
            gitignore.write_text("# Dev Deployment Dashboard config\n.dev-dashboard/\n", encoding="utf-8")
    except Exception:
        pass


def get_workspaces_list() -> dict[str, Any]:
    workspaces = []
    ws_file = DASHBOARD_ROOT / "config" / "workspaces_list.json"
    if not ws_file.exists():
        ws_file = DASHBOARD_ROOT / "config" / "workspaces_list.example.json"

    if ws_file.exists():
        try:
            raw_workspaces = json.loads(ws_file.read_text(encoding="utf-8"))
            if isinstance(raw_workspaces, list):
                workspaces = [w for w in raw_workspaces if isinstance(w, dict) and Path(w.get("path", "")).is_dir()]
        except Exception:
            logging.exception("Failed to load workspaces list from %s", ws_file)

    current_path = str(WORKSPACE_ROOT.resolve())
    if not any(w.get("path") == current_path for w in workspaces):
        workspaces.insert(0, {"name": WORKSPACE_ROOT.name or "Current", "path": current_path})
    # The startup project (WORKSPACE_ROOT) is always shown and cannot be removed from the UI.
    workspaces = [{**w, "isDefault": w.get("path") == current_path} for w in workspaces if isinstance(w, dict)]

    return {
        "success": True,
        "active": current_path,
        "activeName": WORKSPACE_ROOT.name or "Current",
        "workspaces": workspaces,
        "workspaceMissing": WORKSPACE_MISSING,
    }


def remove_workspace(path_str: str) -> dict[str, Any]:
    """Remove a project from the added-projects list. The folder and its settings are not touched."""
    if not path_str or not path_str.strip():
        return {"success": False, "error": "No path provided"}
    target = str(Path(path_str.strip()).resolve())
    if target == str(WORKSPACE_ROOT.resolve()):
        return {"success": False, "error": "This is the startup project (WORKSPACE_ROOT) and is always shown."}
    ws_file = DASHBOARD_ROOT / "config" / "workspaces_list.json"
    try:
        workspaces = json.loads(ws_file.read_text(encoding="utf-8")) if ws_file.exists() else []
    except Exception:
        return {"success": False, "error": f"Could not read {ws_file}"}
    kept = [w for w in workspaces if not (isinstance(w, dict) and str(Path(w.get("path", "")).resolve()) == target)]
    if len(kept) == len(workspaces):
        return {"success": False, "error": "This project is not in the list."}
    try:
        ws_file.write_text(json.dumps(kept, indent=2), encoding="utf-8")
    except Exception as exc:
        return {"success": False, "error": f"Could not write workspaces list: {exc}"}
    return {"success": True, "path": target}


def set_active_workspace(new_path: str) -> dict[str, Any]:
    global WORKSPACE_ROOT, WORKSPACE_MISSING
    candidate = Path(new_path).resolve()
    if not candidate.is_dir():
        return {"success": False, "error": f"Directory not found: {new_path}"}

    allowed_roots = _get_allowed_workspace_roots()
    if not any(candidate == allowed or allowed in candidate.parents for allowed in allowed_roots):
        return {
            "success": False,
            "error": f"Directory '{new_path}' is not in the allowed workspaces list or authorized folders.",
        }

    WORKSPACE_MISSING = None
    WORKSPACE_ROOT = candidate
    os.environ["WORKSPACE_ROOT"] = str(WORKSPACE_ROOT)

    cfg = sys.modules.get("config")
    if cfg is not None:
        cfg.WORKSPACE_ROOT = candidate
        cfg.WORKSPACE_MISSING = None

    active_ws_file = DASHBOARD_ROOT / "config" / "active_workspace.txt"
    try:
        active_ws_file.write_text(str(WORKSPACE_ROOT), encoding="utf-8")
    except Exception:
        logging.exception("Failed to write active workspace to %s", active_ws_file)

    ws_file = DASHBOARD_ROOT / "config" / "workspaces_list.json"
    workspaces = []
    if ws_file.exists():
        try:
            workspaces = json.loads(ws_file.read_text(encoding="utf-8"))
        except Exception:
            logging.exception("Failed to parse workspaces list in %s", ws_file)
    if not any(isinstance(w, dict) and w.get("path") == str(WORKSPACE_ROOT) for w in workspaces):
        workspaces.append({"name": WORKSPACE_ROOT.name, "path": str(WORKSPACE_ROOT)})
        try:
            ws_file.write_text(json.dumps(workspaces, indent=2), encoding="utf-8")
        except Exception:
            logging.exception("Failed to write updated workspaces list to %s", ws_file)

    try:
        from .scanner import discover_workspace_config
    except (ImportError, ValueError):
        from config_modules.scanner import discover_workspace_config
    discover_workspace_config()

    return {
        "success": True,
        "active": str(WORKSPACE_ROOT),
        "activeName": WORKSPACE_ROOT.name,
    }


def allow_workspace(path_str: str) -> dict[str, Any]:
    """Add a workspace folder to workspaces_list.json without requiring a manual JSON edit."""
    if not path_str or not path_str.strip():
        return {"success": False, "error": "No path provided"}

    candidate = Path(path_str.strip()).resolve()
    if not candidate.exists():
        return {"success": False, "error": f"Directory does not exist: {candidate}"}
    if not candidate.is_dir():
        return {"success": False, "error": f"Path is not a directory: {candidate}"}

    ws_file = DASHBOARD_ROOT / "config" / "workspaces_list.json"
    workspaces: list[dict[str, Any]] = []
    if ws_file.exists():
        try:
            workspaces = json.loads(ws_file.read_text(encoding="utf-8"))
        except Exception:
            logging.exception("Failed to parse workspaces list in %s", ws_file)

    path_str_resolved = str(candidate)
    if any(isinstance(w, dict) and w.get("path") == path_str_resolved for w in workspaces):
        return {"success": True, "already_exists": True, "path": path_str_resolved, "name": candidate.name}

    workspaces.append({"name": candidate.name, "path": path_str_resolved})
    try:
        ws_file.write_text(json.dumps(workspaces, indent=2), encoding="utf-8")
    except Exception as exc:
        return {"success": False, "error": f"Could not write workspaces list: {exc}"}

    return {"success": True, "already_exists": False, "path": path_str_resolved, "name": candidate.name}
