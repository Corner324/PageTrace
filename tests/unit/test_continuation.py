"""INV-CONT-001, INV-CONT-002 and INV-TRACE-001: how a trace ends."""

from __future__ import annotations

from tests.factories import page, trace

from pagetrace.checks.base import Check
from pagetrace.checks.continuation import (
    check_empty_page_with_has_more,
    check_trace_ends_with_continuation,
    check_trace_ends_with_has_more,
)
from pagetrace.model import Certainty, Finding, ObservationStatus, Page

ENDS_WITH_HAS_MORE = "TRACE_ENDS_WITH_HAS_MORE"
ENDS_WITH_CONTINUATION = "TRACE_ENDS_WITH_CONTINUATION"
EMPTY_PAGE = "EMPTY_PAGE_WITH_HAS_MORE"
NOT_BOOLEAN = "HAS_MORE_NOT_BOOLEAN"


def run(check: Check, *pages: Page, preset: str = "cursor") -> list[Finding]:
    return list(check(trace(*pages, preset=preset)))


# ---------------------------------------------------------------- INV-CONT-001


def test_a_trace_that_ends_on_has_more_false_is_silent() -> None:
    pages = [page(0, has_more=True), page(1, has_more=False)]
    assert run(check_trace_ends_with_has_more, *pages) == []


def test_a_trace_ending_on_has_more_true_is_proven() -> None:
    (finding,) = run(check_trace_ends_with_has_more, page(0, has_more=True))

    assert finding.code == ENDS_WITH_HAS_MORE
    assert finding.certainty is Certainty.PROVEN
    assert finding.affected_pages == (0,)


def test_the_message_blames_nobody() -> None:
    (finding,) = run(check_trace_ends_with_has_more, page(0, has_more=True))
    message = finding.message.lower()

    assert "may be incomplete" in message
    assert "not recorded" in message
    assert "api failed" not in message
    assert "server" not in message


def test_a_trailing_error_page_does_not_hide_the_last_result_page() -> None:
    """The last 2xx page is what the trace says about pagination."""
    pages = [page(0, has_more=True), page(1, has_more=False, status=500)]
    (finding,) = run(check_trace_ends_with_has_more, *pages)
    assert finding.affected_pages == (0,)


def test_an_unobservable_flag_proves_nothing() -> None:
    assert run(check_trace_ends_with_has_more, page(0, has_more=ObservationStatus.NOT_FOUND)) == []


def test_a_truthy_string_is_not_a_boolean() -> None:
    """Deciding that "true" means true would be a rule about someone else's API."""
    findings = run(check_trace_ends_with_has_more, page(0, has_more="true"))

    assert [f.code for f in findings] == [NOT_BOOLEAN]
    assert findings[0].certainty is Certainty.INSUFFICIENT_EVIDENCE


def test_a_trace_of_only_error_pages_proves_nothing() -> None:
    assert run(check_trace_ends_with_has_more, page(0, has_more=True, status=500)) == []


# ---------------------------------------------------------------- INV-CONT-002


def test_an_empty_intermediate_page_with_has_more_is_suspicious() -> None:
    pages = [page(0, has_more=True, item_count=0), page(1, has_more=False, item_count=3)]
    (finding,) = run(check_empty_page_with_has_more, *pages)

    assert finding.code == EMPTY_PAGE
    assert finding.certainty is Certainty.SUSPICIOUS
    assert finding.affected_pages == (0,)
    assert [e.path for e in finding.evidence] == [
        "page[0].response.has_more",
        "page[0].response.items.count",
    ]


def test_a_non_empty_page_is_silent() -> None:
    pages = [page(0, has_more=True, item_count=2), page(1, has_more=False, item_count=1)]
    assert run(check_empty_page_with_has_more, *pages) == []


def test_the_final_page_is_left_to_the_other_invariant() -> None:
    """One stop, one finding: INV-CONT-001 owns the last page."""
    assert run(check_empty_page_with_has_more, page(0, has_more=True, item_count=0)) == []


def test_an_unobservable_items_array_proves_nothing() -> None:
    pages = [
        page(0, has_more=True, items_status=ObservationStatus.NOT_FOUND),
        page(1, has_more=False, item_count=1),
    ]
    assert run(check_empty_page_with_has_more, *pages) == []


# ---------------------------------------------------------------- INV-TRACE-001


def test_a_trace_ending_on_a_null_continuation_is_silent() -> None:
    assert run(check_trace_ends_with_continuation, page(0, next_cursor=None)) == []


def test_an_empty_string_continuation_is_also_termination() -> None:
    assert run(check_trace_ends_with_continuation, page(0, next_cursor="")) == []


def test_an_unused_continuation_token_is_proven() -> None:
    (finding,) = run(check_trace_ends_with_continuation, page(0, next_cursor="more"))

    assert finding.code == ENDS_WITH_CONTINUATION
    assert finding.certainty is Certainty.PROVEN
    assert finding.evidence[0].value == "more"


def test_it_never_says_the_api_failed_to_answer() -> None:
    (finding,) = run(check_trace_ends_with_continuation, page(0, next_cursor="more"))
    assert "failed" not in finding.message.lower()


def test_has_more_true_wins_so_the_stop_is_reported_once() -> None:
    pages = [page(0, next_cursor="more", has_more=True)]
    assert run(check_trace_ends_with_continuation, *pages) == []


def test_an_unobservable_next_cursor_proves_nothing() -> None:
    pages = [page(0, next_cursor=ObservationStatus.NOT_FOUND)]
    assert run(check_trace_ends_with_continuation, *pages) == []


def test_other_presets_are_left_alone() -> None:
    assert run(check_trace_ends_with_continuation, page(0, next_cursor="x"), preset="page") == []
