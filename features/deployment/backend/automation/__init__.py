"""
Automation package for Dev Deployment Console.

Contains:
- adb_manager: Wireless & USB Android device discovery, pairing, and parallel push.
- build_profiler: Build timing parser, compilation heatmap, and bottleneck detection.
- cache_warmer: Background daemon watching Git branch switches and pre-fetching dependencies.
- github_actions: Cloud CI workflow dispatch and runner polling.
"""

from . import adb_manager, build_profiler, cache_warmer, github_actions
from .adb_manager import (
    connect_wireless_adb,
    disconnect_wireless_adb,
    find_adb_binary,
    get_adb_devices,
    push_apk_to_devices,
)
from .build_profiler import (
    get_job_build_profile,
    profile_build_log,
)

parse_build_profile = profile_build_log
from .cache_warmer import (
    get_cache_warmer_status,
    start_cache_warmer_daemon,
    stop_cache_warmer_daemon,
    trigger_cache_warm,
)
from .github_actions import (
    detect_git_branch,
    detect_github_repo,
    dispatch_workflow,
    find_workflow_file,
    get_android_workflow_template,
    get_stored_github_token,
    install_workflow_template,
    save_github_token,
    save_repo_override,
)
from .version_bumper import (
    bump_version,
    generate_changelog,
    get_version_info,
    parse_pubspec_version,
)

__all__ = [
    "adb_manager",
    "build_profiler",
    "cache_warmer",
    "github_actions",
    "version_bumper",
    "connect_wireless_adb",
    "disconnect_wireless_adb",
    "find_adb_binary",
    "get_adb_devices",
    "push_apk_to_devices",
    "get_job_build_profile",
    "parse_build_profile",
    "get_cache_warmer_status",
    "start_cache_warmer_daemon",
    "stop_cache_warmer_daemon",
    "trigger_cache_warm",
    "detect_git_branch",
    "detect_github_repo",
    "dispatch_workflow",
    "find_workflow_file",
    "get_android_workflow_template",
    "get_stored_github_token",
    "install_workflow_template",
    "save_github_token",
    "save_repo_override",
    "bump_version",
    "generate_changelog",
    "get_version_info",
    "parse_pubspec_version",
]
