"""HAR reader: the second trust boundary, and the one most likely to hold real credentials."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import pytest

from pagetrace.errors import PageTraceError
from pagetrace.inputs.har import read_har


def entry(
    url: str = "https://api.example/items?cursor=abc",
    status: int = 200,
    body: Any = None,
    headers: list[dict[str, str]] | None = None,
    request_headers: list[dict[str, str]] | None = None,
    encoding: str | None = None,
    text: str | None = None,
) -> dict[str, Any]:
    content: dict[str, Any] = {"mimeType": "application/json"}
    if text is not None:
        content["text"] = text
    elif body is not None:
        content["text"] = json.dumps(body)
    if encoding is not None:
        content["encoding"] = encoding

    return {
        "request": {
            "method": "GET",
            "url": url,
            "queryString": [{"name": "cursor", "value": "abc"}],
            "headers": request_headers or [],
        },
        "response": {"status": status, "headers": headers or [], "content": content},
    }


def write(tmp_path: Path, *entries: Any, wrap: bool = True) -> Path:
    path = tmp_path / "trace.har"
    document = {"log": {"version": "1.2", "entries": list(entries)}} if wrap else entries[0]
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_reads_an_entry(tmp_path: Path) -> None:
    (observation,) = read_har(write(tmp_path, entry(body={"items": [], "next_cursor": "d"})))

    assert observation.index == 0
    assert observation.status == 200
    assert observation.body == {"items": [], "next_cursor": "d"}
    assert observation.body_present


def test_query_comes_from_the_recorded_query_string(tmp_path: Path) -> None:
    (observation,) = read_har(write(tmp_path, entry()))
    assert observation.query == {"cursor": "abc"}


def test_query_falls_back_to_the_url(tmp_path: Path) -> None:
    record = entry(url="https://api.example/i?page=2")
    del record["request"]["queryString"]
    (observation,) = read_har(write(tmp_path, record))
    assert observation.query == {"page": "2"}


def test_a_repeated_query_parameter_becomes_a_list(tmp_path: Path) -> None:
    record = entry()
    record["request"]["queryString"] = [
        {"name": "cursor", "value": "a"},
        {"name": "cursor", "value": "b"},
    ]
    (observation,) = read_har(write(tmp_path, record))
    assert observation.query == {"cursor": ["a", "b"]}


def test_credentials_never_reach_the_model(tmp_path: Path) -> None:
    """A HAR is exactly where an Authorization header is expected to be."""
    record = entry(
        request_headers=[{"name": "Authorization", "value": "Bearer SUPERSECRET"}],
        headers=[
            {"name": "Set-Cookie", "value": "session=SUPERSECRET"},
            {"name": "Link", "value": '<https://api.example/i?c=2>; rel="next"'},
        ],
    )
    (observation,) = read_har(write(tmp_path, record))

    assert set(observation.headers) == {"link"}
    assert "SUPERSECRET" not in repr(observation)


def test_base64_content_is_decoded(tmp_path: Path) -> None:
    payload = json.dumps({"items": [{"id": 1}]})
    encoded = base64.b64encode(payload.encode("utf-8")).decode("ascii")
    (observation,) = read_har(write(tmp_path, entry(encoding="base64", text=encoded)))

    assert observation.body == {"items": [{"id": 1}]}


def test_invalid_base64_is_a_usage_error(tmp_path: Path) -> None:
    with pytest.raises(PageTraceError, match="invalid base64"):
        list(read_har(write(tmp_path, entry(encoding="base64", text="not base64 !!"))))


def test_a_base64_bomb_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pagetrace.inputs.har.MAX_BODY_BYTES", 64)
    encoded = base64.b64encode(b"x" * 4096).decode("ascii")
    with pytest.raises(PageTraceError, match="larger than the 64 byte limit"):
        list(read_har(write(tmp_path, entry(encoding="base64", text=encoded))))


def test_an_oversized_plain_body_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("pagetrace.inputs.har.MAX_BODY_BYTES", 64)
    with pytest.raises(PageTraceError, match="larger than the 64 byte limit"):
        list(read_har(write(tmp_path, entry(text="y" * 4096))))


def test_a_non_json_body_is_present_but_carries_no_observations(tmp_path: Path) -> None:
    (observation,) = read_har(write(tmp_path, entry(text="<html>not json</html>")))

    assert observation.body is None
    assert observation.body_present


def test_an_entry_without_content_has_no_body(tmp_path: Path) -> None:
    record = entry()
    del record["response"]["content"]
    (observation,) = read_har(write(tmp_path, record))

    assert observation.body is None
    assert not observation.body_present


MALFORMED: list[tuple[Any, str]] = [
    ({"notlog": {}}, "no HAR log object"),
    ({"log": {}}, r"log\.entries is missing"),
    ({"log": {"entries": {}}}, r"log\.entries is missing"),
    ({"log": {"entries": []}}, "no entries found"),
    ({"log": {"entries": ["nope"]}}, "entry 0 is not an object"),
    ({"log": {"entries": [{"response": {}}]}}, "entry 0 has no request object"),
    ({"log": {"entries": [{"request": {}}]}}, "entry 0 has no response object"),
]


@pytest.mark.parametrize(("document", "message"), MALFORMED)
def test_malformed_documents_are_usage_errors(tmp_path: Path, document: Any, message: str) -> None:
    path = tmp_path / "bad.har"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(PageTraceError, match=message):
        list(read_har(path))


def test_a_missing_url_is_a_usage_error(tmp_path: Path) -> None:
    record = entry()
    del record["request"]["url"]
    with pytest.raises(PageTraceError, match=r"no request\.url"):
        list(read_har(write(tmp_path, record)))


def test_a_missing_status_is_a_usage_error(tmp_path: Path) -> None:
    record = entry()
    del record["response"]["status"]
    with pytest.raises(PageTraceError, match=r"no integer response\.status"):
        list(read_har(write(tmp_path, record)))


def test_invalid_json_is_a_usage_error(tmp_path: Path) -> None:
    path = tmp_path / "bad.har"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(PageTraceError, match="invalid JSON"):
        list(read_har(path))


def test_a_top_level_array_is_a_usage_error(tmp_path: Path) -> None:
    path = tmp_path / "bad.har"
    path.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(PageTraceError, match="expected a JSON object"):
        list(read_har(path))


def test_a_missing_file_is_a_usage_error(tmp_path: Path) -> None:
    with pytest.raises(PageTraceError, match="cannot read"):
        list(read_har(tmp_path / "nope.har"))


def test_deeply_nested_json_is_a_usage_error(tmp_path: Path) -> None:
    path = tmp_path / "deep.har"
    depth = 200_000
    path.write_text('{"log": ' + "[" * depth + "]" * depth + "}", encoding="utf-8")
    with pytest.raises(PageTraceError, match="nested too deeply"):
        list(read_har(path))
