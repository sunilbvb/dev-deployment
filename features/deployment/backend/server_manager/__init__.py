"""Server lifecycle and system integration manager.

Provides desktop launcher (.desktop) generation and systemd user service
management so developers can run, auto-start, and control the deployment server
without typing terminal commands.
"""

from __future__ import annotations

from .desktop import install_desktop_launcher
from .paths import get_repo_root
from .service import (
    get_service_status,
    install_systemd_service,
)

__all__ = [
    "get_repo_root",
    "get_service_status",
    "install_desktop_launcher",
    "install_systemd_service",
]
