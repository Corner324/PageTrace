"""Build benchmark traces in memory.

Nothing large is committed: the corpus described in `docs/performance.md` is generated on
demand, which is also why a hundred thousand pages is cheap to test.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass

from pagetrace.model import RawObservation

BASE_URL = "https://api.example/items"


@dataclass(frozen=True, slots=True)
class Shape:
    """One corpus entry."""

    name: str
    pages: int
    items_per_page: int
    id_style: str = "int"  # int | uuid | long
    pattern: str = "valid"  # valid | duplicates | cycle | repeated

    @property
    def label(self) -> str:
        return (
            f"{self.name} [{self.pages} pages x {self.items_per_page} items, "
            f"{self.id_style} ids, {self.pattern}]"
        )


SMOKE: tuple[Shape, ...] = (
    Shape("small", pages=200, items_per_page=10),
    Shape("duplicates", pages=200, items_per_page=10, pattern="duplicates"),
)

FULL: tuple[Shape, ...] = (
    Shape("empty-pages", pages=1_000, items_per_page=0),
    Shape("small", pages=1_000, items_per_page=10),
    Shape("wide", pages=1_000, items_per_page=100),
    Shape("very-wide", pages=1_000, items_per_page=1_000),
    Shape("uuid-ids", pages=1_000, items_per_page=100, id_style="uuid"),
    Shape("long-ids", pages=1_000, items_per_page=100, id_style="long"),
    Shape("duplicate-heavy", pages=1_000, items_per_page=100, pattern="duplicates"),
    Shape("cycle-heavy", pages=1_000, items_per_page=10, pattern="cycle"),
    Shape("repeated-page", pages=1_000, items_per_page=10, pattern="repeated"),
    Shape("ten-thousand", pages=10_000, items_per_page=100),
    Shape("hundred-thousand", pages=100_000, items_per_page=50),
)


def _identity(style: str, number: int) -> object:
    if style == "uuid":
        return str(uuid.UUID(int=number))
    if style == "long":
        return f"item-{number:0>60}"
    return number


def _cursor(shape: Shape, index: int) -> str:
    if shape.pattern == "cycle" and index > 10:
        # Come back to the same three states over and over.
        return f"c{10 + (index % 3)}"
    if shape.pattern == "repeated":
        return f"c{index // 2}"
    return f"c{index}"


def observations(shape: Shape) -> Iterator[RawObservation]:
    """Generate one trace, one raw observation at a time."""
    next_id = 0
    for index in range(shape.pages):
        ids: list[object] = []
        for offset in range(shape.items_per_page):
            if shape.pattern == "duplicates" and offset == 0 and index > 0:
                ids.append(_identity(shape.id_style, next_id - shape.items_per_page))
            else:
                ids.append(_identity(shape.id_style, next_id))
                next_id += 1

        cursor = _cursor(shape, index)
        following = _cursor(shape, index + 1) if index + 1 < shape.pages else None
        yield RawObservation(
            index=index,
            method="GET",
            url=f"{BASE_URL}?cursor={cursor}",
            query={"cursor": cursor},
            status=200,
            headers={},
            body={
                "items": [{"id": value} for value in ids],
                "next_cursor": following,
                "has_more": index + 1 < shape.pages,
            },
            body_present=True,
        )
