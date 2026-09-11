"""Differential test: the single-name fast path must answer exactly like the JSONPath engine.

An optimization is allowed to be faster. It is not allowed to be different. The reference here
is the compiled RFC 9535 query, and the two are compared on generated documents rather than on
the handful of shapes a person would think to write down.
"""

from __future__ import annotations

from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pagetrace.selectors import Selector, select_scalar, single_name

NAMES = st.sampled_from(["id", "next", "_x", "a1", "total", "missing"])

json_values = st.recursive(
    st.none() | st.booleans() | st.integers() | st.text(max_size=8),
    lambda children: st.lists(children, max_size=3) | st.dictionaries(NAMES, children, max_size=4),
    max_leaves=8,
)


def reference(expression: str, data: object) -> list[Any]:
    """The engine's answer, with the fast path switched off."""
    selector = Selector.compile("--id", expression)
    slow = Selector(
        flag=selector.flag, expression=selector.expression, query=selector.query, field=None
    )
    return [match.value for match in slow.query.finditer(data)]  # pyright: ignore[reportArgumentType]


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("$.id", "id"),
        ("$['id']", "id"),
        ("  $.id  ", "id"),
        ("$['with space']", "with space"),
        ("$.a.b", None),
        ("$.items[*].id", None),
        ("$[0]", None),
        ("$", None),
        ("$..id", None),
        (r"$['it\'s']", None),
    ],
)
def test_which_expressions_take_the_fast_path(expression: str, expected: str | None) -> None:
    assert single_name(expression) == expected


@given(NAMES, json_values)
def test_the_fast_path_agrees_with_the_engine(name: str, document: object) -> None:
    expression = f"$.{name}"
    fast = select_scalar(Selector.compile("--id", expression), document, "p")
    slow = reference(expression, document)

    if len(slow) == 1 and (slow[0] is None or isinstance(slow[0], str | int | float | bool)):
        assert fast.observed
        assert fast.value == slow[0]
    else:
        assert not fast.observed


@given(NAMES, json_values)
def test_the_bracket_form_agrees_too(name: str, document: object) -> None:
    dotted = select_scalar(Selector.compile("--id", f"$.{name}"), document, "p")
    bracketed = select_scalar(Selector.compile("--id", f"$['{name}']"), document, "p")

    assert dotted == bracketed


@given(json_values)
def test_a_key_holding_null_is_still_an_observation(document: object) -> None:
    """The fast path must not turn "present and null" into "absent"."""
    if not isinstance(document, dict):
        return
    with_null: dict[str, Any] = {**document, "id": None}
    observation = select_scalar(Selector.compile("--id", "$.id"), with_null, "p")

    assert observation.observed
    assert observation.is_null


@given(json_values)
def test_a_compound_expression_still_uses_the_engine(document: object) -> None:
    selector = Selector.compile("--id", "$.a.id")
    assert selector.field is None
    expected = reference("$.a.id", document)
    observation = select_scalar(selector, document, "p")

    assert observation.observed == (
        len(expected) == 1 and (expected[0] is None or not isinstance(expected[0], list | dict))
    )
