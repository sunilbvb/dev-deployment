"""Signing/upload credentials: scan folders, import keys, and expose them to jobs.

Secrets never go into the workspace. Key files are copied into private user
directories (0600) and the per-workspace mapping lives in
~/.config/dev-deployment/credentials.json, so nothing sensitive is committed.
"""
import base64
import hashlib
import json
import plistlib
import re
import stat
from pathlib import Path
from typing import Any, Optional

from config import (
    SAFE_ID_PATTERN,
    _discover_apps_in_workspace,
    _resolve_app_dir,
    _scan_android_app_ids,
    _scan_xcconfig_bundle_ids,
    get_deploy_config_file,
    get_workspace_root,
    load_deploy_config,
)

CONFIG_DIR = Path.home() / ".config" / "dev-deployment"
KEYS_DIR = CONFIG_DIR / "keys"
STORE_FILE = CONFIG_DIR / "credentials.json"
APPLE_KEYS_DIR = Path.home() / ".appstoreconnect" / "private_keys"

SCAN_SKIP_DIRS = {
    ".git", ".dart_tool", "build", "node_modules", "Pods", ".gradle", ".idea",
    ".vscode", ".symlinks", "ephemeral", "DerivedData", ".pub-cache", "Library",
}
SCAN_MAX_DEPTH = 6
SCAN_MAX_FILES = 20000
MAX_KEY_FILE_BYTES = 1024 * 1024
P8_KEY_ID = re.compile(r"AuthKey[_-]([A-Z0-9]{10})", re.IGNORECASE)
# Service accounts all look alike; these name hints only rank results for the user.
PLAY_HINTS = ("play", "deploy", "publish", "github-actions", "fastlane", "supply")
NON_PLAY_HINTS = ("firebase-adminsdk", "revenuecat", "revenue-cat", "crashlytics")


# ---------------------------------------------------------------------------
# Per-user store
# ---------------------------------------------------------------------------

def _private_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(stat.S_IRWXU)
    except OSError:
        pass
    return path


def _load_store() -> dict[str, Any]:
    try:
        data = json.loads(STORE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_store(data: dict[str, Any]) -> None:
    _private_dir(CONFIG_DIR)
    tmp = STORE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.chmod(stat.S_IRUSR | stat.S_IWUSR)
    tmp.replace(STORE_FILE)


def _workspace_entry(store: dict[str, Any]) -> dict[str, Any]:
    ws = store.setdefault(str(get_workspace_root().resolve()), {})
    ws.setdefault("global", {})
    ws.setdefault("apps", {})
    return ws


def _scope(ws: dict[str, Any], app_id: Optional[str]) -> dict[str, Any]:
    if app_id:
        return ws["apps"].setdefault(app_id, {})
    return ws["global"]


# ---------------------------------------------------------------------------
# Classification (by content, never by filename alone)
# ---------------------------------------------------------------------------

def _classify_bytes(name: str, raw: bytes) -> Optional[dict[str, Any]]:
    lower = name.lower()
    if lower.endswith(".p8"):
        text = raw.decode("utf-8", errors="replace")
        if "BEGIN PRIVATE KEY" not in text:
            return None
        m = P8_KEY_ID.search(name)
        if m:
            return {"kind": "apple_p8", "key_id": m.group(1).upper()}
        # Apple names App Store Connect API keys AuthKey_<ID>.p8; other .p8 files are
        # In-App Purchase / APNs keys and cannot authenticate uploads.
        return {"kind": "apple_other_p8", "note": "Not an App Store Connect API key (expected AuthKey_<KEYID>.p8)"}

    if lower.endswith(".plist"):
        try:
            data = plistlib.loads(raw)
        except Exception:
            return None
        if isinstance(data, dict) and data.get("GOOGLE_APP_ID") and data.get("BUNDLE_ID"):
            return {"kind": "firebase_ios", "bundle_id": str(data["BUNDLE_ID"]),
                    "project_id": str(data.get("PROJECT_ID", ""))}
        return None

    if lower.endswith(".json"):
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            return None
        if not isinstance(data, dict):
            return None
        if data.get("type") == "service_account" and data.get("private_key") and data.get("client_email"):
            email = str(data["client_email"])
            haystack = f"{email} {name}".lower()
            if any(h in haystack for h in PLAY_HINTS):
                hint = "likely"
            elif any(h in haystack for h in NON_PLAY_HINTS):
                hint = "unlikely"
            else:
                hint = "unknown"
            return {"kind": "play_service_account", "client_email": email,
                    "project_id": str(data.get("project_id", "")), "play_hint": hint}
        if isinstance(data.get("project_info"), dict) and isinstance(data.get("client"), list):
            packages = []
            for c in data["client"]:
                pkg = (((c or {}).get("client_info") or {}).get("android_client_info") or {}).get("package_name")
                if pkg:
                    packages.append(str(pkg))
            return {"kind": "firebase_android", "packages": packages,
                    "project_id": str(data["project_info"].get("project_id", ""))}
    return None


def _classify_file(path: Path) -> Optional[dict[str, Any]]:
    if path.suffix.lower() not in (".json", ".p8", ".plist"):
        return None
    try:
        if not path.is_file() or path.stat().st_size > MAX_KEY_FILE_BYTES:
            return None
        return _classify_bytes(path.name, path.read_bytes())
    except OSError:
        return None


# ---------------------------------------------------------------------------
# App matching
# ---------------------------------------------------------------------------

def _app_identity_index() -> dict[str, list[dict[str, str]]]:
    """Map package/bundle IDs to the apps and flavors that use them."""
    index: dict[str, list[dict[str, str]]] = {}
    deploy_apps = load_deploy_config().get("apps", {})
    apps, _, _ = _discover_apps_in_workspace(get_workspace_root())
    for app in apps:
        if app.get("is_package"):
            continue
        app_id = app["id"]
        ids: dict[str, str] = {}
        app_dir = Path(app["path"])
        try:
            ids.update(_scan_android_app_ids(app_dir))
            ids.update(_scan_xcconfig_bundle_ids(app_dir))
        except Exception:
            pass
        ids.update({k: v for k, v in (deploy_apps.get(app_id) or {}).items() if isinstance(v, str)})
        for key, value in ids.items():
            m = re.match(r"^(android_id|android_package|bundle_id|ios_bundle_id)(?:_(.+))?$", key)
            if not m or not value:
                continue
            entry = {"app": app_id, "flavor": m.group(2) or "default"}
            bucket = index.setdefault(value, [])
            if entry not in bucket:
                bucket.append(entry)
    return index


def _matches_for(info: dict[str, Any], index: dict[str, list[dict[str, str]]]) -> list[dict[str, str]]:
    ids = list(info.get("packages") or [])
    if info.get("bundle_id"):
        ids.append(info["bundle_id"])
    out: list[dict[str, str]] = []
    for i in ids:
        for m in index.get(i, []):
            if m not in out:
                out.append(m)
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scan_credentials(folder: str = "") -> dict[str, Any]:
    root = Path(folder).expanduser() if folder else get_workspace_root()
    if not root.is_absolute():
        root = get_workspace_root() / root
    try:
        root = root.resolve()
    except OSError:
        return {"success": False, "error": f"Cannot access folder: {folder}"}
    if not root.is_dir():
        return {"success": False, "error": f"Not a folder: {root}"}

    index = _app_identity_index()
    found: list[dict[str, Any]] = []
    visited = 0
    stack: list[tuple[Path, int]] = [(root, 0)]
    while stack:
        current, depth = stack.pop()
        try:
            entries = sorted(current.iterdir())
        except OSError:
            continue
        for entry in entries:
            visited += 1
            if visited > SCAN_MAX_FILES:
                stack.clear()
                break
            if entry.is_symlink():
                continue
            if entry.is_dir():
                if depth < SCAN_MAX_DEPTH and entry.name not in SCAN_SKIP_DIRS:
                    stack.append((entry, depth + 1))
                continue
            info = _classify_file(entry)
            if info:
                info["path"] = str(entry)
                info["matches"] = _matches_for(info, index)
                found.append(info)

    order = {"play_service_account": 0, "apple_p8": 1, "firebase_android": 2, "firebase_ios": 3, "apple_other_p8": 4}
    hint_rank = {"likely": 0, "unknown": 1, "unlikely": 2}
    found.sort(key=lambda f: (order.get(f["kind"], 9), hint_rank.get(f.get("play_hint", ""), 1), f["path"]))
    return {"success": True, "folder": str(root), "found": found, "truncated": visited > SCAN_MAX_FILES}


def _store_play_key(raw: bytes, info: dict[str, Any]) -> Path:
    digest = hashlib.sha256(raw).hexdigest()[:10]
    project = re.sub(r"[^A-Za-z0-9_-]", "_", info.get("project_id") or "play")
    dest = _private_dir(KEYS_DIR) / f"play-{project}-{digest}.json"
    dest.write_bytes(raw)
    dest.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return dest


def _store_p8(raw: bytes, key_id: str) -> Path:
    dest = _private_dir(APPLE_KEYS_DIR) / f"AuthKey_{key_id}.p8"
    dest.write_bytes(raw)
    dest.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return dest


def _validate_scope(app_id: str, flavor: str) -> Optional[str]:
    if app_id and not SAFE_ID_PATTERN.match(app_id):
        return f"Invalid app id '{app_id}'"
    if flavor and not SAFE_ID_PATTERN.match(flavor):
        return f"Invalid flavor '{flavor}'"
    return None


def import_credential_bytes(
    name: str, raw: bytes, *, app_id: str = "", flavor: str = "", issuer_id: str = "",
    source_path: Optional[Path] = None,
) -> dict[str, Any]:
    err = _validate_scope(app_id, flavor)
    if err:
        return {"success": False, "error": err}
    if len(raw) > MAX_KEY_FILE_BYTES:
        return {"success": False, "error": "File is too large to be a key"}
    info = _classify_bytes(name, raw)
    if not info:
        return {"success": False, "error": (
            f"'{Path(name).name}' is not a recognised credential. Expected a Google Play service-account "
            "JSON, an App Store Connect AuthKey_XXXXXXXXXX.p8, google-services.json or GoogleService-Info.plist."
        )}

    if info["kind"] == "apple_other_p8":
        return {"success": False, "error": info["note"]}

    store = _load_store()
    ws = _workspace_entry(store)
    scope = _scope(ws, app_id or None)
    kind = info["kind"]
    result: dict[str, Any] = {"success": True, "kind": kind, "app_id": app_id or None}

    if kind == "play_service_account":
        dest = _store_play_key(raw, info)
        scope["play_service_account"] = str(dest)
        result.update(stored_path=str(dest), client_email=info["client_email"])

    elif kind == "apple_p8":
        key_id = info["key_id"]
        if not key_id:
            return {"success": False, "error": (
                "Cannot read the Key ID from the filename. Keep Apple's name: AuthKey_XXXXXXXXXX.p8."
            )}
        if issuer_id and not re.fullmatch(r"[0-9a-fA-F-]{36}", issuer_id):
            return {"success": False, "error": "Issuer ID must be a UUID (xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)"}
        dest = _store_p8(raw, key_id)
        scope["apple_key_id"] = key_id
        scope["apple_p8_path"] = str(dest)
        if issuer_id:
            scope["apple_issuer_id"] = issuer_id
        result.update(stored_path=str(dest), key_id=key_id)

    else:
        # Firebase client configs are not secrets: reference them in the shared deploy config.
        if not app_id or source_path is None:
            return {"success": False, "error": "Firebase config files are imported from a scan for a specific app"}
        field = "google_services_json" if kind == "firebase_android" else "google_service_info_plist"
        key = f"{field}_{flavor}" if flavor and flavor != "default" else field
        ws_root = get_workspace_root().resolve()
        try:
            ref = str(source_path.relative_to(ws_root))
        except ValueError:
            ref = str(source_path)
        cfg = load_deploy_config()
        cfg.setdefault("apps", {}).setdefault(app_id, {})[key] = ref
        get_deploy_config_file().write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        return {**result, "stored_path": ref, "field": key}

    _save_store(store)
    return result


def import_credential_path(path: str, *, app_id: str = "", flavor: str = "", issuer_id: str = "") -> dict[str, Any]:
    p = Path(path).expanduser()
    try:
        p = p.resolve()
        raw = p.read_bytes() if p.is_file() and p.stat().st_size <= MAX_KEY_FILE_BYTES else None
    except OSError:
        raw = None
    if raw is None:
        return {"success": False, "error": f"Cannot read file: {path}"}
    return import_credential_bytes(p.name, raw, app_id=app_id, flavor=flavor, issuer_id=issuer_id, source_path=p)


def remove_credential(kind: str, app_id: str = "") -> dict[str, Any]:
    err = _validate_scope(app_id, "")
    if err:
        return {"success": False, "error": err}
    fields = {"play_service_account": ("play_service_account",),
              "apple_p8": ("apple_key_id", "apple_p8_path", "apple_issuer_id")}.get(kind)
    if not fields:
        return {"success": False, "error": f"Unknown credential kind '{kind}'"}
    store = _load_store()
    scope = _scope(_workspace_entry(store), app_id or None)
    for f in fields:
        scope.pop(f, None)
    _save_store(store)
    return {"success": True}


def _effective(app_id: str) -> dict[str, Any]:
    """App-level credentials override workspace-wide ones."""
    ws = _load_store().get(str(get_workspace_root().resolve()), {})
    merged = dict(ws.get("global", {}))
    merged.update({k: v for k, v in (ws.get("apps", {}).get(app_id) or {}).items() if v})
    sources = {k: ("app" if (ws.get("apps", {}).get(app_id) or {}).get(k) else "workspace") for k in merged}

    # Legacy: a path typed into the deploy config UI.
    legacy = (load_deploy_config().get("apps", {}).get(app_id) or {}).get("play_service_account_path")
    if not merged.get("play_service_account") and legacy:
        lp = Path(legacy).expanduser()
        if not lp.is_absolute():
            lp = get_workspace_root() / lp
        merged["play_service_account"] = str(lp)
        sources["play_service_account"] = "deploy_config"

    # Conventional locations (same order the shell scripts fall back to).
    if not merged.get("play_service_account"):
        app_dir = _resolve_app_dir(app_id)
        for candidate in (
            get_workspace_root() / "private_keys" / "play-store-deployer.json",
            app_dir / "private_keys" / "play-store-deployer.json",
            app_dir / "android" / "play-store-deployer.json",
            CONFIG_DIR / "play-store-deployer.json",
        ):
            if candidate.is_file():
                merged["play_service_account"] = str(candidate)
                sources["play_service_account"] = "auto"
                break
    return {"values": merged, "sources": sources}


def _apple_from_env_files(app_id: str) -> Optional[dict[str, Any]]:
    """Apple key IDs that the app's env/<flavor>.json files already provide to builds."""
    env_dir = _resolve_app_dir(app_id) / "env"
    if not env_dir.is_dir():
        return None
    for env_file in sorted(env_dir.glob("*.json")):
        try:
            data = json.loads(env_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        key_id = str(data.get("APPLE_API_KEY") or "") if isinstance(data, dict) else ""
        if not re.fullmatch(r"[A-Z0-9]{10}", key_id):
            continue
        candidates = [
            APPLE_KEYS_DIR / f"AuthKey_{key_id}.p8",
            Path.home() / ".private_keys" / f"AuthKey_{key_id}.p8",
            get_workspace_root() / "private_keys" / f"AuthKey_{key_id}.p8",
        ]
        p8 = next((c for c in candidates if c.is_file()), candidates[0])
        return {"key_id": key_id, "issuer_id": str(data.get("APPLE_API_ISSUER") or ""),
                "path": str(p8), "exists": p8.is_file(), "source": f"env file ({env_file.name})"}
    return None


def _describe_play(path: str) -> dict[str, Any]:
    p = Path(path)
    out: dict[str, Any] = {"path": path, "exists": p.is_file()}
    info = _classify_file(p) if out["exists"] else None
    out["valid"] = bool(info and info["kind"] == "play_service_account")
    if out["valid"]:
        out["client_email"] = info["client_email"]
    return out


def get_credentials_status(app_id: str) -> dict[str, Any]:
    err = _validate_scope(app_id, "")
    if err or not app_id:
        return {"success": False, "error": err or "app is required"}
    eff = _effective(app_id)
    v, src = eff["values"], eff["sources"]
    status: dict[str, Any] = {"success": True, "app_id": app_id, "play": None, "apple": None}
    if v.get("play_service_account"):
        status["play"] = {**_describe_play(v["play_service_account"]), "source": src.get("play_service_account")}
    if v.get("apple_key_id"):
        p8 = v.get("apple_p8_path") or str(APPLE_KEYS_DIR / f"AuthKey_{v['apple_key_id']}.p8")
        status["apple"] = {"key_id": v["apple_key_id"], "issuer_id": v.get("apple_issuer_id", ""),
                           "path": p8, "exists": Path(p8).is_file(), "source": src.get("apple_key_id")}
    else:
        status["apple"] = _apple_from_env_files(app_id)
    return status


def job_env(app_id: str) -> dict[str, str]:
    """Environment variables handed to build/upload scripts for this app."""
    if not app_id or not SAFE_ID_PATTERN.match(app_id):
        return {}
    v = _effective(app_id)["values"]
    env: dict[str, str] = {}
    if v.get("play_service_account") and Path(v["play_service_account"]).is_file():
        env["SERVICE_ACCOUNT_JSON"] = v["play_service_account"]
    if v.get("apple_key_id"):
        env["APPLE_API_KEY"] = v["apple_key_id"]
        p8 = v.get("apple_p8_path") or str(APPLE_KEYS_DIR / f"AuthKey_{v['apple_key_id']}.p8")
        if Path(p8).is_file():
            env["APPLE_API_KEY_PATH"] = p8
    issuer = v.get("apple_issuer_id") or (load_deploy_config().get("apps", {}).get(app_id) or {}).get("apple_issuer_id")
    if issuer:
        env["APPLE_API_ISSUER"] = issuer
    return env


def migrate_inline_p8() -> None:
    """Move .p8 contents that older versions embedded in deploy_config.json out of the workspace."""
    cfg = load_deploy_config()
    changed = False
    for app_id, app_cfg in (cfg.get("apps") or {}).items():
        if not isinstance(app_cfg, dict) or not app_cfg.get("apple_p8_base64"):
            continue
        try:
            raw = base64.b64decode(app_cfg["apple_p8_base64"])
        except Exception:
            continue
        key_id = app_cfg.get("apple_key_id") or ""
        if key_id and SAFE_ID_PATTERN.match(app_id):
            import_credential_bytes(f"AuthKey_{key_id}.p8", raw, app_id=app_id,
                                    issuer_id=app_cfg.get("apple_issuer_id", "") or "")
        app_cfg.pop("apple_p8_base64", None)
        changed = True
    if changed:
        get_deploy_config_file().write_text(json.dumps(cfg, indent=2), encoding="utf-8")
