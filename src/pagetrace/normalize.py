"""Raw observations plus selectors become a normalized page stream.

This is the last place that touches a response body. Everything downstream sees `Page` objects
only, which is why a detector cannot reach a header or a payload (docs/architecture.md).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pagetrace.model import (
    ItemsObservation,
    Observation,
    ObservationStatus,
    Page,
    RawObservation,
    Trace,
)
from pagetrace.selectors import Selector, select_items, select_scalar

PRESETS = ("cursor", "page", "offset", "link")

# Defaults are a convenience for common APIs, never an assumption a finding rests on: a default
# that does not match the trace resolves to NOT_FOUND, which proves nothing.
PRESET_DEFAULTS: dict[str, dict[str, str]] = {
    "cursor": {
        "cursor": "$.query.cursor",
        "next": "$.next_cursor",
        "items": "$.items",
        "id": "$.id",
        "total": "$.total",
        "has_more": "$.has_more",
    },
    "page": {
        "page": "$.query.page",
        "items": "$.items",
        "id": "$.id",
        "total": "$.total",
        "has_more": "$.has_more",
    },
    "offset": {
        "offset": "$.query.offset",
        "items": "$.items",
        "id": "$.id",
        "total": "$.total",
        "has_more": "$.has_more",
    },
    # The link preset reads continuation from the HTTP Link header, so it has no cursor or next
    # selector: those two come from the request URL and the header instead.
    "link": {
        "items": "$.items",
        "id": "$.id",
        "total": "$.total",
        "has_more": "$.has_more",
    },
}

SELECTOR_FLAGS = ("cursor", "next", "page", "offset", "items", "id", "total", "has_more")

_LINK_NEXT = re.compile(r'<([^>]*)>\s*;[^,]*\brel\s*=\s*"?next"?', re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class SelectorSet:
    """The compiled selectors for one run, after preset defaults are applied."""

    cursor: Selector | None = None
    next: Selector | None = None
    page: Selector | None = None
    offset: Selector | None = None
    items: Selector | None = None
    id: Selector | None = None
    total: Selector | None = None
    has_more: Selector | None = None

    @classmethod
    def build(cls, preset: str, overrides: dict[str, str | None]) -> SelectorSet:
        """Preset defaults, each overridable by the matching command-line flag."""
        defaults = PRESET_DEFAULTS[preset]
        compiled: dict[str, Selector | None] = {}
        for name in SELECTOR_FLAGS:
            expression = overrides.get(name) or defaults.get(name)
            flag = "--has-more" if name == "has_more" else f"--{name}"
            compiled[name] = Selector.compile(flag, expression) if expression else None
        return cls(**compiled)


def canonical_url(url: str) -> str:
    """A URL reduced to what identifies the request.

    Scheme and host are lowercased, a default port is dropped, and query parameters are sorted.
    Two URLs that differ only in parameter order address the same page, so reporting them as a
    continuation mismatch would claim more than the trace proves.
    """
    parts = urlsplit(url)
    host = parts.hostname or ""
    port = parts.port
    default_port = {"http": 80, "https": 443}.get(parts.scheme.lower())
    netloc = host if port in (None, default_port) else f"{host}:{port}"
    query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)))
    return urlunsplit((parts.scheme.lower(), netloc, parts.path, query, ""))


def fingerprint(body: object) -> str | None:
    """A stable digest of a response body, for INV-RESP-001. None when there is no JSON body."""
    if body is None:
        return None
    try:
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    except (TypeError, ValueError):  # pragma: no cover - json.dumps with default=str is total
        return None
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def link_next(headers: dict[str, str]) -> Observation:
    """The `rel=next` URL of an HTTP Link header, canonicalized."""
    header = headers.get("link")
    if header is None:
        return Observation.missing("response.link_next", ObservationStatus.NOT_FOUND)
    match = _LINK_NEXT.search(header)
    if match is None:
        # A Link header without rel=next is how a compliant API says "this is the last page".
        return Observation.of("response.link_next", None)
    return Observation.of("response.link_next", canonical_url(match.group(1).strip()))


def filter_requests(raws: list[RawObservation], url_filter: str | None) -> list[RawObservation]:
    """Keep the requests the user cares about and renumber them from zero.

    A HAR holds every request the browser made. Page indexes in evidence must refer to the
    sequence that was actually analyzed, so the kept records are reindexed.
    """
    kept = raws if url_filter is None else [raw for raw in raws if url_filter in raw.url]
    return [replace(raw, index=position) for position, raw in enumerate(kept)]


def normalize(raw: RawObservation, selectors: SelectorSet, preset: str) -> Page:
    """One raw observation becomes one page. Never raises on trace content."""
    request = raw.request_context
    body = raw.body

    if preset == "link":
        request_cursor = Observation.of("request.url", canonical_url(raw.url))
        next_cursor = link_next(raw.headers)
    else:
        request_cursor = select_scalar(selectors.cursor, request, "request.cursor")
        next_cursor = select_scalar(selectors.next, body, "response.next_cursor")

    items = (
        select_items(selectors.items, selectors.id, body, raw.index)
        if selectors.items is not None
        else ItemsObservation.missing(ObservationStatus.NOT_CONFIGURED)
    )

    return Page(
        index=raw.index,
        url=raw.url,
        status=raw.status,
        request_cursor=request_cursor,
        next_cursor=next_cursor,
        page_number=select_scalar(selectors.page, request, "request.page"),
        offset=select_scalar(selectors.offset, request, "request.offset"),
        total=select_scalar(selectors.total, body, "response.total"),
        has_more=select_scalar(selectors.has_more, body, "response.has_more"),
        items=items,
        fingerprint=fingerprint(body),
        body_present=raw.body_present,
    )


def build_trace(
    raws: list[RawObservation],
    selectors: SelectorSet,
    preset: str,
    source_format: str,
) -> Trace:
    """Normalize a whole trace, preserving capture order."""
    pages = tuple(normalize(raw, selectors, preset) for raw in raws)
    return Trace(pages=pages, preset=preset, source_format=source_format)
