"""RFC 8288 Link headers, and the three outcomes that must stay apart.

Every case here comes from a defect an adversarial review reproduced on a green test suite:
the parser used to accept a relation prefix, choke on a comma inside a quoted parameter, report
a parse failure as "the server declared the end", and leave a relative target unresolved.
"""

from __future__ import annotations

import pytest

from pagetrace.model import ObservationStatus
from pagetrace.normalize import link_next, parse_link_value, split_link_values

BASE = "https://api.example.com/v1/items?page=1"


def next_target(header: str, base: str = BASE) -> object:
    return link_next({"link": header}, base).value


def test_an_absolute_next_target() -> None:
    assert next_target('<https://api.example.com/v1/items?page=2>; rel="next"') == (
        "https://api.example.com/v1/items?page=2"
    )


def test_a_relative_target_is_resolved_against_the_request_url() -> None:
    """RFC 8288 allows a relative reference, and plenty of APIs send one."""
    assert next_target('</v1/items?page=2>; rel="next"') == (
        "https://api.example.com/v1/items?page=2"
    )


def test_a_bare_query_target_is_resolved_too() -> None:
    assert next_target('<?page=2>; rel="next"') == "https://api.example.com/v1/items?page=2"


def test_a_comma_inside_a_quoted_parameter_does_not_split_the_header() -> None:
    header = '<https://a.example/p2>; title="Q1, 2026"; rel="next"'
    assert next_target(header) == "https://a.example/p2"


def test_a_relation_is_a_whole_token_not_a_prefix() -> None:
    """RFC 5005 defines next-archive, and it is not next."""
    assert link_next({"link": '<https://a.example/p2>; rel="next-archive"'}, BASE).is_null
    assert link_next({"link": '<https://a.example/p2>; rel="nextish"'}, BASE).is_null


def test_a_space_separated_relation_list_counts() -> None:
    assert next_target('<https://a.example/p2>; rel="prev next"') == "https://a.example/p2"


def test_an_unquoted_relation_works() -> None:
    assert next_target("<https://a.example/p2>; rel=next") == "https://a.example/p2"


def test_the_relation_name_is_case_insensitive() -> None:
    assert next_target('<https://a.example/p2>; REL="NEXT"') == "https://a.example/p2"


def test_the_next_link_is_found_among_several() -> None:
    header = (
        '<https://a.example/p0>; rel="prev", '
        '<https://a.example/p9>; rel="last", '
        '<https://a.example/p2>; rel="next"'
    )
    assert next_target(header) == "https://a.example/p2"


def test_a_header_that_parses_with_no_next_declares_termination() -> None:
    observation = link_next({"link": '<https://a.example/p0>; rel="prev"'}, BASE)
    assert observation.observed
    assert observation.is_null


def test_a_header_that_does_not_parse_is_not_observed() -> None:
    """A parse failure must never read as "the server said this was the last page"."""
    for header in ["this is not a link header", "", "https://a.example/p2; rel=next", "<no close"]:
        observation = link_next({"link": header}, BASE)
        assert observation.status is ObservationStatus.NOT_FOUND, header


def test_an_absent_header_is_not_observed() -> None:
    assert link_next({}, BASE).status is ObservationStatus.NOT_FOUND


def test_credential_shaped_query_values_are_redacted() -> None:
    """A link finding quotes whole URLs, and JSON reports get pasted into tickets."""
    target = next_target('<https://a.example/p2?api_key=SECRET&cursor=abc>; rel="next"')
    assert "SECRET" not in str(target)
    assert "cursor=abc" in str(target)


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("<a>, <b>", ["<a>", "<b>"]),
        ('<a>; t="x,y", <b>', ['<a>; t="x,y"', "<b>"]),
        ("<a,b>", ["<a,b>"]),
        ('<a>; t="say \\"hi\\", ok"', ['<a>; t="say \\"hi\\", ok"']),
        ("", []),
    ],
)
def test_splitting_link_values(header: str, expected: list[str]) -> None:
    assert split_link_values(header) == expected


def test_parsing_one_value() -> None:
    assert parse_link_value('<https://a.example/p>; rel="next prev"') == (
        "https://a.example/p",
        {"next", "prev"},
    )
    assert parse_link_value("no angle brackets") is None
    assert parse_link_value("<unterminated") is None
