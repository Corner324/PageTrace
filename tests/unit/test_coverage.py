"""INV-TRACE-002: what the analysis left out.

Without this, a trace whose requests all failed produced the same report as a trace that was
fine: nothing. Silence about something nobody could read is not a clean result.
"""

from __future__ import annotations

from tests.factories import page, trace

from pagetrace.checks.coverage import check_excluded_requests
from pagetrace.model import Certainty, Finding, Page

EXCLUDED = "REQUESTS_EXCLUDED_FROM_ANALYSIS"


def run(*pages: Page) -> list[Finding]:
    return list(check_excluded_requests(trace(*pages)))


def test_a_trace_of_only_good_pages_is_silent() -> None:
    assert run(page(0), page(1)) == []


def test_a_failed_request_is_reported_as_missing_evidence() -> None:
    (finding,) = run(page(0), page(1, status=500), page(2))

    assert finding.code == EXCLUDED
    assert finding.invariant == "INV-TRACE-002"
    assert finding.certainty is Certainty.INSUFFICIENT_EVIDENCE
    assert "1 of 3 requests" in finding.message
    assert "Excluded pages: 1." in finding.message


def test_the_evidence_names_the_statuses() -> None:
    (finding,) = run(page(0, status=503), page(1))
    assert finding.evidence[0].path == "page[0].response.status"
    assert finding.evidence[0].value == 503


def test_it_never_suggests_a_cause() -> None:
    (finding,) = run(page(0, status=500), page(1))
    lowered = finding.message.lower()

    assert "not a clean result" in lowered
    assert "broken" not in lowered
    assert "api" not in lowered


def test_many_exclusions_are_summarized_not_listed_in_full() -> None:
    pages = [page(index, status=500) for index in range(25)]
    (finding,) = run(*pages)

    assert "25 of 25 requests" in finding.message
    assert "and 15 more" in finding.message
    assert len(finding.evidence) == 10


def test_a_trace_of_nothing_but_errors_says_so_and_nothing_else() -> None:
    from pagetrace.checks import run_checks

    findings = run_checks(trace(page(0, status=500), page(1, status=502)))

    assert [f.code for f in findings] == [EXCLUDED]
    assert all(f.certainty is Certainty.INSUFFICIENT_EVIDENCE for f in findings)
