import fnmatch
import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

try:
    from .workspace import _get_allowed_workspace_roots, get_workspace_root
    from .storage import get_apps_config_file, load_deploy_config, save_deploy_config
except (ImportError, ValueError):
    from config_modules.workspace import _get_allowed_workspace_roots, get_workspace_root
    from config_modules.storage import get_apps_config_file, load_deploy_config, save_deploy_config

try:
    import picker
except ImportError:
    from .. import picker


def _is_flutter_plugin(pubspec_text: str) -> bool:
    in_flutter = False
    for line in pubspec_text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line[0].isspace():
            in_flutter = line.rstrip() == "flutter:"
        elif in_flutter and line.strip() == "plugin:":
            return True
    return False


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

    # If none of the known project markers exist, this is not a deployable project
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

            # Plugins ship android/ and ios/ folders but are packages, not apps.
            is_plugin = _is_flutter_plugin(content)
            has_entrypoint = any((path / "lib").glob("main*.dart"))
            if is_plugin or not (has_android or has_ios or has_entrypoint):
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

    # Folder names are stabler than package names, so saved configs keep matching.
    app_id = re.sub(r"[^a-zA-Z0-9_-]", "_", path.name.lower())
    return {
        "id": app_id,
        "name": app_name,
        "path": str(path),
        "version": version,
        "stack": stack,
        "is_package": is_package,
    }


def _parse_yaml_list_field(content: str, field_name: str) -> list[str]:
    """Parse list items from a YAML string for a given field key."""
    items: list[str] = []
    inline_match = re.search(rf'^\s*{field_name}\s*:\s*\[(.*?)\]', content, re.MULTILINE | re.DOTALL)
    if inline_match:
        for raw in inline_match.group(1).split(","):
            cleaned = raw.strip().strip("'\"")
            if cleaned:
                items.append(cleaned)
        return items

    lines = content.splitlines()
    in_section = False
    base_indent = 0
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        header_match = re.match(rf'^(\s*){field_name}\s*:\s*$', line)
        if header_match:
            in_section = True
            base_indent = len(header_match.group(1))
            continue
        if in_section:
            current_indent = len(line) - len(line.lstrip())
            if current_indent <= base_indent and not line.lstrip().startswith("-"):
                break
            if stripped.startswith("-"):
                val = stripped.lstrip("-").strip().strip("'\"")
                if val:
                    items.append(val)
            elif current_indent <= base_indent:
                break
    return items


SKIP_DIR_NAMES = {
    ".git", ".dart_tool", "build", "dist", "node_modules", "Pods",
    ".idea", ".vscode", ".dev-dashboard", ".gradle", "ios/Pods",
    "target", ".bundle", "example", "examples", ".symlinks", "ephemeral",
}

# Folders inside a project that never contain sibling projects worth deploying.
PROJECT_INTERNAL_DIRS = {
    "android", "ios", "macos", "linux", "windows", "web", "lib", "test",
    "integration_test", "test_driver", "assets", "fonts", "bin", "src",
}

MAX_SCAN_DEPTH = 4
MANIFEST_FILES = ("pubspec.yaml", "package.json")


def _has_manifest(path: Path) -> bool:
    return any((path / m).is_file() for m in MANIFEST_FILES)


def _discover_apps_in_workspace(candidate: Path) -> tuple[list[dict[str, Any]], bool, bool]:
    """Discover apps and packages under a workspace root.

    Handles Melos (melos.yaml or `melos:` in pubspec), Dart pub workspaces,
    a single project at the root (optionally with local packages), and plain
    folders holding several projects with or without shared packages.
    """
    has_melos = False
    is_workspace_root = False
    package_globs: list[str] = []
    ignore_globs: list[str] = []

    melos_file = candidate / "melos.yaml"
    if melos_file.exists():
        has_melos = True
        is_workspace_root = True
        try:
            m_text = melos_file.read_text(encoding="utf-8", errors="replace")
            package_globs.extend(_parse_yaml_list_field(m_text, "packages"))
            ignore_globs.extend(_parse_yaml_list_field(m_text, "ignore"))
        except Exception:
            logging.exception("Failed to parse melos.yaml in %s", candidate)

    pubspec_file = candidate / "pubspec.yaml"
    if pubspec_file.exists():
        try:
            p_text = pubspec_file.read_text(encoding="utf-8", errors="replace")
            if re.search(r"^melos:", p_text, re.MULTILINE):
                has_melos = True
                is_workspace_root = True
            ws_entries = _parse_yaml_list_field(p_text, "workspace")
            if ws_entries:
                is_workspace_root = True
                package_globs.extend(ws_entries)
        except Exception:
            logging.exception("Failed to parse pubspec.yaml in %s", candidate)

    def _is_ignored(rel_p: Path) -> bool:
        rel_str = str(rel_p).replace("\\", "/")
        for ign in ignore_globs:
            ign_clean = ign.rstrip("/")
            if (
                fnmatch.fnmatch(rel_str, ign_clean)
                or fnmatch.fnmatch(rel_str + "/", ign_clean + "/")
                or fnmatch.fnmatch(rel_p.name, ign_clean)
            ):
                return True
        return False

    def _is_skipped_path(rel_p: Path) -> bool:
        return any(part in SKIP_DIR_NAMES or part.startswith(".") for part in rel_p.parts)

    found_dirs: list[Path] = []

    def _add(path: Path) -> None:
        if path in found_dirs or path == candidate:
            return
        rel = path.relative_to(candidate)
        if _is_skipped_path(rel) or _is_ignored(rel):
            return
        found_dirs.append(path)

    # Explicit membership lists (melos packages / pub workspace) win when present.
    for glob_pat in package_globs:
        clean_glob = glob_pat.strip().strip("'\"").rstrip("/")
        if not clean_glob:
            continue
        direct_p = candidate / clean_glob
        if direct_p.is_dir():
            if _has_manifest(direct_p):
                _add(direct_p)
            continue
        try:
            for matched in sorted(candidate.glob(clean_glob)):
                if matched.is_dir() and _has_manifest(matched):
                    _add(matched)
        except Exception:
            logging.exception("Failed globbing %s in %s", clean_glob, candidate)

    # Otherwise walk the tree: every folder with a manifest is a project.
    if not found_dirs:
        queue: list[tuple[Path, int]] = [(candidate, 0)]
        while queue:
            curr_dir, depth = queue.pop(0)
            curr_is_project = _has_manifest(curr_dir)
            if curr_dir != candidate and curr_is_project:
                _add(curr_dir)
            elif curr_dir != candidate and depth > 0 and _detect_app_in_dir(curr_dir) is not None:
                # Native-only project (no manifest, e.g. bare Xcode/Gradle app).
                _add(curr_dir)
                continue
            if depth >= MAX_SCAN_DEPTH:
                continue
            try:
                children = sorted(curr_dir.iterdir())
            except OSError:
                continue
            for child in children:
                if not child.is_dir() or child.name in SKIP_DIR_NAMES or child.name.startswith("."):
                    continue
                if curr_is_project and child.name in PROJECT_INTERNAL_DIRS:
                    continue
                queue.append((child, depth + 1))

    discovered_apps: list[dict[str, Any]] = []
    for d in found_dirs:
        det = _detect_app_in_dir(d)
        if det is not None:
            discovered_apps.append(det)

    # The root is itself a project unless it only aggregates members.
    if not is_workspace_root:
        root_det = _detect_app_in_dir(candidate)
        if root_det is not None and (not root_det["is_package"] or not discovered_apps):
            discovered_apps.insert(0, root_det)

    discovered_apps.sort(key=lambda a: a["is_package"])

    seen_ids: dict[str, int] = {}
    for app in discovered_apps:
        orig_id = app["id"]
        if orig_id in seen_ids:
            seen_ids[orig_id] += 1
            app_p = Path(app["path"])
            try:
                rel = app_p.relative_to(candidate)
                parent_name = re.sub(r"[^a-zA-Z0-9_-]", "_", rel.parent.name.lower())
                if parent_name and parent_name != ".":
                    new_id = f"{orig_id}_{parent_name}"
                else:
                    new_id = f"{orig_id}_{seen_ids[orig_id]}"
                app["name"] = f"{app['name']} ({rel.parent})"
            except Exception:
                new_id = f"{orig_id}_{seen_ids[orig_id]}"
            app["id"] = new_id
        else:
            seen_ids[orig_id] = 1

    is_monorepo = is_workspace_root or len(discovered_apps) > 1
    return discovered_apps, is_monorepo, has_melos


def _parse_melos_config(root_dir: Path) -> list[str]:
    """Compatibility helper returning top-level folder names from melos config."""
    apps, _, _ = _discover_apps_in_workspace(root_dir)
    folders = []
    for a in apps:
        p = Path(a["path"])
        try:
            rel = p.relative_to(root_dir)
            top = rel.parts[0] if rel.parts else ""
            if top and top not in folders:
                folders.append(top)
        except ValueError:
            pass
    return folders or ["apps"]


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
    flavors: set[str] = set()
    known_flavor_names = {"dev", "qa", "staging", "uat", "sandbox", "beta", "prod"}
    standard_android_dirs = {"main", "debug", "profile", "release", "test", "androidtest", "common"}

    # 1. Read real productFlavors from build.gradle / build.gradle.kts
    gradle_files = [
        app_dir / "android" / "app" / "build.gradle.kts",
        app_dir / "android" / "app" / "build.gradle",
    ]
    found_gradle_flavors = False
    for gradle_file in gradle_files:
        if not gradle_file.exists():
            continue
        try:
            content = gradle_file.read_text(encoding="utf-8")
            idx = content.find("productFlavors")
            if idx != -1:
                brace_start = content.find("{", idx)
                if brace_start != -1:
                    depth = 1
                    pos = brace_start + 1
                    while pos < len(content) and depth > 0:
                        if content[pos] == "{":
                            depth += 1
                        elif content[pos] == "}":
                            depth -= 1
                        pos += 1
                    block = content[brace_start + 1 : pos - 1]
                    found_gradle_flavors = True
                    for name in re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*[\{]', block):
                        if name.lower() not in standard_android_dirs:
                            flavors.add(name.lower())
                    for name in re.findall(r'create\s*\(\s*["\']([^"\']+)["\']', block):
                        if name.lower() not in standard_android_dirs:
                            flavors.add(name.lower())
                    if flavors:
                        break
        except Exception:
            logging.exception("Failed to parse gradle file for productFlavors: %s", gradle_file)

    # Fallback: scan android/app/src/ subfolders only if productFlavors not found in gradle
    if not found_gradle_flavors:
        android_src = app_dir / "android" / "app" / "src"
        if android_src.is_dir():
            for item in android_src.iterdir():
                if item.is_dir() and item.name.lower() not in standard_android_dirs:
                    flavors.add(item.name.lower())

    # 2. iOS xcconfig stem matching
    xcconfig_dir = app_dir / "ios" / "Flutter"
    if xcconfig_dir.is_dir():
        for f in xcconfig_dir.glob("*.xcconfig"):
            stem = f.stem.lower()
            if stem in ("debug", "release", "generated"):
                continue
            for kf in known_flavor_names:
                if re.search(r'(^|[._\-])' + re.escape(kf) + r'($|[._\-])', stem):
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
    try:
        from .scanner import discover_workspace_config
    except (ImportError, ValueError):
        from config_modules.scanner import discover_workspace_config
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
    try:
        from .scanner import scan_app_config
    except (ImportError, ValueError):
        from config_modules.scanner import scan_app_config
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


def _describe_layout(root: Path, apps: list[dict[str, Any]], packages: list[dict[str, Any]], has_melos: bool) -> str:
    """Human-readable name for how the workspace is organised."""
    root_is_app = any(Path(a["path"]) == root for a in apps)
    pubspec = root / "pubspec.yaml"
    pub_workspace = pubspec.exists() and bool(_parse_yaml_list_field(
        pubspec.read_text(encoding="utf-8", errors="replace"), "workspace"))
    if has_melos:
        return "Melos monorepo (apps + packages)"
    if pub_workspace:
        return "Dart pub workspace (apps + packages, no Melos)"
    if root_is_app and len(apps) == 1:
        return "Single app with local packages" if packages else "Single app"
    if packages:
        return "Multiple apps with shared packages (no Melos)"
    if apps:
        return "Multiple apps (no packages, no Melos)"
    return "No apps found"


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
    ) or picker.was_picked(candidate)
    if not is_safe:
        return {
            "success": False,
            "error": "Path traversal restriction: Candidate directory must be within workspace root or authorized folders",
            "exists": True,
            "restricted": True,
        }

    discovered_apps, is_monorepo, has_melos = _discover_apps_in_workspace(candidate)
    detected_app = _detect_app_in_dir(candidate)
    stacks = list(set(a.get("stack", "generic") for a in discovered_apps))
    apps = [a for a in discovered_apps if not a.get("is_package")]
    packages = [a for a in discovered_apps if a.get("is_package")]

    return {
        "success": True,
        "exists": True,
        "path": str(candidate),
        "name": candidate.name or "Root",
        "appCount": len(apps),
        "packageCount": len(packages),
        "apps": discovered_apps,
        "detectedApp": detected_app,
        "stacks": stacks,
        "isMonorepo": is_monorepo,
        "hasMelos": has_melos,
        "layout": _describe_layout(candidate, apps, packages, has_melos),
    }
