"""The central property: a correct trace never produces a proven violation.

This is the direct attack on false positives. Every detector added to the registry is covered
here for free, which is the point of generating traces instead of writing fixtures.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st
from tests.property.strategies import valid_link_trace, valid_trace

from pagetrace.checks import CHECKS, run_checks
from pagetrace.model import Certainty, Trace


def proven(trace: Trace) -> list[str]:
    return [f.code for f in run_checks(trace) if f.certainty is Certainty.PROVEN]


@given(valid_trace())
def test_no_proven_finding_on_a_valid_trace(trace: Trace) -> None:
    assert proven(trace) == []


@given(valid_trace(with_total=True, with_has_more=True))
def test_no_proven_finding_when_total_and_has_more_are_declared(trace: Trace) -> None:
    assert proven(trace) == []


@given(valid_trace(min_pages=1, max_pages=1))
def test_a_single_page_run_proves_nothing(trace: Trace) -> None:
    assert proven(trace) == []


@given(valid_trace(min_pages=40, max_pages=60))
def test_long_runs_stay_quiet(trace: Trace) -> None:
    """Hundreds of pages are generated, never stored as a fixture."""
    assert proven(trace) == []


@given(valid_trace())
def test_analysis_is_deterministic(trace: Trace) -> None:
    assert run_checks(trace) == run_checks(trace)


@given(valid_trace(), st.integers(min_value=0, max_value=len(CHECKS) - 1))
def test_every_check_is_pure(trace: Trace, index: int) -> None:
    """Running one check twice gives the same findings: no hidden state between runs."""
    check = CHECKS[index]
    assert list(check(trace)) == list(check(trace))


@given(valid_trace())
def test_findings_are_sorted_and_reproducible(trace: Trace) -> None:
    findings = run_checks(trace)
    assert [f.sort_key for f in findings] == sorted(f.sort_key for f in findings)


@given(valid_trace())
def test_evidence_paths_point_at_real_pages(trace: Trace) -> None:
    for finding in run_checks(trace):
        for index in finding.affected_pages:
            assert 0 <= index < trace.page_count


@given(valid_link_trace())
def test_no_proven_finding_on_a_valid_link_trace(trace: Trace) -> None:
    """The link preset gets the same guarantee as the cursor preset, not less."""
    assert proven(trace) == []


@given(valid_link_trace(min_pages=3))
def test_a_link_run_is_not_mistaken_for_a_stall(trace: Trace) -> None:
    codes = {f.code for f in run_checks(trace)}
    assert "CURSOR_STALLED" not in codes
    assert "CURSOR_CYCLE" not in codes
