"""The invariant engine.

A check is a pure function from a trace to findings. The registry is a tuple, not a plugin
system: order is fixed, so adding a detector is one import and one line.
"""

from __future__ import annotations

from pagetrace.checks.base import Check
from pagetrace.checks.continuation import (
    check_empty_page_with_has_more,
    check_trace_ends_with_continuation,
    check_trace_ends_with_has_more,
)
from pagetrace.checks.cursors import (
    check_cursor_continuation,
    check_cursor_cycle,
    check_cursor_stalled,
)
from pagetrace.checks.items import check_duplicate_items
from pagetrace.checks.sequence import (
    check_identical_responses,
    check_offset_progression,
    check_page_progression,
)
from pagetrace.checks.totals import check_total_discrepancy
from pagetrace.model import Finding, Trace, sort_findings

# A diff of this tuple is the complete list of what PageTrace can say.
CHECKS: tuple[Check, ...] = (
    check_cursor_continuation,
    check_cursor_stalled,
    check_cursor_cycle,
    check_duplicate_items,
    check_identical_responses,
    check_page_progression,
    check_offset_progression,
    check_trace_ends_with_has_more,
    check_empty_page_with_has_more,
    check_trace_ends_with_continuation,
    check_total_discrepancy,
)


# Every invariant the registry above can report on, in specification order. Kept explicit so a
# renderer can say "this invariant was checked and found nothing", and so a test can compare the
# list against specs/invariants.md instead of trusting that the two stayed in step.
INVARIANT_IDS: tuple[str, ...] = (
    "INV-CURSOR-001",
    "INV-CURSOR-002",
    "INV-CURSOR-003",
    "INV-ITEM-001",
    "INV-RESP-001",
    "INV-PAGE-001",
    "INV-OFFSET-001",
    "INV-CONT-001",
    "INV-CONT-002",
    "INV-TRACE-001",
    "INV-TOTAL-001",
)


def run_checks(trace: Trace) -> list[Finding]:
    """Run every registered check. Same trace in, same findings in the same order out."""
    findings = [finding for check in CHECKS for finding in check(trace)]
    return sort_findings(findings)
