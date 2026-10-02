"""Certificate & Keystore Expiry Sentinel.

Modular architecture:
- parsers: ASN.1 and certificate date parsing helpers
- apple_sentinel: Apple .p8 keys, certificates, and provisioning profile expiry checks
- android_sentinel: Android keystore and upload key validity monitoring
- firebase_sentinel: Cross-platform Firebase project ID and bundle ID consistency checks
- runner: Full sentinel aggregation and badge computation
"""

from .parsers import (
    EXPIRY_THRESHOLD_DAYS,
    _days_until,
    _inspect_p8_key,
    _parse_asn1_time,
    extract_validity_from_keystore_bytes,
)
from .apple_sentinel import check_apple_expiry
from .android_sentinel import (
    _locate_android_keystore,
    _parse_keystore_expiry_keytool,
    _parse_keystore_expiry_openssl,
    check_android_keystore_expiry,
    inspect_android_keystore_expiry,
)
from .firebase_sentinel import (
    _locate_firebase_android_config,
    _locate_firebase_ios_config,
    check_firebase_mismatch,
    check_firebase_sync,
)
from .runner import (
    check_app_sentinel,
    check_credentials_expiry,
    check_workspace_sentinel,
)

# Alias for backward compatibility
check_all_sentinels = check_workspace_sentinel

__all__ = [
    "EXPIRY_THRESHOLD_DAYS",
    "extract_validity_from_keystore_bytes",
    "inspect_android_keystore_expiry",
    "check_apple_expiry",
    "check_android_keystore_expiry",
    "check_firebase_mismatch",
    "check_firebase_sync",
    "check_app_sentinel",
    "check_workspace_sentinel",
    "check_all_sentinels",
    "check_credentials_expiry",
    "_parse_asn1_time",
    "_days_until",
    "_inspect_p8_key",
    "_locate_android_keystore",
    "_parse_keystore_expiry_keytool",
    "_parse_keystore_expiry_openssl",
    "_locate_firebase_android_config",
    "_locate_firebase_ios_config",
]
