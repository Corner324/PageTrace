"""Item identity detectors. Specification: INV-ITEM-001 in specs/invariants.md."""

from __future__ import annotations

from collections.abc import Iterator

from pagetrace.checks.base import insufficient
from pagetrace.model import Certainty, Evidence, Finding, ItemIdentity, Severity, Trace


def check_duplicate_items(trace: Trace) -> Iterator[Finding]:
    """INV-ITEM-001: the same item identity was observed on more than one page.

    The duplicate is proven. What it means is not: overlapping windows can be part of an API
    contract or the result of a dataset that changed during the capture. The message says what
    was seen and names the interpretation as a possibility.
    """
    first_seen: dict[str, ItemIdentity] = {}
    unidentified = 0
    pages_with_items = 0

    for page in trace.pages:
        if not page.ok or not page.items.observed:
            continue
        pages_with_items += 1
        unidentified += page.items.unidentified

        for identity in page.items.identities:
            text = identity.text  # a property; computing it once per item matters at scale
            earlier = first_seen.get(text)
            if earlier is None:
                first_seen[text] = identity
                continue
            if earlier.page_index == identity.page_index:
                # A repeat inside one response says nothing about pagination.
                continue

            yield Finding(
                code="DUPLICATE_ITEM_ACROSS_PAGES",
                invariant="INV-ITEM-001",
                certainty=Certainty.PROVEN,
                severity=Severity.WARNING,
                message=(
                    f"Item {identity.text} was observed on page {earlier.page_index} and again "
                    f"on page {identity.page_index}. That the same item appears twice is a "
                    f"fact; whether it means overlapping pages depends on a uniqueness "
                    f"contract this trace does not contain."
                ),
                affected_pages=(earlier.page_index, identity.page_index),
                evidence=(
                    Evidence(earlier.path, earlier.value),
                    Evidence(identity.path, identity.value),
                ),
            )

    if unidentified:
        yield insufficient(
            code="ITEM_IDENTITY_NOT_OBSERVABLE",
            invariant="INV-ITEM-001",
            message=(
                f"{unidentified} items across {pages_with_items} pages had no observable "
                f"identity and were left out of the duplicate check. Check --id."
            ),
        )
