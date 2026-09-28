import base64
import json
import re
import stat
from pathlib import Path
from typing import Any, Dict, Optional

from config import (
    WORKSPACE_ROOT,
    get_deploy_config_file,
    load_deploy_config,
    save_deploy_config,
)


def upload_p8_key(app_id: str, filename: str, content_bytes: bytes, issuer_id: str = "") -> dict[str, Any]:
    """
    Receive an uploaded .p8 file, base64-encode it, persist to deploy_config,
    and write it to the Apple industry-standard key location with correct permissions.
    """
    # Path traversal protection on filename parameter
    safe_filename = Path(filename).name
    match = re.search(r"AuthKey[_-]([A-Z0-9]{10})", safe_filename, re.IGNORECASE)
    if not match:
        return {
            "success": False,
            "error": (
                f"Cannot extract Key ID from filename '{filename}'. "
                "Expected format: AuthKey_XXXXXXXXXX.p8 (10-char uppercase key ID)."
            ),
        }
    key_id = match.group(1).upper()

    b64_content = base64.b64encode(content_bytes).decode("ascii")

    deploy_config = load_deploy_config()
    if "apps" not in deploy_config:
        deploy_config["apps"] = {}
    if app_id not in deploy_config["apps"]:
        deploy_config["apps"][app_id] = {}

    deploy_config["apps"][app_id]["apple_key_id"] = key_id
    deploy_config["apps"][app_id]["apple_p8_base64"] = b64_content
    if issuer_id:
        deploy_config["apps"][app_id]["apple_issuer_id"] = issuer_id

    cfg_path = get_deploy_config_file()
    try:
        cfg_path.write_text(json.dumps(deploy_config, indent=2), encoding="utf-8")
    except Exception as exc:
        return {"success": False, "error": f"Failed to save deploy config: {exc}"}

    std_dir = Path.home() / ".appstoreconnect" / "private_keys"
    std_dir.mkdir(parents=True, exist_ok=True)
    std_key_path = std_dir / f"AuthKey_{key_id}.p8"
    try:
        std_key_path.write_bytes(content_bytes)
        std_key_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except Exception as exc:
        return {
            "success": False,
            "error": f"Key ID '{key_id}' stored in config, but could not write to {std_key_path}: {exc}",
        }

    return {
        "success": True,
        "key_id": key_id,
        "stored_path": str(std_key_path),
        "b64_stored": True,
        "app_id": app_id,
    }
