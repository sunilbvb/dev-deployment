"""Pure Python QR Code Generator package.

Supports QR Code model 2 (versions 1-10) with byte mode encoding.
No external dependencies — Python standard library only.
"""

from __future__ import annotations

from .matrix import (
    ALIGNMENT_LOCATIONS,
    EXP_TABLE,
    LOG_TABLE,
    SPECS_L,
    SPECS_M,
    generate_qr,
    generate_qr_matrix,
)
from .renderer import (
    qr_ascii,
    qr_svg,
)

__all__ = [
    "ALIGNMENT_LOCATIONS",
    "EXP_TABLE",
    "LOG_TABLE",
    "SPECS_L",
    "SPECS_M",
    "generate_qr",
    "generate_qr_matrix",
    "qr_ascii",
    "qr_svg",
]
