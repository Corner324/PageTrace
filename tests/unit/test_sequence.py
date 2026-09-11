"""INV-PAGE-001, INV-OFFSET-001 and INV-RESP-001."""

from __future__ import annotations

from tests.factories import page, trace

from pagetrace.checks.base import Check
from pagetrace.checks.sequence import (
    check_identical_responses,
    check_offset_progression,
    check_page_progression,
)
from pagetrace.model import Certainty, Finding, ObservationStatus, Page

JUMP = "PAGE_NUMBER_JUMP"
OFFSET_JUMP = "OFFSET_JUMP"
IDENTICAL = "IDENTICAL_CONSECUTIVE_RESPONSES"


def run(check: Check, *pages: Page, preset: str) -> list[Finding]:
    return list(check(trace(*pages, preset=preset)))


# ---------------------------------------------------------------- INV-PAGE-001


def numbered(*values: object, status: int = 200) -> list[Page]:
    return [page(index, page_number=value, status=status) for index, value in enumerate(values)]


def test_one_based_pages_advance_cleanly() -> None:
    assert run(check_page_progression, *numbered(1, 2, 3), preset="page") == []


def test_zero_based_pages_advance_cleanly() -> None:
    """Only the delta is used, so neither convention needs to be assumed."""
    assert run(check_page_progression, *numbered(0, 1, 2), preset="page") == []


def test_numbers_as_query_strings_are_integers() -> None:
    assert run(check_page_progression, *numbered("1", "2"), preset="page") == []


def test_a_skipped_page_is_proven() -> None:
    (finding,) = run(check_page_progression, *numbered(1, 3), preset="page")

    assert finding.code == JUMP
    assert finding.certainty is Certainty.PROVEN
    assert finding.affected_pages == (0, 1)
    assert finding.evidence[-1].value == 2


def test_a_repeated_page_number_is_a_jump_of_zero() -> None:
    (finding,) = run(check_page_progression, *numbered(2, 2), preset="page")
    assert finding.evidence[-1].value == 0


def test_going_backwards_is_reported_by_its_delta_not_by_a_verdict() -> None:
    (finding,) = run(check_page_progression, *numbered(3, 1), preset="page")
    assert "a change of -2 instead of 1" in finding.message
    assert "backwards" not in finding.message


def test_only_the_first_jump_is_reported() -> None:
    assert len(run(check_page_progression, *numbered(1, 3, 9), preset="page")) == 1


def test_a_non_numeric_page_token_proves_nothing() -> None:
    findings = run(check_page_progression, *numbered("abc", "def"), preset="page")
    assert [f.code for f in findings] == ["PAGE_NUMBER_NOT_OBSERVABLE"]
    assert findings[0].certainty is Certainty.INSUFFICIENT_EVIDENCE


def test_non_2xx_pages_are_excluded() -> None:
    assert run(check_page_progression, *numbered(1, 5, status=500), preset="page") == []


def test_other_presets_are_left_alone() -> None:
    assert run(check_page_progression, *numbered(1, 5), preset="cursor") == []


# ---------------------------------------------------------------- INV-OFFSET-001


def offsets(*pairs: tuple[int | str, int]) -> list[Page]:
    return [
        page(index, offset=value, item_count=count) for index, (value, count) in enumerate(pairs)
    ]


def test_offsets_that_follow_the_item_counts_are_silent() -> None:
    pages = offsets((0, 10), (10, 10), (20, 3))
    assert run(check_offset_progression, *pages, preset="offset") == []


def test_a_break_after_an_established_contract_is_proven() -> None:
    pages = offsets((0, 10), (10, 10), (50, 3))
    (finding,) = run(check_offset_progression, *pages, preset="offset")

    assert finding.code == OFFSET_JUMP
    assert finding.certainty is Certainty.PROVEN
    assert finding.affected_pages == (1, 2)
    assert finding.evidence[-1].value == 20


def test_without_a_witness_the_contract_is_only_assumed() -> None:
    """An API may offset by something other than items, and the trace cannot say."""
    pages = offsets((0, 10), (100, 10), (200, 3))
    (finding,) = run(check_offset_progression, *pages, preset="offset")

    assert finding.certainty is Certainty.SUSPICIOUS
    assert "an assumption here rather than an observation" in finding.message


def test_only_the_first_offset_violation_is_reported() -> None:
    pages = offsets((0, 10), (10, 10), (50, 10), (99, 1))
    assert len(run(check_offset_progression, *pages, preset="offset")) == 1


def test_a_partial_last_page_is_normal() -> None:
    pages = offsets((0, 10), (10, 4))
    assert run(check_offset_progression, *pages, preset="offset") == []


def test_an_unobservable_item_count_proves_nothing() -> None:
    pages = [
        page(0, offset=0, items_status=ObservationStatus.NOT_FOUND),
        page(1, offset=99, items_status=ObservationStatus.NOT_FOUND),
    ]
    findings = run(check_offset_progression, *pages, preset="offset")
    assert [f.code for f in findings] == ["OFFSET_NOT_OBSERVABLE"]


# ---------------------------------------------------------------- INV-RESP-001


def fingerprints(*values: str, counts: list[int] | None = None) -> list[Page]:
    sizes = counts or [1] * len(values)
    return [
        page(index, fingerprint=value, item_count=sizes[index])
        for index, value in enumerate(values)
    ]


def test_different_bodies_are_silent() -> None:
    assert run(check_identical_responses, *fingerprints("a", "b"), preset="cursor") == []


def test_identical_bodies_are_only_suspicious() -> None:
    (finding,) = run(check_identical_responses, *fingerprints("a", "a"), preset="cursor")

    assert finding.code == IDENTICAL
    assert finding.certainty is Certainty.SUSPICIOUS
    assert "equally with a cache" in finding.message


def test_a_run_of_identical_pages_is_one_observation() -> None:
    pages = fingerprints("a", "a", "a", "a")
    assert len(run(check_identical_responses, *pages, preset="cursor")) == 1


def test_two_separate_runs_are_two_observations() -> None:
    pages = fingerprints("a", "a", "b", "c", "c")
    assert len(run(check_identical_responses, *pages, preset="cursor")) == 2


def test_two_empty_pages_prove_nothing() -> None:
    pages = fingerprints("a", "a", counts=[0, 0])
    assert run(check_identical_responses, *pages, preset="cursor") == []


def test_a_stall_covers_the_pair_so_this_stays_silent() -> None:
    """One pair, one fact: INV-CURSOR-002 is the specific one."""
    pages = [
        page(0, cursor="x", fingerprint="a", item_count=1),
        page(1, cursor="x", fingerprint="a", item_count=1),
    ]
    assert run(check_identical_responses, *pages, preset="cursor") == []


def test_pages_without_a_body_prove_nothing() -> None:
    pages = [page(0, item_count=1), page(1, item_count=1)]
    assert run(check_identical_responses, *pages, preset="cursor") == []
