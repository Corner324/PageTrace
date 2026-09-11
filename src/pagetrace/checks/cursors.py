"""Cursor detectors. Specification: INV-CURSOR-001..003 in specs/invariants.md."""

from __future__ import annotations

from collections.abc import Iterator

from pagetrace.checks.base import insufficient, transitions
from pagetrace.model import Certainty, Finding, Severity, Trace

CURSOR_PRESETS = frozenset({"cursor", "link"})

# How many intermediate cursors a cycle finding carries as evidence before it stops being
# evidence and starts being a dump.
MAX_CYCLE_EVIDENCE = 5


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


def check_cursor_stalled(trace: Trace) -> Iterator[Finding]:
    """INV-CURSOR-002: the same pagination state was requested twice in a row."""
    if trace.preset not in CURSOR_PRESETS:
        return

    for earlier, later in transitions(trace):
        if not earlier.request_cursor.same_as(later.request_cursor):
            continue

        evidence = [earlier.evidence(earlier.request_cursor), later.evidence(later.request_cursor)]
        if earlier.next_cursor.observed:
            evidence.insert(1, earlier.evidence(earlier.next_cursor))

        yield Finding(
            code="CURSOR_STALLED",
            invariant="INV-CURSOR-002",
            certainty=Certainty.PROVEN,
            severity=Severity.ERROR,
            message=(
                f"Pages {earlier.index} and {later.index} were requested with the same "
                f"pagination state; the recorded sequence did not advance."
            ),
            affected_pages=(earlier.index, later.index),
            evidence=tuple(evidence),
        )
        # Later repeats of the same value follow from this one; they are not new facts.
        return


def check_cursor_cycle(trace: Trace) -> Iterator[Finding]:
    """INV-CURSOR-003: the request cursor returned to a state it had already visited."""
    if trace.preset not in CURSOR_PRESETS:
        return

    first_seen: dict[str, int] = {}
    for page in trace.pages:
        if not page.ok:
            continue
        text = page.request_cursor.text
        if text is None:
            continue

        start = first_seen.get(text)
        if start is None:
            first_seen[text] = page.index
            continue
        if page.index - start == 1:
            # A cycle of length one is a stall, and INV-CURSOR-002 reports it.
            continue

        yield _cycle_finding(trace, start, page.index)
        return


def _cycle_finding(trace: Trace, start: int, repeat: int) -> Finding:
    """Build the cycle finding, downgrading where the trace admits another explanation."""
    pages = trace.pages
    entry, again = pages[start], pages[repeat]
    length = repeat - start

    retried = any(not pages[index].ok for index in range(start, repeat + 1))
    previous = pages[repeat - 1]
    concatenated_runs = start == 0 and (
        previous.next_cursor.is_empty or not previous.next_cursor.observed
    )

    if retried:
        certainty = Certainty.SUSPICIOUS
        note = (
            " A failed request inside the range means the client may simply have retried, "
            "which is ordinary behavior."
        )
    elif concatenated_runs:
        certainty = Certainty.SUSPICIOUS
        note = (
            f" Page {previous.index} declared no continuation, so this file may hold two "
            f"pagination runs one after another rather than a cycle."
        )
    else:
        certainty = Certainty.PROVEN
        note = ""

    middle = tuple(
        pages[index].evidence(pages[index].request_cursor)
        for index in range(start + 1, min(repeat, start + 1 + MAX_CYCLE_EVIDENCE))
        if pages[index].request_cursor.observed
    )

    return Finding(
        code="CURSOR_CYCLE",
        invariant="INV-CURSOR-003",
        certainty=certainty,
        severity=Severity.ERROR,
        message=(
            f"The request cursor used on page {start} was used again on page {repeat}, so the "
            f"recorded sequence revisits a state after {length} pages. Whether pagination would "
            f"continue forever cannot be told from a finite trace.{note}"
        ),
        affected_pages=(start, repeat),
        evidence=(
            entry.evidence(entry.request_cursor),
            *middle,
            again.evidence(again.request_cursor),
        ),
    )
