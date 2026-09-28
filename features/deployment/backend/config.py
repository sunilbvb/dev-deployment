import json
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Optional

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
SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


def get_workspace_root() -> Path:
    return WORKSPACE_ROOT


def _get_allowed_workspace_roots() -> list[Path]:
    allowed = [DASHBOARD_ROOT.resolve()]
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


def get_apps_config_file() -> Path:
    target_dir = get_workspace_root() / ".dev-dashboard"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "apps_config.json"
    if not target.exists():
        target.write_text("[]", encoding="utf-8")
    return target


def get_deploy_config_file() -> Path:
    target_dir = get_workspace_root() / ".dev-dashboard"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "deploy_config.json"
    if not target.exists():
        target.write_text("{}", encoding="utf-8")
    return target


def get_commands_config_file() -> Path:
    target_dir = get_workspace_root() / ".dev-dashboard"
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
    if not isinstance(data, dict):
        return {"success": False, "error": "Invalid deploy config format: expected JSON object"}

    apps = data.get("apps", {})
    if not isinstance(apps, dict):
        return {"success": False, "error": "Invalid 'apps' section in deploy config"}

    for app_id, app_cfg in apps.items():
        if not isinstance(app_id, str) or not SAFE_ID_PATTERN.match(app_id):
            return {"success": False, "error": f"Invalid app ID '{app_id}'. Must match ^[A-Za-z0-9._-]+$"}
        if not isinstance(app_cfg, dict):
            continue
        for key, val in app_cfg.items():
            if val is None or val == "":
                continue
            if isinstance(val, str):
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
    android_dir = path / "android"
    ios_dir = path / "ios"
    build_gradle = android_dir / "build.gradle"
    build_gradle_kts = android_dir / "build.gradle.kts"
    xcodeproj = list(path.glob("*.xcodeproj")) or list(ios_dir.glob("*.xcodeproj"))

    # C1: if none of the known project markers exist, this is not a deployable project
    has_pubspec = pubspec.exists()
    has_package_json = package_json.exists()
    has_android = android_dir.is_dir()
    has_ios = ios_dir.is_dir()
    has_native = build_gradle.exists() or build_gradle_kts.exists() or bool(xcodeproj)

    if not (has_pubspec or has_package_json or has_android or has_ios or has_native):
        return None

    stack = "generic"
    app_name = path.name
    version = "1.0.0 (1)"
    is_package = False

    if has_pubspec:
        stack = "flutter"
        try:
            content = pubspec.read_text(encoding="utf-8")
            name_match = re.search(r"^name:\s*(.+)$", content, re.MULTILINE)
            if name_match:
                app_name = name_match.group(1).strip().strip("'\"")
            ver_match = re.search(r"^version:\s*(.+)$", content, re.MULTILINE)
            if ver_match:
                raw_ver = ver_match.group(1).strip().strip("'\"")
                if "+" in raw_ver:
                    v_parts = raw_ver.split("+", 1)
                    version = f"{v_parts[0]} ({v_parts[1]})"
                else:
                    version = raw_ver

            # C2: a Flutter repo is a deployable app only if it has android/, ios/, or lib/main.dart
            # Pure Dart/Flutter packages won't have those (they just have lib/ with no main.dart).
            has_main = (path / "lib" / "main.dart").exists()
            if not (has_android or has_ios or has_main):
                is_package = True
        except Exception:
            logging.exception("Failed to parse pubspec.yaml in %s", path)
    elif has_package_json:
        stack = "react-native" if (has_android or has_ios) else "node"
        try:
            p_data = json.loads(package_json.read_text(encoding="utf-8"))
            if p_data.get("name"):
                app_name = p_data["name"]
            if p_data.get("version"):
                version = p_data["version"]
        except Exception:
            logging.exception("Failed to parse package.json in %s", path)
    elif has_native:
        stack = "native"

    app_id = re.sub(r"[^a-zA-Z0-9_-]", "_", app_name.lower())
    return {
        "id": app_id,
        "name": app_name,
        "path": str(path),
        "version": version,
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


def _resolve_app_dir(app_id: str) -> Path:
    ws_root = get_workspace_root()

    # 1. Check apps_config.json for explicit path
    cfg_file = get_apps_config_file()
    if cfg_file.exists():
        try:
            apps = json.loads(cfg_file.read_text(encoding="utf-8"))
            if isinstance(apps, list):
                for a in apps:
                    if isinstance(a, dict) and a.get("id") == app_id:
                        raw_p = a.get("path")
                        if raw_p:
                            p = Path(raw_p)
                            if not p.is_absolute():
                                p = ws_root / p
                            if p.is_dir():
                                return p.resolve()
        except Exception:
            logging.exception("Failed to read apps_config.json while resolving app dir for %s", app_id)

    # 2. Check standard monorepo folders
    candidates = [
        ws_root / "apps" / app_id,
        ws_root / "packages" / app_id,
        ws_root / app_id,
    ]
    for c in candidates:
        if c.is_dir():
            return c.resolve()

    # 3. Check if workspace root is the app itself
    if (ws_root / "pubspec.yaml").exists() or (ws_root / "package.json").exists() or (ws_root / "android").exists():
        return ws_root.resolve()

    return ws_root.resolve()


def _detect_app_flavors_from_dir(app_dir: Path) -> list[str]:
    flavors = set()
    standard_android_dirs = {"main", "debug", "profile", "release", "test", "androidtest", "common"}

    # 1. Android src folders
    android_src = app_dir / "android" / "app" / "src"
    if android_src.is_dir():
        for item in android_src.iterdir():
            if item.is_dir() and item.name.lower() not in standard_android_dirs:
                flavors.add(item.name.lower())

    # 2. iOS xcconfig / scheme files
    xcconfig_dir = app_dir / "ios" / "Flutter"
    if xcconfig_dir.is_dir():
        known_flavors = ["dev", "qa", "prod", "staging", "uat", "beta", "sandbox"]
        for f in xcconfig_dir.glob("*.xcconfig"):
            stem = f.stem.lower()
            if stem not in ("debug", "release", "generated"):
                for kf in known_flavors:
                    if kf in stem:
                        flavors.add(kf)

    if flavors:
        ordered = ["dev", "qa", "staging", "uat", "sandbox", "beta", "prod"]
        res = [f for f in ordered if f in flavors]
        for f in sorted(flavors):
            if f not in res:
                res.append(f)
        return res

    return []


def _detect_app_flavors(app_id: str) -> list[str]:
    deploy_cfg = load_deploy_config()
    app_cfg = deploy_cfg.get("apps", {}).get(app_id, {})

    custom_flavors = app_cfg.get("flavors")
    if isinstance(custom_flavors, list):
        return [str(f).strip().lower() for f in custom_flavors if str(f).strip()]

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

    app_dir = _resolve_app_dir(app_id)
    return _detect_app_flavors_from_dir(app_dir)


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
        logging.exception("Failed to read saved apps from %s", cfg_file)
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
    raw_path = str(app_data.get("path", "")).strip()

    # Path traversal validation if path is provided
    detected_info = None
    if raw_path:
        cand = Path(raw_path)
        if not cand.is_absolute():
            cand = (get_workspace_root() / cand).resolve()
        else:
            cand = cand.resolve()

        root_res = get_workspace_root().resolve()
        allowed_roots = _get_allowed_workspace_roots()
        is_safe = (cand == root_res or root_res in cand.parents) or any(
            cand == allowed or allowed in cand.parents for allowed in allowed_roots
        )
        if not is_safe:
            return {
                "success": False,
                "error": "Path traversal restriction: App directory must be within workspace root or authorized folders",
            }

        if cand.is_dir():
            detected_info = _detect_app_in_dir(cand)

    if not raw_id:
        if detected_info and detected_info.get("id"):
            raw_id = detected_info["id"]
        elif raw_path:
            raw_id = Path(raw_path).name
        else:
            return {"success": False, "error": "App ID is required"}

    app_id = re.sub(r"[^a-zA-Z0-9_-]", "_", str(raw_id).strip())[:64]
    if not app_id:
        return {"success": False, "error": "Invalid app ID"}

    apps = [a for a in apps if isinstance(a, dict) and a.get("id") != app_id]

    colors = ["#8b5cf6", "#22c55e", "#f97316", "#ec4899", "#14b8a6", "#06b6d4", "#3b82f6"]
    icons = ["user", "package", "briefcase", "users", "leaf", "wallet", "building-2"]

    resolved_name = app_data.get("name") or (detected_info.get("name") if detected_info else None) or app_id.capitalize()
    resolved_version = app_data.get("version") or (detected_info.get("version") if detected_info else None) or "1.0.0 (1)"
    resolved_stack = app_data.get("stack") or (detected_info.get("stack") if detected_info else None) or "generic"

    clean_name = re.sub(r"[<>&\"']", "", str(resolved_name).strip())[:100]
    clean_version = re.sub(r"[<>&\"']", "", str(resolved_version).strip())[:50]

    color_val = str(app_data.get("color", "")).strip()
    if not re.match(r"^#(?:[0-9a-fA-F]{3}){1,2}$", color_val):
        color_val = colors[len(apps) % len(colors)]

    icon_val = str(app_data.get("icon", "")).strip()
    if not re.match(r"^[a-zA-Z0-9_-]+$", icon_val) or len(icon_val) > 32:
        icon_val = icons[len(apps) % len(icons)]

    stack_val = str(resolved_stack).strip().lower()
    if not re.match(r"^[a-zA-Z0-9_-]+$", stack_val) or len(stack_val) > 32:
        stack_val = "generic"

    new_entry = {
        "id": app_id,
        "name": clean_name or app_id,
        "color": color_val,
        "icon": icon_val,
        "version": clean_version or "1.0.0 (1)",
        "stack": stack_val,
        "is_package": detected_info.get("is_package", False) if detected_info else False,
    }
    if raw_path:
        new_entry["path"] = raw_path

    apps.append(new_entry)
    cfg_file.write_text(json.dumps(apps, indent=2), encoding="utf-8")

    # Run auto-scan on this newly registered app
    scan_res = scan_app_config(app_id)
    deploy_cfg = load_deploy_config()
    if "apps" not in deploy_cfg:
        deploy_cfg["apps"] = {}

    app_entry = deploy_cfg["apps"].get(app_id, {})
    if scan_res.get("success") and scan_res.get("discovered"):
        disc = scan_res["discovered"]
        detected_flavors = disc.get("flavors", [])
        if "flavors" not in app_entry:
            app_entry["flavors"] = detected_flavors
        for k, v in disc.items():
            if k != "flavors" and not app_entry.get(k):
                app_entry[k] = v
    else:
        if "flavors" not in app_entry:
            app_entry["flavors"] = []

    deploy_cfg["apps"][app_id] = app_entry
    save_deploy_config(deploy_cfg)

    return {"success": True, "app": new_entry, "discovered": scan_res.get("discovered", {})}


def get_workspaces_list() -> dict[str, Any]:
    workspaces = []
    ws_file = DASHBOARD_ROOT / "config" / "workspaces_list.json"
    if not ws_file.exists():
        ws_file = DASHBOARD_ROOT / "config" / "workspaces_list.example.json"

    if ws_file.exists():
        try:
            workspaces = json.loads(ws_file.read_text(encoding="utf-8"))
        except Exception:
            logging.exception("Failed to load workspaces list from %s", ws_file)

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

    allowed_roots = _get_allowed_workspace_roots()
    if not any(candidate == allowed or allowed in candidate.parents for allowed in allowed_roots):
        return {
            "success": False,
            "error": f"Directory '{new_path}' is not in the allowed workspaces list or authorized folders.",
        }

    WORKSPACE_ROOT = candidate
    os.environ["WORKSPACE_ROOT"] = str(WORKSPACE_ROOT)

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

    discover_workspace_config()
    return {
        "success": True,
        "active": str(WORKSPACE_ROOT),
        "activeName": WORKSPACE_ROOT.name,
    }


def inspect_workspace_path(path_str: str) -> dict[str, Any]:
    if not path_str or not path_str.strip():
        return {"success": False, "error": "No path provided"}

    candidate = Path(path_str.strip())
    if not candidate.is_absolute():
        candidate = (get_workspace_root() / candidate).resolve()
    else:
        candidate = candidate.resolve()

    if not candidate.exists():
        return {"success": False, "error": f"Directory does not exist: {candidate}", "exists": False}
    if not candidate.is_dir():
        return {"success": False, "error": f"Path is not a directory: {candidate}", "exists": False}

    # Path traversal protection check
    root_res = get_workspace_root().resolve()
    allowed_roots = _get_allowed_workspace_roots()
    is_safe = (candidate == root_res or root_res in candidate.parents) or any(
        candidate == allowed or allowed in candidate.parents for allowed in allowed_roots
    )
    if not is_safe:
        return {
            "success": False,
            "error": "Path traversal restriction: Candidate directory must be within workspace root or authorized folders",
            "exists": True,
            "restricted": True,
        }

    detected_app = _detect_app_in_dir(candidate)
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
        if detected_app:
            discovered_apps.append(detected_app)
        else:
            for child in sorted(candidate.iterdir()):
                if child.is_dir() and not child.name.startswith("."):
                    det = _detect_app_in_dir(child)
                    if det and not any(a["id"] == det["id"] for a in discovered_apps):
                        discovered_apps.append(det)

    stacks = list(set(a.get("stack", "generic") for a in discovered_apps))

    return {
        "success": True,
        "exists": True,
        "path": str(candidate),
        "name": candidate.name or "Root",
        "appCount": len(discovered_apps),
        "apps": discovered_apps,
        "detectedApp": detected_app,
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

    # 1. Scan ios/Flutter/*.xcconfig
    xcconfig_dir = app_dir / "ios" / "Flutter"
    if xcconfig_dir.exists():
        for xcconfig in xcconfig_dir.glob("*.xcconfig"):
            name_lower = xcconfig.stem.lower()
            matched_flavor = None
            for key, val in flavor_map.items():
                # Whole-segment match: key must be a standalone word/segment in the filename
                # e.g. "Debug-dev" matches "dev", but "devstudio" does NOT.
                if re.search(r'(^|[._\-])' + re.escape(key) + r'($|[._\-])', name_lower):
                    matched_flavor = val
                    break
            try:
                for line in xcconfig.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("PRODUCT_BUNDLE_IDENTIFIER"):
                        parts = line.split("=", 1)
                        if len(parts) == 2:
                            bundle_id = parts[1].strip().strip(";").strip("'\"")
                            if matched_flavor:
                                result[f"bundle_id_{matched_flavor}"] = bundle_id
                            elif not result.get("bundle_id"):
                                result["bundle_id"] = bundle_id
                                result["bundle_id_prod"] = bundle_id
                            break
            except Exception:
                logging.exception("Failed to parse xcconfig file %s", xcconfig)

    # 2. Scan ios/Runner.xcodeproj/project.pbxproj
    pbx_files = list(app_dir.glob("ios/*.xcodeproj/project.pbxproj")) or list(app_dir.glob("*.xcodeproj/project.pbxproj"))
    for pbx in pbx_files:
        if pbx.exists():
            try:
                content = pbx.read_text(encoding="utf-8")
                matches = re.findall(r'PRODUCT_BUNDLE_IDENTIFIER\s*=\s*([^;]+);', content)
                for raw_bid in matches:
                    bid = raw_bid.strip().strip("'\"")
                    if not bid or "RunnerTests" in bid or bid.startswith("$"):
                        continue
                    bid_lower = bid.lower()
                    matched_flv = None
                    for key, val in flavor_map.items():
                        if f".{key}" in bid_lower or f"-{key}" in bid_lower:
                            matched_flv = val
                            break
                    if matched_flv:
                        result[f"bundle_id_{matched_flv}"] = bid
                    elif not result.get("bundle_id"):
                        result["bundle_id"] = bid
                        result["bundle_id_prod"] = bid
            except Exception:
                logging.exception("Failed to parse pbxproj file %s", pbx)

    # 3. Scan ios/Runner/Info.plist
    info_plist = app_dir / "ios" / "Runner" / "Info.plist"
    if info_plist.exists() and not result.get("bundle_id"):
        try:
            content = info_plist.read_text(encoding="utf-8")
            match = re.search(r'<key>CFBundleIdentifier</key>\s*<string>([^<$]+)</string>', content)
            if match:
                val = match.group(1).strip()
                if val and not val.startswith("$"):
                    result["bundle_id"] = val
                    result["bundle_id_prod"] = val
        except Exception:
            logging.exception("Failed to parse Info.plist %s", info_plist)

    if result.get("bundle_id") and not result.get("bundle_id_prod"):
        result["bundle_id_prod"] = result["bundle_id"]

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
            logging.exception("Failed to parse gradle.properties in %s", app_dir)

    local_props = app_dir / "android" / "local.properties"
    if local_props.exists() and not result:
        try:
            for line in local_props.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                for prop, key in prop_mappings:
                    if line.startswith(f"{prop}="):
                        result[key] = line.split("=", 1)[1].strip()
        except Exception:
            logging.exception("Failed to parse local.properties in %s", app_dir)

    # Scan build.gradle / build.gradle.kts files
    gradle_files = [
        app_dir / "android" / "app" / "build.gradle.kts",
        app_dir / "android" / "app" / "build.gradle",
        app_dir / "android" / "build.gradle.kts",
        app_dir / "android" / "build.gradle",
    ]
    for build_gradle in gradle_files:
        if build_gradle.exists():
            try:
                content = build_gradle.read_text(encoding="utf-8")
                # 1. Look for applicationId (both Groovy and Kotlin DSL with =)
                app_id_matches = list(re.finditer(r'applicationId\s*=?\s*["\']([^"\'\']+)["\']', content))
                for match in app_id_matches:
                    app_id_val = match.group(1).strip()
                    val_lower = app_id_val.lower()

                    def _seg(kw: str) -> bool:
                        """True iff kw is a whole segment in the reverse-domain string."""
                        return bool(re.search(r'(^|[._\-])' + re.escape(kw) + r'($|[._\-])', val_lower))

                    if _seg("dev"):
                        result["android_id_dev"] = app_id_val
                        result["android_package_dev"] = app_id_val
                    elif _seg("staging"):
                        result["android_id_staging"] = app_id_val
                        result["android_package_staging"] = app_id_val
                    elif _seg("uat"):
                        result["android_id_uat"] = app_id_val
                        result["android_package_uat"] = app_id_val
                    elif _seg("qa") or _seg("test"):
                        result["android_id_qa"] = app_id_val
                        result["android_package_qa"] = app_id_val
                    else:
                        result["android_package"] = app_id_val
                        result["android_package_prod"] = app_id_val
                        result["android_id_prod"] = app_id_val

                # 2. Look for namespace as fallback
                if not result.get("android_package") and not result.get("android_id_prod"):
                    ns_match = re.search(r'namespace\s*=?\s*["\']([^"\'\']+)["\']', content)
                    if ns_match:
                        ns_val = ns_match.group(1).strip()
                        result["android_package"] = ns_val
                        result["android_package_prod"] = ns_val
                        result["android_id_prod"] = ns_val
            except Exception:
                logging.exception("Failed to parse gradle file %s", build_gradle)

    # 3. Check AndroidManifest.xml package attribute
    manifest_files = [
        app_dir / "android" / "app" / "src" / "main" / "AndroidManifest.xml",
        app_dir / "android" / "src" / "main" / "AndroidManifest.xml",
    ]
    for mf in manifest_files:
        if mf.exists() and not result.get("android_package"):
            try:
                content = mf.read_text(encoding="utf-8")
                pkg_match = re.search(r'package\s*=\s*["\']([^"\'\']+)["\']', content)
                if pkg_match:
                    pkg_val = pkg_match.group(1).strip()
                    result["android_package"] = pkg_val
                    result["android_package_prod"] = pkg_val
                    result["android_id_prod"] = pkg_val
            except Exception:
                logging.exception("Failed to parse AndroidManifest.xml %s", mf)

    if result.get("android_package") and not result.get("android_package_prod"):
        result["android_package_prod"] = result["android_package"]
    if result.get("android_package") and not result.get("android_id_prod"):
        result["android_id_prod"] = result["android_package"]

    return result


def _scan_credentials(discovered: dict[str, Any], app_id: str, app_dir: Path) -> None:
    ws_root = get_workspace_root()

    def _rel(p: Path) -> str:
        try:
            return str(p.relative_to(ws_root))
        except ValueError:
            return str(p)

    # 1. Android google-services.json
    android_search_dirs = [
        app_dir / "android" / "app",
        app_dir / "android",
        app_dir / "private_keys",
        ws_root / "private_keys" / "Firebase",
        ws_root / "private_keys",
        app_dir / "firebase",
    ]
    for sdir in android_search_dirs:
        if sdir.is_dir():
            for path in sdir.rglob("google-services.json"):
                rel_path = _rel(path)
                full_lower = str(path).lower()
                if "/dev/" in full_lower:
                    discovered["google_services_json_dev"] = rel_path
                elif "/qa/" in full_lower or "/test/" in full_lower:
                    discovered["google_services_json_qa"] = rel_path
                elif "/staging/" in full_lower:
                    discovered["google_services_json_staging"] = rel_path
                elif "/prod/" in full_lower or "/production/" in full_lower:
                    discovered["google_services_json_prod"] = rel_path
                    if not discovered.get("google_services_json"):
                        discovered["google_services_json"] = rel_path
                else:
                    if not discovered.get("google_services_json"):
                        discovered["google_services_json"] = rel_path
                    if not discovered.get("google_services_json_prod"):
                        discovered["google_services_json_prod"] = rel_path

    # 2. iOS GoogleService-Info.plist
    ios_search_dirs = [
        app_dir / "ios" / "Runner",
        app_dir / "ios",
        app_dir / "private_keys",
        ws_root / "private_keys" / "Firebase",
        ws_root / "private_keys",
        app_dir / "firebase",
    ]
    for sdir in ios_search_dirs:
        if sdir.is_dir():
            for path in sdir.rglob("*GoogleService-Info.plist"):
                rel_path = _rel(path)
                full_lower = str(path).lower()
                if "dev" in full_lower:
                    discovered["google_service_info_plist_dev"] = rel_path
                elif "qa" in full_lower or "test" in full_lower:
                    discovered["google_service_info_plist_qa"] = rel_path
                elif "staging" in full_lower:
                    discovered["google_service_info_plist_staging"] = rel_path
                elif "prod" in full_lower:
                    discovered["google_service_info_plist_prod"] = rel_path
                    if not discovered.get("google_service_info_plist"):
                        discovered["google_service_info_plist"] = rel_path
                else:
                    if not discovered.get("google_service_info_plist"):
                        discovered["google_service_info_plist"] = rel_path
                    if not discovered.get("google_service_info_plist_prod"):
                        discovered["google_service_info_plist_prod"] = rel_path

    # 3. Google Play Service Account JSON
    gplay_search_dirs = [
        ws_root / "private_keys",
        app_dir / "private_keys",
        ws_root / "config",
    ]
    for sdir in gplay_search_dirs:
        if sdir.is_dir():
            for pattern in ("*service-account*.json", "*play*.json", "*gplay*.json", "*google-play*.json"):
                for path in sdir.glob(pattern):
                    if path.is_file() and not path.name.startswith("google-services"):
                        discovered["play_service_account_path"] = _rel(path)
                        break
                if discovered.get("play_service_account_path"):
                    break
        if discovered.get("play_service_account_path"):
            break


def scan_app_config(app_id: str) -> dict[str, Any]:
    app_dir = _resolve_app_dir(app_id)
    discovered: dict[str, Any] = {}
    discovered.update(_scan_xcconfig_bundle_ids(app_dir))
    discovered.update(_scan_android_app_ids(app_dir))
    _scan_credentials(discovered, app_id, app_dir)
    detected_flavors = _detect_app_flavors_from_dir(app_dir)
    discovered["flavors"] = detected_flavors
    return {
        "success": True,
        "discovered": discovered,
        "app_id": app_id,
        "app_path": str(app_dir),
        "has_flavors": len(detected_flavors) > 0,
    }


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
            detected_flavors = disc.get("flavors", [])
            if "flavors" not in app_entry:
                app_entry["flavors"] = detected_flavors
            for k, v in disc.items():
                if k != "flavors" and not app_entry.get(k):
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
            logging.exception("Failed to read existing apps configuration from %s", apps_file)

    existing_cmds = []
    if cmds_file.exists():
        try:
            existing_cmds = json.loads(cmds_file.read_text(encoding="utf-8"))
        except Exception:
            logging.exception("Failed to read existing commands configuration from %s", cmds_file)

    if existing_apps and existing_cmds:
        return

    discovered_apps = []
    ws_root = get_workspace_root()
    search_folders = _parse_melos_config(ws_root)
    for folder_name in search_folders:
        sub_dir = ws_root / folder_name
        if sub_dir.is_dir():
            for child in sorted(sub_dir.iterdir()):
                if child.is_dir() and not child.name.startswith("."):
                    detected = _detect_app_in_dir(child)
                    if detected and not any(a["id"] == detected["id"] for a in discovered_apps):
                        discovered_apps.append(detected)

    if not discovered_apps:
        detected_root = _detect_app_in_dir(ws_root)
        if detected_root:
            discovered_apps.append(detected_root)
        elif ws_root != DASHBOARD_ROOT:
            root_id = re.sub(r"[^a-zA-Z0-9_-]", "_", ws_root.name.lower()) or "app"
            discovered_apps.append({
                "id": root_id,
                "name": ws_root.name or "App",
                "path": str(ws_root),
                "stack": "generic",
            })

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
                "version": app.get("version", "1.0.0 (1)"),
                "stack": app.get("stack", "generic"),
                "is_package": app.get("is_package", False),
                "path": app.get("path", str(ws_root)),
            })
        apps_file.write_text(json.dumps(new_apps, indent=2), encoding="utf-8")

    deploy_cfg_file = get_deploy_config_file()
    if not deploy_cfg_file.exists() or deploy_cfg_file.read_text(encoding="utf-8").strip() in ("", "{}", '{"apps": {}}'):
        scanned_apps = {}
        for app in discovered_apps:
            app_id = app["id"]
            scan_res = scan_app_config(app_id)
            if scan_res.get("success"):
                disc = scan_res["discovered"]
                app_entry = dict(disc)
                scanned_apps[app_id] = app_entry
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
        "workspaceRoot": str(get_workspace_root()),
        "tools": tools,
    }


