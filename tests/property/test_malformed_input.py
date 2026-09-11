"""Malformed input must always be a message, never a traceback.

The parsers are the only place PageTrace meets untrusted bytes. The property here is narrow and
absolute: whatever goes in, either it parses or it raises PageTraceError, and the CLI answers
with an exit code in 0, 1, 2.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from pagetrace.cli import EXIT_OK, EXIT_USAGE, EXIT_VIOLATIONS, main
from pagetrace.errors import PageTraceError
from pagetrace.inputs.har import read_har
from pagetrace.inputs.jsonl import read_jsonl

# tmp_path is function scoped, which Hypothesis rightly complains about; one directory for the
# whole module is enough because every example overwrites the same file. Generated arguments go
# last in every signature here: Hypothesis fills parameters from the right.
NO_FIXTURE_CHECK = settings(suppress_health_check=[HealthCheck.function_scoped_fixture])

json_values = st.recursive(
    st.none()
    | st.booleans()
    | st.integers()
    | st.floats(allow_nan=False, allow_infinity=False)
    | st.text(max_size=20),
    lambda children: (
        st.lists(children, max_size=4) | st.dictionaries(st.text(max_size=8), children, max_size=4)
    ),
    max_leaves=12,
)


@pytest.fixture(scope="module")
def scratch(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("fuzz")


def write_bytes(scratch: Path, name: str, payload: bytes) -> Path:
    path = scratch / name
    path.write_bytes(payload)
    return path


def read_or_reject(reader: Any, path: Path) -> None:
    """The whole contract: a PageTraceError is fine, anything else is a bug."""
    try:
        list(reader(path))
    except PageTraceError:
        return
    except Exception as exc:
        pytest.fail(f"{type(exc).__name__} escaped the parser: {exc}")


@given(st.binary(max_size=400))
@NO_FIXTURE_CHECK
def test_arbitrary_bytes_never_escape_the_jsonl_parser(scratch: Path, payload: bytes) -> None:
    read_or_reject(read_jsonl, write_bytes(scratch, "fuzz.jsonl", payload))


@given(st.binary(max_size=400))
@NO_FIXTURE_CHECK
def test_arbitrary_bytes_never_escape_the_har_parser(scratch: Path, payload: bytes) -> None:
    read_or_reject(read_har, write_bytes(scratch, "fuzz.har", payload))


@given(json_values)
@NO_FIXTURE_CHECK
def test_well_formed_json_of_any_shape_is_handled(scratch: Path, value: object) -> None:
    payload = json.dumps(value).encode("utf-8")
    read_or_reject(read_jsonl, write_bytes(scratch, "shape.jsonl", payload))
    read_or_reject(read_har, write_bytes(scratch, "shape.har", payload))


@given(json_values, json_values, json_values)
@NO_FIXTURE_CHECK
def test_records_with_arbitrary_fields_are_handled(
    scratch: Path, request_value: object, response_value: object, body: object
) -> None:
    record = {"v": 1, "request": request_value, "response": response_value, "body": body}
    payload = json.dumps(record).encode("utf-8")
    read_or_reject(read_jsonl, write_bytes(scratch, "record.jsonl", payload))


@given(json_values)
@NO_FIXTURE_CHECK
def test_har_entries_with_arbitrary_fields_are_handled(scratch: Path, value: object) -> None:
    document = {"log": {"entries": [{"request": value, "response": value}]}}
    payload = json.dumps(document).encode("utf-8")
    read_or_reject(read_har, write_bytes(scratch, "entry.har", payload))


@given(st.text(max_size=200))
@NO_FIXTURE_CHECK
def test_arbitrary_text_bodies_are_handled(scratch: Path, text: str) -> None:
    record = {
        "v": 1,
        "request": {"url": "https://api.example/i"},
        "response": {"status": 200, "body": {"next_cursor": text, "items": [{"id": text}]}},
    }
    payload = json.dumps(record).encode("utf-8")
    read_or_reject(read_jsonl, write_bytes(scratch, "text.jsonl", payload))


@given(st.binary(max_size=400))
@NO_FIXTURE_CHECK
def test_the_cli_always_answers_with_an_exit_code(
    scratch: Path, capsys: pytest.CaptureFixture[str], payload: bytes
) -> None:
    path = write_bytes(scratch, "cli.jsonl", payload)
    exit_code = main(["check", str(path)])
    captured = capsys.readouterr()

    assert exit_code in {EXIT_OK, EXIT_VIOLATIONS, EXIT_USAGE}
    assert "Traceback" not in captured.err
    if exit_code == EXIT_USAGE:
        assert captured.err.startswith("pagetrace: ")


@given(st.text(alphabet='{}[]",:0123456789abc \n\t', max_size=120))
@NO_FIXTURE_CHECK
def test_json_like_noise_never_escapes(scratch: Path, text: str) -> None:
    path = write_bytes(scratch, "noise.jsonl", text.encode("utf-8"))
    assert main(["check", str(path)]) in {EXIT_OK, EXIT_VIOLATIONS, EXIT_USAGE}


@given(st.lists(st.sampled_from(["[", "{", "]", "}", '"', ","]), max_size=60))
@NO_FIXTURE_CHECK
def test_unbalanced_delimiters_never_escape(scratch: Path, pieces: list[str]) -> None:
    path = write_bytes(scratch, "unbalanced.har", "".join(pieces).encode("utf-8"))
    read_or_reject(read_har, path)
