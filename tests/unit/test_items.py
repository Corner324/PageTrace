"""INV-ITEM-001: duplicate item across pages."""

from __future__ import annotations

from tests.factories import page, trace

from pagetrace.checks.items import check_duplicate_items
from pagetrace.model import Certainty, Finding, ObservationStatus, Page

DUPLICATE = "DUPLICATE_ITEM_ACROSS_PAGES"
NOT_OBSERVABLE = "ITEM_IDENTITY_NOT_OBSERVABLE"


def run(*pages: Page) -> list[Finding]:
    return list(check_duplicate_items(trace(*pages)))


def test_disjoint_pages_are_silent() -> None:
    assert run(page(0, item_ids=[1, 2]), page(1, item_ids=[3, 4])) == []


def test_a_duplicate_across_pages_is_proven() -> None:
    (finding,) = run(page(0, item_ids=[1, 2]), page(1, item_ids=[2, 3]))

    assert finding.code == DUPLICATE
    assert finding.invariant == "INV-ITEM-001"
    assert finding.certainty is Certainty.PROVEN
    assert finding.affected_pages == (0, 1)
    assert [e.path for e in finding.evidence] == [
        "page[0].items[1].id",
        "page[1].items[0].id",
    ]


def test_the_message_states_the_observation_and_hedges_the_meaning() -> None:
    """A duplicate proves a duplicate, not a pagination defect."""
    (finding,) = run(page(0, item_ids=[7]), page(1, item_ids=[7]))

    assert "observed on page 0 was observed again on page 1" in finding.message
    assert "depends on a uniqueness contract" in finding.message
    assert "broken" not in finding.message
    assert "bug" not in finding.message


def test_the_item_value_stays_out_of_the_message() -> None:
    """Messages are written by PageTrace; only evidence carries text from the trace.

    A value interpolated into a message would skip the escaping and truncation that `display()`
    applies to evidence, which put raw terminal escapes on screen and produced invalid JUnit XML.
    """
    hostile = "[31mHACK[0m" + "A" * 500
    (finding,) = run(page(0, item_ids=[hostile]), page(1, item_ids=[hostile]))

    assert "" not in finding.message
    assert "HACK" not in finding.message
    assert len(finding.message) < 300
    assert finding.evidence[0].value == hostile


def test_a_repeat_inside_one_page_is_not_claimed() -> None:
    """One response listing an id twice says nothing about pagination."""
    assert run(page(0, item_ids=[1, 1, 2])) == []


def test_ids_of_different_json_types_are_the_same_identity() -> None:
    assert len(run(page(0, item_ids=[5]), page(1, item_ids=["5"]))) == 1


def test_duplicates_spanning_distant_pages_are_found() -> None:
    pages = [page(0, item_ids=[1]), page(1, item_ids=[2]), page(2, item_ids=[1])]
    (finding,) = run(*pages)
    assert finding.affected_pages == (0, 2)


def test_every_duplicate_is_reported() -> None:
    pages = [page(0, item_ids=[1, 2]), page(1, item_ids=[1, 2])]
    assert len(run(*pages)) == 2


def test_non_2xx_pages_are_excluded() -> None:
    assert run(page(0, item_ids=[1]), page(1, item_ids=[1], status=500)) == []


def test_unidentified_items_are_summarized_once() -> None:
    findings = run(page(0, item_ids=[1], unidentified=2), page(1, item_ids=[2], unidentified=1))

    assert [f.code for f in findings] == [NOT_OBSERVABLE]
    assert findings[0].certainty is Certainty.INSUFFICIENT_EVIDENCE
    assert "3 items across 2 pages" in findings[0].message


def test_pages_without_an_items_selector_prove_nothing() -> None:
    assert run(page(0), page(1)) == []


def test_an_unresolvable_items_selector_is_not_a_duplicate() -> None:
    pages = [
        page(0, items_status=ObservationStatus.NOT_FOUND),
        page(1, items_status=ObservationStatus.NOT_FOUND),
    ]
    assert run(*pages) == []


def test_an_empty_page_is_not_a_duplicate() -> None:
    assert run(page(0, item_count=0), page(1, item_count=0)) == []
