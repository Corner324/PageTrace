"""INV-CURSOR-002 (stall) and INV-CURSOR-003 (cycle)."""

from __future__ import annotations

import pytest
from tests.factories import page, trace

from pagetrace.checks.base import Check
from pagetrace.checks.cursors import check_cursor_cycle, check_cursor_stalled
from pagetrace.model import Certainty, Finding, ObservationStatus, Page

STALL = "CURSOR_STALLED"
CYCLE = "CURSOR_CYCLE"


def run(check: Check, *pages: Page, preset: str = "cursor") -> list[Finding]:
    return list(check(trace(*pages, preset=preset)))


def cursors(*values: str | None, statuses: list[int] | None = None) -> list[Page]:
    """Pages whose request cursors are the given values, in order."""
    codes = statuses or [200] * len(values)
    return [
        page(
            index=position,
            cursor=ObservationStatus.NOT_FOUND if value is None else value,
            next_cursor=None if position == len(values) - 1 else "advance",
            status=codes[position],
        )
        for position, value in enumerate(values)
    ]


def test_a_progressing_run_is_silent() -> None:
    assert run(check_cursor_stalled, *cursors("a", "b", "c")) == []
    assert run(check_cursor_cycle, *cursors("a", "b", "c")) == []


def test_stall_is_proven() -> None:
    (finding,) = run(check_cursor_stalled, *cursors("a", "a", "b"))

    assert finding.code == STALL
    assert finding.invariant == "INV-CURSOR-002"
    assert finding.certainty is Certainty.PROVEN
    assert finding.affected_pages == (0, 1)


def test_only_the_first_stall_is_reported() -> None:
    """Later repeats follow from the first; they are not independent observations."""
    assert len(run(check_cursor_stalled, *cursors("a", "a", "a", "a"))) == 1


def test_a_retry_after_a_failure_is_not_a_stall() -> None:
    pages = cursors("a", "a", "b", statuses=[500, 200, 200])
    assert run(check_cursor_stalled, *pages) == []


def test_a_stall_is_not_also_reported_as_a_cycle() -> None:
    assert run(check_cursor_cycle, *cursors("a", "a", "b")) == []


@pytest.mark.parametrize("length", [2, 3, 4, 7])
def test_cycles_of_any_length_are_proven(length: int) -> None:
    values = [chr(ord("a") + index) for index in range(length)]
    (finding,) = run(check_cursor_cycle, *cursors("start", *values, "a"))

    assert finding.code == CYCLE
    assert finding.certainty is Certainty.PROVEN
    assert finding.affected_pages == (1, length + 1)


def test_cycle_message_refuses_to_claim_non_termination() -> None:
    (finding,) = run(check_cursor_cycle, *cursors("a", "b", "a"))
    message = finding.message.lower()
    assert "revisits a state" in message
    assert "forever cannot be told" in message
    assert "never terminates" not in message


def test_cycle_starting_halfway_through() -> None:
    (finding,) = run(check_cursor_cycle, *cursors("a", "b", "c", "b"))
    assert finding.affected_pages == (1, 3)


def test_only_the_first_cycle_is_reported() -> None:
    assert len(run(check_cursor_cycle, *cursors("a", "b", "a", "b", "a"))) == 1


def test_evidence_includes_the_endpoints_and_the_way_round() -> None:
    (finding,) = run(check_cursor_cycle, *cursors("a", "b", "c", "a"))
    assert [e.path for e in finding.evidence] == [
        "page[0].request.cursor",
        "page[1].request.cursor",
        "page[2].request.cursor",
        "page[3].request.cursor",
    ]


def test_long_cycles_do_not_dump_every_cursor() -> None:
    values = [f"c{index}" for index in range(20)]
    (finding,) = run(check_cursor_cycle, *cursors("a", *values, "a"))
    assert len(finding.evidence) <= 7


def test_a_failure_inside_the_range_downgrades_to_suspicious() -> None:
    """A retry after an error explains the repeat just as well as a cycle does."""
    pages = cursors("a", "b", "a", statuses=[200, 503, 200])
    (finding,) = run(check_cursor_cycle, *pages)

    assert finding.certainty is Certainty.SUSPICIOUS
    assert "retried" in finding.message


def test_two_concatenated_runs_are_suspicious_not_proven() -> None:
    """A file holding two runs looks exactly like a cycle back to the start."""
    pages = [
        page(0, cursor="start", next_cursor="b"),
        page(1, cursor="b", next_cursor=None),
        page(2, cursor="start", next_cursor="b"),
    ]
    (finding,) = run(check_cursor_cycle, *pages)

    assert finding.certainty is Certainty.SUSPICIOUS
    assert "two" in finding.message


def test_a_return_to_a_later_state_stays_proven() -> None:
    """Only a return to the starting state admits the two-runs explanation."""
    pages = [
        page(0, cursor="start", next_cursor="b"),
        page(1, cursor="b", next_cursor="c"),
        page(2, cursor="c", next_cursor=None),
        page(3, cursor="b", next_cursor="c"),
    ]
    (finding,) = run(check_cursor_cycle, *pages)
    assert finding.certainty is Certainty.PROVEN


def test_unobservable_cursors_prove_nothing() -> None:
    assert run(check_cursor_cycle, *cursors(None, None, None)) == []
    assert run(check_cursor_stalled, *cursors(None, None)) == []


def test_other_presets_are_left_alone() -> None:
    assert run(check_cursor_stalled, *cursors("a", "a"), preset="page") == []
    assert run(check_cursor_cycle, *cursors("a", "b", "a"), preset="offset") == []
