"""Multi-locale, per-build release notes for Google Play and TestFlight.

Notes are optional. They come from (in order): the dashboard / API
(`RELEASE_NOTES_JSON`), a plain `RELEASE_NOTES` text, then the app's fastlane
metadata files (per-build file first, then the shared default). Pure Python
standard library only.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional

import config
import credentials

from . import store_metadata
from .store_metadata import METADATA_LIMITS, _clean_version, _find_metadata_roots, _notes_file, _read_file_safe

logger = logging.getLogger("metadata.release_notes")

FASTLANE_DIR = Path(__file__).resolve().parents[2] / "fastlane"
LANE_TIMEOUT_SECONDS = 180
DEFAULT_LOCALE = "en-US"
LOCALE_RE = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})?$")
_PACKAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def _platform_key(platform: str) -> str:
    return "android" if (platform or "").lower() == "android" else "ios"


def _limit(platform_key: str) -> int:
    return METADATA_LIMITS[platform_key]["changelog" if platform_key == "android" else "release_notes"]


def _app_dir(app_id: str) -> Path:
    return config._resolve_app_dir(app_id) if app_id else config.get_workspace_root()


# --- app-level locales -------------------------------------------------------

def _clean_locales(raw: Any) -> list[str]:
    out: list[str] = []
    for item in raw if isinstance(raw, list) else []:
        loc = str(item).strip().replace("_", "-")
        if LOCALE_RE.match(loc) and loc not in out:
            out.append(loc)
    return out


def get_app_locales(app_id: str) -> list[str]:
    """Languages release notes are written in: the app's setting, else the
    locale folders already in its fastlane metadata, else en-US."""
    apps = (config.load_deploy_config().get("apps") or {})
    configured = _clean_locales((apps.get(app_id) or {}).get("release_locales"))
    if configured:
        return configured
    found: list[str] = []
    roots = _find_metadata_roots(_app_dir(app_id))
    for key in ("android", "ios"):
        for root in roots[key]:
            for d in sorted(root.iterdir()):
                if d.is_dir() and LOCALE_RE.match(d.name) and d.name not in found:
                    found.append(d.name)
    return found or [DEFAULT_LOCALE]


def set_app_locales(app_id: str, locales: Any) -> dict[str, Any]:
    if not app_id or not config.SAFE_ID_PATTERN.match(app_id):
        return {"success": False, "error": "A valid app id is required."}
    cleaned = _clean_locales(locales)
    if not cleaned:
        return {"success": False, "error": "Give at least one valid locale, e.g. en-US, de-DE."}
    cfg = config.load_deploy_config()
    apps = cfg.setdefault("apps", {})
    apps.setdefault(app_id, {})["release_locales"] = cleaned
    res = config.save_deploy_config(cfg)
    if isinstance(res, dict) and res.get("success") is False:
        return res
    return {"success": True, "locales": cleaned}


# --- reading / saving ----------------------------------------------------------

def _versions_found(app_dir: Path, key: str) -> list[str]:
    """Versions that have their own notes, newest build first."""
    found: set[str] = set()
    for root in _find_metadata_roots(app_dir)[key]:
        for loc_dir in root.iterdir():
            if not loc_dir.is_dir():
                continue
            if key == "android":
                found.update(f.stem for f in (loc_dir / "changelogs").glob("*.txt") if f.stem != "default")
            else:
                found.update(f.stem[len("release_notes_"):] for f in loc_dir.glob("release_notes_*.txt"))

    def order(v: str) -> tuple:
        return tuple(int(p) if p.isdigit() else 0 for p in re.split(r"[.+-]", v))
    return sorted(found, key=order, reverse=True)


def _read_locale(app_dir: Path, key: str, locale: str, version: str) -> tuple[str, str]:
    """(text, source) where source is "version", "default" or ""."""
    for root in _find_metadata_roots(app_dir)[key]:
        if version:
            text = _read_file_safe(_notes_file(key, root / locale, version))
            if text:
                return text, "version"
        text = _read_file_safe(_notes_file(key, root / locale, ""))
        if text:
            return text, "default"
    return "", ""


def get_release_notes(app_id: str, platform: str, version: str = "") -> dict[str, Any]:
    """Notes of every app locale for one version, plus the last build's notes."""
    key = _platform_key(platform)
    if (version or "").strip() and not _clean_version(version):
        return {"success": False, "error": "Invalid version."}
    version = _clean_version(version)
    app_dir = _app_dir(app_id)
    locales = get_app_locales(app_id)
    versions = _versions_found(app_dir, key)
    last = versions[0] if versions else ""
    notes = {}
    for loc in locales:
        text, source = _read_locale(app_dir, key, loc, version)
        notes[loc] = {"text": text, "source": source, "length": len(text)}
    last_notes = {loc: _read_locale(app_dir, key, loc, last)[0] for loc in locales} if last else {}
    return {
        "success": True, "appId": app_id, "platform": key, "version": version,
        "locales": locales, "limit": _limit(key), "notes": notes,
        "versions": versions, "lastBuild": {"version": last, "notes": last_notes},
    }


def save_release_notes(app_id: str, platform: str, version: str, notes: Any) -> dict[str, Any]:
    """Write {locale: text} for a version ("" = shared default). Empty text
    removes that version's file so the default applies again."""
    key = _platform_key(platform)
    if not isinstance(notes, dict) or not notes:
        return {"success": False, "error": "notes must be an object of locale -> text."}
    if (version or "").strip() and not _clean_version(version):
        return {"success": False, "error": "Invalid version."}
    version = _clean_version(version)
    limit = _limit(key)
    cleaned: dict[str, str] = {}
    for loc, text in notes.items():
        loc = str(loc).strip()
        text = str(text or "").strip()
        if not LOCALE_RE.match(loc):
            return {"success": False, "error": f"Invalid locale '{loc}'."}
        if len(text) > limit:
            return {"success": False, "error": f"{loc}: {len(text)} characters; {key} allows {limit}."}
        cleaned[loc] = text
    app_dir = _app_dir(app_id)
    saved = []
    for loc, text in cleaned.items():
        if not text and version:
            for root in _find_metadata_roots(app_dir)[key]:
                _notes_file(key, root / loc, version).unlink(missing_ok=True)
            continue
        if not text:
            continue
        target = _notes_file(key, _locale_dir(app_dir, key, loc), version)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text + "\n", encoding="utf-8")
        saved.append(loc)
    return {"success": True, "saved": saved, "version": version}


def _locale_dir(app_dir: Path, key: str, locale: str) -> Path:
    roots = _find_metadata_roots(app_dir)[key]
    if roots:
        return roots[0] / locale
    if key == "android":
        return app_dir / "android" / "fastlane" / "metadata" / "android" / locale
    return app_dir / "ios" / "fastlane" / "metadata" / locale


# --- what an upload ships ------------------------------------------------------

def resolve_notes_map(app_dir: Path, platform: str, app_id: str = "", version: str = "") -> dict[str, str]:
    """{locale: text} for an upload; {} when there are no notes (never an error)."""
    key = _platform_key(platform)
    limit = _limit(key)
    raw_json = os.environ.get("RELEASE_NOTES_JSON", "").strip()
    if raw_json:
        try:
            parsed = json.loads(raw_json)
            if isinstance(parsed, dict):
                return {l: str(t).strip()[:limit] for l, t in parsed.items() if LOCALE_RE.match(str(l)) and str(t).strip()}
        except ValueError:
            logger.warning("RELEASE_NOTES_JSON is not valid JSON; ignoring it")
    locales = get_app_locales(app_id) if app_id else [DEFAULT_LOCALE]
    plain = os.environ.get("RELEASE_NOTES", "").strip()
    if plain:
        return {locales[0]: plain[:limit]}
    tokens = [t for t in [_clean_version(version), *store_metadata._current_version_tokens(app_dir)] if t]
    out: dict[str, str] = {}
    for loc in locales:
        for tok in [*tokens, ""]:
            text = ""
            for root in _find_metadata_roots(app_dir)[key]:
                text = _read_file_safe(_notes_file(key, root / loc, tok))
                if text:
                    break
            if text:
                out[loc] = text[:limit]
                break
    return out


# --- identifiers + store locale discovery ---------------------------------------

def default_identifier(app_id: str, platform: str, flavor: str = "") -> str:
    """Bundle id (iOS) / package name (Android) discovered for the app, or ""."""
    base = "android_package" if _platform_key(platform) == "android" else "bundle_id"
    for a in config.get_apps().get("apps", []):
        if isinstance(a, dict) and a.get("id") == app_id:
            for k in ([f"{base}_{flavor}"] if flavor else []) + [base, f"{base}_prod"]:
                if a.get(k):
                    return str(a[k])
    if base == "bundle_id":
        found = config._scan_xcconfig_bundle_ids(_app_dir(app_id))
        return found.get(f"bundle_id_{flavor}") or found.get("bundle_id", "")
    return ""


def fetch_store_locales(app_id: str, platform: str, identifier: str = "") -> dict[str, Any]:
    """Languages the store listing of the app already supports (via fastlane)."""
    key = _platform_key(platform)
    identifier = (identifier or default_identifier(app_id, key)).strip()
    if not app_id or not config.SAFE_ID_PATTERN.match(app_id):
        return {"success": False, "error": "A valid app id is required."}
    if not _PACKAGE_RE.match(identifier):
        return {"success": False, "error": "Enter the bundle id / package name first."}
    env = {**os.environ, **credentials.job_env(app_id), "FASTLANE_SKIP_UPDATE_CHECK": "1"}
    if key == "android":
        if not env.get("SERVICE_ACCOUNT_JSON"):
            return {"success": False, "error": "Google Play service account not configured for this app (Credentials)."}
        env["ANDROID_PACKAGE_NAME"] = identifier
    else:
        if not env.get("APPLE_API_KEY") or not env.get("APPLE_API_ISSUER"):
            return {"success": False, "error": "Apple API key / issuer not configured for this app (Credentials)."}
        env["IOS_BUNDLE_ID"] = identifier
    gemfile = FASTLANE_DIR / "Gemfile"
    if gemfile.is_file():
        env.setdefault("BUNDLE_GEMFILE", str(gemfile))
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "locales.json"
        env["LOCALES_OUT"] = str(out)
        cmd = ["bundle", "exec", "fastlane", key, "list_locales"]
        logger.info("Running %s for %s", " ".join(cmd), identifier)
        try:
            proc = subprocess.run(cmd, cwd=str(FASTLANE_DIR), env=env, capture_output=True, text=True,
                                  timeout=LANE_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Timed out after {LANE_TIMEOUT_SECONDS}s talking to the store."}
        except OSError as e:
            return {"success": False, "error": f"Could not run fastlane: {e}"}
        if proc.returncode != 0 or not out.is_file():
            tail = "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-12:])
            return {"success": False, "error": "Could not read locales from the store.", "output": tail}
        try:
            locales = _clean_locales(json.loads(out.read_text(encoding="utf-8")))
        except ValueError:
            return {"success": False, "error": "Store returned an unreadable locale list."}
    return {"success": True, "platform": key, "identifier": identifier, "locales": locales}


def update_build_notes(app_id: str, platform: str, version: str, notes: Any, identifier: str = "") -> dict[str, Any]:
    """Save notes for a build and, on iOS, publish them to that TestFlight build.

    Android keeps "save only": Google Play cannot edit a released track.
    """
    saved = save_release_notes(app_id, platform, version, notes)
    if not saved.get("success") or _platform_key(platform) == "android":
        if saved.get("success"):
            saved["published"] = False
            saved["note"] = "Saved. Google Play cannot change the notes of an already-published release."
        return saved
    identifier = (identifier or default_identifier(app_id, "ios")).strip()
    published, errors = [], []
    for loc, text in notes.items():
        if not str(text or "").strip():
            continue
        res = store_metadata_update(app_id, identifier, _clean_version(version), str(text), str(loc))
        (published if res.get("success") else errors).append(loc if res.get("success") else f"{loc}: {res.get('error')}")
    out = {"success": not errors, "saved": saved["saved"], "published": published, "version": saved["version"]}
    if errors:
        out["error"] = "; ".join(errors)
    return out


def store_metadata_update(app_id: str, bundle_id: str, build: str, text: str, locale: str) -> dict[str, Any]:
    from .notes_updater import update_testflight_notes
    return update_testflight_notes(app_id, bundle_id, build, text, locale, save_to_files=False)
