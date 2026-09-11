"""Sequence detectors: INV-PAGE-001, INV-OFFSET-001, INV-RESP-001."""

from __future__ import annotations

from collections.abc import Iterator

from pagetrace.checks.base import insufficient, transitions
from pagetrace.checks.cursors import CURSOR_PRESETS
from pagetrace.model import Certainty, Evidence, Finding, Page, Severity, Trace


def check_page_progression(trace: Trace) -> Iterator[Finding]:
    """INV-PAGE-001: the requested page number did not advance by exactly one.

    Only the delta is used, so a 0-based API and a 1-based API are both handled without
    assuming which one this is.
    """
    if trace.preset != "page":
        return

    unobserved = 0
    jump: Finding | None = None
    for earlier, later in transitions(trace):
        before, after = earlier.page_number.int_value, later.page_number.int_value
        if before is None or after is None:
            unobserved += 1
            continue
        delta = after - before
        if delta == 1 or jump is not None:
            continue

        jump = Finding(
            code="PAGE_NUMBER_JUMP",
            invariant="INV-PAGE-001",
            certainty=Certainty.PROVEN,
            severity=Severity.ERROR,
            message=(
                f"The requested page number went from {before} on page {earlier.index} to "
                f"{after} on page {later.index}, a change of {delta} instead of 1."
            ),
            affected_pages=(earlier.index, later.index),
            evidence=(
                earlier.evidence(earlier.page_number),
                later.evidence(later.page_number),
                Evidence("trace.page_number_delta", delta),
            ),
        )

    if jump is not None:
        yield jump

    if unobserved:
        yield insufficient(
            code="PAGE_NUMBER_NOT_OBSERVABLE",
            invariant="INV-PAGE-001",
            message=(
                f"{unobserved} transitions had no observable integer page number and were not "
                f"checked. Check --page."
            ),
        )


def check_offset_progression(trace: Trace) -> Iterator[Finding]:
    """INV-OFFSET-001: the offset did not advance by the number of items returned.

    The offset-plus-count contract is not assumed. One transition in the trace has to satisfy
    it first; only then is a later violation proven rather than suspected. Some APIs offset by
    something other than items, and PageTrace cannot see the difference.
    """
    if trace.preset != "offset":
        return

    contract_seen = False
    violation: tuple[Page, Page, int, int, int, bool] | None = None
    unobserved = 0

    for earlier, later in transitions(trace):
        before, after = earlier.offset.int_value, later.offset.int_value
        count = earlier.items.count if earlier.items.observed else None
        if before is None or after is None or count is None:
            unobserved += 1
            continue

        expected = before + count
        if after == expected:
            contract_seen = True
        elif violation is None:
            # The witness has to come first. A transition that follows the violation shows the
            # contract held later, not that it was established when the violation happened,
            # and INV-OFFSET-001 says "at least one earlier transition".
            violation = (earlier, later, before, after, expected, contract_seen)

    if violation is not None:
        earlier, later, before, after, expected, proven = violation
        yield Finding(
            code="OFFSET_JUMP",
            invariant="INV-OFFSET-001",
            certainty=Certainty.PROVEN if proven else Certainty.SUSPICIOUS,
            severity=Severity.ERROR,
            message=(
                f"Page {later.index} was requested with offset {after}; page {earlier.index} "
                f"started at {before} and returned {expected - before} items, so {expected} "
                f"was expected."
                + (
                    ""
                    if proven
                    else " No earlier transition in this trace followed offset plus item count, "
                    "so that contract is an assumption here rather than an observation."
                )
            ),
            affected_pages=(earlier.index, later.index),
            evidence=(
                earlier.evidence(earlier.offset),
                earlier.item_count_evidence,
                later.evidence(later.offset),
                Evidence("trace.expected_offset", expected),
            ),
        )

    if unobserved:
        yield insufficient(
            code="OFFSET_NOT_OBSERVABLE",
            invariant="INV-OFFSET-001",
            message=(
                f"{unobserved} transitions had no observable offset or item count and were not "
                f"checked. Check --offset and --items."
            ),
        )


def check_identical_responses(trace: Trace) -> Iterator[Finding]:
    """INV-RESP-001: two consecutive pages returned identical bodies.

    Never more than suspicious: identical bodies are equally consistent with a stuck paginator,
    a cache, and a resource that genuinely did not change.
    """
    run_continues_at = -1
    for earlier, later in transitions(trace):
        identical = earlier.fingerprint is not None and earlier.fingerprint == later.fingerprint
        if not identical:
            continue
        if earlier.index == run_continues_at:
            # A run of identical pages is one observation, not one per pair. The run is tracked
            # by page index rather than by a flag: pairs are skipped when a page in between
            # failed, and a stale flag would swallow the next run entirely.
            run_continues_at = later.index
            continue
        if _both_empty(earlier, later):
            continue
        if trace.preset in CURSOR_PRESETS and earlier.request_cursor.same_as(later.request_cursor):
            # The stall (INV-CURSOR-002) is the more specific fact about this pair.
            continue

        run_continues_at = later.index
        yield Finding(
            code="IDENTICAL_CONSECUTIVE_RESPONSES",
            invariant="INV-RESP-001",
            certainty=Certainty.SUSPICIOUS,
            severity=Severity.WARNING,
            message=(
                f"Pages {earlier.index} and {later.index} returned identical response bodies. "
                f"That is consistent with a paginator that did not advance, and equally with a "
                f"cache or an unchanged resource."
            ),
            affected_pages=(earlier.index, later.index),
            evidence=(
                Evidence(f"page[{earlier.index}].response.fingerprint", earlier.fingerprint),
                Evidence(f"page[{later.index}].response.fingerprint", later.fingerprint),
            ),
        )


def _both_empty(earlier: Page, later: Page) -> bool:
    """Trailing empty pages are common and prove nothing."""
    return (
        earlier.items.observed
        and later.items.observed
        and earlier.items.count == 0
        and later.items.count == 0
    )
