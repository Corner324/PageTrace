"""Shared helpers for detectors. Importing this never pulls in a detector, so there is no cycle."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator

from pagetrace.model import Certainty, Evidence, Finding, Page, Severity, Trace

Check = Callable[[Trace], Iterable[Finding]]


def transitions(trace: Trace) -> Iterator[tuple[Page, Page]]:
    """Consecutive page pairs. A pair touching a non-2xx page is not yielded.

    Global precondition 4 of specs/invariants.md: an error response body is not a page of
    results, and a retry after one is ordinary client behavior.
    """
    for earlier, later in zip(trace.pages, trace.pages[1:], strict=False):
        if earlier.ok and later.ok:
            yield earlier, later


def last_ok_page(trace: Trace) -> Page | None:
    """The final 2xx page. Whole-trace checks reason about this, not about an error page."""
    for candidate in reversed(trace.pages):
        if candidate.ok:
            return candidate
    return None


def insufficient(
    code: str,
    invariant: str,
    message: str,
    evidence: tuple[Evidence, ...] = (),
) -> Finding:
    """One summary per detector per trace, instead of per-page noise (global precondition 5)."""
    return Finding(
        code=code,
        invariant=invariant,
        certainty=Certainty.INSUFFICIENT_EVIDENCE,
        severity=Severity.INFO,
        message=message,
        affected_pages=(),
        evidence=evidence,
    )
