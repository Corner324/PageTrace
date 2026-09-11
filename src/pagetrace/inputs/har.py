"""HAR reader. Format: the HTTP Archive 1.2 log produced by browser dev tools and proxies.

A HAR holds every request a page made, usually including credentials. Two things follow: the
header allowlist matters more here than anywhere else, and `--url-filter` is normally required
to pick out the API calls.
"""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from pagetrace.errors import PageTraceError
from pagetrace.inputs import HEADER_ALLOWLIST, as_array, as_object
from pagetrace.limits import MAX_BODY_BYTES
from pagetrace.model import RawObservation


def read_har(path: Path) -> Iterator[RawObservation]:
    """Parse a HAR file into raw observations, in capture order."""
    log = _load(path)
    entries = as_array(log.get("entries"))
    if entries is None:
        raise PageTraceError(f"{path.name}: log.entries is missing or not an array")
    if not entries:
        raise PageTraceError(f"{path.name}: no entries found")

    for index, item in enumerate(entries):
        entry = as_object(item)
        if entry is None:
            raise PageTraceError(f"{path.name}: entry {index} is not an object")
        yield _build(entry, index, path.name)


def _load(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PageTraceError(f"cannot read {path}: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise PageTraceError(f"{path.name}: not valid UTF-8 ({exc.reason})") from exc

    try:
        document: object = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PageTraceError(f"{path.name}: invalid JSON: {exc.msg}") from exc
    except RecursionError as exc:
        raise PageTraceError(f"{path.name}: JSON nested too deeply") from exc

    top = as_object(document)
    if top is None:
        raise PageTraceError(f"{path.name}: expected a JSON object at the top level")
    log = as_object(top.get("log"))
    if log is None:
        raise PageTraceError(f"{path.name}: no HAR log object found")
    return log


def _build(entry: dict[str, Any], index: int, name: str) -> RawObservation:
    request = _object(entry, "request", index, name)
    response = _object(entry, "response", index, name)

    url = request.get("url")
    if not isinstance(url, str):
        raise PageTraceError(f"{name}: entry {index} has no request.url")

    status = response.get("status")
    if not isinstance(status, int) or isinstance(status, bool):
        raise PageTraceError(f"{name}: entry {index} has no integer response.status")

    method = request.get("method")
    body, body_present = _body(response, index, name)

    return RawObservation(
        index=index,
        method=method if isinstance(method, str) else "GET",
        url=url,
        query=_query(request, url),
        status=status,
        headers=_headers(response.get("headers")),
        body=body,
        body_present=body_present,
    )


def _object(entry: dict[str, Any], key: str, index: int, name: str) -> dict[str, Any]:
    value = as_object(entry.get(key))
    if value is None:
        raise PageTraceError(f"{name}: entry {index} has no {key} object")
    return value


def _headers(headers: object) -> dict[str, str]:
    """HAR headers are a list of name/value pairs. Only the allowlist survives."""
    kept: dict[str, str] = {}
    entries = as_array(headers)
    if entries is None:
        return kept
    for item in entries:
        header = as_object(item)
        if header is None:
            continue
        name = header.get("name")
        value = header.get("value")
        if isinstance(name, str) and isinstance(value, str) and name.lower() in HEADER_ALLOWLIST:
            kept[name.lower()] = value
    return kept


def _query(request: dict[str, Any], url: str) -> dict[str, str | list[str]]:
    """Prefer the recorded queryString; fall back to parsing the URL."""
    from pagetrace.inputs.jsonl import query_of

    recorded = as_array(request.get("queryString"))
    if recorded is None:
        return query_of({}, url)

    parsed: dict[str, str | list[str]] = {}
    for item in recorded:
        pair = as_object(item)
        if pair is None:
            continue
        name = pair.get("name")
        value = pair.get("value")
        if not isinstance(name, str) or not isinstance(value, str):
            continue
        existing = parsed.get(name)
        if existing is None:
            parsed[name] = value
        elif isinstance(existing, list):
            existing.append(value)
        else:
            parsed[name] = [existing, value]
    return parsed


def _body(response: dict[str, Any], index: int, name: str) -> tuple[object, bool]:
    """Decode response content into parsed JSON, or report it as present but unusable."""
    content = as_object(response.get("content"))
    if content is None:
        return None, False

    text = content.get("text")
    if not isinstance(text, str):
        return None, False

    base64_encoded = content.get("encoding") == "base64"
    decoded = _decode_base64(text, index, name) if base64_encoded else text

    if len(decoded.encode("utf-8", errors="ignore")) > MAX_BODY_BYTES:
        raise PageTraceError(
            f"{name}: entry {index} body is larger than the {MAX_BODY_BYTES} byte limit"
        )

    try:
        return json.loads(decoded), True
    except (json.JSONDecodeError, RecursionError):
        # A non-JSON body is recorded as present but carries no observations.
        return None, True


def _decode_base64(text: str, index: int, name: str) -> str:
    if len(text) > MAX_BODY_BYTES:
        raise PageTraceError(
            f"{name}: entry {index} body is larger than the {MAX_BODY_BYTES} byte limit"
        )
    try:
        raw = base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise PageTraceError(f"{name}: entry {index} has invalid base64 content: {exc}") from exc
    if len(raw) > MAX_BODY_BYTES:
        raise PageTraceError(
            f"{name}: entry {index} decodes to more than the {MAX_BODY_BYTES} byte limit"
        )
    return raw.decode("utf-8", errors="replace")
