"""JSONL v1 reader: the trust boundary. Every bad input is a message, never a traceback."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pagetrace.errors import PageTraceError
from pagetrace.inputs import detect_format, filter_headers, read_trace
from pagetrace.inputs.jsonl import read_jsonl

VALID: dict[str, Any] = {
    "v": 1,
    "seq": 0,
    "request": {"method": "GET", "url": "https://api.example/items?cursor=abc"},
    "response": {"status": 200, "body": {"items": [{"id": 1}], "next": "def"}},
}


def write(tmp_path: Path, *records: Any, name: str = "trace.jsonl") -> Path:
    path = tmp_path / name
    path.write_text(
        "\n".join(json.dumps(r) if not isinstance(r, str) else r for r in records),
        encoding="utf-8",
    )
    return path


def read(tmp_path: Path, *records: Any) -> list[Any]:
    return list(read_jsonl(write(tmp_path, *records)))


def test_reads_a_minimal_record(tmp_path: Path) -> None:
    (observation,) = read_jsonl(write(tmp_path, VALID))
    assert observation.index == 0
    assert observation.status == 200
    assert observation.url.endswith("cursor=abc")
    assert observation.body == {"items": [{"id": 1}], "next": "def"}
    assert observation.body_present


def test_query_is_parsed_from_the_url(tmp_path: Path) -> None:
    (observation,) = read_jsonl(write(tmp_path, VALID))
    assert observation.query == {"cursor": "abc"}
    assert observation.request_context["query"] == {"cursor": "abc"}


def test_explicit_query_wins_over_the_url(tmp_path: Path) -> None:
    record = {**VALID, "request": {**VALID["request"], "query": {"cursor": "explicit"}}}
    (observation,) = read_jsonl(write(tmp_path, record))
    assert observation.query == {"cursor": "explicit"}


def test_repeated_query_parameter_becomes_a_list(tmp_path: Path) -> None:
    """Two values for one parameter is ambiguity, and must surface as such, not as a pick."""
    record = {**VALID, "request": {"url": "https://api.example/i?cursor=a&cursor=b"}}
    (observation,) = read_jsonl(write(tmp_path, record))
    assert observation.query == {"cursor": ["a", "b"]}


def test_blank_lines_are_skipped(tmp_path: Path) -> None:
    assert len(read(tmp_path, VALID, "", {**VALID, "seq": 1}, "   ")) == 2


def test_request_headers_never_reach_the_model(tmp_path: Path) -> None:
    record = {
        **VALID,
        "request": {**VALID["request"], "headers": {"authorization": "Bearer secret"}},
    }
    (observation,) = read_jsonl(write(tmp_path, record))
    assert "secret" not in repr(observation)


def test_response_headers_are_allowlisted(tmp_path: Path) -> None:
    record = {
        **VALID,
        "response": {
            **VALID["response"],
            "headers": {
                "Authorization": "Bearer secret",
                "Set-Cookie": "session=abc",
                "Link": '<https://api.example/i?c=2>; rel="next"',
                "X-Custom": "whatever",
            },
        },
    }
    (observation,) = read_jsonl(write(tmp_path, record))
    assert set(observation.headers) == {"link"}
    assert "secret" not in repr(observation)
    assert "session=abc" not in repr(observation)


def test_filter_headers_ignores_odd_shapes() -> None:
    assert filter_headers(None) == {}
    assert filter_headers(["link"]) == {}
    assert filter_headers({"link": 5, 7: "x", "Content-Type": "application/json"}) == {
        "content-type": "application/json"
    }


@pytest.mark.parametrize(
    ("record", "message"),
    [
        ({**VALID, "v": 2}, "unsupported record version"),
        ({**VALID, "v": None}, "unsupported record version"),
        ({"request": {}, "response": {}}, "unsupported record version"),
        ({**VALID, "request": "no"}, "request must be a JSON object"),
        ({**VALID, "response": []}, "response must be a JSON object"),
        ({**VALID, "request": {"url": 5}}, "request.url must be a string"),
        ({**VALID, "response": {"body": {}}}, "response.status is required"),
        ({**VALID, "response": {"status": "200"}}, "response.status is required"),
        ({**VALID, "response": {"status": True}}, "response.status is required"),
        ({**VALID, "seq": "1"}, "seq must be an integer"),
    ],
)
def test_malformed_records_are_usage_errors(tmp_path: Path, record: Any, message: str) -> None:
    with pytest.raises(PageTraceError, match=message):
        read(tmp_path, record)


def test_seq_must_increase(tmp_path: Path) -> None:
    with pytest.raises(PageTraceError, match="not greater than the previous seq"):
        read(tmp_path, VALID, {**VALID, "seq": 0})


def test_seq_may_be_omitted(tmp_path: Path) -> None:
    record: dict[str, Any] = {k: v for k, v in VALID.items() if k != "seq"}
    assert len(read(tmp_path, record, record)) == 2


def test_invalid_json_names_the_line(tmp_path: Path) -> None:
    with pytest.raises(PageTraceError, match="line 2: invalid JSON"):
        read(tmp_path, VALID, "{not json")


def test_non_object_line(tmp_path: Path) -> None:
    with pytest.raises(PageTraceError, match="line 1: expected a JSON object"):
        read(tmp_path, [1, 2, 3])


def test_invalid_utf8_is_a_usage_error(tmp_path: Path) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_bytes(b'{"v": 1, "x": "\xff\xfe"}\n')
    with pytest.raises(PageTraceError, match="not valid UTF-8"):
        list(read_jsonl(path))


def test_oversized_line_is_refused_by_the_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("pagetrace.inputs.jsonl.MAX_LINE_BYTES", 32)
    with pytest.raises(PageTraceError, match="longer than the 32 byte limit"):
        read(tmp_path, VALID)


def test_empty_file_is_a_usage_error(tmp_path: Path) -> None:
    path = tmp_path / "empty.jsonl"
    path.write_text("", encoding="utf-8")
    with pytest.raises(PageTraceError, match="no trace records found"):
        list(read_jsonl(path))


def test_missing_file_is_a_usage_error(tmp_path: Path) -> None:
    with pytest.raises(PageTraceError, match="cannot read"):
        list(read_jsonl(tmp_path / "nope.jsonl"))


def test_deeply_nested_json_is_a_usage_error(tmp_path: Path) -> None:
    """A nesting bomb must not reach the core as a RecursionError."""
    depth = 200_000
    path = tmp_path / "deep.jsonl"
    path.write_text('{"v": 1, "x": ' + "[" * depth + "]" * depth + "}", encoding="utf-8")
    with pytest.raises(PageTraceError, match="nested too deeply"):
        list(read_jsonl(path))


def test_format_detection(tmp_path: Path) -> None:
    assert detect_format(Path("t.jsonl")) == "jsonl"
    assert detect_format(Path("t.ndjson")) == "jsonl"
    assert detect_format(Path("t.har")) == "har"
    with pytest.raises(PageTraceError, match="cannot tell the format"):
        detect_format(Path("t.txt"))


def test_read_trace_honours_an_explicit_format(tmp_path: Path) -> None:
    path = write(tmp_path, VALID, name="trace.txt")
    assert len(read_trace(path, "jsonl")) == 1


def test_read_trace_dispatches_to_the_har_reader(tmp_path: Path) -> None:
    path = tmp_path / "t.har"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(PageTraceError, match="no HAR log object"):
        read_trace(path, "auto")
