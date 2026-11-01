"""Deployment Queue persistence, file storage, and pruning.

Zero external dependencies - 100% Python standard library.
Supports multi-workspace operations with dual persistence:
1. User-level central store: ~/.config/dev-deployment/deployment_queue.json
2. Workspace-level store: <project>/.dev-dashboard/deployment_queue.json
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import time
from typing import Any, Optional

from config import get_workspace_root

GLOBAL_CONFIG_DIR = Path.home() / ".config" / "dev-deployment"


def get_global_queue_file() -> Path:
    try:
        GLOBAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return GLOBAL_CONFIG_DIR / "deployment_queue.json"


def get_queue_file(ws_root: Optional[Path] = None) -> Path:
    ws = ws_root or get_workspace_root()
    target_dir = ws / ".dev-dashboard"
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return target_dir / "deployment_queue.json"


def prune_queue_items(
    items: list[dict[str, Any]],
    max_history: int = 50,
    max_age_seconds: int = 86400,
) -> list[dict[str, Any]]:
    """Retain all pending and running items, and prune old completed/failed items."""
    now = time.time()
    active_items: list[dict[str, Any]] = []
    finished_items: list[dict[str, Any]] = []

    for item in items:
        status = item.get("status", "pending")
        if status in ("pending", "running"):
            active_items.append(item)
        else:
            finished_at = item.get("finishedAt") or item.get("startedAt", now)
            if now - finished_at <= max_age_seconds:
                finished_items.append(item)

    if len(finished_items) > max_history:
        finished_items.sort(key=lambda x: x.get("finishedAt") or x.get("startedAt", 0), reverse=True)
        finished_items = finished_items[:max_history]

    return active_items + finished_items


def load_queue(ws_root: Optional[Path] = None) -> list[dict[str, Any]]:
    """Load queue from user-level global store, falling back to workspace store."""
    g_file = get_global_queue_file()
    ws_file = get_queue_file(ws_root)

    target_files = [g_file, ws_file]
    for q_file in target_files:
        if q_file.exists():
            try:
                content = q_file.read_text(encoding="utf-8").strip()
                if not content:
                    continue
                data = json.loads(content)
                if isinstance(data, list):
                    return prune_queue_items(data)
                if isinstance(data, dict) and isinstance(data.get("items"), list):
                    return prune_queue_items(data["items"])
            except Exception:
                logging.exception("Failed to load queue from %s", q_file)

    return []


def save_queue(items: list[dict[str, Any]], ws_root: Optional[Path] = None) -> None:
    """Save queue to both user-level central store and workspace-level store."""
    pruned = prune_queue_items(items)
    json_bytes = json.dumps(pruned, indent=2, ensure_ascii=False)

    # 1. Save global user copy
    try:
        g_file = get_global_queue_file()
        g_tmp = g_file.with_suffix(".tmp")
        g_tmp.write_text(json_bytes, encoding="utf-8")
        g_tmp.replace(g_file)
    except Exception:
        logging.exception("Failed to save global queue file")

    # 2. Save workspace copy
    try:
        ws_file = get_queue_file(ws_root)
        ws_tmp = ws_file.with_suffix(".tmp")
        ws_tmp.write_text(json_bytes, encoding="utf-8")
        ws_tmp.replace(ws_file)
    except Exception:
        logging.exception("Failed to save workspace queue file")
