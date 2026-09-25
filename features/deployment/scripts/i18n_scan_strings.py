#!/usr/bin/env python3
"""
Heuristic hard-coded string scanner for Flutter/Dart sources.

Why heuristic?
- Fast, zero dependencies (no analyzer pub get).
- Good enough for "find candidates" workflows.

What it does:
- Recursively scans `lib/` under a given package/app directory.
- Extracts string literals and filters to likely user-facing contexts (e.g. Text(...), hintText: ...).
- Emits a JSON list with absolute/relative paths, line, offset, length, and originalValue.

Limitations:
- Not a full Dart parser; may miss/overmatch in complex cases.
- Use as a candidate generator; review results before applying refactors.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Sequence, Tuple


SKIP_FILE_SUFFIXES: Tuple[str, ...] = (
    ".g.dart",
    ".freezed.dart",
    ".config.dart",
)


DEFAULT_CONTEXT_TOKENS: Tuple[str, ...] = (
    "Text(",
    "RichText(",
    "TextSpan(",
    "Tooltip(",
    "hintText:",
    "labelText:",
    "helperText:",
    "errorText:",
    "title:",
    "subtitle:",
    "content:",
    "message:",
    "placeholder:",
    "emptyText:",
    "validator:",
    "ValidationCallback",
    "FormFieldValidator",
)


IGNORE_VALUE_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s*$"),
    re.compile(r"^https?://", re.IGNORECASE),
    re.compile(r"^file://", re.IGNORECASE),
    re.compile(r"^assets?/", re.IGNORECASE),
    re.compile(r"^[\w\-./]+\.(png|jpg|jpeg|gif|webp|svg|json|yaml|yml)$", re.IGNORECASE),
)


@dataclass(frozen=True)
class Match:
    id: str
    absolutePath: str
    relativePath: str
    lineNumber: int
    characterOffset: int
    length: int
    originalValue: str


def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _is_generated_file(path: Path) -> bool:
    name: str = path.name
    return any(name.endswith(suf) for suf in SKIP_FILE_SUFFIXES)


def _iter_dart_files(root: Path) -> Iterator[Path]:
    for p in root.rglob("*.dart"):
        if _is_generated_file(p):
            continue
        yield p


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _line_starts(text: str) -> List[int]:
    starts: List[int] = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            starts.append(i + 1)
    return starts


def _line_of_offset(starts: Sequence[int], offset: int) -> int:
    # 1-based line number
    lo: int = 0
    hi: int = len(starts) - 1
    while lo <= hi:
        mid: int = (lo + hi) // 2
        if starts[mid] <= offset:
            lo = mid + 1
        else:
            hi = mid - 1
    return hi + 1


def _extract_string_literals(source: str) -> Iterator[Tuple[int, int, str]]:
    """
    Yields (start_offset_including_quotes, end_offset_excluding_end_quote, value_unescaped_minimal)

    Handles:
    - single/double quoted strings
    - triple quoted strings
    - raw strings (r'..', r"..", r'''..''', r\"\"\"..\"\"\")

    Not a full Dart lexer; aims to avoid comments and handle escapes.
    """
    i: int = 0
    n: int = len(source)
    in_line_comment: bool = False
    in_block_comment: int = 0

    while i < n:
        ch: str = source[i]

        # Comments
        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
            i += 1
            continue
        if in_block_comment > 0:
            if source.startswith("/*", i):
                in_block_comment += 1
                i += 2
                continue
            if source.startswith("*/", i):
                in_block_comment -= 1
                i += 2
                continue
            i += 1
            continue

        if source.startswith("//", i):
            in_line_comment = True
            i += 2
            continue
        if source.startswith("/*", i):
            in_block_comment = 1
            i += 2
            continue

        # Detect raw prefix r/R
        raw_prefix: bool = False
        if ch in ("r", "R") and i + 1 < n and source[i + 1] in ("'", '"'):
            raw_prefix = True
            i += 1
            ch = source[i]

        if ch not in ("'", '"'):
            i += 1
            continue

        quote: str = ch
        triple: bool = source.startswith(quote * 3, i)
        qlen: int = 3 if triple else 1
        start: int = i - (1 if raw_prefix else 0)  # include r prefix in offset? no, we want literal start at quote
        start = i  # offset points to opening quote for safe replacement
        i += qlen
        buf: List[str] = []

        while i < n:
            if triple:
                if source.startswith(quote * 3, i):
                    end: int = i + 3
                    i = end
                    yield (start, end, "".join(buf))
                    break
                buf.append(source[i])
                i += 1
                continue

            # single-quote / double-quote
            c: str = source[i]
            if c == "\\" and not raw_prefix:
                if i + 1 < n:
                    # keep next char (approximate); we don't fully unescape because we only need display
                    buf.append(source[i + 1])
                    i += 2
                    continue
            if c == quote:
                end = i + 1
                i = end
                yield (start, end, "".join(buf))
                break
            buf.append(c)
            i += 1

        continue


def _looks_user_facing(value: str) -> bool:
    if "$" in value:
        return False  # interpolations need AST-level handling later
    for pat in IGNORE_VALUE_PATTERNS:
        if pat.search(value):
            return False
    return True


def _has_context(source: str, lit_start: int, context_tokens: Sequence[str], window: int) -> bool:
    left: int = max(0, lit_start - window)
    prefix: str = source[left:lit_start]
    return any(tok in prefix for tok in context_tokens)


def _is_map_key_literal(source: str, lit_end: int) -> bool:
    i: int = lit_end
    n: int = len(source)
    while i < n and source[i] in (" ", "\t", "\n", "\r"):
        i += 1
    return i < n and source[i] == ":"


def _make_id(rel_path: str, offset: int, value: str) -> str:
    return _sha1(f"{rel_path}:{offset}:{value}")


def scan(
    package_root: Path,
    *,
    contexts: Sequence[str],
    context_window: int,
    max_results: int,
) -> List[Match]:
    lib_root: Path = package_root / "lib"
    if not lib_root.exists():
        raise SystemExit(f"lib/ not found under: {package_root}")

    results: List[Match] = []
    workspace_root: Path = package_root

    for dart_file in _iter_dart_files(lib_root):
        source: str = _read_text(dart_file)
        starts: List[int] = _line_starts(source)
        abs_path: str = str(dart_file.resolve())
        rel_path: str = str(dart_file.relative_to(workspace_root))

        for start, end, value in _extract_string_literals(source):
            if len(results) >= max_results:
                return results
            if not _looks_user_facing(value):
                continue
            if _is_map_key_literal(source, end):
                continue
            if not _has_context(source, start, contexts, context_window):
                continue

            line_no: int = _line_of_offset(starts, start)
            m: Match = Match(
                id=_make_id(rel_path, start, value),
                absolutePath=abs_path,
                relativePath=rel_path,
                lineNumber=line_no,
                characterOffset=start,
                length=(end - start),
                originalValue=value,
            )
            results.append(m)

    return results


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Scan Flutter/Dart lib/ for likely user-facing hardcoded strings.")
    parser.add_argument("path", help="Path to app/package root (must contain lib/).")
    parser.add_argument("--out", help="Write JSON output to this file (defaults to stdout).")
    parser.add_argument(
        "--context",
        action="append",
        default=[],
        help="Add an extra context token (may be repeated). Example: --context 'AppText('",
    )
    parser.add_argument("--window", type=int, default=220, help="Context lookback window in characters.")
    parser.add_argument("--max", type=int, default=5000, help="Maximum matches to return.")
    args = parser.parse_args(argv)

    path_strs = [p.strip() for p in str(args.path).split(',') if p.strip()]
    contexts: List[str] = list(DEFAULT_CONTEXT_TOKENS) + list(args.context or [])
    matches: List[Match] = []
    
    for p_str in path_strs:
        package_root = Path(os.path.expanduser(p_str)).resolve()
        if not package_root.exists():
            continue
        sub_matches: List[Match] = scan(
            package_root,
            contexts=contexts,
            context_window=int(args.window),
            max_results=int(args.max),
        )
        matches.extend(sub_matches)

    payload = [m.__dict__ for m in matches]
    data = json.dumps(payload, ensure_ascii=False, indent=2)

    if args.out:
        out_path = Path(os.path.expanduser(args.out)).resolve()
        out_path.write_text(data, encoding="utf-8")
    else:
        sys.stdout.write(data)
        if not data.endswith("\n"):
            sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
