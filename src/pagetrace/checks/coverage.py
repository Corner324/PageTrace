"""What was left unchecked. Specification: INV-TRACE-002 in specs/invariants.md.

Global precondition 4 excludes non-2xx pages from every body-derived check. Excluding them
quietly and then printing "no findings" would be the same over-claim this project exists to
avoid, in the opposite direction: silence about a trace nobody could read looks exactly like
silence about a trace that was fine.
"""

from __future__ import annotations

from collections.abc import Iterator

from pagetrace.checks.base import insufficient
from pagetrace.model import Evidence, Finding, Trace


def check_excluded_requests(trace: Trace) -> Iterator[Finding]:
    """INV-TRACE-002: requests that returned no result page were left out of every check."""
    excluded = [page for page in trace.pages if not page.ok]
    if not excluded:
        return

    indexes = ", ".join(str(page.index) for page in excluded[:10])
    more = "" if len(excluded) <= 10 else f" and {len(excluded) - 10} more"

    yield insufficient(
        code="REQUESTS_EXCLUDED_FROM_ANALYSIS",
        invariant="INV-TRACE-002",
        message=(
            f"{len(excluded)} of {trace.page_count} requests did not return a 2xx response and "
            f"were left out of every check that reads a response body. Transitions touching "
            f"them were not checked at all, so silence about those pages is not a clean result. "
            f"Excluded pages: {indexes}{more}."
        ),
        evidence=tuple(
            Evidence(f"page[{page.index}].response.status", page.status) for page in excluded[:10]
        ),
    )
