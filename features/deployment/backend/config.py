import contextvars
import fnmatch
import json
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Optional

import picker

FEATURE_DIR = Path(__file__).resolve().parents[1]
DASHBOARD_ROOT = FEATURE_DIR.parents[1]

# C12: Track if configured workspace root was missing on disk
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

# C9: ContextVar to allow request-scoped workspace without overriding other tabs
_REQUEST_WORKSPACE: contextvars.ContextVar[Optional[Path]] = contextvars.ContextVar("request_workspace", default=None)


def set_request_workspace(ws: Optional[Path]) -> contextvars.Token:
    return _REQUEST_WORKSPACE.set(ws)


def reset_request_workspace(token: contextvars.Token) -> None:
    _REQUEST_WORKSPACE.reset(token)


def get_workspace_root() -> Path:
    req_ws = _REQUEST_WORKSPACE.get()
    if req_ws is not None:
        return req_ws
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


def _ensure_gitignore_has_dashboard(ws_root: Path) -> None:
    """B7 fix: auto-add .dev-dashboard/ to .gitignore in the user's workspace."""
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


def get_apps_config_file() -> Path:
    ws_root = get_workspace_root()
    _ensure_gitignore_has_dashboard(ws_root)
    target_dir = ws_root / ".dev-dashboard"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "apps_config.json"
    if not target.exists():
        target.write_text("[]", encoding="utf-8")
    return target


def get_deploy_config_file() -> Path:
    ws_root = get_workspace_root()
    _ensure_gitignore_has_dashboard(ws_root)
    target_dir = ws_root / ".dev-dashboard"
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

    # 1. Read real productFlavors from build.gradle / build.gradle.kts (B5 fix)
    # Only fall back to src/ folder scanning if productFlavors block is absent.
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
            # Extract productFlavors { ... } with balanced braces
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
                    # Find all flavor names: identifier followed by { or (
                    # e.g. 'dev {', 'staging {', 'create("prod") {'
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

    # 2. iOS xcconfig stem matching — whole-segment regex (B6 fix, consistent with _scan_xcconfig_bundle_ids)
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


def scan_app_config(app_id: str, *, force: bool = False) -> dict[str, Any]:
    """Scan app project files for config.

    Args:
        app_id: The app identifier.
        force: When True, all discovered values are returned even if the app
               already has values saved — letting the caller decide what to overwrite.
    """
    app_dir = _resolve_app_dir(app_id)
    discovered: dict[str, Any] = {}
    discovered.update(_scan_xcconfig_bundle_ids(app_dir))
    discovered.update(_scan_android_app_ids(app_dir))
    _scan_credentials(discovered, app_id, app_dir)
    detected_flavors = _detect_app_flavors_from_dir(app_dir)
    discovered["flavors"] = detected_flavors

    # Build diff vs current saved config (B3 fix: show what changed)
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
    """Scan all apps in the workspace.

    Args:
        force: When True, overwrite all existing values (not just empty ones) — B3 fix.
    """
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
                # B3: overwrite everything including existing values
                if detected_flavors:
                    app_entry["flavors"] = detected_flavors
                for k, v in disc.items():
                    if k != "flavors":
                        app_entry[k] = v
            else:
                # Original behaviour: only fill empty slots
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
    """B4 fix: force a full re-discovery of the workspace.

    Clears the apps and commands config files so discover_workspace_config()
    runs again, then scans all found apps. Returns the apps that were found.
    """
    apps_file = get_apps_config_file()
    cmds_file = get_commands_config_file()

    # Reset discovery cache
    try:
        apps_file.write_text("[]", encoding="utf-8")
        cmds_file.write_text("[]", encoding="utf-8")
    except Exception as exc:
        return {"success": False, "error": f"Could not reset workspace cache: {exc}"}

    # Re-run discovery
    discover_workspace_config()

    # Auto-scan all discovered apps (force=False so existing manual values survive)
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


def allow_workspace(path_str: str) -> dict[str, Any]:
    """C10 fix: add a workspace folder to workspaces_list.json without requiring a manual JSON edit.

    The path must exist as a directory. No constraint on its location — the user is
    explicitly granting permission by clicking 'Allow this folder'.
    """
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


