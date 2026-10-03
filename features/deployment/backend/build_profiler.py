"""Backward compatibility alias for automation.build_profiler."""
import sys
from automation import build_profiler as _impl

sys.modules[__name__] = _impl
