import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import (
    DASHBOARD_ROOT,
    WORKSPACE_ROOT,
    _detect_app_flavors,
    discover_workspace_config,
    load_deploy_config,
    load_templates,
)

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
    "release_tag": "releaseTag",
    "release_push": "releasePush",
    "release_changelog": "releaseChangelog",
    "release_full": "releaseFull",
}

STORE_UPLOAD_TEMPLATE_IDS = {"upload_ipa", "upload_aab", "deploy_ipa", "deploy_aab", "deploy_both"}
_STORE_SHIPPING_ACTIONS = {"deployIPA", "uploadIPA", "deployAAB", "uploadAAB", "deployBothPlatforms"}
_STORE_SHIPPING_ACTIONS_LOWER = {act.lower() for act in _STORE_SHIPPING_ACTIONS}


def _resolve_command(template: str, app_id: str, flavor: str, deploy_cfg: dict[str, Any]) -> str:
    app_cfg = deploy_cfg.get("apps", {}).get(app_id, {})
    bundle_id = app_cfg.get(f"bundle_id_{flavor}") or app_cfg.get("bundle_id_prod", f"com.example.{app_id}")
    android_package = app_cfg.get(f"android_package_{flavor}") or app_cfg.get("android_package_prod", f"com.example.{app_id}")
    apple_id = app_cfg.get("apple_id", "")

    if flavor in ("any", "none", "default"):
        res = template.replace("--flavor {flavor}", "").replace("-flavor {flavor}", "").replace("{flavor}", "").strip()
    else:
        res = template.replace("{flavor}", flavor)

    return (
        res
        .replace("{bundle_id}", bundle_id)
        .replace("{android_package}", android_package)
        .replace("{apple_id}", apple_id)
        .replace("{app_id}", app_id)
    )


def _build_commands_from_templates(app_id: str, app_path_prefix: str, use_melos: bool, flavors: list[str], deploy_cfg: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
    templates = load_templates()
    if deploy_cfg is None:
        deploy_cfg = load_deploy_config()
    commands: list[dict[str, Any]] = []

    for platform, tmpl_list in templates.items():
        for tmpl in tmpl_list:
            action = ACTION_MAP.get(tmpl["id"], tmpl["id"])
            is_direct = tmpl.get("runner") == "direct" or tmpl.get("direct") is True or not use_melos

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
                    configured = _is_flavor_configured(app_id, flavor)
                    if is_direct and tmpl.get("command_template"):
                        resolved = _resolve_command(tmpl["command_template"], app_id, flavor, deploy_cfg)
                        full_cmd = f"{app_path_prefix} {resolved}".strip()
                    else:
                        full_cmd = f"bash {DASHBOARD_ROOT}/features/deployment/scripts/run_build.sh {action} {app_id} {flavor}"

                    commands.append({
                        "id": f"{tmpl['id']}_{app_id}_{flavor}",
                        "app": app_id,
                        "templateId": tmpl["id"],
                        "name": f"{tmpl['name']} ({flavor.upper()})",
                        "description": tmpl["description"].replace("{app_id}", app_id).replace("{flavor}", flavor),
                        "platform": platform,
                        "flavor": flavor,
                        "runner": "custom",
                        "command": full_cmd,
                        "configured": configured,
                    })

    return commands


def _is_flavor_configured(app_id: str, flavor: str) -> bool:
    cfg = load_deploy_config()
    app_cfg = cfg.get("apps", {}).get(app_id, {})
    bundle_id = str(app_cfg.get(f"bundle_id_{flavor}") or "").strip()
    return len(bundle_id) > 0


def get_commands(app: str) -> dict[str, Any]:
    if not app:
        return {"success": True, "commands": []}

    discover_workspace_config()

    has_melos = any(WORKSPACE_ROOT.glob("melos*.yaml")) or (
        (WORKSPACE_ROOT / "pubspec.yaml").exists()
        and "melos:" in (WORKSPACE_ROOT / "pubspec.yaml").read_text(encoding="utf-8")
    )

    use_apps_dir = (WORKSPACE_ROOT / "apps" / app).exists()
    prefix = f"cd apps/{app} &&" if use_apps_dir else ""

    flavors = _detect_app_flavors(app)
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


def regenerate_commands() -> dict[str, Any]:
    discover_workspace_config()
    return {"success": True}


def _is_prod_store_deploy(resolved_command: str) -> bool:
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
