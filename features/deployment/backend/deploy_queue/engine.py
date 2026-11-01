"""Deployment Queue Engine.

Manages sequential FIFO execution of multi-app deployment commands and pipelines.
Zero external dependencies - 100% Python standard library.
"""

from __future__ import annotations

import logging
from pathlib import Path
import threading
import time
import uuid
from typing import Any, Optional

import commands
from config import (
    SAFE_ID_PATTERN,
    get_workspace_root,
    reset_request_workspace,
    set_request_workspace,
)
import jobs
import pipelines
from .storage import load_queue, save_queue

_QUEUE_LOCK = threading.Lock()
_QUEUE_ITEMS: list[dict[str, Any]] = []
_QUEUE_INITIALIZED = False
_IS_PAUSED = False
_ACTIVE_ITEM_ID: Optional[str] = None
_WORKER_THREAD: Optional[threading.Thread] = None
_STOP_EVENT = threading.Event()


def _ensure_initialized() -> None:
    global _QUEUE_ITEMS, _QUEUE_INITIALIZED
    with _QUEUE_LOCK:
        if not _QUEUE_INITIALIZED:
            _QUEUE_ITEMS = load_queue()
            for item in _QUEUE_ITEMS:
                if item.get("status") == "running":
                    item["status"] = "failed"
                    item["error"] = "Server interrupted during execution"
                    item["finishedAt"] = time.time()
            _QUEUE_INITIALIZED = True


def _generate_item_id() -> str:
    return f"qitem_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"


def _worker_loop() -> None:
    """Sequential execution worker loop. Runs in background daemon thread."""
    global _ACTIVE_ITEM_ID, _IS_PAUSED, _WORKER_THREAD

    while not _STOP_EVENT.is_set():
        next_item: Optional[dict[str, Any]] = None

        with _QUEUE_LOCK:
            if _IS_PAUSED:
                _WORKER_THREAD = None
                return

            for it in _QUEUE_ITEMS:
                if it.get("status") == "pending":
                    next_item = it
                    break

            if not next_item:
                _ACTIVE_ITEM_ID = None
                _WORKER_THREAD = None
                return

            _ACTIVE_ITEM_ID = next_item["id"]
            next_item["status"] = "running"
            next_item["startedAt"] = time.time()
            next_item["error"] = None
            save_queue(_QUEUE_ITEMS)

        item_id = next_item["id"]
        item_type = next_item.get("type", "command")
        app = next_item.get("app", "")
        flavor = next_item.get("flavor", "prod")
        stop_on_error = bool(next_item.get("stopOnError", True))
        ws_str = next_item.get("workspace")

        status = "failed"
        return_code: Optional[int] = None
        error_msg: Optional[str] = None

        ws_token = None
        if ws_str:
            try:
                p = Path(ws_str).resolve()
                if p.is_dir():
                    ws_token = set_request_workspace(p)
            except Exception:
                pass

        try:
            if item_type == "pipeline":
                pipeline_id = next_item.get("pipelineId") or next_item.get("command") or ""
                pipe_res = pipelines.run_pipeline(
                    app=app,
                    pipeline_id=pipeline_id,
                    flavor=flavor,
                    confirmed=True,
                )
                if not pipe_res.get("success"):
                    status = "failed"
                    error_msg = pipe_res.get("error", "Pipeline failed to start")
                else:
                    run_id = pipe_res.get("runId")
                    with _QUEUE_LOCK:
                        next_item["jobId"] = run_id
                        save_queue(_QUEUE_ITEMS)

                    while not _STOP_EVENT.is_set():
                        time.sleep(0.5)
                        prun = pipelines.get_pipeline_run(run_id)
                        p_status = prun.get("status")
                        if p_status in ("success", "error", "stopped"):
                            status = "completed" if p_status == "success" else ("cancelled" if p_status == "stopped" else "failed")
                            return_code = 0 if p_status == "success" else 1
                            if p_status != "success":
                                error_msg = f"Pipeline {pipeline_id} {p_status}"
                            break

            else:
                cmd_key = next_item.get("command", "")
                runner = next_item.get("runner", "make")
                template_id = next_item.get("templateId", "")
                clean_build = next_item.get("cleanBuild")
                release_notes = next_item.get("releaseNotes")

                cmd_res = jobs.execute_command(
                    app=app,
                    command=cmd_key,
                    runner=runner,
                    env=flavor,
                    template_id=template_id,
                    flavor=flavor,
                    confirmed=True,
                    clean_build=clean_build,
                    release_notes=release_notes,
                )
                if not cmd_res.get("success"):
                    status = "failed"
                    error_msg = cmd_res.get("error", "Command failed to start")
                else:
                    job_id = cmd_res.get("jobId")
                    with _QUEUE_LOCK:
                        next_item["jobId"] = job_id
                        save_queue(_QUEUE_ITEMS)

                    while not _STOP_EVENT.is_set():
                        time.sleep(0.5)
                        j = jobs.get_job(job_id)
                        j_status = j.get("status")
                        if j_status in ("success", "error", "stopped"):
                            status = "completed" if j_status == "success" else ("cancelled" if j_status == "stopped" else "failed")
                            return_code = j.get("return_code", 0 if j_status == "success" else 1)
                            if j_status != "success":
                                error_msg = j.get("error") or f"Command exited with status {j_status}"
                            break

        except Exception as exc:
            logging.exception("Exception in queue worker executing %s", item_id)
            status = "failed"
            error_msg = str(exc)
        finally:
            if ws_token is not None:
                try:
                    reset_request_workspace(ws_token)
                except Exception:
                    pass

        finished_ts = time.time()
        with _QUEUE_LOCK:
            next_item["status"] = status
            next_item["finishedAt"] = finished_ts
            next_item["returnCode"] = return_code
            if error_msg:
                next_item["error"] = error_msg
            if next_item.get("startedAt"):
                next_item["durationSeconds"] = int(finished_ts - next_item["startedAt"])

            _ACTIVE_ITEM_ID = None

            if status == "failed" and stop_on_error:
                _IS_PAUSED = True
                save_queue(_QUEUE_ITEMS)
                _WORKER_THREAD = None
                return

            save_queue(_QUEUE_ITEMS)


def _start_worker_if_needed() -> None:
    global _WORKER_THREAD
    with _QUEUE_LOCK:
        if _IS_PAUSED:
            return
        if _WORKER_THREAD is not None and _WORKER_THREAD.is_alive():
            return
        has_pending = any(it.get("status") == "pending" for it in _QUEUE_ITEMS)
        if not has_pending:
            return

        _WORKER_THREAD = threading.Thread(target=_worker_loop, name="DeploymentQueueWorker", daemon=True)
        _WORKER_THREAD.start()


def get_queue_status() -> dict[str, Any]:
    """Return live status of the deployment queue, including active item and counts."""
    _ensure_initialized()
    with _QUEUE_LOCK:
        active_item = None
        counts = {"total": len(_QUEUE_ITEMS), "pending": 0, "running": 0, "completed": 0, "failed": 0, "cancelled": 0}

        for it in _QUEUE_ITEMS:
            st = it.get("status", "pending")
            counts[st] = counts.get(st, 0) + 1
            if it.get("id") == _ACTIVE_ITEM_ID or st == "running":
                active_item = it

        return {
            "success": True,
            "queue": [dict(it) for it in _QUEUE_ITEMS],
            "activeItem": dict(active_item) if active_item else None,
            "isPaused": _IS_PAUSED,
            "counts": counts,
        }


def add_to_queue(
    app: str,
    command: str,
    item_type: str = "command",
    runner: str = "make",
    flavor: str = "prod",
    template_id: str = "",
    title: str = "",
    clean_build: Optional[bool] = None,
    release_notes: Optional[dict[str, str]] = None,
    stop_on_error: bool = True,
) -> dict[str, Any]:
    """Validate and enqueue a command or pipeline for sequential execution."""
    _ensure_initialized()

    if not app or not SAFE_ID_PATTERN.match(app):
        return {"success": False, "error": f"Invalid app ID '{app}'"}

    if item_type == "pipeline":
        pipeline_id = command or template_id
        resolved = pipelines.resolve_pipeline(app, pipeline_id, requested_flavor=flavor)
        if not resolved.get("success"):
            return resolved
        item_title = title or f"{app} • Pipeline: {resolved.get('name', pipeline_id)}"
        final_cmd = pipeline_id
    else:
        allowed_cmds = commands.get_commands(app).get("commands", [])
        target_cmd = None
        for c in allowed_cmds:
            if template_id and c.get("templateId") == template_id and (c.get("flavor") in (flavor, "any", "default")):
                target_cmd = c
                break
            if not target_cmd and c.get("key") == command:
                target_cmd = c
                break

        if not target_cmd and allowed_cmds:
            for c in allowed_cmds:
                if c.get("templateId") == template_id or c.get("key") == command:
                    target_cmd = c
                    break

        if not target_cmd:
            return {"success": False, "error": f"Command not found for app '{app}' (template: {template_id}, key: {command})"}

        final_cmd = target_cmd.get("key", command)
        runner = target_cmd.get("runner", runner)
        template_id = target_cmd.get("templateId", template_id)
        item_title = title or f"{app} • {target_cmd.get('title') or target_cmd.get('key')}"

    item_id = _generate_item_id()
    item: dict[str, Any] = {
        "id": item_id,
        "app": app,
        "type": item_type,
        "title": item_title,
        "command": final_cmd,
        "runner": runner,
        "flavor": flavor,
        "templateId": template_id,
        "pipelineId": final_cmd if item_type == "pipeline" else None,
        "cleanBuild": clean_build,
        "releaseNotes": release_notes,
        "stopOnError": stop_on_error,
        "status": "pending",
        "jobId": None,
        "returnCode": None,
        "error": None,
        "startedAt": None,
        "finishedAt": None,
        "durationSeconds": None,
        "workspace": str(get_workspace_root().resolve()),
        "queuedAt": time.time(),
    }

    with _QUEUE_LOCK:
        _QUEUE_ITEMS.append(item)
        save_queue(_QUEUE_ITEMS)

    _start_worker_if_needed()
    return {"success": True, "item": item, "queue": [dict(it) for it in _QUEUE_ITEMS]}


def remove_from_queue(item_id: str) -> dict[str, Any]:
    """Remove a pending item from the queue, or stop it if currently running."""
    _ensure_initialized()
    if not item_id:
        return {"success": False, "error": "Item ID is required"}

    with _QUEUE_LOCK:
        target_item = None
        for it in _QUEUE_ITEMS:
            if it.get("id") == item_id:
                target_item = it
                break

        if not target_item:
            return {"success": False, "error": f"Item '{item_id}' not found in queue"}

        if target_item.get("status") == "pending":
            _QUEUE_ITEMS.remove(target_item)
            save_queue(_QUEUE_ITEMS)
            return {"success": True, "message": "Pending item removed from queue"}

        if target_item.get("status") == "running":
            target_item["status"] = "cancelled"
            target_item["finishedAt"] = time.time()
            job_id = target_item.get("jobId")
            save_queue(_QUEUE_ITEMS)
            if job_id:
                if target_item.get("type") == "pipeline":
                    pipelines.stop_pipeline_run(job_id)
                else:
                    jobs.stop_job(job_id)
            return {"success": True, "message": "Running item stopped and cancelled"}

        _QUEUE_ITEMS.remove(target_item)
        save_queue(_QUEUE_ITEMS)
        return {"success": True, "message": "Item deleted from queue history"}


def reorder_queue(item_ids: list[str]) -> dict[str, Any]:
    """Reorder pending items in the queue according to the provided list of IDs."""
    _ensure_initialized()
    if not isinstance(item_ids, list):
        return {"success": False, "error": "item_ids must be a list of string IDs"}

    with _QUEUE_LOCK:
        non_pending: list[dict[str, Any]] = []
        pending_map: dict[str, dict[str, Any]] = {}

        for it in _QUEUE_ITEMS:
            if it.get("status") == "pending":
                pending_map[it["id"]] = it
            else:
                non_pending.append(it)

        new_pending: list[dict[str, Any]] = []
        for i_id in item_ids:
            if i_id in pending_map:
                new_pending.append(pending_map.pop(i_id))

        for rem in pending_map.values():
            new_pending.append(rem)

        _QUEUE_ITEMS[:] = [it for it in non_pending if it.get("status") == "running"] + new_pending + [it for it in non_pending if it.get("status") != "running"]
        save_queue(_QUEUE_ITEMS)

    return {"success": True, "queue": [dict(it) for it in _QUEUE_ITEMS]}


def clear_queue(clear_all: bool = False) -> dict[str, Any]:
    """Clear pending queue items, or all items except currently running."""
    _ensure_initialized()
    with _QUEUE_LOCK:
        if clear_all:
            _QUEUE_ITEMS[:] = [it for it in _QUEUE_ITEMS if it.get("status") == "running"]
        else:
            _QUEUE_ITEMS[:] = [it for it in _QUEUE_ITEMS if it.get("status") != "pending"]
        save_queue(_QUEUE_ITEMS)

    return {"success": True, "message": "Queue cleared"}


def pause_queue() -> dict[str, Any]:
    """Pause queue processing. Running item finishes, but subsequent pending items wait."""
    global _IS_PAUSED
    _ensure_initialized()
    with _QUEUE_LOCK:
        _IS_PAUSED = True

    return {"success": True, "isPaused": True, "message": "Queue paused"}


def resume_queue() -> dict[str, Any]:
    """Resume queue processing and trigger background worker for pending items."""
    global _IS_PAUSED
    _ensure_initialized()
    with _QUEUE_LOCK:
        _IS_PAUSED = False

    _start_worker_if_needed()
    return {"success": True, "isPaused": False, "message": "Queue resumed"}


def stop_current_queue_item() -> dict[str, Any]:
    """Stop the currently active queue item."""
    _ensure_initialized()
    with _QUEUE_LOCK:
        if not _ACTIVE_ITEM_ID:
            return {"success": False, "error": "No item is currently running"}
        curr_id = _ACTIVE_ITEM_ID

    return remove_from_queue(curr_id)


def retry_queue_item(item_id: str) -> dict[str, Any]:
    """Re-enqueue a failed or cancelled queue item as pending."""
    _ensure_initialized()
    if not item_id:
        return {"success": False, "error": "Item ID is required"}

    with _QUEUE_LOCK:
        target = None
        for it in _QUEUE_ITEMS:
            if it.get("id") == item_id:
                target = it
                break

        if not target:
            return {"success": False, "error": f"Item '{item_id}' not found"}

        target["status"] = "pending"
        target["error"] = None
        target["returnCode"] = None
        target["startedAt"] = None
        target["finishedAt"] = None
        target["durationSeconds"] = None
        target["queuedAt"] = time.time()
        save_queue(_QUEUE_ITEMS)

    _start_worker_if_needed()
    return {"success": True, "item": target, "message": "Item re-enqueued"}


def _reset_queue_state_for_testing() -> None:
    """Reset module-level state during unit tests."""
    global _QUEUE_ITEMS, _QUEUE_INITIALIZED, _IS_PAUSED, _ACTIVE_ITEM_ID, _WORKER_THREAD
    with _QUEUE_LOCK:
        _QUEUE_ITEMS = []
        _QUEUE_INITIALIZED = True
        _IS_PAUSED = False
        _ACTIVE_ITEM_ID = None
        _WORKER_THREAD = None
