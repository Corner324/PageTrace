"""Mutation properties for the cursor invariants.

Take a valid trace, break exactly one property, and assert three things: the right detector
fires, it points at the right pages, and no unrelated detector is dragged along.
"""

from __future__ import annotations

from hypothesis import assume, given
from hypothesis import strategies as st
from tests.property.strategies import (
    change_next_cursor,
    freeze_cursor,
    insert_cursor_cycle,
    valid_trace,
)

from pagetrace.checks import run_checks
from pagetrace.model import Certainty, Finding, Trace


def proven(trace: Trace) -> list[Finding]:
    return [f for f in run_checks(trace) if f.certainty is Certainty.PROVEN]


def codes(findings: list[Finding]) -> set[str]:
    return {f.code for f in findings}


@given(valid_trace(min_pages=2), st.data())
def test_a_changed_continuation_token_is_detected(trace: Trace, data: st.DataObject) -> None:
    index = data.draw(st.integers(min_value=0, max_value=trace.page_count - 2))
    findings = proven(change_next_cursor(trace, index))

    assert codes(findings) == {"CURSOR_CONTINUATION_MISMATCH"}
    assert findings[0].affected_pages == (index, index + 1)


@given(valid_trace(min_pages=3), st.data())
def test_a_frozen_cursor_is_detected_as_a_stall(trace: Trace, data: st.DataObject) -> None:
    index = data.draw(st.integers(min_value=1, max_value=trace.page_count - 2))
    findings = proven(freeze_cursor(trace, index))

    assert "CURSOR_STALLED" in codes(findings)
    stall = next(f for f in findings if f.code == "CURSOR_STALLED")
    assert stall.affected_pages == (index, index + 1)


@given(valid_trace(min_pages=4), st.data())
def test_an_injected_cycle_is_detected(trace: Trace, data: st.DataObject) -> None:
    length = data.draw(st.integers(min_value=2, max_value=max(trace.page_count - 2, 2)))
    start = data.draw(st.integers(min_value=1, max_value=trace.page_count - 1 - length))
    assume(start + length < trace.page_count)

    findings = proven(insert_cursor_cycle(trace, start, length))
    cycles = [f for f in findings if f.code == "CURSOR_CYCLE"]

    assert len(cycles) == 1
    assert cycles[0].affected_pages == (start, start + length)
    assert f"{length} pages" in cycles[0].message


@given(valid_trace(min_pages=4), st.data())
def test_a_cycle_never_claims_non_termination(trace: Trace, data: st.DataObject) -> None:
    start = data.draw(st.integers(min_value=1, max_value=trace.page_count - 3))
    length = data.draw(st.integers(min_value=2, max_value=trace.page_count - 1 - start))

    for finding in run_checks(insert_cursor_cycle(trace, start, length)):
        assert "never terminates" not in finding.message
        assert "infinite" not in finding.message.lower()


@given(valid_trace(min_pages=2), st.data())
def test_one_broken_property_produces_one_kind_of_finding(
    trace: Trace, data: st.DataObject
) -> None:
    """A single defect must not set off half the registry."""
    index = data.draw(st.integers(min_value=0, max_value=trace.page_count - 2))
    assert len(codes(proven(change_next_cursor(trace, index)))) == 1
