"""Keep tests from writing outside temp dirs.

Without this, tests wrote to the real console config (config/workspaces_list.json,
config/active_workspace.txt), the default workspace (.github/workflows/...), the repo
(dev-deployment.desktop) and the home folder (~/.local/share/applications, ~/Desktop).
Each test module calls these from setUpModule / tearDownModule; tests that patch
config.DASHBOARD_ROOT / WORKSPACE_ROOT themselves still work.
"""
import shutil
import tempfile
from pathlib import Path
from unittest import mock

import config

_saved = []


def isolate_dashboard_config() -> None:
    tmp = tempfile.TemporaryDirectory()
    base = Path(tmp.name).resolve()
    real = Path(config.DASHBOARD_ROOT)
    if (real / "config").is_dir():
        shutil.copytree(real / "config", base / "config")
    else:
        (base / "config").mkdir()
    for d in ("workspace", "home", "repo"):
        (base / d).mkdir()
    (base / "repo" / "start.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")

    patches = [mock.patch.object(Path, "home", return_value=base / "home")]
    try:
        import server_manager.desktop as desktop
        patches.append(mock.patch.object(desktop, "get_repo_root", return_value=base / "repo"))
    except ImportError:
        pass
    for p in patches:
        p.start()

    _saved.append((config.DASHBOARD_ROOT, config.WORKSPACE_ROOT, patches, tmp))
    config.DASHBOARD_ROOT = base
    config.WORKSPACE_ROOT = base / "workspace"


def restore_dashboard_config() -> None:
    root, ws, patches, tmp = _saved.pop()
    for p in patches:
        p.stop()
    config.DASHBOARD_ROOT = root
    config.WORKSPACE_ROOT = ws
    tmp.cleanup()
