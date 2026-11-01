"""Update the "What to Test" notes of an already-uploaded TestFlight build.

Runs the fixed `ios update_testflight_notes` fastlane lane; nothing from the
request becomes command text - values travel as environment variables only.
Pure Python standard library only.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import config
import credentials

from . import store_metadata

logger = logging.getLogger("metadata.notes_updater")

FASTLANE_DIR = Path(__file__).resolve().parents[2] / "fastlane"
LANE_TIMEOUT_SECONDS = 300
_BUNDLE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.\-]{0,127}$")
_BUILD_RE = re.compile(r"^\d+(\.\d+){0,2}$")
_LOCALE_RE = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})?$")


def update_testflight_notes(
    app_id: str,
    bundle_id: str,
    build_number: str,
    release_notes: str,
    locale: str = "en-US",
    save_to_files: bool = True,
) -> dict[str, Any]:
    """Set the notes of build `build_number` in App Store Connect (iOS only)."""
    app_id, bundle_id = (app_id or "").strip(), (bundle_id or "").strip()
    build_number, locale = (build_number or "").strip(), (locale or "en-US").strip()
    notes = (release_notes or "").strip()

    if not app_id or not config.SAFE_ID_PATTERN.match(app_id):
        return {"success": False, "error": "A valid app id is required."}
    if not _BUNDLE_ID_RE.match(bundle_id):
        return {"success": False, "error": "A valid bundleId is required."}
    if not _BUILD_RE.match(build_number):
        return {"success": False, "error": "buildNumber must be the build's number, e.g. 42."}
    if not _LOCALE_RE.match(locale):
        return {"success": False, "error": "Invalid locale."}
    if not notes:
        return {"success": False, "error": "Release notes are empty."}
    limit = store_metadata.METADATA_LIMITS["ios"]["release_notes"]
    if len(notes) > limit:
        return {"success": False, "error": f"Release notes are {len(notes)} characters; App Store Connect allows {limit}."}

    env = {**os.environ, **credentials.job_env(app_id)}
    if not env.get("APPLE_API_KEY") or not env.get("APPLE_API_ISSUER"):
        return {"success": False, "error": "Apple API key / issuer not configured for this app (Credentials)."}
    env.update({
        "IOS_BUNDLE_ID": bundle_id,
        "IOS_BUILD_NUMBER": build_number,
        "RELEASE_NOTES": notes,
        "RELEASE_LOCALE": locale,
        "FASTLANE_SKIP_UPDATE_CHECK": "1",
    })
    gemfile = FASTLANE_DIR / "Gemfile"
    if gemfile.is_file():
        env.setdefault("BUNDLE_GEMFILE", str(gemfile))

    cmd = ["bundle", "exec", "fastlane", "ios", "update_testflight_notes"]
    logger.info("Running %s for %s build %s (%s)", " ".join(cmd), bundle_id, build_number, locale)
    try:
        proc = subprocess.run(cmd, cwd=str(FASTLANE_DIR), env=env, capture_output=True, text=True,
                              timeout=LANE_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Timed out after {LANE_TIMEOUT_SECONDS}s talking to App Store Connect."}
    except OSError as e:
        return {"success": False, "error": f"Could not run fastlane: {e}"}

    tail = "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-20:])
    if proc.returncode != 0:
        logger.warning("update_testflight_notes failed (%s): %s", proc.returncode, tail)
        return {"success": False, "error": "App Store Connect update failed.", "output": tail}

    result: dict[str, Any] = {"success": True, "message": f"Updated notes for build {build_number} ({locale}).", "output": tail}
    if save_to_files:
        saved = store_metadata.save_store_metadata(
            app_id=app_id, platform="ios", locale=locale, release_notes=notes, version=build_number)
        result["saved"] = saved
    return result
