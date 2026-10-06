import shlex
from typing import Any, Optional

from credentials import _apple_from_env_files
from credentials import job_env as credentials_job_env

from config import (
    DASHBOARD_ROOT,
    _detect_app_flavors,
    _resolve_app_dir,
    discover_workspace_config,
    get_workspace_root,
    load_deploy_config,
    load_templates,
)

ACTION_MAP = {
    # Only actions implemented as run_build.sh functions belong here; anything else
    # (e.g. build_apk, clean, pub_get) runs its direct command_template.
    "build_ipa": "buildIPA",
    "deploy_ipa": "deployIPA",
    "upload_ipa": "uploadIPA",
    "build_aab": "buildAAB",
    "deploy_aab": "deployAAB",
    "upload_aab": "uploadAAB",
    "deploy_both": "deployBothPlatforms",
    "release_preview": "releasePreview",
    "release_tag": "releaseTag",
    "release_push": "releasePush",
    "release_changelog": "releaseChangelog",
    "release_commit": "releaseCommit",
    "release_bump_patch": "releaseBumpPatch",
    "release_bump_minor": "releaseBumpMinor",
    "release_bump_major": "releaseBumpMajor",
    "release_store_notes": "releaseStoreNotes",
    "release_verify": "releaseVerify",
    "release_status": "releaseStatus",
    "release_undo": "releaseUndo",
}

STORE_UPLOAD_TEMPLATE_IDS = {"upload_ipa", "upload_aab", "deploy_ipa", "deploy_aab", "deploy_both"}
_STORE_SHIPPING_ACTIONS = {"deployIPA", "uploadIPA", "deployAAB", "uploadAAB", "deployBothPlatforms"}
_STORE_SHIPPING_ACTIONS_LOWER = {act.lower() for act in _STORE_SHIPPING_ACTIONS}


def _resolve_command(template: str, app_id: str, flavor: str, deploy_cfg: dict[str, Any]) -> str:
    app_cfg = deploy_cfg.get("apps", {}).get(app_id, {})
    bundle_id = (
        app_cfg.get(f"bundle_id_{flavor}")
        or app_cfg.get("bundle_id")
        or app_cfg.get("bundle_id_prod", f"com.example.{app_id}")
    )
    android_package = (
        app_cfg.get(f"android_package_{flavor}")
        or app_cfg.get("android_package")
        or app_cfg.get("android_package_prod", f"com.example.{app_id}")
    )
    apple_id = app_cfg.get("apple_id", "")

    # Security: wrap all substituted values in shlex.quote to prevent command injection
    safe_bundle_id = shlex.quote(str(bundle_id))
    safe_android_package = shlex.quote(str(android_package))
    safe_apple_id = shlex.quote(str(apple_id))
    safe_app_id = shlex.quote(str(app_id))
    safe_flavor = shlex.quote(str(flavor))

    if flavor in ("any", "none", "default"):
        res = (
            template
            .replace("--flavor {flavor}", "")
            .replace("-flavor {flavor}", "")
            .replace("{flavor}Release", "release")
            .replace("{flavor}release", "release")
            .replace("-{flavor}-", "-")
            .replace("_{flavor}_", "_")
            .replace("/{flavor}/", "/")
            .replace("{flavor}", "")
            .strip()
        )
    else:
        res = template.replace("{flavor}", safe_flavor)

    return (
        res
        .replace("{bundle_id}", safe_bundle_id)
        .replace("{android_package}", safe_android_package)
        .replace("{apple_id}", safe_apple_id)
        .replace("{app_id}", safe_app_id)
    )


def _build_commands_from_templates(app_id: str, app_path_prefix: str, use_melos: bool, flavors: list[str], deploy_cfg: Optional[dict[str, Any]] = None, app_stack: str = "") -> list[dict[str, Any]]:
    templates = load_templates()
    if deploy_cfg is None:
        deploy_cfg = load_deploy_config()
    commands: list[dict[str, Any]] = []

    target_flavors = flavors if flavors else ["default"]
    stack_lower = app_stack.strip().lower()

    for platform, tmpl_list in templates.items():
        for tmpl in tmpl_list:
            # C11: skip templates that don't apply to this app's stack
            tmpl_stacks = tmpl.get("stacks")
            if tmpl_stacks and stack_lower and stack_lower not in [s.lower() for s in tmpl_stacks]:
                continue
            action = ACTION_MAP.get(tmpl["id"], tmpl["id"])
            is_direct = (
                tmpl.get("runner") == "direct" or tmpl.get("direct") is True or not use_melos
                or tmpl["id"] not in ACTION_MAP
            )

            if platform in ("utility", "release"):
                # Release actions are workspace-level git operations whose script ships with this
                # tool, so always route them through run_build.sh (it resolves script + workspace).
                if platform != "release" and is_direct and tmpl.get("command_template"):
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
                for flavor in target_flavors:
                    configured = _is_flavor_configured(app_id, flavor, tmpl["id"], deploy_cfg=deploy_cfg)
                    if is_direct and tmpl.get("command_template"):
                        resolved = _resolve_command(tmpl["command_template"], app_id, flavor, deploy_cfg)
                        full_cmd = f"{app_path_prefix} {resolved}".strip()
                    else:
                        full_cmd = f"bash {DASHBOARD_ROOT}/features/deployment/scripts/run_build.sh {action} {app_id} {flavor}"

                    name_suffix = f" ({flavor.upper()})" if flavors else ""
                    desc = tmpl["description"].replace("{app_id}", app_id)
                    if flavors:
                        desc = desc.replace("{flavor}", flavor)
                    else:
                        desc = desc.replace(" for {flavor} flavor", "").replace(" for {flavor}", "").replace("{flavor}", "")

                    commands.append({
                        "id": f"{tmpl['id']}_{app_id}_{flavor}",
                        "app": app_id,
                        "templateId": tmpl["id"],
                        "name": f"{tmpl['name']}{name_suffix}",
                        "description": desc,
                        "platform": platform,
                        "flavor": flavor if flavors else "default",
                        "runner": "custom",
                        "command": full_cmd,
                        "configured": configured,
                    })

    return commands


def _is_flavor_configured(app_id: str, flavor: str, template_id: str = "", deploy_cfg: Optional[dict[str, Any]] = None) -> bool:
    cfg = deploy_cfg if deploy_cfg is not None else load_deploy_config()
    app_cfg = cfg.get("apps", {}).get(app_id, {})
    bundle_id = str(
        app_cfg.get(f"bundle_id_{flavor}")
        or app_cfg.get("bundle_id")
        or app_cfg.get("bundle_id_prod")
        or ""
    ).strip()
    android_pkg = str(
        app_cfg.get(f"android_package_{flavor}")
        or app_cfg.get("android_package")
        or app_cfg.get("android_package_prod")
        or ""
    ).strip()

    if not bundle_id and not android_pkg:
        return False

    # B8 fix: iOS store upload/deploy requires Apple credentials
    if template_id in ("upload_ipa", "deploy_ipa", "deploy_both"):
        # Keys in env/<flavor>.json count too: the build scripts read APPLE_API_KEY from there.
        env_key = _apple_from_env_files(app_id, flavor) or {}
        has_apple = bool(
            app_cfg.get("apple_id") or app_cfg.get("apple_key_id")
            or credentials_job_env(app_id).get("APPLE_API_KEY")
            or (env_key.get("key_id") and env_key.get("exists"))
        )
        if not has_apple:
            return False

    return True


def get_commands(app: str) -> dict[str, Any]:
    if not app:
        return {"success": True, "commands": []}

    discover_workspace_config()

    ws_root = get_workspace_root()
    has_melos = any(ws_root.glob("melos*.yaml")) or (
        (ws_root / "pubspec.yaml").exists()
        and "melos:" in (ws_root / "pubspec.yaml").read_text(encoding="utf-8")
    )

    app_dir = _resolve_app_dir(app)
    if app_dir != ws_root:
        try:
            rel_dir = app_dir.relative_to(ws_root)
            prefix = f"cd {rel_dir} &&"
        except ValueError:
            prefix = f"cd {app_dir} &&"
    else:
        prefix = ""

    flavors = _detect_app_flavors(app)
    use_melos = has_melos and (app_dir != ws_root)

    # C11: get app stack for template filtering
    app_stack = ""
    try:
        from config import get_apps_config_file
        import json as _json
        apps_list = _json.loads(get_apps_config_file().read_text(encoding="utf-8"))
        for a in apps_list:
            if a.get("id") == app:
                app_stack = str(a.get("stack", "")).strip().lower()
                break
    except Exception:
        pass

    raw_commands = _build_commands_from_templates(app, prefix, use_melos, flavors, app_stack=app_stack)
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


def regenerate_commands() -> dict[str, Any]:
    discover_workspace_config()
    return {"success": True}


def _is_prod_store_deploy(resolved_command: str = "", *, template_id: str = "", flavor: str = "") -> bool:
    """Return True when this invocation will actually ship a build to a real app store.

    Two calling conventions are supported:
    - Legacy text-based: _is_prod_store_deploy(command_str)  -- kept for backward compat
    - Preferred explicit: _is_prod_store_deploy(template_id=..., flavor=...)

    The explicit form is used by execute_command() and is safe for single-app (no-flavor)
    apps because their flavor value is "default", which counts as a prod-level store upload
    when no flavors are configured (the app IS its prod environment).
    """
    # Explicit call via keyword args (preferred — authoritative check)
    if template_id:
        if template_id not in STORE_UPLOAD_TEMPLATE_IDS:
            return False
        flavor_lower = flavor.strip().lower()
        # "prod", "default" (single app, no flavor = prod tier), or "" all trigger confirmation
        return flavor_lower in ("prod", "default", "")

    # Legacy: fall back to text scanning (still covers old call-sites / tests)
    tokens = resolved_command.split()
    if not tokens:
        return False

    cleaned_tokens = [tok.strip(";").strip("#").lower() for tok in tokens if tok.strip()]
    if not cleaned_tokens:
        return False

    has_prod = False
    for tok in cleaned_tokens:
        if tok == "prod" or tok.endswith("/prod"):
            has_prod = True
            break

    if not has_prod:
        return False

    return any(tok in _STORE_SHIPPING_ACTIONS_LOWER for tok in cleaned_tokens)
