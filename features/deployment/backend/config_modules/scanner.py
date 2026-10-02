import json
import logging
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

try:
    from .workspace import get_workspace_root
    from .storage import (
        get_apps_config_file,
        get_commands_config_file,
        get_deploy_config_file,
        load_deploy_config,
        save_deploy_config,
    )
    from .discovery import (
        _detect_app_flavors_from_dir,
        _discover_apps_in_workspace,
        _resolve_app_dir,
    )
except (ImportError, ValueError):
    from config_modules.workspace import get_workspace_root
    from config_modules.storage import (
        get_apps_config_file,
        get_commands_config_file,
        get_deploy_config_file,
        load_deploy_config,
        save_deploy_config,
    )
    from config_modules.discovery import (
        _detect_app_flavors_from_dir,
        _discover_apps_in_workspace,
        _resolve_app_dir,
    )


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
                app_id_matches = list(re.finditer(r'applicationId\s*=?\s*["\']([^"\'\']+)["\']', content))
                for match in app_id_matches:
                    app_id_val = match.group(1).strip()
                    val_lower = app_id_val.lower()

                    def _seg(kw: str) -> bool:
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

                if not result.get("android_package") and not result.get("android_id_prod"):
                    ns_match = re.search(r'namespace\s*=?\s*["\']([^"\'\']+)["\']', content)
                    if ns_match:
                        ns_val = ns_match.group(1).strip()
                        result["android_package"] = ns_val
                        result["android_package_prod"] = ns_val
                        result["android_id_prod"] = ns_val
            except Exception:
                logging.exception("Failed to parse gradle file %s", build_gradle)

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


def scan_app_config(app_id: str, *, force: bool = False) -> dict[str, Any]:
    """Scan app project files for config."""
    app_dir = _resolve_app_dir(app_id)
    discovered: dict[str, Any] = {}
    discovered.update(_scan_xcconfig_bundle_ids(app_dir))
    discovered.update(_scan_android_app_ids(app_dir))
    _scan_credentials(discovered, app_id, app_dir)
    detected_flavors = _detect_app_flavors_from_dir(app_dir)
    discovered["flavors"] = detected_flavors

    # Build diff vs current saved config
    existing_cfg = load_deploy_config().get("apps", {}).get(app_id, {})
    diff: dict[str, dict[str, Any]] = {}
    for k, new_val in discovered.items():
        old_val = existing_cfg.get(k)
        if old_val != new_val:
            diff[k] = {"old": old_val, "new": new_val}

    return {
        "success": True,
        "discovered": discovered,
        "diff": diff,
        "app_id": app_id,
        "app_path": str(app_dir),
        "has_flavors": len(detected_flavors) > 0,
        "force": force,
    }


def scan_all_apps_config(*, force: bool = False) -> dict[str, Any]:
    """Scan all apps in the workspace."""
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
    all_diffs: dict[str, Any] = {}

    for app in apps:
        app_id = app["id"]
        res = scan_app_config(app_id, force=force)
        if res.get("success") and res.get("discovered"):
            disc = res["discovered"]
            app_entry = existing_apps_cfg.get(app_id, {})
            detected_flavors = disc.get("flavors", [])

            if force:
                if detected_flavors:
                    app_entry["flavors"] = detected_flavors
                for k, v in disc.items():
                    if k != "flavors":
                        app_entry[k] = v
            else:
                if "flavors" not in app_entry:
                    app_entry["flavors"] = detected_flavors
                for k, v in disc.items():
                    if k != "flavors" and not app_entry.get(k):
                        app_entry[k] = v

            existing_apps_cfg[app_id] = app_entry
            scanned_count += 1
            if res.get("diff"):
                all_diffs[app_id] = res["diff"]

    save_deploy_config({"apps": existing_apps_cfg})
    return {"success": True, "count": scanned_count, "total": len(apps), "diffs": all_diffs}


def rescan_workspace() -> dict[str, Any]:
    """Force a full re-discovery of the workspace."""
    apps_file = get_apps_config_file()
    cmds_file = get_commands_config_file()

    try:
        apps_file.write_text("[]", encoding="utf-8")
        cmds_file.write_text("[]", encoding="utf-8")
    except Exception as exc:
        return {"success": False, "error": f"Could not reset workspace cache: {exc}"}

    discover_workspace_config()

    try:
        saved_apps = json.loads(apps_file.read_text(encoding="utf-8"))
    except Exception:
        saved_apps = []

    scan_result = scan_all_apps_config()
    return {
        "success": True,
        "apps": saved_apps,
        "scanned": scan_result.get("count", 0),
        "total": scan_result.get("total", 0),
    }


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

    ws_root = get_workspace_root()
    discovered_apps, is_monorepo, has_melos = _discover_apps_in_workspace(ws_root)

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
