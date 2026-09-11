"""Cursor detectors. Specification: INV-CURSOR-001..003 in specs/invariants.md."""

from __future__ import annotations

from collections.abc import Iterator

from pagetrace.checks.base import insufficient, transitions
from pagetrace.model import Certainty, Finding, Severity, Trace

CURSOR_PRESETS = frozenset({"cursor", "link"})


def check_cursor_continuation(trace: Trace) -> Iterator[Finding]:
    """INV-CURSOR-001: a page was requested with a token the previous page did not return."""
    if trace.preset not in CURSOR_PRESETS:
        return

    unobserved = 0
    for earlier, later in transitions(trace):
        offered = earlier.next_cursor
        used = later.request_cursor

        if not offered.observed or not used.observed:
            unobserved += 1
            continue
        if offered.is_empty:
            # The server declared termination. That the client kept going is a different fact,
            # and INV-CURSOR-002 or INV-TRACE-001 owns it.
            continue
        if used.same_as(earlier.request_cursor):
            # The client repeated the previous request. One observation, one finding:
            # INV-CURSOR-002 reports it.
            continue
        if offered.same_as(used):
            continue

        yield Finding(
            code="CURSOR_CONTINUATION_MISMATCH",
            invariant="INV-CURSOR-001",
            certainty=Certainty.PROVEN,
            severity=Severity.ERROR,
            message=(
                f"Page {later.index} was requested with a continuation token that page "
                f"{earlier.index} did not return."
            ),
            affected_pages=(earlier.index, later.index),
            evidence=(earlier.evidence(offered), later.evidence(used)),
        )

    if unobserved:
        yield insufficient(
            code="CURSOR_CONTINUATION_NOT_OBSERVABLE",
            invariant="INV-CURSOR-001",
            message=(
                f"{unobserved} of {max(trace.page_count - 1, 0)} transitions could not be "
                f"checked for a continuation mismatch: the returned or the requested cursor "
                f"was not observable. Check --next and --cursor."
            ),
        )
