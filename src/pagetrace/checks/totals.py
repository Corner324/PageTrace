"""Declared totals. Specification: INV-TOTAL-001 in specs/invariants.md.

The most precondition-heavy detector in PageTrace, on purpose. A count that does not add up is
the easiest thing to report and the easiest thing to be wrong about: `total` may count a
different population, the dataset may have moved during the capture, the filters may differ.
So the comparison is only made when the trace itself rules those out, and the wording never
says that records are missing.
"""

from __future__ import annotations

from collections.abc import Iterator

from pagetrace.checks.base import insufficient, last_ok_page
from pagetrace.model import Certainty, Evidence, Finding, Page, Severity, Trace


def _terminated(trace: Trace) -> bool:
    """The trace ends on a page that declared no continuation."""
    last = last_ok_page(trace)
    if last is None:
        return False
    if last.has_more.observed and last.has_more.value is False:
        return True
    return last.next_cursor.is_empty


def check_total_discrepancy(trace: Trace) -> Iterator[Finding]:
    """INV-TOTAL-001: the declared total does not match the items observed."""
    pages = [page for page in trace.pages if page.ok]
    if not pages:
        return

    declared = _stable_total(pages)
    if declared is None:
        # A total that changes between pages, or that is observed as something other than an
        # integer, is reported as nothing at all: INV-TOTAL-001 says the dataset moved under the
        # paginator and no comparison is possible, and an insufficient-evidence finding would
        # still be a statement about a total this detector may not reason about.
        return

    if not all(page.items.observed for page in pages):
        yield insufficient(
            code="TOTAL_ITEMS_NOT_OBSERVABLE",
            invariant="INV-TOTAL-001",
            message=(
                "A total is declared but the items of at least one page could not be counted, "
                "so nothing can be compared. Check --items."
            ),
        )
        return

    if not _terminated(trace):
        # An incomplete capture explains any shortfall by itself, and INV-CONT-001 or
        # INV-TRACE-001 has already said the trace ends early.
        return

    raw = sum(page.items.count or 0 for page in pages)
    distinct = len({identity.text for page in pages for identity in page.items.identities})
    fully_identified = all(page.items.fully_identified for page in pages)
    has_duplicates = fully_identified and distinct != raw
    observed = distinct if fully_identified else raw

    if observed == declared:
        return

    # A request that failed means a window of results was never seen at all. Counting the pages
    # that did come back and calling the difference proven would be exactly the over-claim this
    # project exists to avoid.
    complete = len(pages) == trace.page_count
    exact = fully_identified and not has_duplicates and complete
    yield Finding(
        code="TOTAL_COUNT_DISCREPANCY",
        invariant="INV-TOTAL-001",
        certainty=Certainty.PROVEN if exact else Certainty.SUSPICIOUS,
        severity=Severity.WARNING,
        message=_message(
            exact=exact,
            duplicates=has_duplicates,
            failed_requests=trace.page_count - len(pages),
        ),
        affected_pages=tuple(page.index for page in pages[:1]),
        evidence=(
            Evidence("trace.declared_total", declared),
            Evidence("trace.observed_items", raw),
            Evidence("trace.distinct_items", distinct),
            Evidence("trace.page_count", len(pages)),
        ),
    )


def _stable_total(pages: list[Page]) -> int | None:
    """The declared total, when every page that declares one declares the same integer.

    A page whose total is observed but is not an integer makes the whole thing unusable: taking
    the integer from the other pages would be choosing which observation to believe.
    """
    if any(page.total.observed and page.total.int_value is None for page in pages):
        return None
    values = {page.total.int_value for page in pages if page.total.int_value is not None}
    return values.pop() if len(values) == 1 else None


def _message(*, exact: bool, duplicates: bool, failed_requests: int = 0) -> str:
    """Static wording. Every number lives in the evidence (global precondition 8)."""
    message = (
        "The total declared by the trace and the items observed across it are not the same "
        "number; both counts are in the evidence below. PageTrace does not know whether the "
        "total counts the same population under the same filters, so this is a difference "
        "between two numbers, not a count of records that went missing."
    )
    if failed_requests:
        message += (
            " At least one request in this trace did not return a result page, so a window of "
            "items was never observed."
        )
    if duplicates:
        message += (
            " Some items appear on more than one page, which changes what the total should be "
            "compared against."
        )
    elif not exact and not failed_requests:
        message += " Some items had no observable identity, so they could not be deduplicated."
    return message
