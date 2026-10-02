"""Build Size Inspector & Diff for Dev Deployment Console.

Modularized package providing multiplatform artifact discovery, archive inspection,
and size regression diffing.
"""

from __future__ import annotations

from .analyzer import (
    compare_build_size,
    get_build_size_info,
    inspect_and_diff_job,
)
from .archive_inspector import (
    _compute_archive_diff,
    find_build_artifact,
    inspect_archive_contents,
)
from .formatter import (
    CRIT_BYTES_THRESHOLD,
    CRIT_PERCENT_THRESHOLD,
    UNCOMPRESSED_WARN_SIZE,
    WARN_BYTES_THRESHOLD,
    WARN_PERCENT_THRESHOLD,
    detect_artifact_type,
    format_bytes,
    format_delta_bytes,
    format_delta_percent,
)
from .history_tracker import (
    _get_history_file,
    get_previous_successful_build,
)

__all__ = [
    "CRIT_BYTES_THRESHOLD",
    "CRIT_PERCENT_THRESHOLD",
    "UNCOMPRESSED_WARN_SIZE",
    "WARN_BYTES_THRESHOLD",
    "WARN_PERCENT_THRESHOLD",
    "_compute_archive_diff",
    "_get_history_file",
    "compare_build_size",
    "detect_artifact_type",
    "find_build_artifact",
    "format_bytes",
    "format_delta_bytes",
    "format_delta_percent",
    "get_build_size_info",
    "get_previous_successful_build",
    "inspect_and_diff_job",
    "inspect_archive_contents",
]
