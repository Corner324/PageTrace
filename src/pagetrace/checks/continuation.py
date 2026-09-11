"""Continuation detectors: INV-CONT-001, INV-CONT-002, INV-TRACE-001.

All three are statements about the recorded trace, never about the API. PageTrace cannot tell
an incomplete capture from a client that stopped early from a server that stopped answering,
and the wording of every finding here says so.
"""

from __future__ import annotations

from collections.abc import Iterator

from pagetrace.checks.base import insufficient, last_ok_page
from pagetrace.checks.cursors import CURSOR_PRESETS
from pagetrace.model import Certainty, Finding, Observation, Severity, Trace


def declares_more(observation: Observation) -> bool:
    """True only for a real boolean `true`.

    A truthy `"true"` or `1` would need a truthiness rule for someone else's API, and inventing
    one is a claim. Those are counted as missing evidence instead.
    """
    return observation.observed and observation.value is True


def _non_boolean_has_more(trace: Trace) -> int:
    return sum(
        1
        for page in trace.pages
        if page.ok and page.has_more.observed and not isinstance(page.has_more.value, bool)
    )


def check_trace_ends_with_has_more(trace: Trace) -> Iterator[Finding]:
    """INV-CONT-001: the last page declared that more results existed."""
    last = last_ok_page(trace)
    if last is not None and declares_more(last.has_more):
        yield Finding(
            code="TRACE_ENDS_WITH_HAS_MORE",
            invariant="INV-CONT-001",
            certainty=Certainty.PROVEN,
            severity=Severity.WARNING,
            message=(
                f"The trace ends at page {last.index} after a response that declared further "
                f"pagination. The capture may be incomplete, or pagination may have stopped "
                f"early. Which of the two happened is not recorded."
            ),
            affected_pages=(last.index,),
            evidence=(last.evidence(last.has_more),),
        )

    odd = _non_boolean_has_more(trace)
    if odd:
        yield insufficient(
            code="HAS_MORE_NOT_BOOLEAN",
            invariant="INV-CONT-001",
            message=(
                f"{odd} pages carry a continuation flag that is not a JSON boolean, so it was "
                f"not used. PageTrace does not guess what counts as true for an API."
            ),
        )


def check_empty_page_with_has_more(trace: Trace) -> Iterator[Finding]:
    """INV-CONT-002: a page returned no items while declaring that more existed."""
    last = last_ok_page(trace)
    for page in trace.pages:
        if not page.ok or page is last:
            # The final page is INV-CONT-001's business; reporting both is one fact twice.
            continue
        if declares_more(page.has_more) and page.items.observed and page.items.count == 0:
            yield Finding(
                code="EMPTY_PAGE_WITH_HAS_MORE",
                invariant="INV-CONT-002",
                certainty=Certainty.SUSPICIOUS,
                severity=Severity.WARNING,
                message=(
                    f"Page {page.index} returned no items while declaring further pagination. "
                    f"Some APIs return empty intermediate pages on purpose, for example when a "
                    f"filter is applied after the window is chosen."
                ),
                affected_pages=(page.index,),
                evidence=(
                    page.evidence(page.has_more),
                    page.item_count_evidence,
                ),
            )


def check_trace_ends_with_continuation(trace: Trace) -> Iterator[Finding]:
    """INV-TRACE-001: the trace ends while a continuation token is still on offer."""
    if trace.preset not in CURSOR_PRESETS:
        return

    last = last_ok_page(trace)
    if last is None or declares_more(last.has_more):
        # INV-CONT-001 already reported this stop.
        return
    if not last.next_cursor.observed or last.next_cursor.is_empty:
        return

    yield Finding(
        code="TRACE_ENDS_WITH_CONTINUATION",
        invariant="INV-TRACE-001",
        certainty=Certainty.PROVEN,
        severity=Severity.WARNING,
        message=(
            f"The trace ends at page {last.index}, which returned a continuation token that no "
            f"later request used. The capture may be incomplete, or pagination may have "
            f"stopped early."
        ),
        affected_pages=(last.index,),
        evidence=(last.evidence(last.next_cursor),),
    )
