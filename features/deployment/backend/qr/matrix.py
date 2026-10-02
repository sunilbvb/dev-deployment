"""QR Code 2D Boolean Matrix Generator.

Implements QR Code model 2 (versions 1-10) with byte mode encoding, Galois Field
GF(256) arithmetic, Reed-Solomon error correction, alignment patterns, and
penalty evaluation.
"""

from __future__ import annotations

from typing import Optional

# Galois Field GF(256) tables with primitive polynomial 0x11D
EXP_TABLE = [0] * 512
LOG_TABLE = [0] * 256

_x = 1
for _i in range(255):
    EXP_TABLE[_i] = _x
    EXP_TABLE[_i + 255] = _x
    LOG_TABLE[_x] = _i
    _x <<= 1
    if _x & 256:
        _x ^= 0x11D


def _gmult(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return EXP_TABLE[LOG_TABLE[a] + LOG_TABLE[b]]


def _rs_poly(n_ec: int) -> list[int]:
    """Calculate Reed-Solomon error correction generator polynomial."""
    g = [1]
    for i in range(n_ec):
        factor = [1, EXP_TABLE[i]]
        res = [0] * (len(g) + 1)
        for j, c in enumerate(g):
            res[j] ^= _gmult(c, factor[0])
            res[j + 1] ^= _gmult(c, factor[1])
        g = res
    return g


def _rs_encode(data: list[int], n_ec: int) -> list[int]:
    """Calculate Reed-Solomon error correction parity bytes."""
    gen = _rs_poly(n_ec)
    msg = list(data) + [0] * n_ec
    for i in range(len(data)):
        lead = msg[i]
        if lead != 0:
            for j, g in enumerate(gen):
                msg[i + j] ^= _gmult(g, lead)
    return msg[len(data):]


# Capacity specifications for Versions 1-10 in Level L (01) and Level M (00)
# Format: (total_data_bytes, [(num_blocks, data_bytes_per_block, ec_bytes_per_block), ...])
SPECS_L: dict[int, tuple[int, list[tuple[int, int, int]]]] = {
    1: (19, [(1, 19, 7)]),
    2: (34, [(1, 34, 10)]),
    3: (55, [(1, 55, 15)]),
    4: (80, [(1, 80, 20)]),
    5: (108, [(1, 108, 26)]),
    6: (136, [(2, 68, 18)]),
    7: (156, [(2, 78, 20)]),
    8: (194, [(2, 97, 24)]),
    9: (232, [(2, 116, 30)]),
    10: (274, [(2, 68, 18), (2, 69, 18)]),
}

SPECS_M: dict[int, tuple[int, list[tuple[int, int, int]]]] = {
    1: (16, [(1, 16, 10)]),
    2: (28, [(1, 28, 16)]),
    3: (44, [(1, 44, 26)]),
    4: (64, [(2, 32, 18)]),
    5: (86, [(2, 43, 24)]),
    6: (108, [(4, 27, 16)]),
    7: (124, [(4, 31, 18)]),
    8: (154, [(2, 38, 22), (2, 39, 22)]),
    9: (182, [(3, 36, 22), (2, 37, 22)]),
    10: (216, [(4, 40, 26), (1, 41, 26)]),
}

ALIGNMENT_LOCATIONS: dict[int, list[int]] = {
    1: [],
    2: [6, 18],
    3: [6, 22],
    4: [6, 26],
    5: [6, 30],
    6: [6, 34],
    7: [6, 22, 38],
    8: [6, 24, 42],
    9: [6, 26, 46],
    10: [6, 28, 50],
}


def _format_info_bits(ec_level_bits: int, mask_idx: int) -> int:
    """Calculate 15-bit format information with BCH(15, 5) error correction."""
    data = (ec_level_bits << 3) | mask_idx
    rem = data << 10
    for i in range(5):
        if rem & (1 << (14 - i)):
            rem ^= (0x537 << (4 - i))
    return ((data << 10) | rem) ^ 0x5412


def _select_version(data_len: int, ec_level: str) -> int:
    specs = SPECS_M if ec_level == "M" else SPECS_L
    for v in sorted(specs.keys()):
        cap = specs[v][0]
        # In byte mode: 4 bits mode + 8 bits length indicator (16 for v>=10) = ~12 bits overhead
        overhead_bytes = 3 if v >= 10 else 2
        if data_len + overhead_bytes <= cap:
            return v
    raise ValueError(f"Text too long ({data_len} bytes) for supported QR versions 1-10")


def _encode_data(text_bytes: bytes, version: int, ec_level: str) -> list[int]:
    """Pack byte mode data, terminator, padding, and interleave Reed-Solomon blocks."""
    specs = SPECS_M if ec_level == "M" else SPECS_L
    total_data_cap, block_specs = specs[version]

    # Bit stream
    bits = []

    def append_bits(val: int, length: int) -> None:
        for i in range(length - 1, -1, -1):
            bits.append((val >> i) & 1)

    # 1. Mode indicator: Byte mode is 0100
    append_bits(0b0100, 4)

    # 2. Character count indicator: 8 bits for v1-9, 16 for v>=10
    char_count_bits = 16 if version >= 10 else 8
    append_bits(len(text_bytes), char_count_bits)

    # 3. Data bytes
    for b in text_bytes:
        append_bits(b, 8)

    # 4. Terminator (up to 4 zeroes)
    max_bits = total_data_cap * 8
    term_len = min(4, max_bits - len(bits))
    append_bits(0, term_len)

    # 5. Pad to multiple of 8
    while len(bits) % 8 != 0:
        bits.append(0)

    # Convert to bytes
    raw_data_bytes = []
    for i in range(0, len(bits), 8):
        byte_val = 0
        for bit in bits[i:i + 8]:
            byte_val = (byte_val << 1) | bit
        raw_data_bytes.append(byte_val)

    # 6. Pad with alternating 0xEC and 0x11
    pad_bytes = [0xEC, 0x11]
    pad_idx = 0
    while len(raw_data_bytes) < total_data_cap:
        raw_data_bytes.append(pad_bytes[pad_idx % 2])
        pad_idx += 1

    # Split into blocks and compute RS parity bytes
    data_blocks: list[list[int]] = []
    ec_blocks: list[list[int]] = []

    cursor = 0
    for num_blocks, data_len, ec_len in block_specs:
        for _ in range(num_blocks):
            blk_data = raw_data_bytes[cursor:cursor + data_len]
            cursor += data_len
            blk_ec = _rs_encode(blk_data, ec_len)
            data_blocks.append(blk_data)
            ec_blocks.append(blk_ec)

    # Interleave data bytes
    final_codewords: list[int] = []
    max_data_len = max(len(b) for b in data_blocks)
    for i in range(max_data_len):
        for b in data_blocks:
            if i < len(b):
                final_codewords.append(b[i])

    # Interleave EC bytes
    max_ec_len = max(len(b) for b in ec_blocks)
    for i in range(max_ec_len):
        for b in ec_blocks:
            if i < len(b):
                final_codewords.append(b[i])

    return final_codewords


def _mask_condition(mask_idx: int, r: int, c: int) -> bool:
    if mask_idx == 0:
        return (r + c) % 2 == 0
    if mask_idx == 1:
        return r % 2 == 0
    if mask_idx == 2:
        return c % 3 == 0
    if mask_idx == 3:
        return (r + c) % 3 == 0
    if mask_idx == 4:
        return (r // 2 + c // 3) % 2 == 0
    if mask_idx == 5:
        return ((r * c) % 2) + ((r * c) % 3) == 0
    if mask_idx == 6:
        return (((r * c) % 2) + ((r * c) % 3)) % 2 == 0
    if mask_idx == 7:
        return (((r + c) % 2) + ((r * c) % 3)) % 2 == 0
    return False


def _evaluate_penalty(matrix: list[list[bool]], size: int) -> int:
    """Calculate ISO 18004 penalty score (rules N1 to N4)."""
    penalty = 0

    # N1: 5 or more same color in row/col
    for r in range(size):
        run_len = 1
        for c in range(1, size):
            if matrix[r][c] == matrix[r][c - 1]:
                run_len += 1
            else:
                if run_len >= 5:
                    penalty += 3 + (run_len - 5)
                run_len = 1
        if run_len >= 5:
            penalty += 3 + (run_len - 5)

    for c in range(size):
        run_len = 1
        for r in range(1, size):
            if matrix[r][c] == matrix[r - 1][c]:
                run_len += 1
            else:
                if run_len >= 5:
                    penalty += 3 + (run_len - 5)
                run_len = 1
        if run_len >= 5:
            penalty += 3 + (run_len - 5)

    # N2: 2x2 blocks of same color
    for r in range(size - 1):
        for c in range(size - 1):
            val = matrix[r][c]
            if val == matrix[r + 1][c] == matrix[r][c + 1] == matrix[r + 1][c + 1]:
                penalty += 3

    # N4: Dark module ratio
    dark_count = sum(sum(1 for val in row if val) for row in matrix)
    percent = (dark_count * 100) // (size * size)
    prev_mult = abs(percent - 50) // 5
    penalty += prev_mult * 10

    return penalty


def generate_qr_matrix(text: str, ec_level: str = "L") -> list[list[bool]]:
    """Generate 2D boolean QR Code matrix (True = black, False = white)."""
    ec_level = ec_level.upper()
    if ec_level not in ("L", "M"):
        ec_level = "L"

    text_bytes = text.encode("utf-8")
    version = _select_version(len(text_bytes), ec_level)
    size = 17 + 4 * version

    matrix: list[list[Optional[bool]]] = [[None] * size for _ in range(size)]
    reserved: list[list[bool]] = [[False] * size for _ in range(size)]

    def set_module(r: int, c: int, val: bool, is_reserved: bool = True) -> None:
        if 0 <= r < size and 0 <= c < size:
            matrix[r][c] = val
            if is_reserved:
                reserved[r][c] = True

    # 1. Finder patterns (7x7) + separators (1-module white)
    def place_finder(top_r: int, left_c: int) -> None:
        for r in range(-1, 8):
            for c in range(-1, 8):
                mr, mc = top_r + r, left_c + c
                if 0 <= mr < size and 0 <= mc < size:
                    if 0 <= r <= 6 and 0 <= c <= 6:
                        is_black = (r in (0, 6) or c in (0, 6) or (2 <= r <= 4 and 2 <= c <= 4))
                        set_module(mr, mc, is_black)
                    else:
                        set_module(mr, mc, False)

    place_finder(0, 0)
    place_finder(0, size - 7)
    place_finder(size - 7, 0)

    # 2. Timing patterns
    for i in range(8, size - 8):
        is_black = (i % 2 == 0)
        set_module(6, i, is_black)
        set_module(i, 6, is_black)

    # 3. Dark module
    set_module(4 * version + 9, 8, True)

    # 4. Alignment patterns (version >= 2)
    align_pos = ALIGNMENT_LOCATIONS.get(version, [])
    for ar in align_pos:
        for ac in align_pos:
            # Skip if overlapping with finder patterns
            if ar < 9 and ac < 9:
                continue
            if ar < 9 and ac >= size - 9:
                continue
            if ar >= size - 9 and ac < 9:
                continue
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    is_black = (abs(dr) == 2 or abs(dc) == 2 or (dr == 0 and dc == 0))
                    set_module(ar + dr, ac + dc, is_black)

    # 5. Reserve format information areas
    for c in range(9):
        if c != 6:
            reserved[8][c] = True
    for r in range(9):
        if r != 6:
            reserved[r][8] = True
    for c in range(size - 8, size):
        reserved[8][c] = True
    for r in range(size - 7, size):
        reserved[r][8] = True

    # 6. Place data codewords
    codewords = _encode_data(text_bytes, version, ec_level)
    data_bits = []
    for cw in codewords:
        for bit_idx in range(7, -1, -1):
            data_bits.append((cw >> bit_idx) & 1)

    bit_cursor = 0
    c = size - 1
    upward = True

    while c > 0:
        if c == 6:  # Skip vertical timing pattern
            c -= 1
        cols = [c, c - 1]
        row_range = range(size - 1, -1, -1) if upward else range(size)

        for r in row_range:
            for col_idx in cols:
                if not reserved[r][col_idx]:
                    val = bool(data_bits[bit_cursor]) if bit_cursor < len(data_bits) else False
                    matrix[r][col_idx] = val
                    bit_cursor += 1

        upward = not upward
        c -= 2

    # 7. Select best mask
    ec_level_bits = 1 if ec_level == "L" else 0
    best_penalty = 10**9
    best_matrix: list[list[bool]] = []

    for mask_idx in range(8):
        cand: list[list[bool]] = []
        for r in range(size):
            row = []
            for col_idx in range(size):
                orig = bool(matrix[r][col_idx])
                if not reserved[r][col_idx]:
                    if _mask_condition(mask_idx, r, col_idx):
                        orig = not orig
                row.append(orig)
            cand.append(row)

        fmt_bits = _format_info_bits(ec_level_bits, mask_idx)
        for i in range(6):
            cand[8][i] = bool((fmt_bits >> i) & 1)
        cand[8][7] = bool((fmt_bits >> 6) & 1)
        cand[8][8] = bool((fmt_bits >> 7) & 1)
        cand[7][8] = bool((fmt_bits >> 8) & 1)
        for i in range(9, 15):
            cand[14 - i][8] = bool((fmt_bits >> i) & 1)

        for i in range(8):
            cand[size - 1 - i][8] = bool((fmt_bits >> i) & 1)
        for i in range(8, 15):
            cand[8][size - 15 + i] = bool((fmt_bits >> i) & 1)

        penalty = _evaluate_penalty(cand, size)
        if penalty < best_penalty:
            best_penalty = penalty
            best_matrix = cand

    # Add 4-module quiet zone (white border)
    border = 4
    full_size = size + 2 * border
    final_grid: list[list[bool]] = [[False] * full_size for _ in range(full_size)]

    for r in range(size):
        for col_idx in range(size):
            final_grid[r + border][col_idx + border] = best_matrix[r][col_idx]

    return final_grid


generate_qr = generate_qr_matrix
