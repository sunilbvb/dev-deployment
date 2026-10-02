"""Diagnostic check aggregator and report generator."""

from __future__ import annotations

import logging
from pathlib import Path
import time
from typing import Any, Optional

from config import _resolve_app_dir, get_workspace_root, load_deploy_config
from .project_checks import (
    _check_android_env,
    _check_app_project,
    _check_credentials,
    _check_ios_env,
)
from .tool_checks import _check_git_status, _check_toolchain


def diagnose_app(app_id: Optional[str] = None, flavor: str = "prod", ws_root: Optional[Path] = None) -> dict[str, Any]:
    """Run full diagnostic check for an app (or workspace if app_id is None)."""
    started_at = time.time()
    ws_root = ws_root or get_workspace_root()

    all_checks: list[dict[str, Any]] = []

    # 1. Base Toolchain
    all_checks.extend(_check_toolchain(ws_root))

    app_dir = ws_root
    app_cfg = {}
    if app_id:
        try:
            app_dir = _resolve_app_dir(app_id)
            deploy_cfg = load_deploy_config()
            app_cfg = deploy_cfg.get("apps", {}).get(app_id, {})
        except Exception:
            app_dir = ws_root / app_id

        # 2. App Project & Dependencies
        all_checks.extend(_check_app_project(app_id, app_dir))

        # 3. Android Environment
        all_checks.extend(_check_android_env(app_dir, app_cfg))

        # 4. iOS Environment
        all_checks.extend(_check_ios_env(app_id, app_dir, app_cfg, flavor=flavor))

        # 5. Credentials & Secrets
        all_checks.extend(_check_credentials(app_id, app_dir))

        # 6. Certificate & Keystore Sentinel (Expiry & Firebase Mismatches)
        try:
            import sentinel
            sentinel_res = sentinel.check_app_sentinel(app_id, flavor=flavor, ws_root=ws_root)
            sentinel_alerts = sentinel_res.get("alerts", [])
            if sentinel_alerts:
                for a in sentinel_alerts:
                    all_checks.append({
                        "id": a["id"],
                        "category": a.get("category", "credentials"),
                        "name": f"Sentinel: {a['title']}",
                        "status": "fail" if a["severity"] == "critical" else "warn",
                        "message": a["message"],
                        "hint": a.get("hint", ""),
                    })
            else:
                all_checks.append({
                    "id": "sentinel_status_ok",
                    "category": "credentials",
                    "name": "Certificate & Keystore Sentinel",
                    "status": "pass",
                    "message": "Apple certificates, Android keystore, and Firebase project IDs are healthy.",
                })
        except Exception:
            logging.exception("Failed to run sentinel checks in doctor")

    # 7. Git Status
    all_checks.extend(_check_git_status(app_dir))

    # Calculate Score & Overall Status
    pass_count = sum(1 for c in all_checks if c.get("status") == "pass")
    warn_count = sum(1 for c in all_checks if c.get("status") == "warn")
    fail_count = sum(1 for c in all_checks if c.get("status") == "fail")
    info_count = sum(1 for c in all_checks if c.get("status") == "info")
    total_count = len(all_checks)

    if fail_count > 0:
        overall_status = "fail"
        summary_headline = f"{fail_count} critical issue(s) detected that will break builds."
    elif warn_count > 0:
        overall_status = "warn"
        summary_headline = f"Ready to build with {warn_count} warning(s) to review."
    else:
        overall_status = "pass"
        summary_headline = "All pre-flight diagnostic checks passed successfully!"

    duration_ms = int((time.time() - started_at) * 1000)

    # Generate Markdown Report
    report_lines = [
        "# App Doctor Diagnostic Report",
        f"**App**: {app_id or 'Workspace'} | **Flavor**: {flavor} | **Overall Status**: {overall_status.upper()}",
        f"**Checked At**: {time.strftime('%Y-%m-%d %H:%M:%S')} ({duration_ms}ms)",
        "",
        f"### Summary: {summary_headline}",
        f"- Passed: **{pass_count}**",
        f"- Warnings: **{warn_count}**",
        f"- Failures: **{fail_count}**",
        "",
        "| Category | Check | Status | Details |",
        "| :--- | :--- | :---: | :--- |",
    ]

    status_icons = {"pass": "PASS (OK)", "warn": "WARN", "fail": "FAIL", "info": "INFO"}
    for c in all_checks:
        icon = status_icons.get(c.get("status"), c.get("status", "").upper())
        cat = c.get("category", "").capitalize()
        name = c.get("name", "")
        msg = c.get("message", "")
        hint = f" *[Hint: {c['hint']}]*" if c.get("hint") else ""
        report_lines.append(f"| {cat} | {name} | {icon} | {msg}{hint} |")

    markdown_report = "\n".join(report_lines)

    return {
        "success": True,
        "app": app_id,
        "flavor": flavor,
        "overallStatus": overall_status,
        "summary": summary_headline,
        "passCount": pass_count,
        "warnCount": warn_count,
        "failCount": fail_count,
        "infoCount": info_count,
        "totalCount": total_count,
        "durationMs": duration_ms,
        "checks": all_checks,
        "reportMarkdown": markdown_report,
    }
