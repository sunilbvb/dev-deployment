import json
import os
import re
import signal
import subprocess
import threading
import time
import plistlib
import shutil
import tempfile
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Any, Dict, Optional


FEATURE_DIR = Path(__file__).resolve().parents[1]
DASHBOARD_ROOT = FEATURE_DIR.parents[1]


def _resolve_workspace_root() -> Path:
    ws_env = os.environ.get("WORKSPACE_ROOT")
    if ws_env and Path(ws_env).is_dir():
        return Path(ws_env)
    active_ws_file = DASHBOARD_ROOT / "config" / "active_workspace.txt"
    if active_ws_file.exists():
        candidate = active_ws_file.read_text(encoding="utf-8").strip()
        if candidate and Path(candidate).is_dir():
            return Path(candidate)
    return DASHBOARD_ROOT


WORKSPACE_ROOT = _resolve_workspace_root()
TMP_DIR = Path(os.environ.get("DEPLOYMENT_TMP_DIR", str(Path(tempfile.gettempdir()) / "deployment_dashboard_tmp")))
MAX_LOG_CHARS = 40000
TEMPLATES_FILE = DASHBOARD_ROOT / "config" / "deployment_templates.json"

# Map template ID to bash script action name inside json_utils.sh / run_build.sh
ACTION_MAP = {
    "build_ipa": "buildIPA",
    "build_ipa_device": "buildIPADevice",
    "deploy_ipa": "deployIPA",
    "upload_ipa": "uploadIPA",
    "build_aab": "buildAAB",
    "deploy_aab": "deployAAB",
    "upload_aab": "uploadAAB",
    "build_apk": "buildAPK",
    "deploy_both": "deployBothPlatforms",
    "clean": "cleanProject",
    "pub_get": "pubGet",
    "release_preview": "releasePreview",
    "release_changelog": "releaseChangelog",
    "release_commit": "releaseCommit",
    "release_tag": "releaseTag",
    "release_push": "releasePush",
    "release_bump_patch": "releaseBumpPatch",
    "release_bump_minor": "releaseBumpMinor",
    "release_bump_major": "releaseBumpMajor",
    "release_store_notes": "releaseStoreNotes",
    "release_verify": "releaseVerify",
    "release_status": "releaseStatus",
    "release_undo": "releaseUndo",
}

# Template IDs whose success means the build actually reached TestFlight/Play
# Store, not just a local artifact - the only ones eligible to auto-chain a
# release (tag + push).
STORE_UPLOAD_TEMPLATE_IDS = {"deploy_ipa", "upload_ipa", "deploy_aab", "upload_aab", "deploy_both"}

# Bash action names (ACTION_MAP values) that actually push a build to a real app
# store / TestFlight - derived from STORE_UPLOAD_TEMPLATE_IDS so the two can never
# drift apart. Used by the prod-deploy confirmation gate below.
_STORE_SHIPPING_ACTIONS = {ACTION_MAP[t] for t in STORE_UPLOAD_TEMPLATE_IDS if t in ACTION_MAP}

# --- Deployment history log (persists job outcomes across server restarts) ---
HISTORY_MAX_BYTES = 10 * 1024 * 1024        # rotate current file past ~10MB
HISTORY_OUTPUT_EXCERPT_CHARS = 2000          # tail of stdout kept per row
HISTORY_ERROR_EXCERPT_CHARS = 2000           # tail of stderr kept per row
HISTORY_ENDPOINT_MAX_LIMIT = 500             # hard ceiling on ?limit=
_HISTORY_LOCK = threading.Lock()

# --- Pre-flight iOS cert/profile expiry check ---
EXPIRY_WARNING_THRESHOLD_DAYS = 30


def get_apps_config_file() -> Path:
    target_dir = WORKSPACE_ROOT / ".dev-dashboard"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "apps_config.json"
    if not target.exists():
        target.write_text("[]", encoding="utf-8")
    return target


def get_deploy_config_file() -> Path:
    target_dir = WORKSPACE_ROOT / ".dev-dashboard"
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / "deploy_config.json"


def load_templates() -> dict[str, list[dict[str, Any]]]:
    """Load generic deployment command templates from the tool's config dir."""
    if TEMPLATES_FILE.exists():
        try:
            return json.loads(TEMPLATES_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"ios": [], "android": []}


def load_deploy_config() -> dict[str, Any]:
    """Load workspace-level deployment configuration (bundle IDs, credentials paths)."""
    cfg = get_deploy_config_file()
    if cfg.exists():
        try:
            return json.loads(cfg.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"apps": {}}


def save_deploy_config(data: dict[str, Any]) -> dict[str, Any]:
    """Persist workspace deployment configuration to .dev-dashboard/deploy_config.json."""
    cfg = get_deploy_config_file()
    try:
        cfg.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return {"success": True}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def upload_p8_key(app_id: str, filename: str, content_bytes: bytes, issuer_id: str = "") -> dict[str, Any]:
    """
    Receive an uploaded .p8 file, base64-encode it, persist to deploy_config,
    and write it to the Apple industry-standard key location with correct permissions.

    Key ID is extracted from the filename: AuthKey_XXXXXXXXXX.p8 → XXXXXXXXXX.
    If filename doesn't follow the convention the caller must supply key_id separately.
    """
    import base64
    import re
    import stat

    # --- Extract Key ID from filename (AuthKey_XXXXXXXXXX.p8) ---
    match = re.search(r"AuthKey[_-]([A-Z0-9]{10})", filename, re.IGNORECASE)
    if not match:
        return {
            "success": False,
            "error": (
                f"Cannot extract Key ID from filename '{filename}'. "
                "Expected format: AuthKey_XXXXXXXXXX.p8 (10-char uppercase key ID)."
            ),
        }
    key_id = match.group(1).upper()

    # --- Base64-encode the raw bytes ---
    b64_content = base64.b64encode(content_bytes).decode("ascii")

    # --- Persist to deploy_config.json ---
    deploy_config = load_deploy_config()
    if "apps" not in deploy_config:
        deploy_config["apps"] = {}
    if app_id not in deploy_config["apps"]:
        deploy_config["apps"][app_id] = {}

    deploy_config["apps"][app_id]["apple_key_id"] = key_id
    deploy_config["apps"][app_id]["apple_p8_base64"] = b64_content
    if issuer_id:
        deploy_config["apps"][app_id]["apple_issuer_id"] = issuer_id

    cfg_path = get_deploy_config_file()
    try:
        cfg_path.write_text(json.dumps(deploy_config, indent=2), encoding="utf-8")
    except Exception as exc:
        return {"success": False, "error": f"Failed to save deploy config: {exc}"}

    # --- Write to Apple industry-standard path: ~/.appstoreconnect/private_keys/ ---
    std_dir = Path.home() / ".appstoreconnect" / "private_keys"
    std_dir.mkdir(parents=True, exist_ok=True)
    std_key_path = std_dir / f"AuthKey_{key_id}.p8"
    try:
        std_key_path.write_bytes(content_bytes)
        # chmod 600 — owner read/write only (required by altool / notarytool)
        std_key_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except Exception as exc:
        return {
            "success": False,
            "error": f"Key ID '{key_id}' stored in config, but could not write to {std_key_path}: {exc}",
        }

    return {
        "success": True,
        "key_id": key_id,
        "stored_path": str(std_key_path),
        "b64_stored": True,
        "app_id": app_id,
    }


def _resolve_command(template: str, app_id: str, flavor: str, deploy_cfg: dict[str, Any]) -> str:
    """Substitute {placeholders} in a command template with real values."""
    app_cfg = deploy_cfg.get("apps", {}).get(app_id, {})
    bundle_id = app_cfg.get(f"bundle_id_{flavor}") or app_cfg.get("bundle_id_prod", f"com.example.{app_id}")
    android_package = app_cfg.get(f"android_package_{flavor}") or app_cfg.get("android_package_prod", f"com.example.{app_id}")
    apple_id = app_cfg.get("apple_id", "")
    return (
        template
        .replace("{flavor}", flavor)
        .replace("{bundle_id}", bundle_id)
        .replace("{android_package}", android_package)
        .replace("{apple_id}", apple_id)
        .replace("{app_id}", app_id)
    )


def _build_commands_from_templates(app_id: str, app_path_prefix: str, use_melos: bool, flavors: list[str], deploy_cfg: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
    """Generate command entries for an app pointing to direct commands or bash script runner."""
    templates = load_templates()
    if deploy_cfg is None:
        deploy_cfg = load_deploy_config()
    commands: list[dict[str, Any]] = []

    for platform, tmpl_list in templates.items():
        for tmpl in tmpl_list:
            action = ACTION_MAP.get(tmpl["id"], tmpl["id"])
            is_direct = tmpl.get("runner") == "direct" or tmpl.get("direct") is True

            if platform in ("utility", "release"):
                if is_direct and tmpl.get("command_template"):
                    resolved = _resolve_command(tmpl["command_template"], app_id, "any", deploy_cfg)
                    full_cmd = f"{app_path_prefix} {resolved}".strip()
                else:
                    full_cmd = f"bash {DASHBOARD_ROOT}/features/deployment/scripts/run_build.sh {action} {app_id} any"

                commands.append({
                    "id": f"{tmpl['id']}_{app_id}",
                    "app": app_id,
                    "templateId": tmpl["id"],
                    "name": tmpl["name"],
                    "description": tmpl["description"].replace("{app_id}", app_id),
                    "platform": platform,
                    "flavor": "any",
                    "runner": "custom",
                    "command": full_cmd,
                    "configured": True,
                })
            else:
                for flavor in flavors:
                    if is_direct and tmpl.get("command_template"):
                        resolved = _resolve_command(tmpl["command_template"], app_id, flavor, deploy_cfg)
                        full_cmd = f"{app_path_prefix} {resolved}".strip()
                    else:
                        full_cmd = f"bash {DASHBOARD_ROOT}/features/deployment/scripts/run_build.sh {action} {app_id} {flavor}"

                    commands.append({
                        "id": f"{tmpl['id']}_{app_id}_{flavor}",
                        "app": app_id,
                        "templateId": tmpl["id"],
                        "name": tmpl["name"],
                        "description": tmpl["description"].replace("{flavor}", flavor),
                        "platform": platform,
                        "flavor": flavor,
                        "runner": "custom",
                        "command": full_cmd,
                        "configured": True if is_direct else _is_flavor_configured(app_id, flavor),
                    })
    return commands


def regenerate_commands() -> dict[str, Any]:
    """Re-generate commands_config.json from templates + current deploy_config. Replaces old commands."""
    apps_file = get_apps_config_file()
    cmds_file = get_commands_config_file()
    try:
        existing_apps = json.loads(apps_file.read_text(encoding="utf-8"))
    except Exception:
        return {"success": False, "error": "No apps configured yet"}

    has_melos = any(WORKSPACE_ROOT.glob("melos*.yaml")) or (
        (WORKSPACE_ROOT / "pubspec.yaml").exists() and
        "melos:" in (WORKSPACE_ROOT / "pubspec.yaml").read_text(encoding="utf-8")
    )

    new_cmds: list[dict[str, Any]] = []
    deploy_cfg = load_deploy_config()
    for app in existing_apps:
        app_id = app["id"]
        if use_apps_dir := (WORKSPACE_ROOT / "apps" / app_id).exists():
            prefix = f"cd apps/{app_id} &&"
        else:
            prefix = ""
        flavors = deploy_cfg.get("apps", {}).get(app_id, {}).get("flavors", ["dev", "qa", "prod"])
        new_cmds.extend(_build_commands_from_templates(app_id, prefix, has_melos and bool(use_apps_dir), flavors))

    cmds_file.write_text(json.dumps(new_cmds, indent=2), encoding="utf-8")
    return {"success": True, "count": len(new_cmds)}


def inject_melos_scripts(app_id: str) -> dict[str, Any]:
    """Write build/deploy melos scripts for an app into the workspace pubspec.yaml."""
    pubspec_path = WORKSPACE_ROOT / "pubspec.yaml"
    if not pubspec_path.exists():
        return {"success": False, "error": "No pubspec.yaml found in workspace root"}

    deploy_cfg = load_deploy_config()
    templates = load_templates()
    flavors = ["dev", "qa", "prod"]

    # Build the YAML block to inject
    inject_lines: list[str] = [
        f"    # --- auto-generated by developer-dashboard for {app_id} ---"
    ]
    for platform, tmpl_list in templates.items():
        for tmpl in tmpl_list:
            for flavor in flavors:
                script_name = f"{tmpl['id'].replace('_', ':')}:{app_id}:{flavor}"
                resolved_cmd = _resolve_command(tmpl["command_template"], app_id, flavor, deploy_cfg)
                if (WORKSPACE_ROOT / "apps" / app_id).exists():
                    full_cmd = f"cd apps/{app_id} && {resolved_cmd}"
                else:
                    full_cmd = resolved_cmd
                desc = tmpl["description"].replace("{flavor}", flavor)
                inject_lines.append(f"    {script_name}:")
                inject_lines.append(f"      run: {full_cmd}")
                inject_lines.append(f"      description: \"[auto] {desc}\"")

    inject_lines.append(f"    # --- end auto-generated for {app_id} ---")
    inject_block = "\n".join(inject_lines)

    content = pubspec_path.read_text(encoding="utf-8")

    # Remove old injected block for this app if present
    start_marker = f"    # --- auto-generated by developer-dashboard for {app_id} ---"
    end_marker = f"    # --- end auto-generated for {app_id} ---"
    if start_marker in content:
        start_idx = content.index(start_marker)
        end_idx = content.index(end_marker) + len(end_marker)
        content = content[:start_idx].rstrip("\n") + "\n" + content[end_idx:].lstrip("\n")

    # Append inside the scripts block
    if "  scripts:" in content:
        insert_pos = content.index("  scripts:") + len("  scripts:")
        content = content[:insert_pos] + "\n" + inject_block + "\n" + content[insert_pos:]
    else:
        content += "\n  scripts:\n" + inject_block + "\n"

    pubspec_path.write_text(content, encoding="utf-8")
    return {"success": True, "injected": len(inject_lines)}

_JOBS: dict[str, dict[str, Any]] = {}
_JOBS_LOCK = threading.Lock()
_NEXT_JOB_ID = 1

# --- Per-app concurrency guard -------------------------------------------
# Keyed by `app` alone, NOT by (app, flavor). Every action registered in
# ACTION_MAP today - every ios/android/combined build/deploy/upload AND
# every release_* action - ends up mutating the SAME shared, app-level
# state: apps/<app>/pubspec.yaml's version+build number (bumped directly by
# buildAABRaw and buildIPARaw, independent of which flavor was passed), and
# for release_* actions, CHANGELOG.md and git tags. iOS's own upload path
# (build/ios/ipa/*.ipa) isn't even flavor-namespaced. A "dev" build and a
# "prod" build of the same app racing on that pubspec bump is exactly the
# corruption this guard exists to prevent, so a narrower per-(app,flavor)
# lock would be unsound. `flavor` is still recorded below, purely so
# rejection error messages can say which flavor is currently running.
# Guarded by the EXISTING _JOBS_LOCK (not a second lock) to avoid any
# lock-ordering hazard between two separate locks.
_APP_LOCKS: dict[str, dict[str, Any]] = {}


def _new_job_id() -> str:
    global _NEXT_JOB_ID
    with _JOBS_LOCK:
        job_id = f"deployment-{_NEXT_JOB_ID}"
        _NEXT_JOB_ID += 1
    return job_id


def _append_job_log(job_id: str, field: str, chunk: str) -> None:
    if not chunk:
        return
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        existing = str(job.get(field) or "")
        merged = existing + chunk
        if len(merged) > MAX_LOG_CHARS:
            merged = merged[-MAX_LOG_CHARS:]
        job[field] = merged


def _detect_app_in_dir(d: Path) -> Optional[dict[str, Any]]:
    """Detect app id, name, and stack from a directory."""
    if not d.is_dir():
        return None
    app_id = d.name

    # 1. Flutter (pubspec.yaml)
    pub = d / "pubspec.yaml"
    if pub.exists():
        app_name = app_id.capitalize()
        is_package = False
        try:
            pub_content = pub.read_text(encoding="utf-8")
            for line in pub_content.splitlines():
                if line.startswith("name:"):
                    app_name = line.split(":", 1)[1].strip()
                elif line.startswith("publish_to:"):
                    # Common indicator of internal library packages
                    val = line.split(":", 1)[1].strip()
                    if val == "none" and not (d / "android").is_dir() and not (d / "ios").is_dir():
                        is_package = True
        except Exception:
            pass

        # If project is located under packages/ folder and lacks native app runners (android/ios), treat as package
        if "packages" in d.parts and not (d / "android").is_dir() and not (d / "ios").is_dir():
            is_package = True

        return {"id": app_id, "name": app_name, "stack": "flutter", "is_package": is_package}

    # 2. Node / React Native (package.json)
    pkg = d / "package.json"
    if pkg.exists():
        app_name = app_id.capitalize()
        stack = "node"
        try:
            pkg_data = json.loads(pkg.read_text(encoding="utf-8"))
            app_name = pkg_data.get("name", app_id)
            deps = {**pkg_data.get("dependencies", {}), **pkg_data.get("devDependencies", {})}
            if "react-native" in deps:
                stack = "react-native"
        except Exception:
            pass
        return {"id": app_id, "name": app_name, "stack": stack}

    # 3. Android Native
    if (d / "build.gradle").exists() or (d / "build.gradle.kts").exists() or (d / "android").is_dir():
        return {"id": app_id, "name": app_id.capitalize(), "stack": "android"}

    # 4. iOS Native
    if list(d.glob("*.xcodeproj")) or list(d.glob("*.xcworkspace")) or (d / "ios").is_dir():
        return {"id": app_id, "name": app_id.capitalize(), "stack": "ios"}

    return None


def _parse_melos_config(root_dir: Path) -> list[str]:
    """Parse melos.yaml or pubspec.yaml melos: section to extract configured package folder names."""
    folder_names: list[str] = ["apps", "packages", "modules", "projects"]

    # 1. Try melos.yaml
    melos_file = root_dir / "melos.yaml"
    content = ""
    if melos_file.exists():
        try:
            content = melos_file.read_text(encoding="utf-8")
        except Exception:
            pass
    elif (root_dir / "pubspec.yaml").exists():
        try:
            pub_text = (root_dir / "pubspec.yaml").read_text(encoding="utf-8")
            if "melos:" in pub_text:
                content = pub_text
        except Exception:
            pass

    if content:
        # Extract glob paths under packages: (e.g. - apps/*, - features/*)
        in_packages = False
        for line in content.splitlines():
            line_str = line.strip()
            if line_str.startswith("packages:"):
                in_packages = True
                continue
            if in_packages:
                if line_str.startswith("-") or line_str.startswith("*"):
                    item = line_str.lstrip("-* ").strip("'\"")
                    # Extract top folder name before / or *
                    parts = item.split("/")
                    if parts and parts[0] and not parts[0].startswith("*"):
                        if parts[0] not in folder_names:
                            folder_names.append(parts[0])
                elif line_str and not line_str.startswith("#") and not line_str.startswith(" "):
                    in_packages = False

    return folder_names


def discover_workspace_config():
    apps_file = get_apps_config_file()
    cmds_file = get_commands_config_file()

    # Read existing apps config
    existing_apps = []
    if apps_file.exists():
        try:
            existing_apps = json.loads(apps_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Read existing commands config
    existing_cmds = []
    if cmds_file.exists():
        try:
            existing_cmds = json.loads(cmds_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    # If both already have content, do nothing (preserve user edits)
    if existing_apps and existing_cmds:
        return

    # Discover apps across monorepo folders or root dynamically via Melos config if present
    discovered_apps = []
    search_folders = _parse_melos_config(WORKSPACE_ROOT)
    for folder_name in search_folders:
        sub_dir = WORKSPACE_ROOT / folder_name
        if sub_dir.is_dir():
            for child in sorted(sub_dir.iterdir()):
                if child.is_dir() and not child.name.startswith("."):
                    detected = _detect_app_in_dir(child)
                    if detected and not any(a["id"] == detected["id"] for a in discovered_apps):
                        discovered_apps.append(detected)

    # If no apps found in subfolders, inspect WORKSPACE_ROOT itself
    if not discovered_apps:
        detected_root = _detect_app_in_dir(WORKSPACE_ROOT)
        if detected_root:
            discovered_apps.append(detected_root)
        elif WORKSPACE_ROOT != DASHBOARD_ROOT:
            # Fallback: Treat WORKSPACE_ROOT as a generic app only if it is an external user project
            root_id = re.sub(r"[^a-zA-Z0-9_-]", "_", WORKSPACE_ROOT.name.lower()) or "app"
            discovered_apps.append({"id": root_id, "name": WORKSPACE_ROOT.name or "App", "stack": "generic"})

    # Populate apps_config.json if empty and apps were discovered
    if not existing_apps and discovered_apps:
        new_apps = []
        colors = ["#8b5cf6", "#22c55e", "#f97316", "#ec4899", "#14b8a6", "#06b6d4", "#3b82f6"]
        icons = ["user", "package", "briefcase", "users", "leaf", "wallet", "building-2"]
        for idx, app in enumerate(discovered_apps):
            new_apps.append({
                "id": app["id"],
                "name": app["name"],
                "color": colors[idx % len(colors)],
                "icon": icons[idx % len(icons)],
                "version": "1.0.0 (1)",
                "stack": app.get("stack", "generic"),
                "is_package": app.get("is_package", False),
            })
        apps_file.write_text(json.dumps(new_apps, indent=2), encoding="utf-8")
        existing_apps = new_apps

    # Auto-initialize deploy_config.json with scanned bundle IDs if empty/not exists
    deploy_cfg_file = get_deploy_config_file()
    if not deploy_cfg_file.exists() or deploy_cfg_file.read_text(encoding="utf-8").strip() in ("", "{}", '{"apps": {}}'):
        scanned_apps = {}
        for app in discovered_apps:
            app_id = app["id"]
            scan_res = scan_app_config(app_id)
            if scan_res.get("success"):
                scanned_apps[app_id] = scan_res["discovered"]
        save_deploy_config({"apps": scanned_apps})


def get_apps() -> dict[str, Any]:
    discover_workspace_config()
    cfg_file = get_apps_config_file()
    if not cfg_file.exists():
        return {"success": True, "apps": []}

    try:
        saved = json.loads(cfg_file.read_text(encoding="utf-8"))
        if isinstance(saved, list):
            return {"success": True, "apps": saved}
    except Exception:
        pass
    return {"success": True, "apps": []}


def get_workspaces_list() -> dict[str, Any]:
    """Return available workspaces and the current active workspace."""
    workspaces = []
    ws_file = DASHBOARD_ROOT / "config" / "workspaces_list.json"
    if not ws_file.exists():
        ws_file = DASHBOARD_ROOT / "config" / "workspaces_list.example.json"

    if ws_file.exists():
        try:
            workspaces = json.loads(ws_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    current_path = str(WORKSPACE_ROOT.resolve())
    if not any(w.get("path") == current_path for w in workspaces):
        workspaces.insert(0, {"name": WORKSPACE_ROOT.name or "Current", "path": current_path})

    return {
        "success": True,
        "active": current_path,
        "activeName": WORKSPACE_ROOT.name or "Current",
        "workspaces": workspaces,
    }


def set_active_workspace(new_path: str) -> dict[str, Any]:
    """Change the active workspace root dynamically without restarting server."""
    global WORKSPACE_ROOT
    candidate = Path(new_path).resolve()
    if not candidate.is_dir():
        return {"success": False, "error": f"Directory not found: {new_path}"}

    WORKSPACE_ROOT = candidate
    os.environ["WORKSPACE_ROOT"] = str(WORKSPACE_ROOT)

    active_ws_file = DASHBOARD_ROOT / "config" / "active_workspace.txt"
    try:
        active_ws_file.write_text(str(WORKSPACE_ROOT), encoding="utf-8")
    except Exception:
        pass

    ws_file = DASHBOARD_ROOT / "config" / "workspaces_list.json"
    workspaces = []
    if ws_file.exists():
        try:
            workspaces = json.loads(ws_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    if not any(isinstance(w, dict) and w.get("path") == str(WORKSPACE_ROOT) for w in workspaces):
        workspaces.append({"name": WORKSPACE_ROOT.name, "path": str(WORKSPACE_ROOT)})
        try:
            ws_file.write_text(json.dumps(workspaces, indent=2), encoding="utf-8")
        except Exception:
            pass

    discover_workspace_config()
    return {
        "success": True,
        "active": str(WORKSPACE_ROOT),
        "activeName": WORKSPACE_ROOT.name,
    }


def inspect_workspace_path(path_str: str) -> dict[str, Any]:
    """Inspect a candidate directory path and return detected apps and tech stacks."""
    if not path_str or not path_str.strip():
        return {"success": False, "error": "No path provided"}

    candidate = Path(path_str.strip()).resolve()
    if not candidate.exists():
        return {"success": False, "error": "Directory does not exist", "exists": False}
    if not candidate.is_dir():
        return {"success": False, "error": "Path is not a directory", "exists": False}

    discovered_apps = []
    is_monorepo = False

    has_melos = (candidate / "melos.yaml").exists() or (
        (candidate / "pubspec.yaml").exists() and "melos:" in (candidate / "pubspec.yaml").read_text(encoding="utf-8", errors="replace")
    )

    for folder_name in _parse_melos_config(candidate):
        sub_dir = candidate / folder_name
        if sub_dir.is_dir():
            is_monorepo = True
            for child in sorted(sub_dir.iterdir()):
                if child.is_dir() and not child.name.startswith("."):
                    detected = _detect_app_in_dir(child)
                    if detected and not any(a["id"] == detected["id"] for a in discovered_apps):
                        discovered_apps.append(detected)

    if not discovered_apps:
        detected_root = _detect_app_in_dir(candidate)
        if detected_root:
            discovered_apps.append(detected_root)

    stacks = list(set(a.get("stack", "generic") for a in discovered_apps))

    return {
        "success": True,
        "exists": True,
        "path": str(candidate),
        "name": candidate.name or "Root",
        "appCount": len(discovered_apps),
        "apps": discovered_apps,
        "stacks": stacks,
        "isMonorepo": is_monorepo,
        "hasMelos": has_melos,
    }





def get_commands_config_file() -> Path:
    target_dir = WORKSPACE_ROOT / ".dev-dashboard"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "commands_config.json"
    if not target.exists():
        target.write_text("[]", encoding="utf-8")
    return target


def _is_flavor_configured(app_id: str, flavor: str) -> bool:
    """Return True only if deploy_config has a non-empty bundle_id for this app+flavor."""
    cfg = load_deploy_config()
    app_cfg = cfg.get("apps", {}).get(app_id, {})
    bundle_id = str(app_cfg.get(f"bundle_id_{flavor}") or "").strip()
    return len(bundle_id) > 0


def _scan_xcconfig_bundle_ids(app_dir: Path) -> dict[str, str]:
    """Scan iOS Flutter xcconfig files to extract per-flavor PRODUCT_BUNDLE_IDENTIFIER."""
    result: dict[str, str] = {}
    flavor_map = {"dev": "dev", "qa": "qa", "test": "qa", "prod": "prod", "production": "prod"}
    xcconfig_dir = app_dir / "ios" / "Flutter"
    if not xcconfig_dir.exists():
        return result
    for xcconfig in xcconfig_dir.glob("*.xcconfig"):
        name_lower = xcconfig.stem.lower()
        # only process flavor-specific files e.g. Flavor-Dev.xcconfig
        matched_flavor = None
        for keyword, canon in flavor_map.items():
            if keyword in name_lower and "flavor" in name_lower:
                matched_flavor = canon
                break
        if not matched_flavor:
            continue
        # skip profile/release variants — prefer the base flavor file
        if any(v in name_lower for v in ["release", "debug", "profile"]):
            if f"bundle_id_{matched_flavor}" in result:
                continue
        try:
            for line in xcconfig.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("PRODUCT_BUNDLE_IDENTIFIER"):
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        bundle_id = parts[1].strip()
                        result[f"bundle_id_{matched_flavor}"] = bundle_id
                        break
        except Exception:
            pass
    return result


def _scan_android_app_ids(app_dir: Path) -> dict[str, str]:
    """Scan Android local.properties, gradle.properties, and build.gradle to find per-flavor applicationIds."""
    result: dict[str, str] = {}
    
    # Try gradle.properties
    gradle_props = app_dir / "android" / "gradle.properties"
    if gradle_props.exists():
        try:
            for line in gradle_props.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                for prop, key in [("APP_ID_DEV", "android_id_dev"), ("APP_ID_TEST", "android_id_qa"), ("APP_ID_QA", "android_id_qa"), ("APP_ID_PROD", "android_id_prod")]:
                    if line.startswith(f"{prop}="):
                        result[key] = line.split("=", 1)[1].strip()
        except Exception:
            pass

    # Try local.properties
    local_props = app_dir / "android" / "local.properties"
    if local_props.exists() and not result:
        try:
            for line in local_props.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                for prop, key in [("APP_ID_DEV", "android_id_dev"), ("APP_ID_TEST", "android_id_qa"), ("APP_ID_QA", "android_id_qa"), ("APP_ID_PROD", "android_id_prod")]:
                    if line.startswith(f"{prop}="):
                        result[key] = line.split("=", 1)[1].strip()
        except Exception:
            pass

    # Try build.gradle inline applicationId values
    build_gradle = app_dir / "android" / "app" / "build.gradle"
    if build_gradle.exists() and not result:
        try:
            content = build_gradle.read_text(encoding="utf-8")
            for match in re.finditer(r'applicationId\s+["\']([^"\'\']+)["\']', content):
                app_id_val = match.group(1)
                if "dev" in app_id_val.lower():
                    result["android_id_dev"] = app_id_val
                elif "qa" in app_id_val.lower() or "test" in app_id_val.lower():
                    result["android_id_qa"] = app_id_val
                elif not result.get("android_id_prod"):
                    result["android_id_prod"] = app_id_val
        except Exception:
            pass
    return result


def _scan_credentials(discovered: dict[str, Any], app_id: str) -> None:
    """Scan app directories for client configuration files like google-services.json."""
    app_dir = WORKSPACE_ROOT / "apps" / app_id
    if not app_dir.exists():
        app_dir = WORKSPACE_ROOT

    android_app_dir = app_dir / "android" / "app"
    if android_app_dir.exists():
        for path in android_app_dir.rglob("google-services.json"):
            rel_path = str(path.relative_to(WORKSPACE_ROOT))
            full_path_str = str(path).lower()
            if "/dev/" in full_path_str:
                discovered["google_services_json_dev"] = rel_path
            elif "/qa/" in full_path_str or "/test/" in full_path_str:
                discovered["google_services_json_qa"] = rel_path
            elif "/prod/" in full_path_str or "/production/" in full_path_str:
                discovered["google_services_json_prod"] = rel_path
            elif not discovered.get("google_services_json_prod"):
                discovered["google_services_json_prod"] = rel_path


def scan_app_config(app_id: str) -> dict[str, Any]:
    """Scan workspace files to auto-discover bundle IDs and Android app IDs for an app."""
    app_dir = WORKSPACE_ROOT / "apps" / app_id
    if not app_dir.exists():
        app_dir = WORKSPACE_ROOT  # single-app workspace

    discovered: dict[str, Any] = {}
    discovered.update(_scan_xcconfig_bundle_ids(app_dir))
    discovered.update(_scan_android_app_ids(app_dir))
    _scan_credentials(discovered, app_id)
    return {"success": True, "discovered": discovered, "app_id": app_id}


def scan_all_apps_config() -> dict[str, Any]:
    """Bulk scan all configured apps in the workspace and merge their configuration."""
    apps_file = get_apps_config_file()
    if not apps_file.exists():
        return {"success": False, "error": "No apps configured yet"}

    try:
        apps = json.loads(apps_file.read_text(encoding="utf-8"))
    except Exception:
        return {"success": False, "error": "Failed to read apps configuration"}

    deploy_cfg = load_deploy_config()
    existing_apps_cfg = deploy_cfg.get("apps", {})
    scanned_count = 0

    for app in apps:
        app_id = app["id"]
        res = scan_app_config(app_id)
        if res.get("success") and res.get("discovered"):
            disc = res["discovered"]
            app_entry = existing_apps_cfg.get(app_id, {})
            # Merge discovered values into existing config without overwriting existing user edits
            for k, v in disc.items():
                if not app_entry.get(k):
                    app_entry[k] = v
            existing_apps_cfg[app_id] = app_entry
            scanned_count += 1

    save_deploy_config({"apps": existing_apps_cfg})
    return {"success": True, "count": scanned_count, "total": len(apps)}


# =============================================================================
# Pre-flight iOS certificate / provisioning-profile expiry check
# =============================================================================
# Read-only, advisory, synchronous introspection (same style as scan_app_config
# above) - never touches ACTION_MAP/execute_command/the _JOBS dict, never runs
# as part of an actual build. Trust order: macOS Keychain (exact dates via
# openssl, handles multiple installed certs) -> local .mobileprovision files
# under private_keys/<app>/ (exact dates via `security cms -D`) -> the last
# real build's DistributionSummary.plist as a best-effort, possibly-stale
# fallback (that file is only ever generated AFTER a full ~20min build
# completes, so it can never be a true pre-flight source - only ever used when
# nothing better exists).


def _app_has_ios(app_id: str) -> bool:
    app_dir = WORKSPACE_ROOT / "apps" / app_id
    return (app_dir / "ios").exists()


def _run_cli(args: list[str], input_bytes: Optional[bytes] = None, timeout: float = 5.0) -> tuple[int, bytes, bytes]:
    try:
        r = subprocess.run(args, input=input_bytes, capture_output=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except Exception:
        return 1, b"", b""


def _find_keychain_distribution_certs() -> list[dict]:
    rc, out, _ = _run_cli(["security", "find-certificate", "-a", "-c", "Apple Distribution", "-p", "login.keychain"])
    if rc != 0 or not out:
        return []  # normal for cloud-managed/automatic signing - NOT an error
    pem_blocks = re.findall(rb"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", out, re.DOTALL)
    results = []
    for block in pem_blocks:
        rc2, out2, _ = _run_cli(["openssl", "x509", "-noout", "-subject", "-enddate", "-fingerprint", "-sha1"], input_bytes=block)
        if rc2 != 0:
            continue
        text = out2.decode(errors="replace")
        end_match = re.search(r"notAfter=(.+)", text)
        subj_match = re.search(r"subject=(.+)", text)
        expires_on = None
        if end_match:
            try:
                expires_on = datetime.strptime(end_match.group(1).strip(), "%b %d %H:%M:%S %Y %Z").date().isoformat()
            except Exception:
                pass
        if expires_on:
            results.append({"name": subj_match.group(1).strip() if subj_match else None, "expiresOn": expires_on})
    return sorted(results, key=lambda c: c["expiresOn"])  # soonest-expiring first


def _find_local_mobileprovision_files(app_id: str) -> list[Path]:
    search_dir = WORKSPACE_ROOT / "private_keys" / app_id
    if not search_dir.exists():
        return []
    return list(search_dir.rglob("*.mobileprovision"))


def _read_mobileprovision_metadata(path: Path) -> Optional[dict]:
    rc, out, _ = _run_cli(["security", "cms", "-D", "-i", str(path)])
    if rc != 0 or not out:
        return None
    try:
        plist = plistlib.loads(out)
    except Exception:
        return None
    expires = plist.get("ExpirationDate")  # native datetime, no locale ambiguity
    entitlements = plist.get("Entitlements", {}) or {}
    return {
        "path": str(path),
        "name": plist.get("Name"),
        "uuid": plist.get("UUID"),
        "applicationIdentifier": entitlements.get("application-identifier"),
        "isDistributionStyle": "ProvisionedDevices" not in plist,
        "expiresOn": expires.date().isoformat() if hasattr(expires, "date") else None,
    }


def _select_matching_profile(candidates: list[dict], app_id: str, flavor: str) -> Optional[dict]:
    if not candidates:
        return None
    deploy_cfg = load_deploy_config()
    app_cfg = deploy_cfg.get("apps", {}).get(app_id, {})
    bundle_id = str(app_cfg.get(f"bundle_id_{flavor}") or app_cfg.get("bundle_id_prod") or "").strip()
    scored = []
    for c in candidates:
        app_identifier = str(c.get("applicationIdentifier") or "")
        matches_bundle = bool(bundle_id) and app_identifier.endswith(bundle_id)
        scored.append((matches_bundle, c.get("isDistributionStyle", False), c))
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return scored[0][2] if scored else None


def _find_last_distribution_summary(app_id: str) -> Optional[Path]:
    candidate = WORKSPACE_ROOT / "apps" / app_id / "build" / "ios" / "ipa" / "DistributionSummary.plist"
    return candidate if candidate.exists() else None


def _parse_distribution_summary_expiry(raw: str) -> dict:
    """raw like '14/06/27'. dateExpires is a *display string* (a plain <string> in the
    plist, not a <date> element) written in the exporting Mac's current short-date
    locale format - NOT a fixed Apple format. Only trust it as day-first when one
    component is unambiguously >12."""
    try:
        a, b, yy = (int(x) for x in raw.split("/"))
    except Exception:
        return {"raw": raw, "expiresOn": None, "formatConfidence": "unparseable"}
    year = 2000 + yy
    if a > 12:
        day, month = a, b
    elif b > 12:
        day, month = b, a
    else:
        return {"raw": raw, "expiresOn": None, "formatConfidence": "ambiguous"}
    try:
        d = date(year, month, day)
        return {"raw": raw, "expiresOn": d.isoformat(), "formatConfidence": "day_first_unambiguous"}
    except ValueError:
        return {"raw": raw, "expiresOn": None, "formatConfidence": "unparseable"}


def check_ios_expiry(app: str, flavor: str = "prod") -> dict[str, Any]:
    if not app:
        return {"success": False, "error": "app is required"}
    if not _app_has_ios(app):
        return {"success": True, "app": app, "flavor": flavor, "status": "not_ios_app"}

    warnings: list[str] = []
    now = datetime.utcnow()

    def _status_for(expires_on: Optional[str]) -> str:
        if not expires_on:
            return "unknown"
        days = (date.fromisoformat(expires_on) - now.date()).days
        if days < 0:
            return "expired"
        if days < EXPIRY_WARNING_THRESHOLD_DAYS:
            return "warning"
        return "ok"

    # 1. Keychain (highest trust - exact dates via openssl, handles multi-cert naturally)
    certs = _find_keychain_distribution_certs()
    cert_result = None
    if certs:
        best = certs[0]
        cert_result = {**best, "source": "keychain", "confidence": "high",
                       "status": _status_for(best["expiresOn"]),
                       "candidates": certs if len(certs) > 1 else None}
        if len(certs) > 1:
            warnings.append(f"{len(certs)} 'Apple Distribution' identities found in Keychain - "
                             "showing the soonest-expiring; verify which one Xcode will actually pick.")

    # 2. Local .mobileprovision files (exact dates, but cross-checked below against a
    #    real build's reported cert 'type' to catch a stale/mismatched local file)
    profile_result = None
    local_files = _find_local_mobileprovision_files(app)
    profiles = [m for m in (_read_mobileprovision_metadata(p) for p in local_files) if m]
    matched = _select_matching_profile(profiles, app, flavor)
    if matched:
        profile_result = {**matched, "source": "local_mobileprovision", "confidence": "high",
                           "status": _status_for(matched["expiresOn"])}

    # 3. Fallback: last build's DistributionSummary.plist (best-effort, possibly stale/ambiguous)
    summary_path = _find_last_distribution_summary(app)
    if summary_path and (not cert_result or not profile_result):
        try:
            summary = plistlib.load(summary_path.open("rb"))
            build_key = next(iter(summary))  # e.g. "PROD.ipa"
            entry = summary[build_key][0]
            cert_parsed = _parse_distribution_summary_expiry(entry["certificate"]["dateExpires"])
            profile_parsed = _parse_distribution_summary_expiry(entry["profile"]["dateExpires"])
            stale_days = (now - datetime.utcfromtimestamp(summary_path.stat().st_mtime)).days
            if cert_result is None:
                cert_result = {**cert_parsed, "source": "last_build_summary", "confidence": "low",
                               "bestEffort": True, "staleBuildDays": stale_days,
                               "status": _status_for(cert_parsed["expiresOn"]) if cert_parsed["expiresOn"] else "unknown"}
            if profile_result is None:
                profile_result = {**profile_parsed, "source": "last_build_summary", "confidence": "low",
                                   "bestEffort": True, "staleBuildDays": stale_days,
                                   "status": _status_for(profile_parsed["expiresOn"]) if profile_parsed["expiresOn"] else "unknown"}
            if "Cloud Managed" in entry["certificate"].get("type", "") and local_files:
                warnings.append("Local .mobileprovision file(s) found on disk, but the last real build was "
                                 "signed with a Cloud Managed (Xcode-automatic) identity - the local files may "
                                 "be stale test artifacts, not what will actually be used.")
        except Exception:
            pass

    return {
        "success": True,
        "app": app,
        "flavor": flavor,
        "thresholdDays": EXPIRY_WARNING_THRESHOLD_DAYS,
        "checkedAt": now.isoformat() + "Z",
        "certificate": cert_result or {"status": "unknown", "source": "none"},
        "provisioningProfile": profile_result or {"status": "unknown", "source": "none"},
        "warnings": warnings,
    }


def get_commands(app: str) -> dict[str, Any]:
    if not app:
        return {"success": True, "commands": []}

    discover_workspace_config()
    
    has_melos = any(WORKSPACE_ROOT.glob("melos*.yaml")) or (
        (WORKSPACE_ROOT / "pubspec.yaml").exists() and
        "melos:" in (WORKSPACE_ROOT / "pubspec.yaml").read_text(encoding="utf-8")
    )
    
    use_apps_dir = (WORKSPACE_ROOT / "apps" / app).exists()
    prefix = f"cd apps/{app} &&" if use_apps_dir else ""
    
    # Load dynamic flavors list from deploy_config.json for this app
    deploy_cfg = load_deploy_config()
    flavors = deploy_cfg.get("apps", {}).get(app, {}).get("flavors", ["dev", "qa", "prod"])
    
    raw_commands = _build_commands_from_templates(app, prefix, has_melos and use_apps_dir, flavors)
    commands = []
    
    for c in raw_commands:
        commands.append({
            "id": c["id"],
            "templateId": c["templateId"],
            "runner": c["runner"],
            "key": c["command"],
            "name": c["name"],
            "desc": c["description"],
            "description": c["description"],
            "platform": c["platform"],
            "flavor": c["flavor"],
            "configured": c["configured"],
        })
        
    return {"success": True, "commands": commands}


# Template ids eligible for the "Deploy All Apps" batch trigger - build/deploy/
# upload actions only. release/utility templates are a different fan-out concern
# (they operate at "any" flavor, not per-selected-flavor) and are excluded.
BATCH_ELIGIBLE_TEMPLATE_IDS = {
    "deploy_both", "deploy_aab", "deploy_ipa", "upload_aab", "upload_ipa",
    "build_aab", "build_ipa", "build_apk", "build_ipa_device",
}


def get_batch_deploy_plan(flavor: str, template_id: str = "auto") -> dict[str, Any]:
    """Read-only: for every app in get_apps(), resolve which single command would
    run for `flavor` under `template_id` ('auto' = deploy_both, falling back to
    whichever single platform is configured). Never spawns anything - purely a
    preview for the batch-deploy confirmation modal."""
    if not flavor:
        return {"success": False, "error": "flavor is required"}
    if template_id and template_id != "auto" and template_id not in BATCH_ELIGIBLE_TEMPLATE_IDS:
        return {"success": False, "error": f"Unsupported batch template: {template_id}"}

    plan: list[dict[str, Any]] = []
    for app in get_apps().get("apps", []):
        app_id = app["id"]
        by_template = {
            c["templateId"]: c
            for c in get_commands(app_id).get("commands", [])
            if c.get("flavor") == flavor
        }
        entry: dict[str, Any] = {"appId": app_id, "appName": app.get("name", app_id), "color": app.get("color", "#6366f1")}

        def _use(cmd: dict[str, Any]) -> None:
            entry.update({"templateId": cmd["templateId"], "templateName": cmd["name"],
                          "command": cmd["key"], "runner": cmd["runner"],
                          "willRun": True, "skipReason": None})

        if template_id and template_id != "auto":
            cmd = by_template.get(template_id)
            if cmd and cmd.get("configured"):
                _use(cmd)
            else:
                entry.update({"willRun": False, "skipReason":
                    f"'{template_id}' not configured for {flavor} (missing bundle_id_{flavor})"})
        else:
            both, aab, ipa = by_template.get("deploy_both"), by_template.get("deploy_aab"), by_template.get("deploy_ipa")
            aab_ok, ipa_ok = bool(aab and aab.get("configured")), bool(ipa and ipa.get("configured"))
            if both and both.get("configured"):
                _use(both)
            elif aab_ok and not ipa_ok:
                _use(aab)
            elif ipa_ok and not aab_ok:
                _use(ipa)
            elif aab_ok and ipa_ok:
                entry.update({"willRun": False, "skipReason":
                    "both platforms configured individually but 'deploy_both' isn't - running "
                    "deploy_aab + deploy_ipa separately here would bump the version twice"})
            else:
                entry.update({"willRun": False, "skipReason":
                    f"no deploy command configured for {flavor} (missing bundle_id_{flavor})"})
        plan.append(entry)

    return {"success": True, "flavor": flavor, "templateId": template_id or "auto", "plan": plan}


def _release_auto_chain_configured(app_id: str, flavor: str) -> tuple[bool, str]:
    """Read-only check: should a successful store-upload for this app/flavor auto-chain
    a release (tag + push)? Returns (should_chain, action_template_id)."""
    deploy_cfg = load_deploy_config()
    app_cfg = deploy_cfg.get("apps", {}).get(app_id, {})
    if not app_cfg.get("auto_release_on_success"):
        return False, ""
    allowed_flavors = app_cfg.get("auto_release_flavors") or ["prod"]
    if flavor and flavor not in allowed_flavors:
        return False, ""
    action_id = app_cfg.get("auto_release_action") or "release_push"
    return True, action_id


def _trigger_chained_release(app_id: str, flavor: str, action_id: str, source_job_id: str) -> None:
    """Spawn the release (tag + push) job chained from a just-succeeded store upload.
    Reuses execute_command()'s existing "any" -> real-flavor substitution - the same
    mechanism a manual click on that Release card already relies on. Runs entirely
    inside this feature's own job-execution scripts; no dependency on any other feature."""
    try:
        action = ACTION_MAP.get(action_id, action_id)
        release_cmd = f"bash {DASHBOARD_ROOT}/features/deployment/scripts/run_build.sh {action} {app_id} any"
        # confirmed=True: automated continuation of a job whose upstream prod store
        # deploy the operator already explicitly confirmed once - no human in the
        # loop here to confirm a second time. In practice no release_* action is ever
        # in _STORE_SHIPPING_ACTIONS, so _is_prod_store_deploy() would return False
        # for this call regardless of flavor; passed explicitly so that stays true by
        # design, not by accident, if the action set ever changes.
        # _assume_app_lock_held=True: this app's concurrency-guard lock is still held
        # from the just-finished store-upload job (finish_job() deliberately left it
        # in place) - reuse it rather than re-acquiring, so there is never a gap where
        # an unrelated manual click could slip in between the two jobs.
        result = execute_command(
            app_id, release_cmd, "custom", env=flavor, template_id=action_id,
            flavor=flavor, confirmed=True, _assume_app_lock_held=True,
        )
        with _JOBS_LOCK:
            job = _JOBS.get(source_job_id)
            if job:
                job["status"] = "success"
                if result.get("success"):
                    job["chainedJobId"] = result["jobId"]
        if result.get("success"):
            _append_job_log(source_job_id, "output", f"\n🔗 Auto-triggering release ({action_id}) for {app_id}{f' ({flavor})' if flavor else ''}... job {result['jobId']}\n")
        else:
            _append_job_log(source_job_id, "output", f"\n⚠️ Auto-release failed to start: {result.get('error')}\n")
        _record_history_entry(source_job_id)
    except Exception as exc:
        with _JOBS_LOCK:
            job = _JOBS.get(source_job_id)
            if job:
                job["status"] = "success"
        _append_job_log(source_job_id, "output", f"\n⚠️ Auto-release error: {exc}\n")
        _record_history_entry(source_job_id)


def _get_history_file() -> Path:
    target_dir = WORKSPACE_ROOT / ".dev-dashboard"
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / "deployment_history.jsonl"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _duration_seconds(started_at: Optional[float]) -> Optional[float]:
    if not started_at:
        return None
    return round(time.time() - started_at, 1)


def _tail(text: str, limit: int) -> str:
    text = text or ""
    return text[-limit:] if len(text) > limit else text


def _append_history_line(entry: dict) -> None:
    """Append one row and rotate the file if it's grown past the cap. Never
    lets a history-persistence failure break the deployment job itself."""
    line = json.dumps(entry) + "\n"
    history_file = _get_history_file()
    with _HISTORY_LOCK:
        try:
            with history_file.open("a", encoding="utf-8") as f:
                f.write(line)
            if history_file.stat().st_size > HISTORY_MAX_BYTES:
                backup = history_file.parent / (history_file.name + ".1")
                try:
                    backup.unlink()
                except FileNotFoundError:
                    pass
                history_file.rename(backup)
        except Exception:
            pass


def _record_history_entry(job_id: str) -> None:
    """Append a durable row for a job that just reached a terminal status
    (success/error/stopped). Call exactly once per job - see finish_job()
    and _trigger_chained_release() for the two call sites, chosen so a
    chained job's row is only written once chainedJobId is actually known."""
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        entry = {
            "id": job.get("id", job_id),
            "completedAt": _utc_now_iso(),
            "startedAt": job.get("started_at"),
            "durationSeconds": _duration_seconds(job.get("started_at")),
            "app": job.get("app", ""),
            "templateId": job.get("template_id", ""),
            "flavor": job.get("env", ""),
            "command": job.get("command", ""),
            "runner": job.get("runner", ""),
            "status": job.get("status"),
            "returnCode": job.get("return_code"),
            "outputExcerpt": _tail(job.get("output", ""), HISTORY_OUTPUT_EXCERPT_CHARS),
            "errorExcerpt": _tail(job.get("error", ""), HISTORY_ERROR_EXCERPT_CHARS),
            "chainedJobId": job.get("chainedJobId"),
        }
    _append_history_line(entry)


def get_deployment_history(limit: int = 50, app: str = "", flavor: str = "", status: str = "") -> dict[str, Any]:
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 50
    limit = max(1, min(limit, HISTORY_ENDPOINT_MAX_LIMIT))

    results: list[dict] = []

    def scan_file(path: Path) -> None:
        if not path.exists():
            return
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except Exception:
            return
        for raw in reversed(lines):          # file is oldest-first; walk backwards
            if len(results) >= limit:
                return
            raw = raw.strip()
            if not raw:
                continue
            try:
                entry = json.loads(raw)
            except Exception:
                continue                       # tolerate a torn/partial trailing line
            if app and entry.get("app") != app:
                continue
            if flavor and entry.get("flavor") != flavor:
                continue
            if status and entry.get("status") != status:
                continue
            results.append(entry)

    history_file = _get_history_file()
    with _HISTORY_LOCK:
        scan_file(history_file)
        if len(results) < limit:
            scan_file(history_file.parent / (history_file.name + ".1"))

    return {"success": True, "entries": results, "count": len(results)}


def _is_prod_store_deploy(resolved_command: str) -> bool:
    """Ground-truth prod-shipping detection for the confirmation gate in
    execute_command(). Deliberately inspects the ACTUAL resolved command line about
    to be handed to the shell - never a client-asserted flavor/templateId field, which
    a caller bypassing the UI (a future "Deploy All Apps" batch trigger, a
    hand-written API script) could get wrong or simply never set. Every command this
    router generates ends in "<bash_action> <app_id> <flavor>" (see
    _build_commands_from_templates and the "any"->env substitution in
    execute_command()), so the last token is always the real flavor about to run, and
    one of the earlier tokens names the bash action.

    Scoped to true store-shipping actions only: a prod git release (release_tag /
    release_push) or a local prod build artifact (build_ipa / build_aab) doesn't
    itself put a build in front of real app-store users, so those stay ungated here
    even when run with flavor "prod".
    """
    tokens = resolved_command.split()
    if not tokens or tokens[-1].strip().lower() != "prod":
        return False
    return any(tok in _STORE_SHIPPING_ACTIONS for tok in tokens)


def execute_command(
    app: str,
    command: str,
    runner: str = "make",
    env: str = "",
    template_id: str = "",
    flavor: str = "",
    confirmed: bool = False,
    _assume_app_lock_held: bool = False,
) -> dict[str, Any]:
    if not app or not command:
        return {"success": False, "error": "App and command are required"}

    # Release/utility command templates are generated with a literal trailing "any"
    # placeholder for the env/flavor slot (see _build_commands_from_templates) — unlike
    # build/upload commands, there's one card per action rather than one per flavor, so
    # the flavor can't be baked in at generation time. Substitute in whatever environment
    # the dashboard's Dev/QA/Prod selector actually has active right now, so the release
    # tag/changelog/"since last release" window reflect it. Build/upload commands always
    # end in a real flavor name already, never literally "any", so this never touches them.
    if env and command.rstrip().endswith(" any"):
        command = command.rstrip()[: -len(" any")] + f" {env}"

    # --- Prod deploy confirmation gate (defense in depth) ---
    # The frontend already blocks this with a confirm modal before ever POSTing for a
    # prod store-shipping command (see app.js isProdStoreDeploy()/executeSelected()).
    # This exists so every OTHER caller - a future "Deploy All Apps" batch trigger, a
    # hand-written API script, a bug in the UI - can't slip one through unconfirmed.
    # Runs before any subprocess is spawned, before the job is registered, and before
    # the concurrency-guard lock below - a rejected, unconfirmed request has zero side
    # effects to unwind.
    if _is_prod_store_deploy(command) and not confirmed:
        return {
            "success": False,
            "error": f"This runs a PROD store deploy for '{app}' - resend with confirmed: true once explicitly approved.",
            "needsConfirmation": True,
        }

    # --- concurrency guard: reject if this app already has a running/chaining job ---
    if not _assume_app_lock_held:
        with _JOBS_LOCK:
            existing = _APP_LOCKS.get(app)
            if existing is not None:
                return {
                    "success": False,
                    "error": (
                        f"A deployment job is already running for '{app}' "
                        f"({existing.get('flavor') or 'any flavor'}): {existing.get('command')}. "
                        "Wait for it to finish, or stop it, before starting another."
                    ),
                    "code": "APP_BUSY",
                    "runningJob": {
                        "jobId": existing.get("job_id"),
                        "flavor": existing.get("flavor"),
                        "command": existing.get("command"),
                        "startedAt": existing.get("started_at"),
                    },
                }
            # Reserve NOW, in the SAME critical section as the check above - closes
            # the check-then-act race where two overlapping calls could both observe
            # "nothing running" before either registers. job_id is filled in below,
            # once we actually have one.
            _APP_LOCKS[app] = {
                "job_id": None,
                "flavor": flavor,
                "command": command,
                "started_at": time.time(),
            }

    try:
        TMP_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    child_env = os.environ.copy()
    child_env["TMPDIR"] = str(TMP_DIR)
    child_env["TMP"] = str(TMP_DIR)
    child_env["TEMP"] = str(TMP_DIR)
    # Melos scripts injected into each app's pubspec.yaml resolve run_build.sh via
    # ${DASHBOARD_SCRIPTS_PATH:-<stale pre-extraction path>} — without this, every
    # nested `melos run ...` step silently falls back to that old, unfixed copy
    # instead of this feature's own scripts.
    child_env["DASHBOARD_SCRIPTS_PATH"] = str(FEATURE_DIR / "scripts")

    if runner == "custom":
        shell_bin = shutil.which("bash") or shutil.which("zsh") or os.environ.get("SHELL") or "/bin/sh"
        cmd = [shell_bin, "-c", command]
        cmd_str = command
    elif runner == "melos":
        cmd = ["melos", "run", command]
        cmd_str = f"melos run {command}"
    else:
        cmd = ["make", command]
        cmd_str = f"make {command}"

    job_id = _new_job_id()
    try:
        process = subprocess.Popen(
            cmd,
            cwd=WORKSPACE_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            start_new_session=True,
            bufsize=0,
            env=child_env,
        )
    except Exception as exc:
        if not _assume_app_lock_held:
            with _JOBS_LOCK:
                _APP_LOCKS.pop(app, None)   # release reservation; nothing was spawned
        return {"success": False, "error": str(exc)}

    with _JOBS_LOCK:
        _JOBS[job_id] = {
            "id": job_id,
            "command": cmd_str,
            "status": "running",
            "return_code": None,
            "output": "",
            "error": "",
            "pid": process.pid,
            "pgid": process.pid,
            "process": process,
            "app": app,
            "template_id": template_id,
            "env": env,
            "started_at": time.time(),
        }
        # Finalize (or, for the chained handoff, create) this app's lock entry with
        # the real job_id/command now that we have them.
        lock_entry = _APP_LOCKS.get(app)
        if lock_entry is not None:
            lock_entry["job_id"] = job_id
            lock_entry["command"] = cmd_str
        else:
            _APP_LOCKS[app] = {
                "job_id": job_id,
                "flavor": flavor,
                "command": cmd_str,
                "started_at": time.time(),
            }

    def stream_pipe(pipe, field: str) -> None:
        try:
            if pipe is None:
                return
            while True:
                line = pipe.readline()
                if not line:
                    break
                try:
                    text = line.decode("utf-8")
                except UnicodeDecodeError:
                    text = line.decode("utf-8", errors="replace")
                _append_job_log(job_id, field, text)
        finally:
            try:
                if pipe is not None:
                    pipe.close()
            except Exception:
                pass

    threading.Thread(target=stream_pipe, args=(process.stdout, "output"), daemon=True).start()
    threading.Thread(target=stream_pipe, args=(process.stderr, "error"), daemon=True).start()

    def finish_job() -> None:
        process.wait()
        with _JOBS_LOCK:
            job = _JOBS.get(job_id)
            if not job:
                return
            job["return_code"] = process.returncode
            status = "stopped" if job.get("status") == "stopping" else ("success" if process.returncode == 0 else "error")
            job.pop("process", None)

        should_chain = False
        action_id = ""
        if status == "success" and template_id in STORE_UPLOAD_TEMPLATE_IDS:
            should_chain, action_id = _release_auto_chain_configured(app, env)

        with _JOBS_LOCK:
            job = _JOBS.get(job_id)
            if job:
                job["status"] = "chaining" if should_chain else status
            if not should_chain:
                held = _APP_LOCKS.get(app)
                if held is not None and held.get("job_id") == job_id:
                    _APP_LOCKS.pop(app, None)
            # else: leave _APP_LOCKS[app] exactly as-is - it still points at this
            # just-finished job. _trigger_chained_release(), called right below,
            # re-enters execute_command() with _assume_app_lock_held=True, which
            # overwrites this same entry with the chained job's own job_id/command
            # once it spawns. The app is therefore NEVER actually unlocked between
            # the store-upload job and its automatic release - no window for an
            # unrelated manual click to slip in.

        if should_chain:
            _trigger_chained_release(app, env, action_id, job_id)
        else:
            _record_history_entry(job_id)

    threading.Thread(target=finish_job, daemon=True).start()
    return {"success": True, "jobId": job_id, "command": cmd_str}


def get_job(job_id: Optional[str]) -> dict[str, Any]:
    if not job_id:
        return {"success": False, "error": "Missing job id"}
    with _JOBS_LOCK:
        job = _JOBS.get(str(job_id))
        if not job:
            return {"success": False, "error": "Job not found"}
        payload = {k: v for k, v in job.items() if k != "process"}
    return {"success": True, "job": payload}


def stop_job(job_id: Optional[str]) -> dict[str, Any]:
    if not job_id:
        return {"success": False, "error": "Missing jobId"}

    with _JOBS_LOCK:
        job = _JOBS.get(str(job_id))
        if not job:
            return {"success": False, "error": "Job not found"}
        process = job.get("process")
        if process is None:
            return {"success": False, "error": "Job is not running"}
        job["status"] = "stopping"

    try:
        pgid = job.get("pgid")
        if pgid:
            os.killpg(int(pgid), signal.SIGTERM)
        else:
            process.terminate()
    except Exception:
        pass

    def kill_later() -> None:
        try:
            process.wait(timeout=5)
        except Exception:
            try:
                pgid = job.get("pgid")
                if pgid:
                    os.killpg(int(pgid), signal.SIGKILL)
                else:
                    process.kill()
            except Exception:
                pass

    threading.Thread(target=kill_later, daemon=True).start()
    return {"success": True, "message": "Stop requested"}


def add_app(app_data: dict[str, Any]) -> dict[str, Any]:
    """Manually register a custom app configuration to apps_config.json."""
    cfg_file = get_apps_config_file()
    try:
        if cfg_file.exists():
            apps = json.loads(cfg_file.read_text(encoding="utf-8"))
        else:
            apps = []
    except Exception:
        apps = []
        
    if not isinstance(apps, list):
        apps = []
        
    app_id = app_data.get("id")
    if not app_id:
        return {"success": False, "error": "App ID is required"}
        
    app_id = app_id.strip()
    
    # Remove existing duplicate
    apps = [a for a in apps if isinstance(a, dict) and a.get("id") != app_id]
    
    colors = ["#8b5cf6", "#22c55e", "#f97316", "#ec4899", "#14b8a6", "#06b6d4", "#3b82f6"]
    icons = ["user", "package", "briefcase", "users", "leaf", "wallet", "building-2"]
    
    new_entry = {
        "id": app_id,
        "name": app_data.get("name", app_id.capitalize()),
        "color": app_data.get("color", colors[len(apps) % len(colors)]),
        "icon": app_data.get("icon", icons[len(apps) % len(icons)]),
        "version": app_data.get("version", "1.0.0 (1)")
    }
    apps.append(new_entry)
    cfg_file.write_text(json.dumps(apps, indent=2), encoding="utf-8")
    
    # Pre-populate dynamic flavors to deploy_config.json if not present
    deploy_cfg = load_deploy_config()
    if "apps" not in deploy_cfg:
        deploy_cfg["apps"] = {}
    if app_id not in deploy_cfg["apps"]:
        deploy_cfg["apps"][app_id] = {
            "flavors": ["dev", "qa", "prod"]
        }
        save_deploy_config(deploy_cfg)
        
    return {"success": True, "app": new_entry}
