"""
GitHub Actions Hybrid Cloud Dispatcher & Artifact Synchronizer.

Enables hybrid distributed builds:
- Offloads Android compilation to GitHub Actions (free Ubuntu Linux runners).
- Allows concurrent local iOS compilation (Apple Silicon Mac) without CPU/RAM lockups.
- Streams GitHub Actions run status and downloads build artifacts (APK/AAB) back to the local
  console so QR code scan-to-install works seamlessly.

Pure Python standard library (0 external dependencies).
"""

import json
import logging
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Callable, Optional

from config import get_workspace_root

_CONFIG_DIR = Path.home() / ".config" / "dev-deployment"
_GITHUB_TOKEN_FILE = _CONFIG_DIR / "github_token.txt"
_GITHUB_REPO_OVERRIDE_FILE = _CONFIG_DIR / "github_repo.txt"


def get_stored_github_token() -> Optional[str]:
    """Retrieve GitHub Personal Access Token from env, file, or local gh CLI."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token and token.strip():
        return token.strip()

    if _GITHUB_TOKEN_FILE.exists():
        try:
            stored = _GITHUB_TOKEN_FILE.read_text(encoding="utf-8").strip()
            if stored:
                return stored
        except Exception:
            logging.exception("Failed to read stored GitHub token")

    # Fallback to local gh CLI auth token if installed
    gh_bin = shutil.which("gh")
    if gh_bin:
        try:
            res = subprocess.run(
                [gh_bin, "auth", "token"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except Exception:
            pass

    return None


def save_github_token(token: str) -> bool:
    """Securely save GitHub token with 0600 permissions."""
    token = token.strip()
    try:
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        _GITHUB_TOKEN_FILE.write_text(token, encoding="utf-8")
        try:
            _GITHUB_TOKEN_FILE.chmod(0o600)
        except Exception:
            pass
        return True
    except Exception:
        logging.exception("Failed to save GitHub token")
        return False


def get_stored_repo_override() -> Optional[str]:
    if _GITHUB_REPO_OVERRIDE_FILE.exists():
        try:
            v = _GITHUB_REPO_OVERRIDE_FILE.read_text(encoding="utf-8").strip()
            if v:
                return v
        except Exception:
            pass
    return None


def save_repo_override(repo: str) -> bool:
    repo = repo.strip()
    try:
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if repo:
            _GITHUB_REPO_OVERRIDE_FILE.write_text(repo, encoding="utf-8")
        elif _GITHUB_REPO_OVERRIDE_FILE.exists():
            _GITHUB_REPO_OVERRIDE_FILE.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def detect_github_repo(app_dir: Optional[Path] = None) -> Optional[str]:
    """
    Detect 'owner/repo' from git origin remote or manual override.
    Supports SSH (git@github.com:owner/repo.git) and HTTPS (https://github.com/owner/repo.git).
    """
    override = get_stored_repo_override()
    if override:
        return override

    target_dir = app_dir or get_workspace_root()
    if not (target_dir / ".git").exists() and (get_workspace_root() / ".git").exists():
        target_dir = get_workspace_root()

    try:
        res = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=target_dir,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode != 0 or not res.stdout.strip():
            return None

        url = res.stdout.strip()
        # Parse SSH: git@github.com:owner/repo.git
        ssh_match = re.search(r"github\.com[:/]([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?$", url)
        if ssh_match:
            return ssh_match.group(1)

        # Parse HTTPS: https://github.com/owner/repo(.git)
        https_match = re.search(r"https?://(?:[^@/]+@)?github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?/?$", url)
        if https_match:
            return https_match.group(1)
    except Exception:
        pass

    return None


def detect_git_branch(target_dir: Optional[Path] = None) -> str:
    """Determine current Git branch name."""
    root = target_dir or get_workspace_root()
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode == 0 and res.stdout.strip() and res.stdout.strip() != "HEAD":
            return res.stdout.strip()
    except Exception:
        pass
    return "develop"


def _github_api_request(
    endpoint: str,
    method: str = "GET",
    data: Optional[dict[str, Any]] = None,
    token: Optional[str] = None,
) -> tuple[int, Any]:
    """Execute authenticated GitHub REST API request with standard urllib."""
    auth_token = token or get_stored_github_token()
    if not auth_token:
        return 401, {"message": "GitHub Personal Access Token not configured"}

    url = f"https://api.github.com{endpoint}" if endpoint.startswith("/") else f"https://api.github.com/{endpoint}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {auth_token}",
        "User-Agent": "dev-deployment-console/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    body = None
    if data is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
            resp_body = resp.read()
            if not resp_body:
                return status, {}
            try:
                return status, json.loads(resp_body.decode("utf-8"))
            except Exception:
                return status, {"raw": resp_body}
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        try:
            err_data = json.loads(err_body)
        except Exception:
            err_data = {"message": err_body}
        return exc.code, err_data
    except Exception as exc:
        return 500, {"message": str(exc)}


def dispatch_workflow(
    repo: str,
    workflow_id_or_file: str,
    ref: str = "develop",
    inputs: Optional[dict[str, Any]] = None,
    token: Optional[str] = None,
) -> dict[str, Any]:
    """Trigger a workflow_dispatch event on GitHub Actions."""
    endpoint = f"/repos/{repo}/actions/workflows/{workflow_id_or_file}/dispatches"
    payload = {
        "ref": ref,
        "inputs": {k: str(v) for k, v in (inputs or {}).items()},
    }

    status, resp = _github_api_request(endpoint, method="POST", data=payload, token=token)
    if status == 204:
        return {"success": True, "message": f"Workflow {workflow_id_or_file} dispatched successfully."}
    return {
        "success": False,
        "status": status,
        "error": resp.get("message") or f"GitHub API error (HTTP {status})",
    }


def cancel_workflow_run(repo: str, run_id: int, token: Optional[str] = None) -> bool:
    """Request cancellation of a running workflow run."""
    endpoint = f"/repos/{repo}/actions/runs/{run_id}/cancel"
    status, _ = _github_api_request(endpoint, method="POST", token=token)
    return status in (202, 204)


def get_latest_workflow_run(
    repo: str,
    workflow_id_or_file: str,
    ref: Optional[str] = None,
    token: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Find the most recent workflow run for given workflow and ref."""
    endpoint = f"/repos/{repo}/actions/workflows/{workflow_id_or_file}/runs?per_page=5"
    if ref:
        endpoint += f"&branch={ref}"

    status, resp = _github_api_request(endpoint, method="GET", token=token)
    if status != 200 or not isinstance(resp, dict):
        return None

    runs = resp.get("workflow_runs", [])
    return runs[0] if runs else None


def get_run_status(repo: str, run_id: int, token: Optional[str] = None) -> dict[str, Any]:
    """Fetch status and conclusion of a workflow run."""
    endpoint = f"/repos/{repo}/actions/runs/{run_id}"
    status, resp = _github_api_request(endpoint, method="GET", token=token)
    if status == 200 and isinstance(resp, dict):
        return {
            "success": True,
            "id": resp.get("id"),
            "status": resp.get("status"),  # queued, in_progress, completed
            "conclusion": resp.get("conclusion"),  # success, failure, cancelled
            "html_url": resp.get("html_url"),
            "name": resp.get("name"),
            "event": resp.get("event"),
            "created_at": resp.get("created_at"),
            "updated_at": resp.get("updated_at"),
        }
    return {"success": False, "error": resp.get("message") or f"HTTP {status}"}


def list_run_artifacts(repo: str, run_id: int, token: Optional[str] = None) -> list[dict[str, Any]]:
    """List downloadable artifacts generated by a workflow run."""
    endpoint = f"/repos/{repo}/actions/runs/{run_id}/artifacts"
    status, resp = _github_api_request(endpoint, method="GET", token=token)
    if status == 200 and isinstance(resp, dict):
        return resp.get("artifacts", [])
    return []


def download_artifact_file(
    repo: str,
    artifact_id: int,
    dest_dir: Path,
    token: Optional[str] = None,
) -> Optional[Path]:
    """Download ZIP artifact from GitHub Actions and extract APK/AAB inside dest_dir."""
    auth_token = token or get_stored_github_token()
    if not auth_token:
        return None

    url = f"https://api.github.com/repos/{repo}/actions/artifacts/{artifact_id}/zip"
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "User-Agent": "dev-deployment-console/1.0",
        "Accept": "application/vnd.github+json",
    }
    req = urllib.request.Request(url, headers=headers)

    dest_dir.mkdir(parents=True, exist_ok=True)
    temp_zip = dest_dir / f"artifact_{artifact_id}.zip"

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            with temp_zip.open("wb") as out:
                while chunk := resp.read(65536):
                    out.write(chunk)

        with zipfile.ZipFile(temp_zip, "r") as zf:
            for member in zf.namelist():
                if member.endswith(".apk") or member.endswith(".aab"):
                    extracted = zf.extract(member, dest_dir)
                    try:
                        temp_zip.unlink(missing_ok=True)
                    except Exception:
                        pass
                    return Path(extracted)
    except Exception:
        logging.exception("Failed to download or extract GitHub Actions artifact")
    finally:
        try:
            if temp_zip.exists():
                temp_zip.unlink(missing_ok=True)
        except Exception:
            pass

    return None


def get_android_workflow_template() -> str:
    """Return standard GitHub Actions workflow YAML for building Android APK/AAB."""
    return """name: Build & Package Android (Hybrid Cloud Runner)

on:
  workflow_dispatch:
    inputs:
      flavor:
        description: 'Target Flavor / Environment'
        required: true
        default: 'prod'
        type: choice
        options:
          - dev
          - qa
          - prod
      build_type:
        description: 'Output Package Type'
        required: true
        default: 'apk'
        type: choice
        options:
          - apk
          - aab
      callback_url:
        description: 'Optional callback webhook URL to notify deployment console'
        required: false
        type: string

jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 45

    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Set up Java Development Kit (JDK 17)
        uses: actions/setup-java@v4
        with:
          distribution: 'temurin'
          java-version: '17'
          cache: 'gradle'

      - name: Set up Flutter SDK
        uses: subosito/flutter-action@v2
        with:
          channel: 'stable'
          cache: true

      - name: Install Project Dependencies
        run: flutter pub get

      - name: Decode Android Keystore
        if: env.ANDROID_KEYSTORE_BASE64 != ''
        env:
          ANDROID_KEYSTORE_BASE64: ${{ secrets.ANDROID_KEYSTORE_BASE64 }}
        run: |
          mkdir -p android/app/keystore
          echo "$ANDROID_KEYSTORE_BASE64" | base64 --decode > android/app/keystore/upload-keystore.jks

      - name: Build Android APK
        if: ${{ inputs.build_type == 'apk' }}
        run: flutter build apk --flavor ${{ inputs.flavor }} --release

      - name: Build Android App Bundle (AAB)
        if: ${{ inputs.build_type == 'aab' }}
        run: flutter build appbundle --flavor ${{ inputs.flavor }} --release

      - name: Upload Build Artifact
        uses: actions/upload-artifact@v4
        with:
          name: android-${{ inputs.flavor }}-${{ inputs.build_type }}
          path: |
            build/app/outputs/flutter-apk/*.apk
            build/app/outputs/bundle/*/*.aab
          retention-days: 14

      - name: Notify Deployment Console Webhook (Optional)
        if: always() && inputs.callback_url != ''
        run: |
          curl -s -X POST "${{ inputs.callback_url }}" \\
            -H "Content-Type: application/json" \\
            -d '{"status": "${{ job.status }}", "flavor": "${{ inputs.flavor }}", "build_type": "${{ inputs.build_type }}"}' || true
"""


def install_workflow_template(target_dir: Optional[Path] = None) -> tuple[bool, str]:
    """Write standard workflow file into target repository."""
    root = target_dir or get_workspace_root()
    wf_dir = root / ".github" / "workflows"
    wf_file = wf_dir / "deploy-android.yml"
    try:
        wf_dir.mkdir(parents=True, exist_ok=True)
        wf_file.write_text(get_android_workflow_template(), encoding="utf-8")
        return True, f"Installed workflow template at {wf_file.relative_to(root)}"
    except Exception as exc:
        return False, f"Failed to install workflow: {exc}"


def find_workflow_file(target_dir: Optional[Path] = None) -> str:
    """Find appropriate workflow filename in project."""
    root = target_dir or get_workspace_root()
    wf_dir = root / ".github" / "workflows"
    candidates = ["deploy-android.yml", "build-android.yml", "android.yml", "build.yml"]
    if wf_dir.is_dir():
        for c in candidates:
            if (wf_dir / c).exists():
                return c
    return "deploy-android.yml"


def run_github_job_worker(
    job_id: str,
    app: str,
    flavor: str,
    template_id: str,
    command: str,
    ws_root: Path,
    append_log_fn: Callable[[str, str, str], None],
    finish_job_fn: Callable[..., None],
    stop_event: threading.Event,
    token: Optional[str] = None,
    repo_override: Optional[str] = None,
    ref_override: Optional[str] = None,
) -> None:
    """
    Background worker thread executed when runner == 'github_actions'.
    Dispatches workflow, streams status into job terminal, and downloads artifact.
    """
    append_log_fn(job_id, "output", f"🚀 [GitHub Actions Hybrid Runner] Initializing cloud dispatch for '{app}'...\n")

    auth_token = token or get_stored_github_token()
    if not auth_token:
        append_log_fn(
            job_id,
            "error",
            "❌ [GitHub Actions] GitHub Personal Access Token not configured.\n"
            "   Add your token in Configure -> Cloud CI or export GITHUB_TOKEN.\n"
        )
        finish_job_fn(1)
        return

    repo = repo_override or detect_github_repo(ws_root)
    if not repo:
        append_log_fn(
            job_id,
            "error",
            "❌ [GitHub Actions] Could not detect GitHub repository from git remote 'origin'.\n"
            "   Ensure the project has a git remote or configure repository in Configure -> Cloud CI.\n"
        )
        finish_job_fn(1)
        return

    ref = ref_override or detect_git_branch(ws_root)
    workflow_file = find_workflow_file(ws_root)
    build_type = "aab" if ("aab" in template_id.lower() or "aab" in command.lower()) else "apk"
    target_flavor = flavor or "prod"

    append_log_fn(job_id, "output", f"📦 [GitHub Actions] Target Repository: {repo}\n")
    append_log_fn(job_id, "output", f"🌿 [GitHub Actions] Branch: {ref}\n")
    append_log_fn(job_id, "output", f"⚙️  [GitHub Actions] Workflow: .github/workflows/{workflow_file}\n")
    append_log_fn(job_id, "output", f"📋 [GitHub Actions] Inputs: flavor={target_flavor}, build_type={build_type}\n")
    append_log_fn(job_id, "output", "📡 [GitHub Actions] Dispatching workflow via GitHub REST API...\n")

    dispatch_res = dispatch_workflow(
        repo=repo,
        workflow_id_or_file=workflow_file,
        ref=ref,
        inputs={"flavor": target_flavor, "build_type": build_type},
        token=auth_token,
    )

    if not dispatch_res.get("success"):
        append_log_fn(job_id, "error", f"❌ [GitHub Actions] Dispatch failed: {dispatch_res.get('error')}\n")
        finish_job_fn(1)
        return

    append_log_fn(job_id, "output", "✓ [GitHub Actions] Workflow dispatched successfully (HTTP 204)!\n")
    append_log_fn(job_id, "output", "⏳ [GitHub Actions] Waiting for runner to pick up workflow run...\n")

    run_id: Optional[int] = None
    html_url = ""
    # Look for run up to 45 seconds
    for _ in range(9):
        if stop_event.is_set():
            append_log_fn(job_id, "output", "\n⚠️ [GitHub Actions] Cancelled by user.\n")
            finish_job_fn(130)
            return

        time.sleep(5)
        latest = get_latest_workflow_run(repo, workflow_file, ref=ref, token=auth_token)
        if latest and latest.get("id"):
            run_id = int(latest["id"])
            html_url = latest.get("html_url", "")
            break

    if not run_id:
        append_log_fn(
            job_id,
            "output",
            f"ℹ️  Workflow run was queued. Check status directly on GitHub: https://github.com/{repo}/actions\n"
        )
        finish_job_fn(0)
        return

    append_log_fn(job_id, "output", f"🔗 [GitHub Actions] Run #{run_id} started!\n   Live Web View: {html_url}\n")

    last_status = ""
    start_watch_ts = time.time()

    # Poll status until finished or stopped
    while not stop_event.is_set():
        time.sleep(6)
        run_info = get_run_status(repo, run_id, token=auth_token)
        if not run_info.get("success"):
            continue

        curr_status = run_info.get("status") or ""
        conclusion = run_info.get("conclusion")
        elapsed = int(time.time() - start_watch_ts)
        mins, secs = divmod(elapsed, 60)
        time_str = f"[{mins:02d}:{secs:02d}]"

        if curr_status != last_status:
            append_log_fn(job_id, "output", f"{time_str} Status changed: {curr_status.upper()}\n")
            last_status = curr_status

        if curr_status == "completed":
            if conclusion == "success":
                append_log_fn(job_id, "output", f"\n🎉 [GitHub Actions] Cloud build completed with SUCCESS! ({mins}m {secs}s)\n")
                # Look for artifacts to sync back locally
                append_log_fn(job_id, "output", "📦 [GitHub Actions] Inspecting build artifacts...\n")
                artifacts = list_run_artifacts(repo, run_id, token=auth_token)
                matched_art = None
                for a in artifacts:
                    aname = (a.get("name") or "").lower()
                    if "android" in aname or "apk" in aname or "aab" in aname:
                        matched_art = a
                        break
                if not matched_art and artifacts:
                    matched_art = artifacts[0]

                if matched_art:
                    art_id = matched_art.get("id")
                    art_name = matched_art.get("name")
                    append_log_fn(job_id, "output", f"📥 [GitHub Actions] Downloading artifact '{art_name}'...\n")
                    dest_dir = ws_root / "build" / "app" / "outputs" / ("bundle" if build_type == "aab" else "flutter-apk")
                    extracted = download_artifact_file(repo, art_id, dest_dir, token=auth_token)
                    if extracted and extracted.exists():
                        append_log_fn(job_id, "output", f"✓ [GitHub Actions] Artifact successfully extracted to: {extracted}\n")
                        finish_job_fn(0, artifact_path=str(extracted))
                        return

                finish_job_fn(0)
                return
            else:
                append_log_fn(job_id, "error", f"\n❌ [GitHub Actions] Run finished with failure conclusion: {conclusion}\n")
                finish_job_fn(1)
                return

    # If stop_event was triggered
    append_log_fn(job_id, "output", "\n⚠️ [GitHub Actions] Cancellation requested by user. Terminating cloud run...\n")
    if run_id:
        cancel_workflow_run(repo, run_id, token=auth_token)
    finish_job_fn(130)
