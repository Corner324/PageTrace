"""JSONL v1 reader. Format contract: specs/formats/jsonl-v1.md."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from pagetrace.errors import PageTraceError
from pagetrace.inputs import as_object, filter_headers, iter_lines
from pagetrace.limits import MAX_LINE_BYTES
from pagetrace.model import RawObservation, canonical_text

SUPPORTED_VERSION = 1


def read_jsonl(path: Path) -> Iterator[RawObservation]:
    """Parse a JSONL trace, one bounded line at a time."""
    previous_seq: int | None = None
    index = 0

    for line_number, raw in iter_lines(path, MAX_LINE_BYTES):
        text = _decode(raw, line_number)
        if not text.strip():
            continue

        record = _parse_object(text, line_number)
        _check_version(record, line_number)
        previous_seq = _check_seq(record, line_number, previous_seq)

        yield _build(record, line_number, index)
        index += 1

    if index == 0:
        raise PageTraceError(f"{path.name}: no trace records found")


def _decode(raw: bytes, line_number: int) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PageTraceError(f"line {line_number}: not valid UTF-8 ({exc.reason})") from exc


def _parse_object(text: str, line_number: int) -> dict[str, Any]:
    try:
        value: object = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PageTraceError(f"line {line_number}: invalid JSON: {exc.msg}") from exc
    except RecursionError as exc:
        raise PageTraceError(f"line {line_number}: JSON nested too deeply") from exc

    record = as_object(value)
    if record is None:
        raise PageTraceError(f"line {line_number}: expected a JSON object")
    return record


def _check_version(record: dict[str, Any], line_number: int) -> None:
    version = record.get("v")
    if version != SUPPORTED_VERSION:
        raise PageTraceError(
            f"line {line_number}: unsupported record version {version!r}, "
            f"expected {SUPPORTED_VERSION}"
        )


def _check_seq(record: dict[str, Any], line_number: int, previous: int | None) -> int | None:
    seq: object = record.get("seq")
    if seq is None:
        return previous
    if not isinstance(seq, int) or isinstance(seq, bool):
        raise PageTraceError(f"line {line_number}: seq must be an integer")
    if previous is not None and seq <= previous:
        raise PageTraceError(
            f"line {line_number}: seq {seq} is not greater than the previous seq {previous}"
        )
    return seq


def _build(record: dict[str, Any], line_number: int, index: int) -> RawObservation:
    request = _require_object(record, "request", line_number)
    response = _require_object(record, "response", line_number)

    url = request.get("url")
    if not isinstance(url, str):
        raise PageTraceError(f"line {line_number}: request.url must be a string")

    status = response.get("status")
    if not isinstance(status, int) or isinstance(status, bool):
        raise PageTraceError(
            f"line {line_number}: response.status is required and must be an integer"
        )

    method = request.get("method")

    return RawObservation(
        index=index,
        method=method if isinstance(method, str) else "GET",
        url=url,
        query=query_of(request, url),
        status=status,
        headers=filter_headers(response.get("headers")),
        body=response.get("body"),
    )


def _require_object(record: dict[str, Any], name: str, line_number: int) -> dict[str, Any]:
    value = as_object(record.get(name))
    if value is None:
        raise PageTraceError(f"line {line_number}: {name} must be a JSON object")
    return value


def query_of(request: dict[str, Any], url: str) -> dict[str, str | list[str]]:
    """Explicit `query` wins; otherwise the query string of the URL is parsed.

    A parameter that appears more than once becomes a list, so a selector resolves it to
    NOT_SCALAR instead of silently picking one of the values.
    """
    explicit = as_object(request.get("query"))
    if explicit is not None:
        # canonical_text, not str(): a JSON true recorded in an explicit query object must read
        # as "true", the way it would have arrived in a URL, and null must not become "None".
        return {
            str(name): value if isinstance(value, list) else canonical_text(value)
            for name, value in explicit.items()
        }

    parsed: dict[str, str | list[str]] = {}
    for name, value in parse_qsl(urlsplit(url).query, keep_blank_values=True):
        existing = parsed.get(name)
        if existing is None:
            parsed[name] = value
        elif isinstance(existing, list):
            existing.append(value)
        else:
            parsed[name] = [existing, value]
    return parsed
