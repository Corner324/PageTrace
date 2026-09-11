"""The correctness vocabulary. Global preconditions 1-3 of specs/invariants.md."""

from __future__ import annotations

import pytest

from pagetrace.model import (
    Certainty,
    Evidence,
    Finding,
    ItemsObservation,
    Observation,
    ObservationStatus,
    Page,
    Scalar,
    Severity,
    canonical_text,
    exit_code_for,
    sort_findings,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (5, "5"),
        ("5", "5"),
        (True, "true"),
        ("true", "true"),
        (False, "false"),
        (None, "null"),
        (5.0, "5.0"),
        ("", ""),
    ],
)
def test_canonical_text(value: Scalar, expected: str) -> None:
    assert canonical_text(value) == expected


def test_int_and_string_are_the_same_observation() -> None:
    """A query parameter only carries text, so 5 and "5" must never read as a mismatch."""
    assert Observation.of("a", 5).same_as(Observation.of("b", "5"))


def test_float_and_int_text_differ() -> None:
    assert not Observation.of("a", 5.0).same_as(Observation.of("b", 5))


def test_json_null_is_observed_not_absent() -> None:
    """Global precondition 2: {"next": null} declares termination; a missing selector does not."""
    null = Observation.of("response.next_cursor", None)
    absent = Observation.missing("response.next_cursor", ObservationStatus.NOT_FOUND)

    assert null.observed
    assert null.is_null
    assert null.is_empty
    assert not absent.observed
    assert not absent.is_null
    assert null.text is None
    assert absent.text is None


def test_empty_string_counts_as_no_continuation() -> None:
    assert Observation.of("response.next_cursor", "").is_empty
    assert not Observation.of("response.next_cursor", "x").is_empty


def test_unobserved_values_never_compare_equal() -> None:
    """Two missing observations are not evidence of agreement."""
    a = Observation.missing("request.cursor", ObservationStatus.NOT_FOUND)
    b = Observation.missing("request.cursor", ObservationStatus.NOT_FOUND)
    assert not a.same_as(b)
    assert not Observation.of("a", None).same_as(Observation.of("b", None))


def test_missing_rejects_the_observed_status() -> None:
    with pytest.raises(ValueError, match=r"Observation\.of"):
        Observation.missing("x", ObservationStatus.OBSERVED)


@pytest.mark.parametrize(
    ("status", "ok"),
    [
        (200, True),
        (204, True),
        (299, True),
        (300, False),
        (404, False),
        (500, False),
        (None, False),
    ],
)
def test_page_ok_is_2xx_only(status: int | None, ok: bool) -> None:
    assert Page(index=0, url="u", status=status).ok is ok


def test_page_evidence_is_page_qualified() -> None:
    page = Page(index=4, url="u", status=200, next_cursor=Observation.of("response.next", "abc"))
    assert page.evidence(page.next_cursor) == Evidence("page[4].response.next", "abc")


def test_items_observation_identification() -> None:
    absent = ItemsObservation.missing(ObservationStatus.NOT_CONFIGURED)
    assert not absent.observed
    assert not absent.fully_identified

    partial = ItemsObservation(ObservationStatus.OBSERVED, count=3, unidentified=1)
    assert partial.observed
    assert not partial.fully_identified
    assert ItemsObservation(ObservationStatus.OBSERVED, count=0).fully_identified


def _finding(code: str, certainty: Certainty, pages: tuple[int, ...] = ()) -> Finding:
    return Finding(
        code=code,
        invariant=f"INV-TEST-{code[:3]}",
        certainty=certainty,
        severity=Severity.WARNING,
        message="m",
        affected_pages=pages,
    )


def _severe(code: str) -> Finding:
    return Finding(
        code=code,
        invariant=f"INV-TEST-{code}",
        certainty=Certainty.PROVEN,
        severity=Severity.ERROR,
        message="m",
        affected_pages=(1,),
    )


def test_findings_sort_strongest_first_then_by_page() -> None:
    unordered = [
        _finding("AAA", Certainty.INSUFFICIENT_EVIDENCE),
        _finding("BBB", Certainty.PROVEN, (7,)),
        _finding("CCC", Certainty.SUSPICIOUS, (1,)),
        _finding("DDD", Certainty.PROVEN, (2,)),
    ]
    assert [f.code for f in sort_findings(unordered)] == ["DDD", "BBB", "CCC", "AAA"]


def test_sort_is_stable_across_runs() -> None:
    findings = [_finding("B", Certainty.PROVEN, (1,)), _finding("A", Certainty.PROVEN, (1,))]
    assert sort_findings(findings) == sort_findings(list(reversed(findings)))


def test_exit_code_needs_both_proven_and_severe() -> None:
    """A proven observation whose meaning the finding declines to assert must not fail a build."""
    assert exit_code_for([]) == 0
    assert exit_code_for([_finding("A", Certainty.SUSPICIOUS, (1,))]) == 0
    assert exit_code_for([_finding("A", Certainty.INSUFFICIENT_EVIDENCE)]) == 0
    assert exit_code_for([_finding("A", Certainty.PROVEN, (1,))]) == 0  # severity WARNING
    assert exit_code_for([_severe("A")]) == 1
    assert exit_code_for([_finding("A", Certainty.SUSPICIOUS, (1,)), _severe("B")]) == 1


def test_a_severe_finding_that_is_not_proven_does_not_fail_a_build() -> None:
    suspicion = Finding(
        code="A",
        invariant="INV-TEST-A",
        certainty=Certainty.SUSPICIOUS,
        severity=Severity.ERROR,
        message="m",
        affected_pages=(1,),
    )
    assert exit_code_for([suspicion]) == 0
