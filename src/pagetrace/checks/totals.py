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
        if _total_changes(pages):
            yield insufficient(
                code="TOTAL_CHANGED_BETWEEN_PAGES",
                invariant="INV-TOTAL-001",
                message=(
                    "The declared total changed between pages, so the dataset moved while it "
                    "was being paginated. No comparison is possible."
                ),
                evidence=tuple(page.evidence(page.total) for page in pages if page.total.observed)[
                    :5
                ],
            )
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

    exact = fully_identified and not has_duplicates
    yield Finding(
        code="TOTAL_COUNT_DISCREPANCY",
        invariant="INV-TOTAL-001",
        certainty=Certainty.PROVEN if exact else Certainty.SUSPICIOUS,
        severity=Severity.WARNING,
        message=_message(
            declared, raw, distinct, len(pages), exact=exact, duplicates=has_duplicates
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
    """The declared total, when every page that declares one declares the same."""
    values = {page.total.int_value for page in pages if page.total.int_value is not None}
    return values.pop() if len(values) == 1 else None


def _total_changes(pages: list[Page]) -> bool:
    values = {page.total.int_value for page in pages if page.total.int_value is not None}
    return len(values) > 1


def _message(
    declared: int,
    raw: int,
    distinct: int,
    page_count: int,
    *,
    exact: bool,
    duplicates: bool,
) -> str:
    counted = (
        f"{distinct} distinct items" if exact else f"{raw} items ({distinct} of them distinct)"
    )
    message = (
        f"The trace declares a total of {declared}, and {counted} were observed across "
        f"{page_count} pages. PageTrace does not know whether the total counts the same "
        f"population under the same filters, so this is a difference between two numbers, not "
        f"a count of records that went missing."
    )
    if duplicates:
        message += (
            " Some items appear on more than one page, which changes what the total should be "
            "compared against."
        )
    elif not exact:
        message += " Some items had no observable identity, so they could not be deduplicated."
    return message
