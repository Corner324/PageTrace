"""Hypothesis strategies for pagination traces.

Two halves, per docs/testing.md:

- `valid_trace()` builds a run that is correct by construction. The property that no PROVEN
  finding may come out of one is the direct attack on false positives.
- the mutation operators each break exactly one property of a valid trace, so a test can assert
  that the matching detector fires, points at the right pages, and that nothing else fires.

Traces are built as normalized pages rather than as JSON. A detector's contract is about
observations, and going through a parser would make every property test a format test too.
"""

from __future__ import annotations

from dataclasses import replace

from hypothesis import strategies as st

from pagetrace.model import (
    ItemIdentity,
    ItemsObservation,
    Observation,
    ObservationStatus,
    Page,
    Trace,
)

CURSOR_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789-_"

cursors = st.text(alphabet=CURSOR_ALPHABET, min_size=1, max_size=12)
item_ids = st.integers(min_value=0, max_value=10**6)


def _page(
    index: int,
    cursor: str | None,
    next_cursor: str | None,
    ids: list[int],
    total: int | None = None,
    has_more: bool | None = None,
) -> Page:
    def observation(path: str, value: object, *, present: bool) -> Observation:
        if not present:
            return Observation.missing(path, ObservationStatus.NOT_FOUND)
        return Observation.of(path, value)  # pyright: ignore[reportArgumentType]

    identities = tuple(ItemIdentity(index, position, value) for position, value in enumerate(ids))
    return Page(
        index=index,
        url=f"https://api.example/items?cursor={cursor or ''}",
        status=200,
        request_cursor=observation("request.cursor", cursor, present=cursor is not None),
        next_cursor=Observation.of("response.next_cursor", next_cursor),
        total=observation("response.total", total, present=total is not None),
        has_more=observation("response.has_more", has_more, present=has_more is not None),
        items=ItemsObservation(
            status=ObservationStatus.OBSERVED,
            count=len(ids),
            identities=identities,
        ),
        fingerprint=f"fp-{index}-{'-'.join(str(i) for i in ids)}",
        body_present=True,
    )


@st.composite
def valid_trace(
    draw: st.DrawFn,
    min_pages: int = 1,
    max_pages: int = 12,
    with_total: bool = False,
    with_has_more: bool = False,
) -> Trace:
    """A cursor run that violates no invariant.

    Distinct cursors, each page continuing from the one the server offered, unique item ids
    across the whole run, a terminal null continuation on the last page, and a declared total
    that matches the items when one is asked for.
    """
    page_count = draw(st.integers(min_value=min_pages, max_value=max_pages))
    tokens = draw(st.lists(cursors, min_size=page_count, max_size=page_count, unique=True))
    per_page = draw(
        st.lists(st.integers(min_value=0, max_value=5), min_size=page_count, max_size=page_count)
    )

    next_id = 0
    ids_per_page: list[list[int]] = []
    for count in per_page:
        ids_per_page.append(list(range(next_id, next_id + count)))
        next_id += count

    total = next_id if with_total else None
    pages: list[Page] = []
    for index in range(page_count):
        pages.append(
            _page(
                index=index,
                # Page 0 carries no incoming cursor, exactly like a real first request.
                cursor=None if index == 0 else tokens[index],
                next_cursor=tokens[index + 1] if index + 1 < page_count else None,
                ids=ids_per_page[index],
                total=total,
                has_more=(index + 1 < page_count) if with_has_more else None,
            )
        )
    return Trace(pages=tuple(pages), preset="cursor", source_format="jsonl")


# ---------------------------------------------------------------- mutation operators
# Each one breaks a single property. They return a new trace; nothing is mutated in place.


def _with_pages(trace: Trace, pages: list[Page]) -> Trace:
    return replace(trace, pages=tuple(pages))


def change_next_cursor(trace: Trace, index: int) -> Trace:
    """Break INV-CURSOR-001: the page offers a token the next request does not use."""
    pages = list(trace.pages)
    pages[index] = replace(
        pages[index],
        next_cursor=Observation.of("response.next_cursor", "mutated-token"),
    )
    return _with_pages(trace, pages)


def freeze_cursor(trace: Trace, index: int) -> Trace:
    """Break INV-CURSOR-002: page index+1 repeats the request of page index."""
    pages = list(trace.pages)
    earlier, later = pages[index], pages[index + 1]
    pages[index + 1] = replace(
        later,
        request_cursor=earlier.request_cursor,
        next_cursor=earlier.next_cursor,
    )
    return _with_pages(trace, pages)


def insert_cursor_cycle(trace: Trace, start: int, length: int) -> Trace:
    """Break INV-CURSOR-003: the request cursor of `start` returns `length` pages later."""
    pages = list(trace.pages)
    target = start + length
    pages[target] = replace(pages[target], request_cursor=pages[start].request_cursor)
    # Keep the continuation consistent so only the cycle invariant is violated.
    pages[target - 1] = replace(
        pages[target - 1],
        next_cursor=Observation.of("response.next_cursor", pages[start].request_cursor.value),
    )
    return _with_pages(trace, pages)


def duplicate_item(trace: Trace, source: int, destination: int) -> Trace:
    """Break INV-ITEM-001: an id seen on `source` appears again on `destination`."""
    pages = list(trace.pages)
    borrowed = pages[source].items.identities[0].value
    target = pages[destination]
    identities = (
        *target.items.identities,
        ItemIdentity(destination, len(target.items.identities), borrowed),
    )
    pages[destination] = replace(
        target,
        items=replace(
            target.items,
            count=(target.items.count or 0) + 1,
            identities=identities,
        ),
    )
    return _with_pages(trace, pages)


def set_has_more_true_on_final_page(trace: Trace) -> Trace:
    """Break INV-CONT-001: the last page declares that more results exist."""
    pages = list(trace.pages)
    pages[-1] = replace(pages[-1], has_more=Observation.of("response.has_more", True))
    return _with_pages(trace, pages)


def drop_last_page(trace: Trace) -> Trace:
    """Break INV-TRACE-001: the trace stops while a continuation token is still offered."""
    return _with_pages(trace, list(trace.pages[:-1]))


def duplicate_response(trace: Trace, index: int) -> Trace:
    """Break INV-RESP-001: two consecutive pages carry an identical body."""
    pages = list(trace.pages)
    pages[index + 1] = replace(pages[index + 1], fingerprint=pages[index].fingerprint)
    return _with_pages(trace, pages)


def corrupt_total(trace: Trace, delta: int) -> Trace:
    """Break INV-TOTAL-001: the declared total stops matching the items observed."""
    pages = [
        replace(
            page,
            total=Observation.of("response.total", (page.total.int_value or 0) + delta),
        )
        for page in trace.pages
    ]
    return _with_pages(trace, pages)
