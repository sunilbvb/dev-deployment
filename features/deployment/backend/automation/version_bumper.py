"""Semantic Version Bumper & Conventional Commit Changelog Generator.

Reads and safely updates pubspec.yaml versioning (patch, minor, major, build).
Parses git commit history into categorized Markdown changelogs and concise
Play Store / TestFlight release notes. Pure Python standard library only.
"""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path
from typing import Any, Optional

import config

logger = logging.getLogger("automation.version")

CONVENTIONAL_CATEGORIES = {
    "feat": "Features 🚀",
    "feature": "Features 🚀",
    "fix": "Bug Fixes 🐛",
    "bugfix": "Bug Fixes 🐛",
    "perf": "Performance Improvements ⚡",
    "refactor": "Refactoring 🛠️",
    "docs": "Documentation 📝",
    "chore": "Maintenance 🧹",
    "style": "UI & Styling 🎨",
}


def parse_pubspec_version(pubspec_path: Path) -> dict[str, Any]:
    """Parse version string from pubspec.yaml (e.g., '1.2.3+45')."""
    if not pubspec_path.exists() or not pubspec_path.is_file():
        return {
            "exists": False,
            "raw": "",
            "major": 0,
            "minor": 0,
            "patch": 0,
            "build": 0,
            "versionName": "1.0.0",
        }

    content = pubspec_path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"^\s*version:\s*([^\s#]+)", content, re.MULTILINE)
    if not match:
        return {
            "exists": True,
            "raw": "",
            "major": 1,
            "minor": 0,
            "patch": 0,
            "build": 1,
            "versionName": "1.0.0",
        }

    raw = match.group(1).strip()
    # Match major.minor.patch(+build)?
    v_match = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:\+(\d+))?$", raw)
    if v_match:
        major = int(v_match.group(1))
        minor = int(v_match.group(2))
        patch = int(v_match.group(3))
        build = int(v_match.group(4) or 1)
        return {
            "exists": True,
            "raw": raw,
            "major": major,
            "minor": minor,
            "patch": patch,
            "build": build,
            "versionName": f"{major}.{minor}.{patch}",
        }

    return {
        "exists": True,
        "raw": raw,
        "major": 1,
        "minor": 0,
        "patch": 0,
        "build": 1,
        "versionName": raw,
    }


def get_version_info(app_id: str = "") -> dict[str, Any]:
    """Get current version info and next bump previews for an app."""
    ws = config.get_workspace_root()
    app_dir = ws / "apps" / app_id if app_id else ws
    if not app_dir.exists():
        app_dir = ws

    pubspec_path = app_dir / "pubspec.yaml"
    curr = parse_pubspec_version(pubspec_path)

    maj, min_, pat, bld = curr["major"], curr["minor"], curr["patch"], curr["build"]
    previews = {
        "patch": f"{maj}.{min_}.{pat + 1}+{bld + 1}",
        "minor": f"{maj}.{min_ + 1}.0+{bld + 1}",
        "major": f"{maj + 1}.0.0+{bld + 1}",
        "build": f"{maj}.{min_}.{pat}+{bld + 1}",
    }

    return {
        "success": True,
        "appId": app_id,
        "pubspecPath": str(pubspec_path),
        "current": curr,
        "previews": previews,
    }


def bump_version(
    app_id: str,
    bump_type: str = "patch",
    custom_version: str = "",
    custom_build: Optional[int] = None,
) -> dict[str, Any]:
    """Bump the version in pubspec.yaml safely preserving comments."""
    ws = config.get_workspace_root()
    app_dir = ws / "apps" / app_id if app_id else ws
    if not app_dir.exists():
        app_dir = ws

    pubspec_path = app_dir / "pubspec.yaml"
    if not pubspec_path.exists():
        return {"success": False, "error": f"pubspec.yaml not found at {pubspec_path}"}

    curr = parse_pubspec_version(pubspec_path)
    maj, min_, pat, bld = curr["major"], curr["minor"], curr["patch"], curr["build"]

    bump_type = bump_type.lower().strip()
    if bump_type == "patch":
        new_ver_name = f"{maj}.{min_}.{pat + 1}"
        new_build = bld + 1
    elif bump_type == "minor":
        new_ver_name = f"{maj}.{min_ + 1}.0"
        new_build = bld + 1
    elif bump_type == "major":
        new_ver_name = f"{maj + 1}.0.0"
        new_build = bld + 1
    elif bump_type == "build":
        new_ver_name = f"{maj}.{min_}.{pat}"
        new_build = bld + 1
    elif bump_type == "custom":
        new_ver_name = custom_version.strip() or f"{maj}.{min_}.{pat}"
        new_build = custom_build if custom_build is not None else (bld + 1)
    else:
        return {"success": False, "error": f"Invalid bump type: {bump_type}"}

    target_full_version = f"{new_ver_name}+{new_build}"

    content = pubspec_path.read_text(encoding="utf-8", errors="replace")
    new_content, count = re.subn(
        r"^(\s*version:\s*)([^\s#]+)",
        rf"\g<1>{target_full_version}",
        content,
        count=1,
        flags=re.MULTILINE,
    )

    if count == 0:
        # If no version key existed, prepend it
        new_content = f"version: {target_full_version}\n" + content

    pubspec_path.write_text(new_content, encoding="utf-8")

    return {
        "success": True,
        "appId": app_id,
        "bumpType": bump_type,
        "oldVersion": curr["raw"],
        "newVersion": target_full_version,
        "versionName": new_ver_name,
        "buildNumber": new_build,
    }


def generate_changelog(
    app_id: str = "",
    since_ref: str = "",
    max_commits: int = 50,
) -> dict[str, Any]:
    """Generate categorized changelog and Play Store release notes from git commits."""
    ws = config.get_workspace_root()
    repo_dir = ws
    if app_id:
        app_p = ws / "apps" / app_id
        if (app_p / ".git").exists():
            repo_dir = app_p

    # Determine latest tag if since_ref not specified
    tag_used = since_ref.strip()
    if not tag_used:
        try:
            p = subprocess.run(
                ["git", "describe", "--tags", "--abbrev=0"],
                cwd=str(repo_dir),
                capture_output=True,
                text=True,
                timeout=3,
            )
            if p.returncode == 0 and p.stdout.strip():
                tag_used = p.stdout.strip()
        except Exception:
            tag_used = ""

    # Fetch git log commits
    cmd = ["git", "log", f"-n{max_commits}", "--pretty=format:%h|||%s|||%an|||%ad", "--date=short"]
    if tag_used:
        cmd = ["git", "log", f"{tag_used}..HEAD", f"-n{max_commits}", "--pretty=format:%h|||%s|||%an|||%ad", "--date=short"]

    try:
        res = subprocess.run(cmd, cwd=str(repo_dir), capture_output=True, text=True, timeout=5)
        raw_log = res.stdout if res.returncode == 0 else ""
    except Exception as e:
        logger.debug("Failed running git log: %s", e)
        raw_log = ""

    commits: list[dict[str, str]] = []
    categorized: dict[str, list[dict[str, str]]] = {cat: [] for cat in CONVENTIONAL_CATEGORIES.values()}
    categorized["Other Changes 📦"] = []

    for line in raw_log.strip().splitlines():
        parts = line.split("|||")
        if len(parts) >= 2:
            c_hash = parts[0].strip()
            c_msg = parts[1].strip()
            c_author = parts[2].strip() if len(parts) > 2 else ""
            c_date = parts[3].strip() if len(parts) > 3 else ""

            # Check conventional commit prefix (e.g., feat(auth): add login)
            match = re.match(r"^([a-zA-Z]+)(?:\([^\)]+\))?:\s*(.+)$", c_msg)
            assigned = False
            item = {"hash": c_hash, "message": c_msg, "author": c_author, "date": c_date}
            commits.append(item)

            if match:
                prefix = match.group(1).lower()
                clean_desc = match.group(2).strip()
                item["cleanMessage"] = clean_desc
                if prefix in CONVENTIONAL_CATEGORIES:
                    cat_name = CONVENTIONAL_CATEGORIES[prefix]
                    categorized[cat_name].append(item)
                    assigned = True

            if not assigned:
                categorized["Other Changes 📦"].append(item)

    # Build Markdown changelog
    md_lines = [f"# Release Changelog ({tag_used or 'Latest Commits'} → HEAD)\n"]
    for cat_name, items in categorized.items():
        if items:
            md_lines.append(f"### {cat_name}")
            for it in items:
                desc = it.get("cleanMessage") or it["message"]
                md_lines.append(f"- **{it['hash']}** {desc} ({it['author']})")
            md_lines.append("")

    markdown_changelog = "\n".join(md_lines).strip()

    # Build concise bulleted release notes for Play Store (must be ≤ 500 chars)
    store_lines: list[str] = []
    # Prioritize features and bug fixes
    key_items = (
        categorized.get("Features 🚀", []) +
        categorized.get("Bug Fixes 🐛", []) +
        categorized.get("Performance Improvements ⚡", [])
    )
    if not key_items:
        key_items = commits[:5]

    for it in key_items:
        desc = it.get("cleanMessage") or it["message"]
        candidate = f"• {desc}"
        if sum(len(x) + 1 for x in store_lines) + len(candidate) <= 490:
            store_lines.append(candidate)
        else:
            break

    store_notes = "\n".join(store_lines) or "• Bug fixes and general performance enhancements."

    return {
        "success": True,
        "appId": app_id,
        "sinceRef": tag_used,
        "commitCount": len(commits),
        "markdownChangelog": markdown_changelog,
        "storeNotes": store_notes,
        "storeNotesLength": len(store_notes),
        "storeNotesExceedsLimit": len(store_notes) > 500,
        "commits": commits[:max_commits],
    }
