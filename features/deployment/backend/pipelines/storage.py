"""Pipeline definitions storage, schema validation, and template resolution."""

from __future__ import annotations

import re
import shlex
import time
from typing import Any

import commands
from config import SAFE_ID_PATTERN, load_deploy_config, save_deploy_config


def resolve_pipeline(app: str, pipeline_id: str, requested_flavor: str = "") -> dict[str, Any]:
    """Resolve a pipeline definition and each of its steps against configured commands."""
    if not app or not SAFE_ID_PATTERN.match(app):
        return {"success": False, "error": f"Invalid app ID '{app}'"}
    if not pipeline_id or not re.match(r"^[a-z0-9-]+$", pipeline_id):
        return {"success": False, "error": f"Invalid pipeline ID '{pipeline_id}'"}

    deploy_cfg = load_deploy_config()
    app_cfg = deploy_cfg.get("apps", {}).get(app, {})
    pipelines = app_cfg.get("pipelines", [])

    matched = None
    for p in pipelines:
        if isinstance(p, dict) and p.get("id") == pipeline_id:
            matched = p
            break

    if not matched:
        return {"success": False, "error": f"Pipeline '{pipeline_id}' not found for app '{app}'"}

    pipe_name = matched.get("name", pipeline_id)
    effective_flavor = str(matched.get("flavor") or requested_flavor or "prod").strip()

    app_commands_data = commands.get_commands(app)
    available_cmds = app_commands_data.get("commands", [])

    resolved_steps = []
    needs_confirmation = False

    for idx, step in enumerate(matched.get("steps", [])):
        if not isinstance(step, dict):
            continue
        step_flavor = str(step.get("flavor") or effective_flavor or "any").strip()
        custom_cmd = step.get("command")
        tmpl_id = step.get("templateId")
        step_continue = bool(step.get("continueOnFailure", False))

        if custom_cmd:
            step_name = step.get("name") or f"Custom #{idx + 1}"
            resolved_steps.append({
                "index": idx + 1,
                "name": step_name,
                "templateId": None,
                "command": custom_cmd,
                "flavor": step_flavor,
                "continueOnFailure": step_continue,
                "isCustom": True,
            })
            needs_confirmation = True
            continue

        if not tmpl_id:
            return {"success": False, "error": f"Step #{idx + 1} has no templateId or command"}

        # Match template in available commands
        matched_cmd = None
        for c in available_cmds:
            if c.get("templateId") == tmpl_id and c.get("flavor") in (step_flavor, "any", "default"):
                matched_cmd = c
                break

        # Fallback to any flavor if exact match didn't find one
        if not matched_cmd:
            for c in available_cmds:
                if c.get("templateId") == tmpl_id:
                    matched_cmd = c
                    break

        if not matched_cmd:
            return {
                "success": False,
                "error": f"Step #{idx + 1} template '{tmpl_id}' not found or configured for app '{app}'",
            }

        cmd_str = matched_cmd.get("command", "")
        # Apply flavor substitution if template ended in " any"
        if step_flavor and step_flavor not in ("any", "default") and cmd_str.endswith(" any"):
            cmd_str = cmd_str[:-4] + f" {shlex.quote(step_flavor)}"

        is_prod = commands._is_prod_store_deploy(template_id=tmpl_id, flavor=step_flavor)
        is_release_push = tmpl_id in ("release_push", "release_verify") or "git push" in cmd_str

        if is_prod or is_release_push:
            needs_confirmation = True

        resolved_steps.append({
            "index": idx + 1,
            "name": step.get("name") or matched_cmd.get("name", tmpl_id),
            "templateId": tmpl_id,
            "command": cmd_str,
            "flavor": step_flavor,
            "continueOnFailure": step_continue,
            "isCustom": False,
        })

    return {
        "success": True,
        "id": pipeline_id,
        "name": pipe_name,
        "app": app,
        "flavor": effective_flavor,
        "needsConfirmation": needs_confirmation,
        "steps": resolved_steps,
    }


def get_pipelines(app: str) -> dict[str, Any]:
    """Return all saved pipelines for an app with their steps resolved."""
    if not app:
        return {"success": True, "pipelines": []}

    deploy_cfg = load_deploy_config()
    app_cfg = deploy_cfg.get("apps", {}).get(app, {})
    raw_pipelines = app_cfg.get("pipelines", [])

    results = []
    for p in raw_pipelines:
        if isinstance(p, dict) and p.get("id"):
            res = resolve_pipeline(app, p["id"])
            if res.get("success"):
                results.append(res)
            else:
                results.append({
                    "id": p.get("id"),
                    "name": p.get("name", p.get("id")),
                    "flavor": p.get("flavor", ""),
                    "steps": p.get("steps", []),
                    "unresolvedError": res.get("error"),
                })

    return {"success": True, "pipelines": results}


def save_pipeline(app: str, pipeline_data: dict[str, Any]) -> dict[str, Any]:
    """Save or update a pipeline definition for an app in deploy_config.json."""
    if not app or not SAFE_ID_PATTERN.match(app):
        return {"success": False, "error": f"Invalid app ID '{app}'"}
    if not isinstance(pipeline_data, dict):
        return {"success": False, "error": "Pipeline data must be a JSON object"}

    name = str(pipeline_data.get("name") or "").strip()
    if not name or len(name) > 60:
        return {"success": False, "error": "Pipeline name is required (1–60 chars)"}

    pipe_id = str(pipeline_data.get("id") or "").strip()
    if not pipe_id:
        pipe_id = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        if not pipe_id:
            pipe_id = f"pipe-{int(time.time())}"

    steps = pipeline_data.get("steps", [])
    if not isinstance(steps, list) or not steps:
        return {"success": False, "error": "Pipeline must have at least 1 step"}
    if len(steps) > 20:
        return {"success": False, "error": "Maximum 20 steps allowed per pipeline"}

    cleaned_steps = []
    for s in steps:
        if not isinstance(s, dict):
            continue
        cleaned_steps.append({
            "name": str(s.get("name") or "").strip(),
            "templateId": s.get("templateId"),
            "command": s.get("command"),
            "flavor": s.get("flavor"),
            "continueOnFailure": bool(s.get("continueOnFailure", False)),
        })

    deploy_cfg = load_deploy_config()
    apps = deploy_cfg.setdefault("apps", {})
    app_cfg = apps.setdefault(app, {})
    pipelines_list = app_cfg.setdefault("pipelines", [])

    entry = {
        "id": pipe_id,
        "name": name,
        "flavor": pipeline_data.get("flavor") or "",
        "steps": cleaned_steps,
    }

    found = False
    for i, p in enumerate(pipelines_list):
        if isinstance(p, dict) and p.get("id") == pipe_id:
            pipelines_list[i] = entry
            found = True
            break
    if not found:
        pipelines_list.append(entry)

    res = save_deploy_config(deploy_cfg)
    if not res.get("success"):
        return res

    return {
        "success": True,
        "pipeline": entry,
        "pipelines": get_pipelines(app).get("pipelines", []),
    }


def delete_pipeline(app: str, pipeline_id: str) -> dict[str, Any]:
    """Delete a pipeline definition for an app in deploy_config.json."""
    if not app or not SAFE_ID_PATTERN.match(app):
        return {"success": False, "error": f"Invalid app ID '{app}'"}
    if not pipeline_id:
        return {"success": False, "error": "Pipeline ID required"}

    deploy_cfg = load_deploy_config()
    apps = deploy_cfg.get("apps", {})
    app_cfg = apps.get(app, {})
    pipelines_list = app_cfg.get("pipelines", [])

    new_list = [p for p in pipelines_list if isinstance(p, dict) and p.get("id") != pipeline_id]
    if len(new_list) == len(pipelines_list):
        return {"success": False, "error": f"Pipeline '{pipeline_id}' not found"}

    app_cfg["pipelines"] = new_list

    res = save_deploy_config(deploy_cfg)
    if not res.get("success"):
        return res

    return {
        "success": True,
        "deletedId": pipeline_id,
        "pipelines": get_pipelines(app).get("pipelines", []),
    }
