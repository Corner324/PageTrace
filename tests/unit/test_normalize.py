"""Normalization: presets, URL canonicalization, fingerprints, Link headers."""

from __future__ import annotations

import pytest
from tests.factories import raw

from pagetrace.errors import PageTraceError
from pagetrace.model import ObservationStatus
from pagetrace.normalize import (
    PRESET_DEFAULTS,
    PRESETS,
    SelectorSet,
    build_trace,
    canonical_url,
    filter_requests,
    fingerprint,
    link_next,
    normalize,
)


def test_every_preset_has_defaults() -> None:
    assert set(PRESET_DEFAULTS) == set(PRESETS)


def test_cursor_preset_reads_query_and_body() -> None:
    selectors = SelectorSet.build("cursor", {})
    page = normalize(raw(body={"next_cursor": "def", "items": [{"id": 1}]}), selectors, "cursor")

    assert page.request_cursor.value == "abc"
    assert page.next_cursor.value == "def"
    assert page.items.count == 1
    assert page.ok


def test_flags_override_preset_defaults() -> None:
    selectors = SelectorSet.build("cursor", {"next": "$.paging.after"})
    page = normalize(raw(body={"paging": {"after": "zzz"}}), selectors, "cursor")
    assert page.next_cursor.value == "zzz"


def test_a_default_that_does_not_match_proves_nothing() -> None:
    """A preset default is a convenience, never an assumption a finding may rest on."""
    page = normalize(
        raw(body={"paging": {"after": "zzz"}}), SelectorSet.build("cursor", {}), "cursor"
    )
    assert page.next_cursor.status is ObservationStatus.NOT_FOUND


def test_invalid_override_is_a_usage_error() -> None:
    with pytest.raises(PageTraceError, match="--next"):
        SelectorSet.build("cursor", {"next": "$.[[bad"})


def test_link_preset_uses_url_and_link_header() -> None:
    headers = {"link": '<https://api.example/items?cursor=def>; rel="next"'}
    page = normalize(raw(headers=headers), SelectorSet.build("link", {}), "link")

    assert page.request_cursor.value == "https://api.example/items?cursor=abc"
    assert page.next_cursor.value == "https://api.example/items?cursor=def"


def test_link_header_without_rel_next_declares_termination() -> None:
    """A last page says so by omitting rel=next; that is an observation, not an absence."""
    observation = link_next({"link": '<https://api.example/items>; rel="prev"'})
    assert observation.observed
    assert observation.is_null


def test_absent_link_header_is_not_observed() -> None:
    assert link_next({}).status is ObservationStatus.NOT_FOUND


def test_link_header_with_several_relations() -> None:
    header = '<https://a.example/p1>; rel="prev", <https://a.example/p3>; rel="next"'
    assert link_next({"link": header}).value == "https://a.example/p3"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("HTTPS://API.Example/Items?b=2&a=1", "https://api.example/Items?a=1&b=2"),
        ("https://api.example:443/x", "https://api.example/x"),
        ("http://api.example:80/x", "http://api.example/x"),
        ("https://api.example:8443/x", "https://api.example:8443/x"),
        ("https://api.example/x#frag", "https://api.example/x"),
    ],
)
def test_canonical_url(url: str, expected: str) -> None:
    assert canonical_url(url) == expected


def test_parameter_order_is_not_a_mismatch() -> None:
    """Two URLs differing only in parameter order address the same page."""
    assert canonical_url("https://a.example/i?x=1&y=2") == canonical_url(
        "https://a.example/i?y=2&x=1"
    )


def test_fingerprint_ignores_key_order_only() -> None:
    assert fingerprint({"a": 1, "b": 2}) == fingerprint({"b": 2, "a": 1})
    assert fingerprint({"a": 1}) != fingerprint({"a": 2})
    assert fingerprint([1, 2]) != fingerprint([2, 1])
    assert fingerprint(None) is None


def test_non_2xx_pages_are_marked_not_ok() -> None:
    page = normalize(
        raw(status=500, body={"error": "x"}), SelectorSet.build("cursor", {}), "cursor"
    )
    assert not page.ok


def test_filter_requests_reindexes() -> None:
    raws = [
        raw(index=0, url="https://cdn.example/logo.png"),
        raw(index=1, url="https://api.example/items?cursor=a"),
        raw(index=2, url="https://api.example/items?cursor=b"),
    ]
    kept = filter_requests(raws, "api.example/items")

    assert [r.index for r in kept] == [0, 1]
    assert [r.url for r in kept] == [raws[1].url, raws[2].url]


def test_filter_requests_without_a_filter_keeps_order() -> None:
    raws = [raw(index=0), raw(index=1)]
    assert [r.index for r in filter_requests(raws, None)] == [0, 1]


def test_item_identities_carry_the_filtered_page_index() -> None:
    raws = filter_requests(
        [
            raw(index=0, url="https://cdn.example/x.png"),
            raw(index=1, body={"items": [{"id": 9}]}),
        ],
        "api.example",
    )
    trace = build_trace(raws, SelectorSet.build("cursor", {}), "cursor", "jsonl")

    assert trace.page_count == 1
    assert trace.pages[0].items.identities[0].path == "page[0].items[0].id"


def test_build_trace_preserves_order() -> None:
    raws = [raw(index=i, url=f"https://api.example/i?cursor={i}") for i in range(3)]
    trace = build_trace(raws, SelectorSet.build("cursor", {}), "cursor", "jsonl")
    assert [p.request_cursor.value for p in trace.pages] == ["0", "1", "2"]


def test_normalization_is_deterministic() -> None:
    raws = [raw(index=0, body={"items": [{"id": 1}], "next_cursor": "x"})]
    selectors = SelectorSet.build("cursor", {})
    assert build_trace(raws, selectors, "cursor", "jsonl") == build_trace(
        raws, selectors, "cursor", "jsonl"
    )
