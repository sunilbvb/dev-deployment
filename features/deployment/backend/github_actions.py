"""Backward compatibility alias for automation.github_actions."""
import sys
from automation import github_actions as _impl

sys.modules[__name__] = _impl
