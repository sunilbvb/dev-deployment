"""Store Metadata & Localized Release Notes Hub.

Handles Fastlane metadata scanning, multi-locale changelog management,
real-time character count limits (500-char Play Store limit, 4000-char App Store limit),
and phone update card preview generation. Pure Python standard library only.
"""

from .store_metadata import (
    METADATA_LIMITS,
    get_store_metadata,
    save_store_metadata,
    preview_store_card,
)
from .notes_updater import update_testflight_notes
from . import release_notes

__all__ = [
    "METADATA_LIMITS",
    "get_store_metadata",
    "save_store_metadata",
    "preview_store_card",
    "update_testflight_notes",
    "release_notes",
]
