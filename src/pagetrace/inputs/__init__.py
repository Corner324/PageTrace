"""Trace parsers. Untrusted input stops here: bodies are parsed, headers are filtered.

Every parser yields `RawObservation` and raises only `PageTraceError`, never a traceback.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

from pagetrace.errors import PageTraceError
from pagetrace.model import RawObservation

# Only these response headers reach the model. An allowlist cannot leak the next secret header
# somebody invents; a denylist can. See docs/security.md.
HEADER_ALLOWLIST = frozenset({"link", "content-type"})


def read_trace(path: Path, input_format: str) -> list[RawObservation]:
    """Read a whole trace. `input_format` is "auto", "jsonl" or "har"."""
    from pagetrace.inputs.har import read_har
    from pagetrace.inputs.jsonl import read_jsonl

    resolved = detect_format(path) if input_format == "auto" else input_format
    reader = read_jsonl if resolved == "jsonl" else read_har
    return list(reader(path))


def detect_format(path: Path) -> str:
    """Pick a parser from the file extension. Content sniffing would guess; this does not."""
    suffix = path.suffix.lower()
    if suffix in {".jsonl", ".ndjson"}:
        return "jsonl"
    if suffix == ".har":
        return "har"
    raise PageTraceError(
        f"cannot tell the format of {path.name} from its extension; pass --input-format"
    )


def as_object(value: object) -> dict[str, Any] | None:
    """A JSON object, or None.

    One place to lose the `Unknown` a bare isinstance leaves behind, so parsers read
    as parsers instead of as a wall of type suppressions.
    """
    if isinstance(value, dict):
        return cast("dict[str, Any]", value)
    return None


def as_array(value: object) -> list[Any] | None:
    """A JSON array, or None."""
    if isinstance(value, list):
        return cast("list[Any]", value)
    return None


def filter_headers(headers: object) -> dict[str, str]:
    """Lowercase header names and keep only the allowlist. Anything odd is dropped silently."""
    mapping = as_object(headers)
    if mapping is None:
        return {}
    kept: dict[str, str] = {}
    for name, value in mapping.items():
        lowered = str(name).lower()
        if isinstance(value, str) and lowered in HEADER_ALLOWLIST:
            kept[lowered] = value
    return kept


def iter_lines(path: Path, max_bytes: int) -> Iterator[tuple[int, bytes]]:
    """Yield (line number, bytes) without ever holding more than one bounded line in memory."""
    try:
        handle = path.open("rb")
    except OSError as exc:
        raise PageTraceError(f"cannot read {path}: {exc}") from exc

    with handle:
        line_number = 0
        while True:
            # readline(size) stops after size bytes, so a single huge line cannot be inhaled.
            chunk = handle.readline(max_bytes + 1)
            if not chunk:
                return
            line_number += 1
            if len(chunk) > max_bytes:
                raise PageTraceError(f"line {line_number}: longer than the {max_bytes} byte limit")
            yield line_number, chunk
