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
from pagetrace.model import Finding, Trace, sort_findings

# A diff of this tuple is the complete list of what PageTrace can say.
CHECKS: tuple[Check, ...] = (
    check_cursor_continuation,
    check_cursor_stalled,
    check_cursor_cycle,
    check_duplicate_items,
    check_trace_ends_with_has_more,
    check_empty_page_with_has_more,
    check_trace_ends_with_continuation,
)


def run_checks(trace: Trace) -> list[Finding]:
    """Run every registered check. Same trace in, same findings in the same order out."""
    findings = [finding for check in CHECKS for finding in check(trace)]
    return sort_findings(findings)
