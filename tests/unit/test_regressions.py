"""One oracle per defect found by review after the suite was already green.

A fixed PageTrace bug never gets fixed without a regression test (`docs/engineering-principles.md`
point 10). Each test below names the defect and what it used to do.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from tests.factories import page, trace

from pagetrace.checks.cursors import check_cursor_stalled
from pagetrace.checks.sequence import check_identical_responses, check_offset_progression
from pagetrace.checks.totals import check_total_discrepancy
from pagetrace.cli import EXIT_OK, EXIT_USAGE, main
from pagetrace.inputs.jsonl import query_of
from pagetrace.model import Certainty, Observation


def test_a_unicode_digit_page_number_is_not_an_integer() -> None:
    """Used to crash: str.isdigit() is true for the superscript two, int() refuses it."""
    for value in ["²", "①", "٣", "½"]:
        assert Observation.of("request.page", value).int_value is None


def test_a_unicode_digit_in_a_trace_exits_cleanly(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Used to raise ValueError out of the core and exit 1 with a traceback."""
    records: list[dict[str, Any]] = [
        {
            "v": 1,
            "request": {"url": "https://api.example/i?page=²"},
            "response": {"status": 200, "body": {"items": []}},
        },
        {
            "v": 1,
            "request": {"url": "https://api.example/i?page=2"},
            "response": {"status": 200, "body": {"items": []}},
        },
    ]
    path = tmp_path / "weird.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")

    exit_code = main(["check", str(path), "--preset", "page"])
    captured = capsys.readouterr()

    assert exit_code in {EXIT_OK, EXIT_USAGE}
    assert "Traceback" not in captured.err
    assert "PAGE_NUMBER_NOT_OBSERVABLE" in captured.out


def test_a_second_stall_on_another_value_is_reported() -> None:
    """Used to stop after the first stall, so a stall on another cursor went unreported."""
    pages = [
        page(0, cursor="A", next_cursor="B"),
        page(1, cursor="A", next_cursor="B"),
        page(2, cursor="B", next_cursor="C"),
        page(3, cursor="B", next_cursor=None),
    ]
    findings = list(check_cursor_stalled(trace(*pages)))

    assert [f.affected_pages for f in findings] == [(0, 1), (2, 3)]


def test_a_run_of_one_stalled_value_is_still_one_finding() -> None:
    pages = [page(index, cursor="A", next_cursor="B") for index in range(4)]
    assert len(list(check_cursor_stalled(trace(*pages)))) == 1


def test_a_second_run_of_identical_pages_after_an_error_is_reported() -> None:
    """Used to be swallowed: the run flag was never reset for pairs the engine skipped."""
    pages = [
        page(0, fingerprint="X", item_ids=[1]),
        page(1, fingerprint="X", item_ids=[1]),
        page(2, status=500),
        page(3, fingerprint="Y", item_ids=[2]),
        page(4, fingerprint="Y", item_ids=[2]),
    ]
    findings = list(check_identical_responses(trace(*pages, preset="page")))

    assert [f.affected_pages for f in findings] == [(0, 1), (3, 4)]


def test_a_total_comparison_over_a_failed_request_is_not_proven() -> None:
    """Used to be PROVEN: a window of items was never seen, and the count said so anyway."""
    pages = [
        page(0, cursor="A", next_cursor="B", total=5, item_ids=[1, 2]),
        page(1, cursor="B", status=500),
        page(2, cursor="C", next_cursor=None, total=5, item_ids=[4, 5]),
    ]
    (finding,) = list(check_total_discrepancy(trace(*pages)))

    assert finding.certainty is Certainty.SUSPICIOUS
    assert "did not return a result page" in finding.message


def test_a_total_that_is_not_an_integer_on_one_page_stops_the_comparison() -> None:
    """Used to silently believe the integer from the other page."""
    pages = [
        page(0, total=5, next_cursor="b", item_ids=[1]),
        page(1, total="many", next_cursor=None, item_ids=[2]),
    ]
    (finding,) = list(check_total_discrepancy(trace(*pages)))

    assert finding.certainty is Certainty.INSUFFICIENT_EVIDENCE
    assert finding.code == "TOTAL_CHANGED_BETWEEN_PAGES"


def test_an_offset_witness_after_the_violation_does_not_prove_it() -> None:
    """INV-OFFSET-001 says "at least one earlier transition"; the code used to accept any."""
    pages = [
        page(0, offset=0, item_count=10),
        page(1, offset=100, item_count=10),
        page(2, offset=110, item_count=5),
    ]
    (finding,) = list(check_offset_progression(trace(*pages, preset="offset")))

    assert finding.certainty is Certainty.SUSPICIOUS
    assert finding.affected_pages == (0, 1)


def test_a_page_jump_does_not_swallow_the_missing_evidence_summary() -> None:
    """Used to return early, dropping the summary of transitions it could not check."""
    from pagetrace.checks.sequence import check_page_progression

    pages = [
        page(0, page_number="abc"),
        page(1, page_number=1),
        page(2, page_number=7),
    ]
    codes = [f.code for f in check_page_progression(trace(*pages, preset="page"))]

    assert "PAGE_NUMBER_JUMP" in codes
    assert "PAGE_NUMBER_NOT_OBSERVABLE" in codes


def test_an_explicit_query_keeps_the_canonical_text_of_its_values() -> None:
    """Used to run str() over the value, turning JSON true into "True" and null into "None"."""
    parsed = query_of({"query": {"flag": True, "empty": None, "n": 5}}, "https://api.example/i")

    assert parsed == {"flag": "true", "empty": "null", "n": "5"}


def test_a_duplicate_item_alone_does_not_fail_a_build(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Used to exit 1: a proven observation whose meaning the finding declines to assert."""
    records: list[dict[str, Any]] = [
        {
            "v": 1,
            "request": {"url": "https://api.example/i"},
            "response": {"status": 200, "body": {"items": [{"id": 1}], "next_cursor": "c2"}},
        },
        {
            "v": 1,
            "request": {"url": "https://api.example/i?cursor=c2"},
            "response": {"status": 200, "body": {"items": [{"id": 1}], "next_cursor": None}},
        },
    ]
    path = tmp_path / "dupes.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")

    assert main(["check", str(path)]) == EXIT_OK
    assert "DUPLICATE_ITEM_ACROSS_PAGES" in capsys.readouterr().out


def test_a_text_response_body_is_never_read_as_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Used to crash, or worse, read a text body that happened to contain JSON as the response.

    The JSONPath engine parses a string argument as a JSON document. A response body recorded as
    text is not a document to read into.
    """
    records: list[dict[str, Any]] = [
        {
            "v": 1,
            "request": {"url": "https://api.example/i"},
            "response": {"status": 200, "body": '{"next_cursor": "SMUGGLED"}'},
        },
        {
            "v": 1,
            "request": {"url": "https://api.example/i?cursor=c2"},
            "response": {"status": 200, "body": "{"},
        },
    ]
    path = tmp_path / "text-body.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")

    exit_code = main(["check", str(path), "--next", "$.next_cursor"])
    captured = capsys.readouterr()

    assert exit_code == EXIT_OK
    assert "Traceback" not in captured.err
    assert "SMUGGLED" not in captured.out
