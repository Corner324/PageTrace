"""RFC 9535 JSONPath selectors, turned into three-valued observations.

A selector never raises while reading a trace. Either it resolves to exactly one scalar, or the
result is one of the not-observed statuses, and nothing may be proven from it
(specs/invariants.md, global precondition 1).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from jsonpath import JSONPathEnvironment, JSONPathError

from pagetrace.errors import PageTraceError
from pagetrace.model import (
    ItemIdentity,
    ItemsObservation,
    Observation,
    ObservationStatus,
)

if TYPE_CHECKING:
    from jsonpath import CompoundJSONPath, JSONPath

# strict=True is RFC 9535 and nothing else: no extra selectors, no extra filter functions.
# A selector that works here works in any compliant implementation. See docs/adr/0003.
_ENV = JSONPathEnvironment(strict=True)

_SCALAR_TYPES = (str, int, float, bool)


@dataclass(frozen=True, slots=True)
class Selector:
    """One compiled selector, remembering the flag it came from for error messages."""

    flag: str
    expression: str
    query: JSONPath | CompoundJSONPath

    @classmethod
    def compile(cls, flag: str, expression: str) -> Selector:
        try:
            return cls(flag=flag, expression=expression, query=_ENV.compile(expression))
        except JSONPathError as exc:
            raise PageTraceError(f"{flag}: invalid JSONPath {expression!r}: {exc}") from exc


def _values(selector: Selector, data: object) -> list[Any]:
    # finditer accepts any JSON value; a non-container simply yields no nodes.
    return [match.value for match in selector.query.finditer(data)]  # pyright: ignore[reportArgumentType]


def select_scalar(selector: Selector | None, data: object, path: str) -> Observation:
    """Resolve one selector to a single scalar observation.

    JSON null is an observed value. Zero nodes, several nodes, or a container are all
    not-observed, each with its own reason so the report can say which.
    """
    if selector is None:
        return Observation.missing(path, ObservationStatus.NOT_CONFIGURED)

    values = _values(selector, data)
    if not values:
        return Observation.missing(path, ObservationStatus.NOT_FOUND)
    if len(values) > 1:
        return Observation.missing(path, ObservationStatus.AMBIGUOUS)

    value = values[0]
    if value is None or isinstance(value, _SCALAR_TYPES):
        return Observation.of(path, value)
    return Observation.missing(path, ObservationStatus.NOT_SCALAR)


def select_array(selector: Selector | None, data: object) -> tuple[ObservationStatus, list[Any]]:
    """Resolve a selector expected to yield one array.

    Returns the status plus the elements. An array of items is the only shape accepted: a
    selector that matches the items one by one (`$.items[*]`) would make an empty page
    indistinguishable from a missing field, and INV-CONT-002 depends on telling those apart.
    """
    if selector is None:
        return ObservationStatus.NOT_CONFIGURED, []

    values = _values(selector, data)
    if not values:
        return ObservationStatus.NOT_FOUND, []
    if len(values) > 1:
        return ObservationStatus.AMBIGUOUS, []
    if not isinstance(values[0], list):
        return ObservationStatus.NOT_SCALAR, []
    return ObservationStatus.OBSERVED, list(values[0])  # pyright: ignore[reportUnknownArgumentType]


def select_items(
    items_selector: Selector | None,
    id_selector: Selector | None,
    body: object,
    page_index: int,
) -> ItemsObservation:
    """Resolve the items array and, for each element, its identity."""
    status, elements = select_array(items_selector, body)
    if status is not ObservationStatus.OBSERVED:
        return ItemsObservation.missing(status)

    identities: list[ItemIdentity] = []
    unidentified = 0
    for item_index, element in enumerate(elements):
        identity = select_scalar(id_selector, element, "id")
        if identity.observed and identity.value is not None:
            identities.append(ItemIdentity(page_index, item_index, identity.value))
        else:
            unidentified += 1

    return ItemsObservation(
        status=ObservationStatus.OBSERVED,
        count=len(elements),
        identities=tuple(identities),
        unidentified=unidentified,
    )
