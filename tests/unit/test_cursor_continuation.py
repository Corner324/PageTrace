"""INV-CURSOR-001: continuation cursor mismatch.

Per docs/testing.md every detector gets an obvious positive, an obvious negative, a boundary,
and an insufficient-evidence case. The non-claim conditions of the spec entry get one each.
"""

from __future__ import annotations

from tests.factories import cursor_pages, page, trace

from pagetrace.checks.cursors import check_cursor_continuation
from pagetrace.model import Certainty, ObservationStatus, Page

MISMATCH = "CURSOR_CONTINUATION_MISMATCH"
NOT_OBSERVABLE = "CURSOR_CONTINUATION_NOT_OBSERVABLE"


def codes(*pages: Page) -> list[str]:
    return [finding.code for finding in check_cursor_continuation(trace(*pages))]


def test_a_correct_run_is_silent() -> None:
    assert codes(*cursor_pages(None, "b", "c")) == []


def test_mismatch_is_proven() -> None:
    pages = [
        page(0, next_cursor="b"),
        page(1, cursor="WRONG", next_cursor=None),
    ]
    (finding,) = list(check_cursor_continuation(trace(*pages)))

    assert finding.code == MISMATCH
    assert finding.invariant == "INV-CURSOR-001"
    assert finding.certainty is Certainty.PROVEN
    assert finding.affected_pages == (0, 1)
    assert [(e.path, e.value) for e in finding.evidence] == [
        ("page[0].response.next_cursor", "b"),
        ("page[1].request.cursor", "WRONG"),
    ]


def test_message_does_not_blame_the_api() -> None:
    (finding,) = list(
        check_cursor_continuation(trace(page(0, next_cursor="b"), page(1, cursor="x")))
    )
    lowered = finding.message.lower()
    assert "api" not in lowered
    assert "fail" not in lowered
    assert "bug" not in lowered


def test_type_difference_alone_is_not_a_mismatch() -> None:
    """Global precondition 3: a query parameter can only carry text."""
    assert codes(page(0, next_cursor=5), page(1, cursor="5")) == []


def test_null_next_cursor_is_termination_not_a_mismatch() -> None:
    """The server declared the end; what the client did next belongs to another invariant."""
    assert codes(page(0, next_cursor=None), page(1, cursor="anything")) == []


def test_empty_string_next_cursor_is_also_termination() -> None:
    assert codes(page(0, next_cursor=""), page(1, cursor="anything")) == []


def test_a_repeated_request_is_left_to_the_stall_detector() -> None:
    """One observation, one finding: the repeat is reported by INV-CURSOR-002."""
    assert codes(page(0, cursor="a", next_cursor="b"), page(1, cursor="a")) == []


def test_non_2xx_pages_are_excluded() -> None:
    assert codes(page(0, next_cursor="b", status=500), page(1, cursor="x")) == []
    assert codes(page(0, next_cursor="b"), page(1, cursor="x", status=503)) == []


def test_missing_evidence_is_summarized_once() -> None:
    pages = [
        page(0, next_cursor=ObservationStatus.NOT_FOUND),
        page(1, cursor=ObservationStatus.NOT_FOUND),
        page(2, cursor=ObservationStatus.NOT_FOUND),
    ]
    findings = list(check_cursor_continuation(trace(*pages)))

    assert [f.code for f in findings] == [NOT_OBSERVABLE]
    assert findings[0].certainty is Certainty.INSUFFICIENT_EVIDENCE
    assert "2 of 2 transitions" in findings[0].message


def test_ambiguous_cursor_is_not_a_mismatch() -> None:
    """Two matching nodes means PageTrace does not know which one the client used."""
    pages = [page(0, next_cursor="b"), page(1, cursor=ObservationStatus.AMBIGUOUS)]
    assert codes(*pages) == [NOT_OBSERVABLE]


def test_first_page_without_a_cursor_is_normal() -> None:
    assert (
        codes(page(0, cursor=ObservationStatus.NOT_FOUND, next_cursor="b"), page(1, cursor="b"))
        == []
    )


def test_other_presets_are_left_alone() -> None:
    pages = [page(0, next_cursor="b"), page(1, cursor="WRONG")]
    assert [f.code for f in check_cursor_continuation(trace(*pages, preset="page"))] == []


def test_every_mismatch_is_reported() -> None:
    pages = [
        page(0, cursor="a", next_cursor="b"),
        page(1, cursor="X", next_cursor="c"),
        page(2, cursor="Y", next_cursor=None),
    ]
    assert codes(*pages) == [MISMATCH, MISMATCH]


def test_single_page_trace_has_nothing_to_compare() -> None:
    assert codes(page(0, cursor="a", next_cursor="b")) == []
