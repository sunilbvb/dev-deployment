from pathlib import Path
from typing import Any

from credentials import import_credential_bytes


def upload_p8_key(app_id: str, filename: str, content_bytes: bytes, issuer_id: str = "") -> dict[str, Any]:
    """Store an uploaded App Store Connect .p8 key outside the workspace (chmod 600)."""
    safe_name = Path(filename).name
    if not safe_name.lower().endswith(".p8"):
        return {"success": False, "error": "Expected an App Store Connect key file named AuthKey_XXXXXXXXXX.p8"}
    res = import_credential_bytes(safe_name, content_bytes, app_id=app_id, issuer_id=issuer_id)
    if res.get("success"):
        res["b64_stored"] = False
    return res
