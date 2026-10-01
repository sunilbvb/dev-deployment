"""Pipelines backend engine: define, resolve, and sequentially run saved workflows.

Follows Proposal 0001 (0001-pipelines.md) and ADR 0004:
- Chains commands sequentially with a single upfront confirmation.
- Holds the app lock for the duration of the entire pipeline run.
- Halts immediately on step failure unless step has continueOnFailure=True.
- Records a consolidated 'type': 'pipeline' entry in deployment_history.jsonl.
- Python standard library only.
"""

import json
import logging
import re
import shlex
import threading
import time
from typing import Any, Optional

import commands
from config import SAFE_ID_PATTERN, get_workspace_root, load_deploy_config
import jobs

_PIPELINE_RUNS: dict[str, dict[str, Any]] = {}
_PIPELINES_LOCK = threading.Lock()


def _prune_pipeline_runs() -> None:
    now = time.time()
    with _PIPELINES_LOCK:
        finished_runs = []
        for rid, r in list(_PIPELINE_RUNS.items()):
            if r.get("status") in ("success", "error", "stopped"):
                finished_at = r.get("finishedAt") or r.get("startedAt", now)
                if now - finished_at > 3600:
                    _PIPELINE_RUNS.pop(rid, None)
                else:
                    finished_runs.append((finished_at, rid))
        if len(_PIPELINE_RUNS) > 50:
            finished_runs.sort(key=lambda x: x[0])
            for _, rid in finished_runs:
                _PIPELINE_RUNS.pop(rid, None)
                if len(_PIPELINE_RUNS) <= 50:
                    break


def _record_pipeline_history(run: dict[str, Any]) -> None:
    target_dir = get_workspace_root() / ".dev-dashboard"
    target_dir.mkdir(parents=True, exist_ok=True)
    history_file = target_dir / "deployment_history.jsonl"

    started_at = run.get("startedAt")
    finished_at = run.get("finishedAt") or time.time()
    duration_sec = int(finished_at - started_at) if started_at else None

    entry = {
        "type": "pipeline",
        "id": run["id"],
        "app": run.get("app"),
        "pipelineId": run.get("pipelineId"),
        "name": run.get("name"),
        "flavor": run.get("flavor"),
        "status": run.get("status"),
        "failedStep": run.get("failedStep"),
        "steps": [
            {
                "name": s.get("name"),
                "templateId": s.get("templateId"),
                "jobId": s.get("jobId"),
                "status": s.get("status"),
                "returnCode": s.get("returnCode"),
                "durationSeconds": s.get("durationSeconds"),
                "isCustom": s.get("isCustom", False),
            }
            for s in run.get("steps", [])
        ],
        "startedAt": started_at,
        "finishedAt": finished_at,
        "completedAt": int(finished_at * 1000) if finished_at else None,
        "durationSeconds": duration_sec,
    }

    with jobs._HISTORY_LOCK:
        try:
            with history_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            logging.exception("Failed to write pipeline history entry")


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
                # Include unresolved representation if error occurred
                results.append({
                    "id": p.get("id"),
                    "name": p.get("name", p.get("id")),
                    "flavor": p.get("flavor", ""),
                    "steps": p.get("steps", []),
                    "unresolvedError": res.get("error"),
                })

    return {"success": True, "pipelines": results}


def run_pipeline(
    app: str,
    pipeline_id: str,
    flavor: str = "",
    confirmed: bool = False,
) -> dict[str, Any]:
    """Start running a saved pipeline sequentially under an exclusive app lock."""
    resolved = resolve_pipeline(app, pipeline_id, requested_flavor=flavor)
    if not resolved.get("success"):
        return resolved

    if resolved.get("needsConfirmation") and not confirmed:
        return {
            "success": False,
            "needsConfirmation": True,
            "error": f"Pipeline '{resolved['name']}' requires confirmation before running.",
            "commands": [
                {
                    "step": s["name"],
                    "command": s["command"],
                    "templateId": s.get("templateId"),
                    "isCustom": s.get("isCustom", False),
                }
                for s in resolved["steps"]
            ],
        }

    ws_root = get_workspace_root()
    lock_key = f"{ws_root.resolve()}:{app}"

    with jobs._JOBS_LOCK:
        existing = jobs._APP_LOCKS.get(lock_key) or jobs._APP_LOCKS.get(app)
        if existing is not None:
            started_at = existing.get("started_at")
            elapsed_sec = int(time.time() - started_at) if started_at else None
            return {
                "success": False,
                "error": (
                    f"A deployment job or pipeline is already running for '{app}': {existing.get('command')}. "
                    "Wait for it to finish or stop it before running another."
                ),
                "code": "APP_BUSY",
                "runningJob": {
                    "jobId": existing.get("job_id"),
                    "command": existing.get("command"),
                    "startedAt": existing.get("started_at"),
                    "elapsedSeconds": elapsed_sec,
                },
            }

        run_id = f"pipe_{int(time.time() * 1000)}"
        jobs._APP_LOCKS[lock_key] = {
            "job_id": None,
            "pipeline_id": run_id,
            "app": app,
            "flavor": resolved.get("flavor", ""),
            "command": f"Pipeline: {resolved['name']}",
            "started_at": time.time(),
            "workspace": str(ws_root.resolve()),
        }

    steps_state = [
        {
            "name": s["name"],
            "templateId": s.get("templateId"),
            "command": s["command"],
            "flavor": s.get("flavor", ""),
            "continueOnFailure": s.get("continueOnFailure", False),
            "isCustom": s.get("isCustom", False),
            "status": "pending",
            "jobId": None,
            "returnCode": None,
            "startedAt": None,
            "finishedAt": None,
            "durationSeconds": None,
        }
        for s in resolved["steps"]
    ]

    with _PIPELINES_LOCK:
        _PIPELINE_RUNS[run_id] = {
            "id": run_id,
            "app": app,
            "pipelineId": pipeline_id,
            "name": resolved["name"],
            "flavor": resolved.get("flavor", ""),
            "status": "running",
            "currentStep": 0,
            "currentJobId": None,
            "failedStep": None,
            "stopped": False,
            "steps": steps_state,
            "startedAt": time.time(),
            "finishedAt": None,
            "durationSeconds": None,
            "workspace": str(ws_root.resolve()),
        }

    jobs._start_in_context(_execute_pipeline_worker, run_id, app, lock_key)
    return {
        "success": True,
        "runId": run_id,
        "pipelineId": pipeline_id,
        "name": resolved["name"],
        "stepsCount": len(steps_state),
    }


def _execute_pipeline_worker(run_id: str, app: str, lock_key: str) -> None:
    with _PIPELINES_LOCK:
        run = _PIPELINE_RUNS.get(run_id)
    if not run:
        return

    steps = run["steps"]
    for idx, step in enumerate(steps):
        with _PIPELINES_LOCK:
            if run.get("stopped"):
                run["status"] = "stopped"
                for rem in steps[idx:]:
                    if rem["status"] == "pending":
                        rem["status"] = "skipped"
                break
            run["currentStep"] = idx + 1
            step["status"] = "running"
            step["startedAt"] = time.time()

        # Execute step via jobs.execute_command
        exec_res = jobs.execute_command(
            app=app,
            command=step["command"],
            runner="custom",
            template_id=step.get("templateId") or "",
            flavor=step.get("flavor") or run.get("flavor") or "",
            env=step.get("flavor") or run.get("flavor") or "",
            confirmed=True,
            _assume_app_lock_held=True,
            chained_parent_id=run_id,
        )

        if not exec_res.get("success"):
            with _PIPELINES_LOCK:
                step["status"] = "error"
                step["finishedAt"] = time.time()
                step["durationSeconds"] = 0
                if not step.get("continueOnFailure"):
                    run["failedStep"] = idx + 1
                    run["status"] = "error"
                    for rem in steps[idx + 1:]:
                        rem["status"] = "skipped"
                    break
            continue

        job_id = exec_res.get("jobId")
        with _PIPELINES_LOCK:
            step["jobId"] = job_id
            run["currentJobId"] = job_id

        # Poll active step job until termination
        while True:
            j_res = jobs.get_job(job_id)
            if not j_res.get("success"):
                break
            j_data = j_res.get("job", {})
            j_status = j_data.get("status")
            if j_status in ("success", "error", "stopped"):
                break
            with _PIPELINES_LOCK:
                if run.get("stopped"):
                    jobs.stop_job(job_id)
            time.sleep(0.15)

        finished_ts = time.time()
        final_job = jobs.get_job(job_id).get("job", {})
        final_status = final_job.get("status") or "error"

        with _PIPELINES_LOCK:
            step["status"] = final_status
            step["returnCode"] = final_job.get("return_code")
            step["finishedAt"] = finished_ts
            started = step.get("startedAt") or finished_ts
            step["durationSeconds"] = int(finished_ts - started)

            if run.get("stopped"):
                run["status"] = "stopped"
                for rem in steps[idx + 1:]:
                    rem["status"] = "skipped"
                break

            if final_status != "success":
                if not step.get("continueOnFailure"):
                    run["failedStep"] = idx + 1
                    run["status"] = "stopped" if final_status == "stopped" else "error"
                    for rem in steps[idx + 1:]:
                        rem["status"] = "skipped"
                    break

    # Finalize pipeline run
    with _PIPELINES_LOCK:
        if run["status"] == "running":
            run["status"] = "success"
        run["finishedAt"] = time.time()
        st = run.get("startedAt") or run["finishedAt"]
        run["durationSeconds"] = int(run["finishedAt"] - st)
        run["currentJobId"] = None

    # Release app lock
    with jobs._JOBS_LOCK:
        held = jobs._APP_LOCKS.get(lock_key) or jobs._APP_LOCKS.get(app)
        if held and (held.get("pipeline_id") == run_id or held.get("job_id") is None):
            jobs._APP_LOCKS.pop(lock_key, None)
            jobs._APP_LOCKS.pop(app, None)

    _record_pipeline_history(run)
    _prune_pipeline_runs()


def stop_pipeline_run(run_id: str) -> dict[str, Any]:
    """Request stopping an active pipeline run and its current running job."""
    if not run_id:
        return {"success": False, "error": "Missing runId"}

    with _PIPELINES_LOCK:
        run = _PIPELINE_RUNS.get(run_id)
        if not run:
            return {"success": False, "error": f"Pipeline run '{run_id}' not found"}
        if run.get("status") != "running":
            return {"success": False, "error": "Pipeline run is not running"}

        run["stopped"] = True
        run["status"] = "stopping"
        active_job_id = run.get("currentJobId")

    if active_job_id:
        jobs.stop_job(active_job_id)

    return {"success": True, "message": "Pipeline run stop requested"}


def get_pipeline_run(run_id: Optional[str]) -> dict[str, Any]:
    """Return live status and steps progress for a pipeline run."""
    if not run_id:
        return {"success": False, "error": "Missing run id"}

    with _PIPELINES_LOCK:
        run = _PIPELINE_RUNS.get(str(run_id))
        if not run:
            return {"success": False, "error": f"Pipeline run '{run_id}' not found"}
        payload = dict(run)

    return {"success": True, "run": payload}
