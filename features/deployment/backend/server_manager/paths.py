"""Repository and environment paths for server manager."""

from __future__ import annotations

from pathlib import Path


def get_repo_root() -> Path:
    """Resolve repository root directory."""
    cand = Path(__file__).resolve().parents[4]
    if (cand / "start.sh").is_file():
        return cand
    # Fallback to checking parents[3] if relative structure differs
    cand_alt = Path(__file__).resolve().parents[3]
    if (cand_alt / "start.sh").is_file():
        return cand_alt
    return Path.cwd().resolve()
