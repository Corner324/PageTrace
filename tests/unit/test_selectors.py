"""Selectors: RFC 9535 in, three-valued observations out."""

from __future__ import annotations

import pytest

from pagetrace.errors import PageTraceError
from pagetrace.model import ObservationStatus
from pagetrace.selectors import Selector, select_array, select_items, select_scalar


def sel(expression: str) -> Selector:
    return Selector.compile("--cursor", expression)


def test_resolves_a_single_scalar() -> None:
    observation = select_scalar(sel("$.next"), {"next": "abc"}, "response.next")
    assert observation.observed
    assert observation.value == "abc"
    assert observation.path == "response.next"


def test_json_null_resolves_as_observed() -> None:
    observation = select_scalar(sel("$.next"), {"next": None}, "response.next")
    assert observation.observed
    assert observation.is_null


def test_absent_field_is_not_found() -> None:
    observation = select_scalar(sel("$.next"), {}, "response.next")
    assert observation.status is ObservationStatus.NOT_FOUND


def test_unconfigured_selector_is_not_configured() -> None:
    assert select_scalar(None, {}, "p").status is ObservationStatus.NOT_CONFIGURED


def test_multiple_matches_are_ambiguous_not_a_guess() -> None:
    """Picking the first node would invent a fact the trace does not support."""
    observation = select_scalar(sel("$.items[*].id"), {"items": [{"id": 1}, {"id": 2}]}, "p")
    assert observation.status is ObservationStatus.AMBIGUOUS
    assert observation.value is None


def test_container_where_a_scalar_is_required() -> None:
    observation = select_scalar(sel("$.next"), {"next": {"token": "x"}}, "p")
    assert observation.status is ObservationStatus.NOT_SCALAR


def test_scalar_body_yields_no_match_instead_of_raising() -> None:
    assert select_scalar(sel("$.next"), 5, "p").status is ObservationStatus.NOT_FOUND


def test_invalid_expression_is_a_usage_error() -> None:
    with pytest.raises(PageTraceError, match="--cursor"):
        Selector.compile("--cursor", "$.[[nope")


def test_non_standard_syntax_is_rejected() -> None:
    """strict=True keeps selectors portable: only RFC 9535 is accepted."""
    with pytest.raises(PageTraceError):
        Selector.compile("--cursor", "$.foo[?@.a > 0 and @.b < 100]")


def test_array_selector_distinguishes_empty_from_absent() -> None:
    """INV-CONT-002 needs "the page returned zero items" to differ from "no items field"."""
    empty_status, empty = select_array(sel("$.items"), {"items": []})
    absent_status, absent = select_array(sel("$.items"), {})

    assert empty_status is ObservationStatus.OBSERVED
    assert empty == []
    assert absent_status is ObservationStatus.NOT_FOUND
    assert absent == []


def test_array_selector_rejects_a_non_array() -> None:
    status, _ = select_array(sel("$.items"), {"items": {"a": 1}})
    assert status is ObservationStatus.NOT_SCALAR


def test_items_carry_page_qualified_identities() -> None:
    body = {"items": [{"id": 7}, {"id": 8}]}
    items = select_items(sel("$.items"), sel("$.id"), body, page_index=3)

    assert items.count == 2
    assert items.fully_identified
    assert [i.text for i in items.identities] == ["7", "8"]
    assert items.identities[1].path == "page[3].items[1].id"


def test_items_without_a_resolvable_id_are_counted_not_invented() -> None:
    body = {"items": [{"id": 1}, {"name": "no id"}, {"id": None}]}
    items = select_items(sel("$.items"), sel("$.id"), body, page_index=0)

    assert items.count == 3
    assert items.unidentified == 2
    assert not items.fully_identified
    assert [i.text for i in items.identities] == ["1"]


def test_items_without_an_id_selector_are_counted_only() -> None:
    items = select_items(sel("$.items"), None, {"items": [{"id": 1}]}, page_index=0)
    assert items.count == 1
    assert items.identities == ()
    assert items.unidentified == 1


def test_missing_items_selector_reports_status() -> None:
    items = select_items(None, None, {"items": []}, page_index=0)
    assert items.status is ObservationStatus.NOT_CONFIGURED
    assert items.count is None
