"""Smart Silent Cache Warmer for Mobile Builds.

Monitors Git branch switches, pulls, and dependency lockfile modifications.
Runs low-priority background `flutter pub get` & dependency pre-fetches
silently to eliminate cold-start lag when developers click Run.
Python standard library only.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
import subprocess
import threading
import time
from typing import Any, Optional


class CacheWarmer:
    def __init__(self, check_interval_sec: float = 15.0) -> None:
        self.check_interval_sec = check_interval_sec
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # State
        self.status = "idle"  # idle | checking | warming | warm | error
        self.last_warmed_at: Optional[float] = None
        self.last_duration_sec: Optional[float] = None
        self.last_branch: Optional[str] = None
        self.last_commit: Optional[str] = None
        self.last_lockfile_hash: Optional[str] = None
        self.last_error: Optional[str] = None
        self.warmed_count: int = 0
        self.is_enabled: bool = True

    def get_status(self) -> dict[str, Any]:
        """Return current status of the cache warmer."""
        with self._lock:
            formatted_time = None
            if self.last_warmed_at:
                formatted_time = time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(self.last_warmed_at)
                )
            return {
                "success": True,
                "status": self.status,
                "enabled": self.is_enabled,
                "lastWarmedAt": self.last_warmed_at,
                "lastWarmedFormatted": formatted_time,
                "lastDurationSeconds": self.last_duration_sec,
                "lastBranch": self.last_branch,
                "lastCommit": self.last_commit,
                "warmedCount": self.warmed_count,
                "lastError": self.last_error,
                "isWatching": bool(self._thread and self._thread.is_alive()),
            }

    def _get_workspace_root(self) -> Path:
        from config import get_workspace_root
        return get_workspace_root()

    def _get_git_info(self, ws_root: Path) -> tuple[Optional[str], Optional[str]]:
        """Read current branch and commit hash cleanly via Git."""
        try:
            head_proc = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(ws_root),
                capture_output=True,
                text=True,
                timeout=4,
                check=False,
            )
            branch = head_proc.stdout.strip() or None

            rev_proc = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=str(ws_root),
                capture_output=True,
                text=True,
                timeout=4,
                check=False,
            )
            commit = rev_proc.stdout.strip() or None
            return branch, commit
        except Exception:
            return None, None

    def _compute_lockfile_hash(self, ws_root: Path) -> str:
        """Compute MD5 hash across dependency files to detect changes."""
        hasher = hashlib.md5()
        target_names = [
            "pubspec.yaml",
            "pubspec.lock",
            "Podfile.lock",
            "package.json",
            "package-lock.json",
            "yarn.lock",
        ]
        found_any = False
        # Check in root and 1 level down
        cands: list[Path] = [ws_root / n for n in target_names]
        try:
            for child in ws_root.iterdir():
                if child.is_dir() and not child.name.startswith((".", "build")):
                    for n in target_names:
                        cands.append(child / n)
        except Exception:
            pass

        for p in cands:
            if p.is_file():
                found_any = True
                try:
                    st = p.stat()
                    # Hash path + mtime + size for speed without reading full bytes
                    hasher.update(f"{p.name}:{st.st_mtime}:{st.st_size}".encode("utf-8"))
                except Exception:
                    pass

        return hasher.hexdigest() if found_any else ""

    def _is_system_busy(self) -> bool:
        """Check if any deployment jobs or pipelines are currently executing."""
        try:
            import jobs
            if jobs.get_running_jobs():
                return True
        except Exception:
            pass
        return False

    def warm_cache_now(self, force: bool = False) -> dict[str, Any]:
        """Trigger an immediate cache warm pass."""
        ws_root = self._get_workspace_root()
        branch, commit = self._get_git_info(ws_root)
        lock_hash = self._compute_lockfile_hash(ws_root)

        with self._lock:
            if not force and branch == self.last_branch and commit == self.last_commit and lock_hash == self.last_lockfile_hash:
                return {
                    "success": True,
                    "warmed": False,
                    "reason": "Dependencies are already fresh and warmed.",
                    "status": self.status,
                }

        if self._is_system_busy():
            return {
                "success": True,
                "warmed": False,
                "reason": "Build job currently active; postponing warming.",
                "status": self.status,
            }

        with self._lock:
            self.status = "warming"

        start_time = time.time()
        actions_taken: list[str] = []
        error_msg: Optional[str] = None

        try:
            # 1. Flutter pub get
            pubspec = ws_root / "pubspec.yaml"
            if pubspec.is_file():
                # Low priority subprocess
                cmd = ["flutter", "pub", "get"]
                proc = subprocess.run(
                    cmd,
                    cwd=str(ws_root),
                    capture_output=True,
                    text=True,
                    timeout=90,
                    check=False,
                )
                if proc.returncode == 0:
                    actions_taken.append("flutter pub get in root")
                else:
                    error_msg = proc.stderr.strip() or "flutter pub get returned non-zero"

            # Check sub-apps
            try:
                for child in ws_root.iterdir():
                    if child.is_dir() and (child / "pubspec.yaml").is_file():
                        sub_proc = subprocess.run(
                            ["flutter", "pub", "get"],
                            cwd=str(child),
                            capture_output=True,
                            text=True,
                            timeout=90,
                            check=False,
                        )
                        if sub_proc.returncode == 0:
                            actions_taken.append(f"flutter pub get in {child.name}")
            except Exception:
                pass

        except subprocess.TimeoutExpired:
            error_msg = "Cache pre-fetch timed out."
        except Exception as exc:
            error_msg = str(exc)

        duration = round(time.time() - start_time, 2)

        with self._lock:
            self.last_warmed_at = time.time()
            self.last_duration_sec = duration
            self.last_branch = branch
            self.last_commit = commit
            self.last_lockfile_hash = lock_hash
            self.last_error = error_msg
            if error_msg:
                self.status = "error"
            else:
                self.status = "warm"
                self.warmed_count += 1

        return {
            "success": True,
            "warmed": len(actions_taken) > 0,
            "actions": actions_taken,
            "durationSeconds": duration,
            "branch": branch,
            "commit": commit,
            "error": error_msg,
            "status": self.status,
        }

    def _daemon_loop(self) -> None:
        """Background monitoring loop."""
        while not self._stop_event.is_set():
            try:
                if self.is_enabled and not self._is_system_busy():
                    ws_root = self._get_workspace_root()
                    branch, commit = self._get_git_info(ws_root)
                    lock_hash = self._compute_lockfile_hash(ws_root)

                    needs_warm = False
                    with self._lock:
                        if branch and (branch != self.last_branch or commit != self.last_commit or lock_hash != self.last_lockfile_hash):
                            needs_warm = True

                    if needs_warm:
                        self.warm_cache_now(force=True)
            except Exception:
                logging.exception("Error during CacheWarmer daemon cycle")

            self._stop_event.wait(self.check_interval_sec)

    def start_daemon(self) -> None:
        """Start the background cache warmer watcher thread."""
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._daemon_loop,
                name="CacheWarmerDaemon",
                daemon=True,
            )
            self._thread.start()

    def stop_daemon(self) -> None:
        """Stop the background watcher thread."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)


# Global singleton instance
_GLOBAL_WARMER = CacheWarmer()


def get_cache_warmer_status() -> dict[str, Any]:
    """Public router interface for cache warmer status."""
    return _GLOBAL_WARMER.get_status()


def trigger_cache_warm(force: bool = False) -> dict[str, Any]:
    """Public router interface for manual cache warm trigger."""
    return _GLOBAL_WARMER.warm_cache_now(force=force)


def start_cache_warmer_daemon() -> None:
    """Start the cache warmer daemon."""
    _GLOBAL_WARMER.start_daemon()


def stop_cache_warmer_daemon() -> None:
    """Stop the cache warmer daemon."""
    _GLOBAL_WARMER.stop_daemon()
