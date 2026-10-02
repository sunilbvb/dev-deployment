"""Desktop application launcher (.desktop) management."""

from __future__ import annotations

import logging
from pathlib import Path
import shutil
import subprocess
from typing import Any

from .paths import get_repo_root


def install_desktop_launcher() -> dict[str, Any]:
    """Install a .desktop application launcher to ~/.local/share/applications/

    and ~/Desktop/ so user can start server with a single click.
    """
    repo_root = get_repo_root()
    start_sh = repo_root / "start.sh"

    if not start_sh.is_file():
        return {"success": False, "error": f"start.sh not found at {start_sh}"}

    desktop_content = f"""[Desktop Entry]
Version=1.0
Type=Application
Name=Dev Deployment Console
Comment=Flutter & Mobile Deployment Automation Dashboard
Exec="{start_sh}" --open
Path={repo_root}
Icon=utilities-terminal
Terminal=false
Categories=Development;Building;
StartupNotify=true
"""

    created_paths = []

    # 1. ~/.local/share/applications/ (appears in app search/dock)
    app_dir = Path.home() / ".local" / "share" / "applications"
    try:
        app_dir.mkdir(parents=True, exist_ok=True)
        target = app_dir / "dev-deployment.desktop"
        target.write_text(desktop_content, encoding="utf-8")
        target.chmod(0o755)
        created_paths.append(str(target))
    except Exception as e:
        logging.warning("Failed to write desktop launcher to %s: %s", app_dir, e)

    # 2. ~/Desktop/ (optional, if Desktop exists)
    desktop_dir = Path.home() / "Desktop"
    if desktop_dir.is_dir():
        try:
            target_desk = desktop_dir / "dev-deployment.desktop"
            target_desk.write_text(desktop_content, encoding="utf-8")
            target_desk.chmod(0o755)
            created_paths.append(str(target_desk))
        except Exception as e:
            logging.warning("Failed to write desktop launcher to %s: %s", desktop_dir, e)

    # Also keep a copy in repo root
    try:
        repo_desk = repo_root / "dev-deployment.desktop"
        repo_desk.write_text(desktop_content, encoding="utf-8")
        repo_desk.chmod(0o755)
    except Exception:
        pass

    # Update desktop database if available
    if shutil.which("update-desktop-database"):
        try:
            subprocess.run(["update-desktop-database", str(app_dir)], check=False, capture_output=True)
        except Exception:
            pass

    return {
        "success": True,
        "message": "Desktop shortcut created! You can now launch from your application menu or desktop.",
        "paths": created_paths,
    }
