"""App Doctor: 1-Click Pre-flight Diagnostics.

Modular architecture:
- tool_checks: SDKs and command-line utilities (Flutter, Git, Bash, Melos)
- project_checks: Project files and platform environments (Android, iOS, Credentials)
- runner: Full workspace/app diagnostic execution and Markdown report generator
"""

from .tool_checks import (
    _check_flutter_sdk,
    _check_git_status,
    _check_tool,
    _check_toolchain,
)
from .project_checks import (
    _check_android_env,
    _check_app_project,
    _check_credentials,
    _check_ios_env,
)
from .runner import diagnose_app

# Aliases for API compatibility
run_doctor_checks = diagnose_app
get_doctor_summary = diagnose_app

__all__ = [
    "diagnose_app",
    "run_doctor_checks",
    "get_doctor_summary",
    "_check_tool",
    "_check_flutter_sdk",
    "_check_toolchain",
    "_check_git_status",
    "_check_app_project",
    "_check_android_env",
    "_check_ios_env",
    "_check_credentials",
]
