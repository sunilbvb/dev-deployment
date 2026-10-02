"""Toolchain and system environment checks (Flutter, Git, Bash, Melos)."""

from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess
from typing import Any


def _check_tool(cmd: str, flag: str = "--version", timeout: float = 2.5) -> dict[str, Any]:
    """Locate executable and retrieve its version output."""
    path = shutil.which(cmd)
    if not path:
        return {"available": False, "path": None, "version": None, "raw": None}
    try:
        res = subprocess.run([cmd, flag], capture_output=True, text=True, timeout=timeout)
        raw = (res.stdout or res.stderr or "").strip()
        first_line = raw.splitlines()[0] if raw else "available"
        return {"available": True, "path": path, "version": first_line, "raw": raw}
    except Exception as exc:
        return {"available": True, "path": path, "version": "available", "raw": str(exc)}


def _check_flutter_sdk() -> dict[str, Any]:
    """Check Flutter SDK availability, version, channel, and Dart version."""
    path = shutil.which("flutter")
    if not path:
        return {
            "id": "flutter_sdk",
            "category": "toolchain",
            "name": "Flutter SDK",
            "status": "fail",
            "message": "Flutter CLI not found in PATH",
            "hint": "Install Flutter SDK and ensure 'flutter/bin' is added to your PATH.",
        }

    try:
        res = subprocess.run(["flutter", "--version"], capture_output=True, text=True, timeout=3.5)
        raw = (res.stdout or res.stderr or "").strip()
        lines = raw.splitlines()
        first_line = lines[0] if lines else "Flutter available"

        version_match = re.search(r"Flutter\s+([0-9]+\.[0-9]+\.[0-9]+[^\s]*)", raw)
        channel_match = re.search(r"channel\s+([a-zA-Z0-9_-]+)", raw)
        dart_match = re.search(r"Dart\s+([0-9]+\.[0-9]+\.[0-9]+[^\s]*)", raw)

        flutter_ver = version_match.group(1) if version_match else ""
        channel = channel_match.group(1) if channel_match else ""
        dart_ver = dart_match.group(1) if dart_match else ""

        detail_parts = []
        if flutter_ver:
            detail_parts.append(f"v{flutter_ver}")
        if channel:
            detail_parts.append(f"channel {channel}")
        if dart_ver:
            detail_parts.append(f"Dart {dart_ver}")

        detail_str = " • ".join(detail_parts) if detail_parts else first_line

        return {
            "id": "flutter_sdk",
            "category": "toolchain",
            "name": "Flutter SDK",
            "status": "pass",
            "message": f"Flutter {detail_str}",
            "path": path,
            "version": flutter_ver or first_line,
            "dartVersion": dart_ver,
            "channel": channel,
        }
    except Exception as exc:
        return {
            "id": "flutter_sdk",
            "category": "toolchain",
            "name": "Flutter SDK",
            "status": "pass",
            "message": f"Flutter available at {path} (version check timed out)",
            "path": path,
            "version": "available",
            "raw": str(exc),
        }


def _check_toolchain(ws_root: Path) -> list[dict[str, Any]]:
    """Check base CLI utilities: Flutter, Git, Bash, Melos."""
    checks = []

    # 1. Flutter SDK
    checks.append(_check_flutter_sdk())

    # 2. Git
    git_info = _check_tool("git")
    if git_info["available"]:
        checks.append({
            "id": "git_cli",
            "category": "toolchain",
            "name": "Git CLI",
            "status": "pass",
            "message": git_info["version"] or "Git available",
            "path": git_info["path"],
        })
    else:
        checks.append({
            "id": "git_cli",
            "category": "toolchain",
            "name": "Git CLI",
            "status": "fail",
            "message": "Git executable not found in PATH",
            "hint": "Install Git using your system package manager (e.g. apt install git or brew install git).",
        })

    # 3. Bash
    bash_path = shutil.which("bash")
    if bash_path:
        checks.append({
            "id": "bash_shell",
            "category": "toolchain",
            "name": "Bash Shell",
            "status": "pass",
            "message": f"Bash available ({bash_path})",
            "path": bash_path,
        })
    else:
        checks.append({
            "id": "bash_shell",
            "category": "toolchain",
            "name": "Bash Shell",
            "status": "fail",
            "message": "Bash shell not found in PATH",
            "hint": "Bash is required to execute deployment scripts.",
        })

    # 4. Melos (optional monorepo tool)
    melos_file = ws_root / "melos.yaml"
    melos_info = _check_tool("melos")
    if melos_info["available"]:
        checks.append({
            "id": "melos_cli",
            "category": "toolchain",
            "name": "Melos CLI",
            "status": "pass",
            "message": f"Melos available ({melos_info['version'] or 'installed'})",
            "path": melos_info["path"],
        })
    elif melos_file.exists():
        checks.append({
            "id": "melos_cli",
            "category": "toolchain",
            "name": "Melos CLI",
            "status": "warn",
            "message": "Workspace defines melos.yaml but 'melos' CLI is not found in PATH.",
            "hint": "Install melos globally: dart pub global activate melos",
        })

    return checks


def _check_git_status(target_dir: Path) -> list[dict[str, Any]]:
    """Check Git working tree cleanliness, branch name, and upstream sync."""
    checks = []
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        if res.returncode != 0 or res.stdout.strip() != "true":
            checks.append({
                "id": "git_repo",
                "category": "git",
                "name": "Git Repository",
                "status": "info",
                "message": "Not a Git repository (or git not initialized).",
            })
            return checks
    except Exception:
        checks.append({
            "id": "git_repo",
            "category": "git",
            "name": "Git Repository",
            "status": "info",
            "message": "Git status check skipped.",
        })
        return checks

    # 1. Branch name
    try:
        branch_res = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        branch = branch_res.stdout.strip()
        if branch == "HEAD":
            checks.append({
                "id": "git_branch",
                "category": "git",
                "name": "Git Branch",
                "status": "warn",
                "message": "Detached HEAD state. Releases should be tagged from a named branch (e.g. main/develop).",
                "hint": "Switch to a valid branch: git checkout <branch-name>",
            })
        elif branch:
            checks.append({
                "id": "git_branch",
                "category": "git",
                "name": "Git Branch",
                "status": "pass",
                "message": f"Active branch: {branch}",
                "branch": branch,
            })
    except Exception as exc:
        checks.append({
            "id": "git_branch",
            "category": "git",
            "name": "Git Branch",
            "status": "info",
            "message": f"Could not determine branch: {exc}",
        })

    # 2. Dirty tree check
    try:
        stat_res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        dirty_lines = [item for item in (stat_res.stdout or "").splitlines() if item.strip()]
        if dirty_lines:
            untracked = sum(1 for item in dirty_lines if item.startswith("??"))
            modified = len(dirty_lines) - untracked
            checks.append({
                "id": "git_dirty",
                "category": "git",
                "name": "Working Tree Status",
                "status": "warn",
                "message": f"{len(dirty_lines)} uncommitted file(s) ({modified} modified, {untracked} untracked).",
                "hint": "Recommended to commit or stash uncommitted changes before production releases: git status",
            })
        else:
            checks.append({
                "id": "git_dirty",
                "category": "git",
                "name": "Working Tree Status",
                "status": "pass",
                "message": "Clean working tree (no uncommitted or untracked changes)",
            })
    except Exception as exc:
        checks.append({
            "id": "git_dirty",
            "category": "git",
            "name": "Working Tree Status",
            "status": "info",
            "message": f"Could not check working tree: {exc}",
        })

    # 3. Upstream sync check
    try:
        sync_res = subprocess.run(
            ["git", "rev-list", "--left-right", "--count", "HEAD...@{upstream}"],
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        if sync_res.returncode == 0:
            counts = sync_res.stdout.strip().split()
            if len(counts) == 2:
                ahead, behind = int(counts[0]), int(counts[1])
                if ahead > 0 and behind > 0:
                    checks.append({
                        "id": "git_sync",
                        "category": "git",
                        "name": "Remote Sync",
                        "status": "warn",
                        "message": f"Branch has diverged from remote ({ahead} ahead, {behind} behind).",
                        "hint": "Pull and rebase or merge remote changes: git pull --rebase",
                    })
                elif ahead > 0:
                    checks.append({
                        "id": "git_sync",
                        "category": "git",
                        "name": "Remote Sync",
                        "status": "warn",
                        "message": f"Local branch has {ahead} unpushed commit(s) ahead of remote.",
                        "hint": "Push commits before creating release tags: git push",
                    })
                else:
                    checks.append({
                        "id": "git_sync",
                        "category": "git",
                        "name": "Remote Sync",
                        "status": "pass",
                        "message": "Local branch is up to date with remote tracking branch.",
                    })
    except Exception:
        pass

    return checks
