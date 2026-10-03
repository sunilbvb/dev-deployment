"""Backward compatibility alias for automation.adb_manager."""
import sys
from automation import adb_manager as _impl

sys.modules[__name__] = _impl
