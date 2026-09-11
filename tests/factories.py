"""Builders for test data.

Detector tests build normalized pages directly: a detector's contract is about observations,
not about JSON shapes, and going through a parser would couple every unit test to the format.
"""

from __future__ import annotations

from typing import Any

from pagetrace.inputs.jsonl import query_of
from pagetrace.model import (
    ItemIdentity,
    ItemsObservation,
    Observation,
    ObservationStatus,
    Page,
    RawObservation,
    Trace,
)

MISSING = ObservationStatus.NOT_CONFIGURED


def raw(
    index: int = 0,
    url: str = "https://api.example/items?cursor=abc",
    status: int = 200,
    body: Any = None,
    headers: dict[str, str] | None = None,
) -> RawObservation:
    """A parsed trace record, as a reader would produce it."""
    return RawObservation(
        index=index,
        method="GET",
        url=url,
        query=query_of({}, url),
        status=status,
        headers=headers or {},
        body=body,
        body_present=body is not None,
    )


def observed(path: str, value: object) -> Observation:
    return Observation.of(path, value)  # pyright: ignore[reportArgumentType]


def absent(path: str, status: ObservationStatus = MISSING) -> Observation:
    return Observation.missing(path, status)


def items(
    page_index: int,
    ids: list[Any] | None = None,
    count: int | None = None,
    unidentified: int = 0,
    status: ObservationStatus = ObservationStatus.OBSERVED,
) -> ItemsObservation:
    """An items observation. `ids` are the identities that resolved."""
    if status is not ObservationStatus.OBSERVED:
        return ItemsObservation.missing(status)
    resolved = ids or []
    identities = tuple(
        ItemIdentity(page_index, position, value) for position, value in enumerate(resolved)
    )
    return ItemsObservation(
        status=status,
        count=len(resolved) + unidentified if count is None else count,
        identities=identities,
        unidentified=unidentified,
    )


def page(
    index: int,
    cursor: object = MISSING,
    next_cursor: object = MISSING,
    page_number: object = MISSING,
    offset: object = MISSING,
    total: object = MISSING,
    has_more: object = MISSING,
    item_ids: list[Any] | None = None,
    item_count: int | None = None,
    unidentified: int = 0,
    items_status: ObservationStatus = ObservationStatus.OBSERVED,
    status: int = 200,
    fingerprint: str | None = None,
) -> Page:
    """A normalized page.

    Any observation argument accepts either a value (observed) or an `ObservationStatus`
    (not observed), so a test can say "this page has no cursor" without ceremony.
    """

    def build(path: str, value: object) -> Observation:
        if isinstance(value, ObservationStatus):
            return Observation.missing(path, value)
        return Observation.of(path, value)  # pyright: ignore[reportArgumentType]

    resolved_items = (
        ItemsObservation.missing(items_status)
        if items_status is not ObservationStatus.OBSERVED
        else items(index, item_ids, item_count, unidentified)
        if item_ids is not None or item_count is not None or unidentified
        else ItemsObservation.missing(MISSING)
    )

    return Page(
        index=index,
        url=f"https://api.example/items?page={index}",
        status=status,
        request_cursor=build("request.cursor", cursor),
        next_cursor=build("response.next_cursor", next_cursor),
        page_number=build("request.page", page_number),
        offset=build("request.offset", offset),
        total=build("response.total", total),
        has_more=build("response.has_more", has_more),
        items=resolved_items,
        fingerprint=fingerprint,
        body_present=True,
    )


def trace(*pages: Page, preset: str = "cursor", source_format: str = "jsonl") -> Trace:
    return Trace(pages=tuple(pages), preset=preset, source_format=source_format)


def cursor_pages(*cursors: str | None, next_cursors: list[Any] | None = None) -> list[Page]:
    """A straightforward cursor run: page n is requested with `cursors[n]`.

    When `next_cursors` is omitted the run is correct by construction: every page returns the
    cursor the next request uses, and the last page returns null.
    """
    nexts: list[Any] = (
        next_cursors
        if next_cursors is not None
        else [*list(cursors[1:]), None]  # last page declares termination
    )
    return [
        page(
            index=position,
            cursor=MISSING if value is None else value,
            next_cursor=nexts[position],
        )
        for position, value in enumerate(cursors)
    ]
