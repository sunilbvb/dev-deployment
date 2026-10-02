"""Backend configuration modules package.

Deconstructs monolithic config logic into single-responsibility submodules:
- workspace: Path resolution, request-scoped context, allowed workspace management
- storage: Apps, commands, and deploy config file persistence and template loading
- discovery: Monorepo scanning, Melos parsing, app path resolution, flavor detection
- scanner: Xcode/Android project inspection, credential discovery, system health diagnostics
"""

from .workspace import (
    DASHBOARD_ROOT,
    FEATURE_DIR,
    SAFE_ID_PATTERN,
    TEMPLATES_FILE,
    TMP_DIR,
    WORKSPACE_MISSING,
    WORKSPACE_ROOT,
    _ensure_gitignore_has_dashboard,
    _get_allowed_workspace_roots,
    _resolve_workspace_root,
    allow_workspace,
    get_workspace_root,
    get_workspaces_list,
    remove_workspace,
    reset_request_workspace,
    set_active_workspace,
    set_request_workspace,
)
from .storage import (
    get_apps_config_file,
    get_commands_config_file,
    get_deploy_config_file,
    load_deploy_config,
    load_templates,
    save_deploy_config,
)
from .discovery import (
    MANIFEST_FILES,
    MAX_SCAN_DEPTH,
    PROJECT_INTERNAL_DIRS,
    SKIP_DIR_NAMES,
    _describe_layout,
    _detect_app_flavors,
    _detect_app_flavors_from_dir,
    _detect_app_in_dir,
    _discover_apps_in_workspace,
    _has_manifest,
    _is_flutter_plugin,
    _parse_melos_config,
    _parse_yaml_list_field,
    _resolve_app_dir,
    add_app,
    get_apps,
    inspect_workspace_path,
)
from .scanner import (
    _scan_android_app_ids,
    _scan_credentials,
    _scan_xcconfig_bundle_ids,
    check_system_health,
    discover_workspace_config,
    rescan_workspace,
    scan_all_apps_config,
    scan_app_config,
)

__all__ = [
    # workspace
    "DASHBOARD_ROOT",
    "FEATURE_DIR",
    "SAFE_ID_PATTERN",
    "TEMPLATES_FILE",
    "TMP_DIR",
    "WORKSPACE_MISSING",
    "WORKSPACE_ROOT",
    "_ensure_gitignore_has_dashboard",
    "_get_allowed_workspace_roots",
    "_resolve_workspace_root",
    "allow_workspace",
    "get_workspace_root",
    "get_workspaces_list",
    "remove_workspace",
    "reset_request_workspace",
    "set_active_workspace",
    "set_request_workspace",
    # storage
    "get_apps_config_file",
    "get_commands_config_file",
    "get_deploy_config_file",
    "load_deploy_config",
    "load_templates",
    "save_deploy_config",
    # discovery
    "MANIFEST_FILES",
    "MAX_SCAN_DEPTH",
    "PROJECT_INTERNAL_DIRS",
    "SKIP_DIR_NAMES",
    "_describe_layout",
    "_detect_app_flavors",
    "_detect_app_flavors_from_dir",
    "_detect_app_in_dir",
    "_discover_apps_in_workspace",
    "_has_manifest",
    "_is_flutter_plugin",
    "_parse_melos_config",
    "_parse_yaml_list_field",
    "_resolve_app_dir",
    "add_app",
    "get_apps",
    "inspect_workspace_path",
    # scanner
    "_scan_android_app_ids",
    "_scan_credentials",
    "_scan_xcconfig_bundle_ids",
    "check_system_health",
    "discover_workspace_config",
    "rescan_workspace",
    "scan_all_apps_config",
    "scan_app_config",
]
