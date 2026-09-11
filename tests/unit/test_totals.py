"""INV-TOTAL-001: declared total against the items observed."""

from __future__ import annotations

from tests.factories import page, trace

from pagetrace.checks.totals import check_total_discrepancy
from pagetrace.model import Certainty, Finding, ObservationStatus, Page

DISCREPANCY = "TOTAL_COUNT_DISCREPANCY"
CHANGED = "TOTAL_CHANGED_BETWEEN_PAGES"
NOT_OBSERVABLE = "TOTAL_ITEMS_NOT_OBSERVABLE"


def run(*pages: Page) -> list[Finding]:
    return list(check_total_discrepancy(trace(*pages)))


def run_pages(
    ids_per_page: list[list[int]],
    total: object = 4,
    *,
    terminated: bool = True,
    unidentified: int = 0,
) -> list[Finding]:
    """A terminated run declaring `total`, carrying the given ids page by page."""
    last = len(ids_per_page) - 1
    pages = [
        page(
            index,
            total=total,
            item_ids=ids,
            unidentified=unidentified if index == last else 0,
            next_cursor=(None if terminated else "more") if index == last else "next",
        )
        for index, ids in enumerate(ids_per_page)
    ]
    return run(*pages)


def test_a_matching_total_is_silent() -> None:
    assert run_pages([[1, 2], [3, 4]], total=4) == []


def test_a_mismatch_on_a_terminated_fully_identified_trace_is_proven() -> None:
    (finding,) = run_pages([[1, 2], [3]], total=4)

    assert finding.code == DISCREPANCY
    assert finding.certainty is Certainty.PROVEN
    assert [e.value for e in finding.evidence] == [4, 3, 3, 2]


def test_the_message_refuses_to_count_missing_records() -> None:
    (finding,) = run_pages([[1, 2], [3]], total=4)
    message = finding.message.lower()

    assert "not a count of records that went missing" in message
    assert "missing 1" not in message
    assert "lost" not in message


def test_an_unterminated_trace_is_left_alone() -> None:
    """An incomplete capture explains a shortfall by itself, and another invariant reports it."""
    assert run_pages([[1, 2], [3]], total=4, terminated=False) == []


def test_termination_declared_by_has_more_false_is_enough() -> None:
    pages = [
        page(0, total=4, item_ids=[1, 2], has_more=True),
        page(1, total=4, item_ids=[3], has_more=False),
    ]
    (finding,) = run(*pages)
    assert finding.certainty is Certainty.PROVEN


def test_a_changing_total_stops_the_comparison() -> None:
    pages = [
        page(0, total=10, item_ids=[1], next_cursor="n"),
        page(1, total=12, item_ids=[2], next_cursor=None),
    ]
    findings = run(*pages)

    assert [f.code for f in findings] == [CHANGED]
    assert findings[0].certainty is Certainty.INSUFFICIENT_EVIDENCE
    assert "dataset moved" in findings[0].message


def test_unidentified_items_downgrade_to_suspicious() -> None:
    (finding,) = run_pages([[1, 2], [3]], total=9, unidentified=2)

    assert finding.certainty is Certainty.SUSPICIOUS
    assert "could not be deduplicated" in finding.message


def test_duplicates_downgrade_to_suspicious() -> None:
    """With overlapping pages it is no longer clear what the total should be compared against."""
    (finding,) = run_pages([[1, 2], [2]], total=4)

    assert finding.certainty is Certainty.SUSPICIOUS
    assert "appear on more than one page" in finding.message


def test_a_total_without_countable_items_proves_nothing() -> None:
    pages = [
        page(0, total=10, items_status=ObservationStatus.NOT_FOUND, next_cursor=None),
    ]
    findings = run(*pages)

    assert [f.code for f in findings] == [NOT_OBSERVABLE]
    assert findings[0].certainty is Certainty.INSUFFICIENT_EVIDENCE


def test_no_total_selector_means_no_finding() -> None:
    assert run(page(0, item_ids=[1], next_cursor=None)) == []


def test_a_non_integer_total_is_not_used() -> None:
    assert run_pages([[1]], total="many") == []


def test_error_pages_are_excluded_from_the_count() -> None:
    pages = [
        page(0, total=2, item_ids=[1, 2], next_cursor="n"),
        page(1, total=2, item_ids=[9], status=500, next_cursor=None),
        page(2, total=2, item_ids=[], next_cursor=None),
    ]
    assert run(*pages) == []


def test_a_trace_of_only_error_pages_proves_nothing() -> None:
    assert run(page(0, total=5, item_ids=[1], status=500)) == []
