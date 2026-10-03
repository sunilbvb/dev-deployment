"""Backward compatibility alias for automation.cache_warmer."""
import sys
from automation import cache_warmer as _impl

sys.modules[__name__] = _impl
