import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

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
TEMPLATES_FILE = DASHBOARD_ROOT / "config" / "deployment_templates.json"


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
    target = target_dir / "deploy_config.json"
    if not target.exists():
        target.write_text("{}", encoding="utf-8")
    return target


def get_commands_config_file() -> Path:
    target_dir = WORKSPACE_ROOT / ".dev-dashboard"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "commands_config.json"
    if not target.exists():
        target.write_text("[]", encoding="utf-8")
    return target


def load_deploy_config() -> dict[str, Any]:
    cfg_file = get_deploy_config_file()
    if not cfg_file.exists():
        return {}
    try:
        content = cfg_file.read_text(encoding="utf-8").strip()
        return json.loads(content) if content else {}
    except Exception:
        return {}


def save_deploy_config(data: dict[str, Any]) -> dict[str, Any]:
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


def _detect_app_in_dir(path: Path) -> Optional[dict[str, Any]]:
    if not path.is_dir():
        return None
    pubspec = path / "pubspec.yaml"
    package_json = path / "package.json"
    build_gradle = path / "android" / "build.gradle"
    build_gradle_kts = path / "android" / "build.gradle.kts"
    xcodeproj = list(path.glob("*.xcodeproj")) or list((path / "ios").glob("*.xcodeproj"))

    stack = "generic"
    app_name = path.name
    is_package = False

    if pubspec.exists():
        stack = "flutter"
        try:
            content = pubspec.read_text(encoding="utf-8")
            name_match = re.search(r"^name:\s*(.+)$", content, re.MULTILINE)
            if name_match:
                app_name = name_match.group(1).strip().strip("'\"")
            if "executables:" not in content and "flutter:" not in content:
                is_package = True
        except Exception:
            pass
    elif package_json.exists():
        stack = "react-native" if (path / "ios").exists() or (path / "android").exists() else "node"
    elif build_gradle.exists() or build_gradle_kts.exists() or xcodeproj:
        stack = "native"

    app_id = re.sub(r"[^a-zA-Z0-9_-]", "_", app_name.lower())
    return {
        "id": app_id,
        "name": app_name,
        "path": str(path),
        "stack": stack,
        "is_package": is_package,
    }


def _parse_melos_config(root_dir: Path) -> list[str]:
    melos_file = root_dir / "melos.yaml"
    if not melos_file.exists():
        pubspec = root_dir / "pubspec.yaml"
        if pubspec.exists() and "melos:" in pubspec.read_text(encoding="utf-8", errors="replace"):
            melos_file = pubspec
        else:
            return ["apps"]

    try:
        content = melos_file.read_text(encoding="utf-8", errors="replace")
        packages: list[str] = []
        in_pkgs = False
        for line in content.splitlines():
            if line.strip().startswith("packages:"):
                in_pkgs = True
                continue
            if in_pkgs:
                if line and not line.startswith(" ") and not line.startswith("\t") and not line.strip().startswith("-"):
                    break
                stripped = line.strip()
                if stripped.startswith("-"):
                    pkg_glob = stripped.lstrip("-").strip().strip("'\"")
                    folder = pkg_glob.split("/")[0].replace("*", "").strip()
                    if folder and folder not in packages:
                        packages.append(folder)
        return packages or ["apps"]
    except Exception:
        return ["apps"]


def _detect_app_flavors(app_id: str) -> list[str]:
    deploy_cfg = load_deploy_config()
    app_cfg = deploy_cfg.get("apps", {}).get(app_id, {})

    custom_flavors = app_cfg.get("flavors")
    if isinstance(custom_flavors, list) and custom_flavors:
        valid = [str(f).strip().lower() for f in custom_flavors if str(f).strip()]
        if valid:
            return valid

    found = set()
    for k in app_cfg.keys():
        if k.startswith("bundle_id_") and len(k) > len("bundle_id_"):
            found.add(k[len("bundle_id_"):])
        elif k.startswith("android_id_") and len(k) > len("android_id_"):
            found.add(k[len("android_id_"):])

    if found:
        ordered = ["dev", "qa", "staging", "uat", "sandbox", "beta", "prod"]
        res = [f for f in ordered if f in found]
        for f in sorted(found):
            if f not in res:
                res.append(f)
        return res

    return ["dev", "qa", "prod"]


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


def add_app(app_data: dict[str, Any]) -> dict[str, Any]:
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

    raw_id = app_data.get("id")
    if not raw_id:
        return {"success": False, "error": "App ID is required"}

    app_id = re.sub(r"[^a-zA-Z0-9_-]", "_", str(raw_id).strip())

    apps = [a for a in apps if isinstance(a, dict) and a.get("id") != app_id]

    colors = ["#8b5cf6", "#22c55e", "#f97316", "#ec4899", "#14b8a6", "#06b6d4", "#3b82f6"]
    icons = ["user", "package", "briefcase", "users", "leaf", "wallet", "building-2"]

    new_entry = {
        "id": app_id,
        "name": app_data.get("name", app_id.capitalize()),
        "color": app_data.get("color", colors[len(apps) % len(colors)]),
        "icon": app_data.get("icon", icons[len(apps) % len(icons)]),
        "version": app_data.get("version", "1.0.0 (1)"),
    }
    apps.append(new_entry)
    cfg_file.write_text(json.dumps(apps, indent=2), encoding="utf-8")

    deploy_cfg = load_deploy_config()
    if "apps" not in deploy_cfg:
        deploy_cfg["apps"] = {}
    if app_id not in deploy_cfg["apps"]:
        deploy_cfg["apps"][app_id] = {"flavors": ["dev", "qa", "prod"]}
        save_deploy_config(deploy_cfg)

    return {"success": True, "app": new_entry}


def get_workspaces_list() -> dict[str, Any]:
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
    if not path_str or not path_str.strip():
        return {"success": False, "error": "No path provided"}

    candidate = Path(path_str.strip()).resolve()
    if not candidate.exists():
        return {"success": False, "error": "Directory does not exist", "exists": False}
    if not candidate.is_dir():
        return {"success": False, "error": "Path is not a directory", "exists": False}

    # Path traversal protection check
    root_res = WORKSPACE_ROOT.resolve()
    if candidate != root_res and root_res not in candidate.parents:
        return {
            "success": False,
            "error": "Path traversal restriction: Candidate directory must be within workspace root",
            "exists": True,
            "restricted": True,
        }

    discovered_apps = []
    is_monorepo = False

    has_melos = (candidate / "melos.yaml").exists() or (
        (candidate / "pubspec.yaml").exists()
        and "melos:" in (candidate / "pubspec.yaml").read_text(encoding="utf-8", errors="replace")
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


def _scan_xcconfig_bundle_ids(app_dir: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    flavor_map = {
        "dev": "dev", "qa": "qa", "test": "qa", "prod": "prod", "production": "prod",
        "staging": "staging", "uat": "uat", "sandbox": "sandbox", "beta": "beta", "demo": "demo"
    }
    xcconfig_dir = app_dir / "ios" / "Flutter"
    if not xcconfig_dir.exists():
        return result
    for xcconfig in xcconfig_dir.glob("*.xcconfig"):
        name_lower = xcconfig.stem.lower()
        matched_flavor = None
        for key, val in flavor_map.items():
            if key in name_lower:
                matched_flavor = val
                break
        if not matched_flavor:
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
    result: dict[str, str] = {}
    prop_mappings = [
        ("APP_ID_DEV", "android_id_dev"), ("APP_ID_TEST", "android_id_qa"), ("APP_ID_QA", "android_id_qa"),
        ("APP_ID_STAGING", "android_id_staging"), ("APP_ID_UAT", "android_id_uat"),
        ("APP_ID_SANDBOX", "android_id_sandbox"), ("APP_ID_BETA", "android_id_beta"),
        ("APP_ID_PROD", "android_id_prod")
    ]

    gradle_props = app_dir / "android" / "gradle.properties"
    if gradle_props.exists():
        try:
            for line in gradle_props.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                for prop, key in prop_mappings:
                    if line.startswith(f"{prop}="):
                        result[key] = line.split("=", 1)[1].strip()
        except Exception:
            pass

    local_props = app_dir / "android" / "local.properties"
    if local_props.exists() and not result:
        try:
            for line in local_props.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                for prop, key in prop_mappings:
                    if line.startswith(f"{prop}="):
                        result[key] = line.split("=", 1)[1].strip()
        except Exception:
            pass

    for gradle_name in ("app/build.gradle", "app/build.gradle.kts", "build.gradle"):
        build_gradle = app_dir / "android" / gradle_name
        if build_gradle.exists():
            try:
                content = build_gradle.read_text(encoding="utf-8")
                for match in re.finditer(r'applicationId\s+["\']([^"\'\']+)["\']', content):
                    app_id_val = match.group(1)
                    val_lower = app_id_val.lower()
                    if "dev" in val_lower:
                        result["android_id_dev"] = app_id_val
                    elif "staging" in val_lower:
                        result["android_id_staging"] = app_id_val
                    elif "uat" in val_lower:
                        result["android_id_uat"] = app_id_val
                    elif "qa" in val_lower or "test" in val_lower:
                        result["android_id_qa"] = app_id_val
                    elif not result.get("android_id_prod"):
                        result["android_id_prod"] = app_id_val
            except Exception:
                pass
    return result


def _scan_credentials(discovered: dict[str, Any], app_id: str) -> None:
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
    app_dir = WORKSPACE_ROOT / "apps" / app_id
    if not app_dir.exists():
        app_dir = WORKSPACE_ROOT

    discovered: dict[str, Any] = {}
    discovered.update(_scan_xcconfig_bundle_ids(app_dir))
    discovered.update(_scan_android_app_ids(app_dir))
    _scan_credentials(discovered, app_id)
    return {"success": True, "discovered": discovered, "app_id": app_id}


def scan_all_apps_config() -> dict[str, Any]:
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
            for k, v in disc.items():
                if not app_entry.get(k):
                    app_entry[k] = v
            existing_apps_cfg[app_id] = app_entry
            scanned_count += 1

    save_deploy_config({"apps": existing_apps_cfg})
    return {"success": True, "count": scanned_count, "total": len(apps)}


def discover_workspace_config() -> None:
    apps_file = get_apps_config_file()
    cmds_file = get_commands_config_file()

    existing_apps = []
    if apps_file.exists():
        try:
            existing_apps = json.loads(apps_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    existing_cmds = []
    if cmds_file.exists():
        try:
            existing_cmds = json.loads(cmds_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    if existing_apps and existing_cmds:
        return

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

    if not discovered_apps:
        detected_root = _detect_app_in_dir(WORKSPACE_ROOT)
        if detected_root:
            discovered_apps.append(detected_root)
        elif WORKSPACE_ROOT != DASHBOARD_ROOT:
            root_id = re.sub(r"[^a-zA-Z0-9_-]", "_", WORKSPACE_ROOT.name.lower()) or "app"
            discovered_apps.append({"id": root_id, "name": WORKSPACE_ROOT.name or "App", "stack": "generic"})

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

    deploy_cfg_file = get_deploy_config_file()
    if not deploy_cfg_file.exists() or deploy_cfg_file.read_text(encoding="utf-8").strip() in ("", "{}", '{"apps": {}}'):
        scanned_apps = {}
        for app in discovered_apps:
            app_id = app["id"]
            scan_res = scan_app_config(app_id)
            if scan_res.get("success"):
                scanned_apps[app_id] = scan_res["discovered"]
        save_deploy_config({"apps": scanned_apps})


def check_system_health() -> dict[str, Any]:
    """Check CLI tools and environment dependencies for pre-flight diagnostics."""
    import shutil
    import subprocess

    def _check_tool(cmd: str, flag: str = "--version") -> dict[str, Any]:
        path = shutil.which(cmd)
        if not path:
            return {"available": False, "path": None, "version": None}
        try:
            res = subprocess.run([cmd, flag], capture_output=True, text=True, timeout=3)
            out = (res.stdout or res.stderr or "").strip().splitlines()
            ver = out[0] if out else "available"
            return {"available": True, "path": path, "version": ver}
        except Exception:
            return {"available": True, "path": path, "version": "available"}

    tools = {
        "python": _check_tool("python3"),
        "git": _check_tool("git"),
        "bash": _check_tool("bash"),
        "flutter": _check_tool("flutter"),
        "xcodebuild": _check_tool("xcodebuild", "-version"),
        "gradle": _check_tool("gradle"),
        "melos": _check_tool("melos"),
    }

    healthy = tools["python"]["available"] and tools["git"]["available"] and tools["bash"]["available"]

    return {
        "success": True,
        "healthy": healthy,
        "workspaceRoot": str(WORKSPACE_ROOT),
        "tools": tools,
    }

