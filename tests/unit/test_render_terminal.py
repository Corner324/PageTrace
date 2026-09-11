"""Display safety and the terminal report."""

from __future__ import annotations

import pytest
from tests.factories import page, trace

from pagetrace.model import Certainty, Evidence, Finding, Observation, Scalar, Severity
from pagetrace.render import display
from pagetrace.render.terminal import MAX_SHOWN_PER_CODE, render_terminal


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "null"),
        (True, "true"),
        (False, "false"),
        (5, "5"),
        (5.5, "5.5"),
        ("abc", '"abc"'),
    ],
)
def test_display_of_simple_values(value: Scalar, expected: str) -> None:
    assert display(value).text == expected


def test_control_characters_are_escaped() -> None:
    shown = display("a\x1b[31mb\n")
    assert shown.text == '"a\\x1b[31mb\\x0a"'
    assert not shown.truncated


def test_long_values_are_truncated_but_the_true_length_is_kept() -> None:
    shown = display("x" * 500, limit=10)
    assert shown.value == "x" * 10
    assert shown.text == '"xxxxxxxxxx..."'
    assert shown.truncated
    assert shown.length == 500


def test_a_value_at_the_limit_is_not_truncated() -> None:
    shown = display("x" * 10, limit=10)
    assert not shown.truncated
    assert shown.length == 10


def finding(
    code: str, certainty: Certainty = Certainty.PROVEN, pages: tuple[int, ...] = (0, 1)
) -> Finding:
    return Finding(
        code=code,
        invariant="INV-CURSOR-001",
        certainty=certainty,
        severity=Severity.ERROR,
        message="Something observable happened.",
        affected_pages=pages,
        evidence=(Evidence("page[0].response.next_cursor", "abc"),),
    )


def test_clean_report_says_so() -> None:
    report = render_terminal(trace(page(0)), [], "trace.jsonl")
    assert "No findings" in report
    assert "0 proven, 0 suspicious, 0 insufficient evidence" in report


def test_report_header_names_the_source_and_preset() -> None:
    report = render_terminal(trace(page(0), page(1)), [], "trace.jsonl")
    assert report.startswith("trace.jsonl: 2 pages, preset cursor")


def test_finding_block_shows_certainty_invariant_and_evidence() -> None:
    report = render_terminal(trace(page(0)), [finding("X")], "t.jsonl")
    assert "PROVEN ERROR X [INV-CURSOR-001] pages 0, 1" in report
    assert 'page[0].response.next_cursor = "abc"' in report


def test_single_page_finding_reads_as_one_page() -> None:
    report = render_terminal(trace(page(0)), [finding("X", pages=(3,))], "t.jsonl")
    assert "page 3" in report


def test_finding_without_pages_has_no_page_suffix() -> None:
    report = render_terminal(
        trace(page(0)),
        [finding("X", Certainty.INSUFFICIENT_EVIDENCE, pages=())],
        "t.jsonl",
    )
    assert "[INV-CURSOR-001]\n" in report


def test_repeated_findings_are_capped_with_a_pointer_to_the_json_report() -> None:
    findings = [finding("X") for _ in range(MAX_SHOWN_PER_CODE + 5)]
    report = render_terminal(trace(page(0)), findings, "t.jsonl")

    assert report.count("Something observable happened.") == MAX_SHOWN_PER_CODE
    assert "... and 5 more X findings, see the JSON report" in report
    assert f"{MAX_SHOWN_PER_CODE + 5} proven" in report


def test_summary_counts_each_certainty() -> None:
    findings = [
        finding("A", Certainty.PROVEN),
        finding("B", Certainty.SUSPICIOUS),
        finding("C", Certainty.INSUFFICIENT_EVIDENCE),
        finding("D", Certainty.SUSPICIOUS),
    ]
    report = render_terminal(trace(page(0)), findings, "t.jsonl")
    assert "1 proven, 2 suspicious, 1 insufficient evidence" in report


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (5, 5),
        ("5", 5),
        ("-5", -5),
        ("+5", 5),
        (" 7 ", 7),
        (True, None),
        ("5.0", None),
        ("x", None),
        (5.0, None),
    ],
)
def test_int_value_parses_text_without_inventing_rules(value: Scalar, expected: int | None) -> None:
    assert Observation.of("p", value).int_value == expected


def test_int_value_of_an_unobserved_selector_is_none() -> None:
    from pagetrace.model import ObservationStatus

    assert Observation.missing("p", ObservationStatus.NOT_FOUND).int_value is None


def test_the_trace_filename_is_escaped() -> None:
    """A filename is not an observation, so nothing else escapes it on the way out."""
    report = render_terminal(trace(page(0)), [], "run[2J.jsonl")

    assert "" not in report
    assert report.startswith("run" + chr(92) + "x1b[2J.jsonl:")
