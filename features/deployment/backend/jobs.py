import json
import logging
import os
import shlex
import shutil
import signal
import subprocess
import sys
import contextvars
import threading
import time
from pathlib import Path
from typing import Any, Optional

from config import (
    FEATURE_DIR,
    TMP_DIR,
    SAFE_ID_PATTERN,
    get_workspace_root,
    load_deploy_config,
)
from credentials import job_env as credentials_job_env
from commands import (
    STORE_UPLOAD_TEMPLATE_IDS,
    _is_prod_store_deploy,
    get_commands,
)

_JOBS: dict[str, dict[str, Any]] = {}
_JOBS_LOCK = threading.Lock()
_APP_LOCKS: dict[str, dict[str, Any]] = {}
_HISTORY_LOCK = threading.Lock()
EXPIRY_WARNING_THRESHOLD_DAYS = 30


def _start_in_context(target, *args) -> None:
    """Run a job thread with the request's context so it keeps the request's workspace."""
    ctx = contextvars.copy_context()
    threading.Thread(target=ctx.run, args=(target, *args), daemon=True).start()


def _prune_jobs() -> None:
    """Drop finished jobs older than 1 hour or when count of jobs exceeds 50."""
    now = time.time()
    with _JOBS_LOCK:
        finished_jobs = []
        for jid, j in list(_JOBS.items()):
            if j.get("status") in ("success", "error", "stopped"):
                finished_at = j.get("finished_at") or j.get("started_at", now)
                # Drop if older than 1 hour (3600 seconds)
                if now - finished_at > 3600:
                    _JOBS.pop(jid, None)
                else:
                    finished_jobs.append((finished_at, jid))

        # If still more than 50 jobs in total, prune oldest finished jobs
        if len(_JOBS) > 50:
            finished_jobs.sort(key=lambda x: x[0])
            for _, jid in finished_jobs:
                _JOBS.pop(jid, None)
                if len(_JOBS) <= 50:
                    break


def _new_job_id() -> str:
    return f"job_{int(time.time() * 1000)}"


def _get_history_file() -> Path:
    target_dir = get_workspace_root() / ".dev-dashboard"
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / "deployment_history.jsonl"



def _append_job_log(job_id: str, field: str, text: str) -> None:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        curr = job.get(field, "")
        if len(curr) > 40000:
            curr = curr[-30000:] + "\n... [truncated]\n"
        job[field] = curr + text


def _record_history_entry(job_id: str, chained_job_id: Optional[str] = None) -> None:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        started_at = job.get("started_at")
        finished_at = job.get("finished_at") or time.time()
        duration_sec = int(finished_at - started_at) if started_at else None

        # Build concise excerpts for frontend history view
        err_raw = (job.get("error") or "").strip()
        out_raw = (job.get("output") or "").strip()
        error_excerpt = "\n".join(err_raw.splitlines()[-10:]) if err_raw else ""
        output_excerpt = "\n".join(out_raw.splitlines()[-10:]) if out_raw else ""

        entry = {
            "id": job["id"],
            "app": job.get("app"),
            "command": job.get("command"),
            "status": job.get("status"),
            "returnCode": job.get("return_code"),
            "startedAt": started_at,
            "finishedAt": finished_at,
            "completedAt": int(finished_at * 1000) if finished_at else None,
            "durationSeconds": duration_sec,
            "env": job.get("env"),
            "flavor": job.get("flavor") or job.get("env"),
            "templateId": job.get("template_id"),
            "chainedJobId": chained_job_id or job.get("chained_job_id"),
            "errorExcerpt": error_excerpt,
            "outputExcerpt": output_excerpt,
            "artifact": job.get("artifact"),
            "buildSize": job.get("buildSize"),
        }

    history_file = _get_history_file()
    with _HISTORY_LOCK:
        try:
            with history_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
            if history_file.exists():
                lines = history_file.read_text(encoding="utf-8").splitlines()
                if len(lines) > 1000:
                    history_file.write_text("\n".join(lines[-1000:]) + "\n", encoding="utf-8")
        except Exception:
            logging.exception("Failed to write deployment history entry")


def _release_auto_chain_configured(app: str, env: str) -> tuple[bool, str]:
    """Settings from Configure → Release: run a release action after a successful upload."""
    app_cfg = load_deploy_config().get("apps", {}).get(app, {})
    enabled = bool(app_cfg.get("auto_release_on_success") or app_cfg.get("auto_release_tag"))
    if not enabled:
        return False, ""
    flavors = [str(f).lower() for f in (app_cfg.get("auto_release_flavors") or ["prod"])]
    # Apps without flavors build as "default"; treat them as their production flavor.
    env_l = (env or "").lower()
    if env_l not in flavors and not (env_l in ("default", "any", "") and "prod" in flavors):
        return False, ""
    action = str(app_cfg.get("auto_release_action") or "release_push")
    if not action.startswith("release_"):
        return False, ""
    return True, action


def _trigger_chained_release(app: str, env: str, action_id: str, parent_job_id: str) -> None:
    target_cmd = None
    for c in get_commands(app).get("commands", []):
        if c.get("templateId") == action_id:
            target_cmd = c
            break

    if not target_cmd:
        _record_history_entry(parent_job_id)
        return

    _record_history_entry(parent_job_id)
    execute_command(
        app=app,
        command=target_cmd["key"],
        runner=target_cmd.get("runner", "custom"),
        env=env,
        template_id=action_id,
        flavor=env,
        confirmed=True,
        _assume_app_lock_held=True,
        chained_parent_id=parent_job_id,
    )


def execute_command(
    app: str,
    command: str,
    runner: str = "make",
    env: str = "",
    template_id: str = "",
    flavor: str = "",
    confirmed: bool = False,
    _assume_app_lock_held: bool = False,
    chained_parent_id: Optional[str] = None,
    response_url: Optional[str] = None,
) -> dict[str, Any]:
    if not app or not command:
        return {"success": False, "error": "App and command are required"}

    if not SAFE_ID_PATTERN.match(app):
        return {"success": False, "error": f"Invalid app ID '{app}'. Must match ^[A-Za-z0-9._-]+$"}

    if flavor and not SAFE_ID_PATTERN.match(flavor):
        return {"success": False, "error": f"Invalid flavor parameter '{flavor}'. Must match ^[A-Za-z0-9._-]+$"}

    if env:
        if not SAFE_ID_PATTERN.match(env):
            return {"success": False, "error": f"Invalid env parameter '{env}'. Must match ^[A-Za-z0-9._-]+$"}
        if command.rstrip().endswith(" any"):
            command = command.rstrip()[: -len(" any")] + f" {shlex.quote(env)}"

    if _is_prod_store_deploy(template_id=template_id, flavor=flavor) and not confirmed:
        return {
            "success": False,
            "error": f"This runs a PROD store deploy for '{app}' - resend with confirmed: true once explicitly approved.",
            "needsConfirmation": True,
        }

    ws_root = get_workspace_root()
    is_cloud_runner = (runner == "github_actions")
    lock_key = f"{ws_root.resolve()}:{app}:cloud" if is_cloud_runner else f"{ws_root.resolve()}:{app}"

    if not _assume_app_lock_held:
        with _JOBS_LOCK:
            existing = _APP_LOCKS.get(lock_key) if is_cloud_runner else (_APP_LOCKS.get(lock_key) or _APP_LOCKS.get(app))
            if existing is not None:
                started_at = existing.get("started_at")
                elapsed_sec = int(time.time() - started_at) if started_at else None
                if elapsed_sec is not None:
                    if elapsed_sec >= 60:
                        m, s = divmod(elapsed_sec, 60)
                        elapsed_str = f"running for {m}m {s}s" if s else f"running for {m}m"
                    else:
                        elapsed_str = f"running for {elapsed_sec}s"
                else:
                    elapsed_str = "running"

                prefix = "A GitHub Actions cloud job" if is_cloud_runner else "A deployment job"
                return {
                    "success": False,
                    "error": (
                        f"{prefix} is already running for '{app}' "
                        f"({existing.get('flavor') or 'any flavor'}) ({elapsed_str}): {existing.get('command')}. "
                        "Wait for it to finish, check the History tab, or stop it before starting another."
                    ),
                    "code": "APP_BUSY",
                    "runningJob": {
                        "jobId": existing.get("job_id"),
                        "flavor": existing.get("flavor"),
                        "command": existing.get("command"),
                        "startedAt": existing.get("started_at"),
                        "elapsedSeconds": elapsed_sec,
                    },
                }
            _APP_LOCKS[lock_key] = {
                "job_id": None,
                "flavor": flavor,
                "command": command,
                "started_at": time.time(),
                "workspace": str(ws_root.resolve()),
                "app": app,
                "runner": runner,
            }

    try:
        TMP_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        logging.exception("Failed to create temporary directory")

    child_env = os.environ.copy()
    child_env["TMPDIR"] = str(TMP_DIR)
    child_env["TMP"] = str(TMP_DIR)
    child_env["TEMP"] = str(TMP_DIR)
    child_env["DASHBOARD_SCRIPTS_PATH"] = str(FEATURE_DIR / "scripts")
    child_env["DEPLOYMENT_PYTHON"] = sys.executable
    child_env["WORKSPACE_ROOT"] = str(get_workspace_root())
    child_env.update(credentials_job_env(app))

    if runner == "custom":
        shell_bin = shutil.which("bash") or shutil.which("zsh") or os.environ.get("SHELL") or "/bin/sh"
        cmd = [shell_bin, "-c", command]
        cmd_str = command
    elif runner == "melos":
        cmd = ["melos", "run", command]
        cmd_str = f"melos run {command}"
    else:
        cmd = ["make", command]
        cmd_str = f"make {command}"

    _prune_jobs()
    job_id = _new_job_id()

    if is_cloud_runner:
        import github_actions
        stop_event = threading.Event()
        cmd_str = f"github-actions dispatch {template_id or command} ({flavor or 'prod'})"
        with _JOBS_LOCK:
            _JOBS[job_id] = {
                "id": job_id,
                "command": cmd_str,
                "status": "running",
                "return_code": None,
                "output": "",
                "error": "",
                "pid": None,
                "pgid": None,
                "process": None,
                "stop_event": stop_event,
                "app": app,
                "template_id": template_id,
                "env": env,
                "flavor": flavor or env,
                "chained_job_id": chained_parent_id,
                "is_pipeline_step": bool(_assume_app_lock_held),
                "started_at": time.time(),
                "workspace": str(ws_root.resolve()),
                "runner": "github_actions",
                "response_url": response_url,
            }
            lock_entry = _APP_LOCKS.get(lock_key)
            if lock_entry is not None:
                lock_entry["job_id"] = job_id
                lock_entry["command"] = cmd_str
            else:
                _APP_LOCKS[lock_key] = {
                    "job_id": job_id,
                    "flavor": flavor,
                    "command": cmd_str,
                    "started_at": time.time(),
                    "workspace": str(ws_root.resolve()),
                    "app": app,
                    "runner": "github_actions",
                }

        def finish_cloud_job(return_code: int = 0, artifact_path: Optional[str] = None) -> None:
            finished_ts = time.time()
            with _JOBS_LOCK:
                job = _JOBS.get(job_id)
                if not job:
                    return
                job["return_code"] = return_code
                status = "stopped" if job.get("status") == "stopping" else ("success" if return_code == 0 else "error")
                job["status"] = status
                job["finished_at"] = finished_ts
                if artifact_path:
                    job["artifact"] = artifact_path
                if not _assume_app_lock_held:
                    held = _APP_LOCKS.get(lock_key)
                    if held is not None and (held.get("job_id") == job_id or held.get("job_id") is None):
                        _APP_LOCKS.pop(lock_key, None)

            _record_history_entry(job_id)
            try:
                import notifications
                with _JOBS_LOCK:
                    finished_job_copy = dict(_JOBS.get(job_id) or {})
                notifications.notify_job_finished(finished_job_copy)
            except Exception:
                logging.exception("Failed to dispatch outgoing notification for cloud job %s", job_id)
            _prune_jobs()

        def worker_target() -> None:
            github_actions.run_github_job_worker(
                job_id=job_id,
                app=app,
                flavor=flavor or "prod",
                template_id=template_id,
                command=command,
                ws_root=ws_root,
                append_log_fn=_append_job_log,
                finish_job_fn=finish_cloud_job,
                stop_event=stop_event,
            )

        _start_in_context(worker_target)
        return {"success": True, "jobId": job_id, "command": cmd_str}
    try:
        process = subprocess.Popen(
            cmd,
            cwd=get_workspace_root(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            start_new_session=True,
            bufsize=0,
            env=child_env,
        )
    except Exception as exc:
        if not _assume_app_lock_held:
            with _JOBS_LOCK:
                _APP_LOCKS.pop(lock_key, None)
                _APP_LOCKS.pop(app, None)
        return {"success": False, "error": str(exc)}

    with _JOBS_LOCK:
        _JOBS[job_id] = {
            "id": job_id,
            "command": cmd_str,
            "status": "running",
            "return_code": None,
            "output": "",
            "error": "",
            "pid": process.pid,
            "pgid": process.pid,
            "process": process,
            "app": app,
            "template_id": template_id,
            "env": env,
            "flavor": flavor or env,
            "chained_job_id": chained_parent_id,
            "is_pipeline_step": bool(_assume_app_lock_held),
            "started_at": time.time(),
            "workspace": str(ws_root.resolve()),
            "response_url": response_url,
        }
        lock_entry = _APP_LOCKS.get(lock_key) or _APP_LOCKS.get(app)
        if lock_entry is not None:
            lock_entry["job_id"] = job_id
            lock_entry["command"] = cmd_str
            lock_entry["workspace"] = str(ws_root.resolve())
            lock_entry["app"] = app
        else:
            _APP_LOCKS[lock_key] = {
                "job_id": job_id,
                "flavor": flavor,
                "command": cmd_str,
                "started_at": time.time(),
                "workspace": str(ws_root.resolve()),
                "app": app,
            }

    def stream_pipe(pipe, field: str) -> None:
        try:
            if pipe is None:
                return
            while True:
                line = pipe.readline()
                if not line:
                    break
                try:
                    text = line.decode("utf-8")
                except UnicodeDecodeError:
                    text = line.decode("utf-8", errors="replace")
                _append_job_log(job_id, field, text)
        finally:
            try:
                if pipe is not None:
                    pipe.close()
            except Exception:
                logging.exception("Failed to close process stream pipe")

    _start_in_context(stream_pipe, process.stdout, "output")
    _start_in_context(stream_pipe, process.stderr, "error")

    def finish_job() -> None:
        process.wait()
        finished_ts = time.time()
        with _JOBS_LOCK:
            job = _JOBS.get(job_id)
            if not job:
                return
            job["return_code"] = process.returncode
            status = "stopped" if job.get("status") == "stopping" else ("success" if process.returncode == 0 else "error")
            job["finished_at"] = finished_ts
            job.pop("process", None)
            if status == "success":
                try:
                    import build_size
                    bs_res = build_size.inspect_and_diff_job(job)
                    if bs_res:
                        out = job.get("output", "")
                        summary_box = f"\n📦 Build Size Inspector: {bs_res['summary']}\n"
                        if bs_res.get("warnings"):
                            summary_box += "".join(f"⚠️  {w}\n" for w in bs_res["warnings"])
                        job["output"] = (out + f"\n{summary_box}").lstrip()
                except Exception:
                    logging.exception("Failed to scan and diff build size")

        should_chain = False
        action_id = ""
        if chained_parent_id is None and status == "success" and template_id in STORE_UPLOAD_TEMPLATE_IDS:
            should_chain, action_id = _release_auto_chain_configured(app, env)

        with _JOBS_LOCK:
            job = _JOBS.get(job_id)
            if job:
                job["status"] = "chaining" if should_chain else status
            if not should_chain and not _assume_app_lock_held:
                held = _APP_LOCKS.get(lock_key) or _APP_LOCKS.get(app)
                if held is not None and (held.get("job_id") == job_id or held.get("job_id") is None):
                    _APP_LOCKS.pop(lock_key, None)
                    _APP_LOCKS.pop(app, None)

        if should_chain:
            _trigger_chained_release(app, env, action_id, job_id)
        else:
            _record_history_entry(job_id)
            try:
                import notifications
                with _JOBS_LOCK:
                    finished_job_copy = dict(_JOBS.get(job_id) or {})
                notifications.notify_job_finished(finished_job_copy)
            except Exception:
                logging.exception("Failed to dispatch outgoing notification for job %s", job_id)

        _prune_jobs()

    _start_in_context(finish_job)
    return {"success": True, "jobId": job_id, "command": cmd_str}


def get_running_jobs() -> list[dict[str, Any]]:
    """Return all currently running jobs across all workspaces (C8 fix)."""
    with _JOBS_LOCK:
        running = []
        for lock_k, info in list(_APP_LOCKS.items()):
            if isinstance(info, dict) and info.get("job_id"):
                running.append({
                    "jobId": info.get("job_id"),
                    "app": info.get("app"),
                    "flavor": info.get("flavor"),
                    "command": info.get("command"),
                    "startedAt": info.get("started_at"),
                    "workspace": info.get("workspace"),
                    "elapsedSeconds": int(time.time() - info["started_at"]) if info.get("started_at") else 0,
                })
        return running


def get_job(job_id: Optional[str]) -> dict[str, Any]:
    if not job_id:
        return {"success": False, "error": "Missing job id"}
    with _JOBS_LOCK:
        job = _JOBS.get(str(job_id))
        if not job:
            return {"success": False, "error": "Job not found"}
        payload = {k: v for k, v in job.items() if k not in ("process", "stop_event")}
    return {"success": True, "job": payload}


def stop_job(job_id: Optional[str]) -> dict[str, Any]:
    if not job_id:
        return {"success": False, "error": "Missing jobId"}

    with _JOBS_LOCK:
        job = _JOBS.get(str(job_id))
        if not job:
            return {"success": False, "error": "Job not found"}
        process = job.get("process")
        stop_event = job.get("stop_event")
        if process is None and stop_event is None:
            return {"success": False, "error": "Job is not running"}
        job["status"] = "stopping"
        if stop_event is not None:
            stop_event.set()
            return {"success": True, "message": "Cloud job cancellation requested"}

    try:
        pgid = job.get("pgid")
        if pgid:
            os.killpg(int(pgid), signal.SIGTERM)
        else:
            process.terminate()
    except Exception:
        logging.exception("Failed to terminate job process")

    def kill_later() -> None:
        try:
            process.wait(timeout=5)
        except Exception:
            try:
                pgid = job.get("pgid")
                if pgid:
                    os.killpg(int(pgid), signal.SIGKILL)
                else:
                    process.kill()
            except Exception:
                logging.exception("Failed to force-kill job process")

    threading.Thread(target=kill_later, daemon=True).start()
    return {"success": True, "message": "Stop requested"}


def get_deployment_history(limit: int = 50, app: str = "", flavor: str = "", status: str = "") -> dict[str, Any]:
    results: list[dict[str, Any]] = []

    def scan_file(fpath: Path) -> None:
        if not fpath.exists():
            return
        try:
            lines = fpath.read_text(encoding="utf-8").splitlines()
        except Exception:
            return
        for raw in reversed(lines):
            if len(results) >= limit:
                return
            raw = raw.strip()
            if not raw:
                continue
            try:
                entry = json.loads(raw)
            except Exception:
                continue
            if app and entry.get("app") != app:
                continue
            entry_flavor = entry.get("flavor") or entry.get("env")
            if flavor and entry_flavor != flavor:
                continue
            if status and entry.get("status") != status:
                continue
            results.append(entry)

    history_file = _get_history_file()
    with _HISTORY_LOCK:
        scan_file(history_file)
        if len(results) < limit:
            scan_file(history_file.parent / (history_file.name + ".1"))

    return {"success": True, "entries": results, "count": len(results)}


def check_ios_expiry(app: str, flavor: str = "prod") -> dict[str, Any]:
    """Check Apple iOS certificate and provisioning profile expiration.

    Delegates to sentinel.apple_sentinel.
    """
    try:
        from .sentinel.apple_sentinel import check_ios_expiry as _check_ios_expiry
    except (ImportError, ValueError):
        from sentinel.apple_sentinel import check_ios_expiry as _check_ios_expiry
    return _check_ios_expiry(app, flavor=flavor)

