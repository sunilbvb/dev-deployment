"""Short-lived, file-scoped tokens for install links and QR codes.

Install links are scanned by phones on the LAN and end up in logs and history, so
they must not carry the console's master API token (which can run deploys). A
download token only opens one artifact (target) for one purpose (scope) and
expires after DOWNLOAD_TOKEN_TTL seconds. It is not single-use: Android download
managers and iOS make several requests (HEAD, ranges, manifest + IPA) per install.
"""

from __future__ import annotations

import hmac
import secrets
import threading
import time

DOWNLOAD_TOKEN_TTL = 30 * 60
_MAX_TOKENS = 500

_lock = threading.Lock()
_tokens: dict[str, tuple[str, frozenset[str], float]] = {}


def issue(target: str, scopes: set[str] | frozenset[str]) -> str:
    """Create a token valid for `target` in the given scopes ('apk', 'ipa', 'manifest')."""
    now = time.time()
    token = "dl_" + secrets.token_hex(16)
    with _lock:
        for t, (_, _, exp) in list(_tokens.items()):
            if exp <= now:
                del _tokens[t]
        if len(_tokens) >= _MAX_TOKENS:
            oldest = min(_tokens, key=lambda t: _tokens[t][2])
            del _tokens[oldest]
        _tokens[token] = (str(target), frozenset(scopes), now + DOWNLOAD_TOKEN_TTL)
    return token


def check(token: str, target: str, scope: str) -> bool:
    if not token or not token.startswith("dl_"):
        return False
    with _lock:
        entry = _tokens.get(token)
    if not entry:
        return False
    t_target, t_scopes, exp = entry
    return exp > time.time() and scope in t_scopes and hmac.compare_digest(t_target, str(target))
