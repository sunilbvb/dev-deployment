"""QR Code Renderers.

Provides SVG vector markup generation and compact UTF-8 half-block ASCII
rendering for terminals.
"""

from __future__ import annotations

from .matrix import generate_qr_matrix


def qr_svg(
    text: str,
    box_size: int = 6,
    ec_level: str = "L",
    fg_color: str = "#000000",
    bg_color: str = "#ffffff",
) -> str:
    """Generate clean, scalable SVG markup for QR Code."""
    grid = generate_qr_matrix(text, ec_level=ec_level)
    dim = len(grid)
    svg_size = dim * box_size

    rects = []
    for r, row in enumerate(grid):
        for c, is_black in enumerate(row):
            if is_black:
                rects.append(
                    f'<rect x="{c * box_size}" y="{r * box_size}" '
                    f'width="{box_size}" height="{box_size}" fill="{fg_color}"/>'
                )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_size} {svg_size}" '
        f'width="{svg_size}" height="{svg_size}" style="background: {bg_color}; border-radius: 8px;">\n'
        f'  <rect width="100%" height="100%" fill="{bg_color}"/>\n'
        f'  {"".join(rects)}\n'
        f'</svg>'
    )


def qr_ascii(text: str, ec_level: str = "L") -> str:
    """Generate compact two-line Unicode block character ASCII string for terminal display."""
    grid = generate_qr_matrix(text, ec_level=ec_level)
    dim = len(grid)

    lines = []
    # Process 2 vertical modules per terminal line using half-block characters
    # ▀ (top black, bottom white)
    # ▄ (top white, bottom black)
    # █ (both black)
    # ' ' (both white)
    for r in range(0, dim, 2):
        line = ""
        for c in range(dim):
            top = grid[r][c]
            bottom = grid[r + 1][c] if r + 1 < dim else False
            if top and bottom:
                line += "█"
            elif top and not bottom:
                line += "▀"
            elif not top and bottom:
                line += "▄"
            else:
                line += " "
        lines.append(line)

    return "\n".join(lines)
