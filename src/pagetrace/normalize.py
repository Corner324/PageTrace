"""Raw observations plus selectors become a normalized page stream.

This is the last place that touches a response body. Everything downstream sees `Page` objects
only, which is why a detector cannot reach a header or a payload (docs/architecture.md).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

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

# Query parameters whose value is never shown, because a link-preset finding quotes whole URLs
# and people paste JSON reports into tickets. A denylist is the wrong tool for deciding what
# reaches the model, and the right one here: this is display of a value the user pointed us at,
# and redacting everything would leave a finding that proves nothing. An unusual name is not
# caught, which docs/security.md says out loud.
SECRET_QUERY_PARAMETERS = frozenset(
    {
        "access_token",
        "api_key",
        "apikey",
        "auth",
        "key",
        "password",
        "secret",
        "sig",
        "signature",
        "token",
    }
)
REDACTED = "REDACTED"


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


def display_url(url: str) -> str:
    """A canonical URL with credential-shaped query values removed.

    The link preset puts whole URLs into evidence, and a JSON report gets pasted into tickets.
    """
    parts = urlsplit(canonical_url(url))
    if not parts.query:
        return canonical_url(url)
    redacted = urlencode(
        [
            (name, REDACTED if name.lower() in SECRET_QUERY_PARAMETERS else value)
            for name, value in parse_qsl(parts.query, keep_blank_values=True)
        ]
    )
    return urlunsplit((parts.scheme, parts.netloc, parts.path, redacted, ""))


def fingerprint(body: object) -> str | None:
    """A stable digest of a response body, for INV-RESP-001. None when there is no JSON body."""
    if body is None:
        return None
    try:
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    except (TypeError, ValueError):  # pragma: no cover - json.dumps with default=str is total
        return None
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def split_link_values(header: str) -> list[str]:
    """Split a Link header on the commas that separate link-values.

    A comma inside angle brackets or inside a quoted parameter belongs to the value, not to the
    list: `<...>; title="Q1, 2026"; rel="next"` is one link, and a splitter that misses this
    turns a perfectly good header into a parse failure.
    """
    values: list[str] = []
    current: list[str] = []
    in_angle = False
    in_quotes = False
    escaped = False

    for character in header:
        if escaped:
            current.append(character)
            escaped = False
            continue
        if in_quotes:
            if character == "\\":
                escaped = True
            elif character == '"':
                in_quotes = False
            current.append(character)
            continue
        if character == "<":
            in_angle = True
        elif character == ">":
            in_angle = False
        elif character == '"':
            in_quotes = True
        elif character == "," and not in_angle:
            values.append("".join(current))
            current = []
            continue
        current.append(character)

    values.append("".join(current))
    return [value.strip() for value in values if value.strip()]


def parse_link_value(value: str) -> tuple[str, set[str]] | None:
    """One link-value as (target, relation types), or None when it is not one."""
    if not value.startswith("<"):
        return None
    closing = value.find(">")
    if closing == -1:
        return None

    target = value[1:closing].strip()
    relations: set[str] = set()
    for parameter in split_parameters(value[closing + 1 :]):
        name, _, raw = parameter.partition("=")
        if name.strip().lower() != "rel":
            continue
        relations.update(unquote_parameter(raw).lower().split())
    return target, relations


def split_parameters(tail: str) -> list[str]:
    """Split the `; a=b; c="d;e"` tail of a link-value, respecting quotes."""
    parameters: list[str] = []
    current: list[str] = []
    in_quotes = False
    escaped = False

    for character in tail:
        if escaped:
            current.append(character)
            escaped = False
            continue
        if character == "\\" and in_quotes:
            escaped = True
            current.append(character)
            continue
        if character == '"':
            in_quotes = not in_quotes
        if character == ";" and not in_quotes:
            parameters.append("".join(current))
            current = []
            continue
        current.append(character)

    parameters.append("".join(current))
    return [parameter.strip() for parameter in parameters if parameter.strip()]


def unquote_parameter(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
        return value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return value


def link_next(headers: dict[str, str], base_url: str) -> Observation:
    """The `rel=next` target of an HTTP Link header, resolved against the request URL.

    Three outcomes, and keeping them apart is the whole point:

    - no Link header at all, or a header nothing in which parses: not observed, so nothing may
      be proven from it;
    - a header that parses and offers no `next` relation: observed null, which is how a
      compliant API says "this was the last page";
    - a `next` target: observed, resolved against the request URL because RFC 8288 allows a
      relative reference, and canonicalized so parameter order is not a mismatch.
    """
    path = "response.link_next"
    header = headers.get("link")
    if header is None:
        return Observation.missing(path, ObservationStatus.NOT_FOUND)

    parsed_any = False
    for value in split_link_values(header):
        parsed = parse_link_value(value)
        if parsed is None:
            continue
        parsed_any = True
        target, relations = parsed
        # An exact relation token: `next-archive` (RFC 5005) is not `next`.
        if "next" in relations:
            return Observation.of(path, display_url(urljoin(base_url, target)))

    if not parsed_any:
        # The header is there but unreadable. Saying "no continuation" here would turn a
        # parsing failure into a claim that the server declared the end.
        return Observation.missing(path, ObservationStatus.NOT_FOUND)
    return Observation.of(path, None)


# A page of results is never carried by one of these. OPTIONS is a CORS preflight and HEAD has
# no body by definition, so both are dropped before anything is numbered: a browser HAR puts a
# preflight in front of every cross-origin request, and it repeats the URL and the query of the
# request that follows. Left in, it looks exactly like a client that did not advance.
NON_RESULT_METHODS = frozenset({"OPTIONS", "HEAD"})


def filter_requests(raws: list[RawObservation], url_filter: str | None) -> list[RawObservation]:
    """Keep the requests that could carry a page and renumber them from zero.

    A HAR holds every request the browser made. Page indexes in evidence must refer to the
    sequence that was actually analyzed, so the kept records are reindexed.
    """
    kept = [
        raw
        for raw in raws
        if raw.method.upper() not in NON_RESULT_METHODS
        and (url_filter is None or url_filter in raw.url)
    ]
    return [replace(raw, index=position) for position, raw in enumerate(kept)]


def normalize(raw: RawObservation, selectors: SelectorSet, preset: str) -> Page:
    """One raw observation becomes one page. Never raises on trace content."""
    request = raw.request_context
    body = raw.body

    if preset == "link":
        request_cursor = Observation.of("request.url", display_url(raw.url))
        next_cursor = link_next(raw.headers, raw.url)
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
