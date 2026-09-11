"""End to end on a HAR capture, including the Link-header preset.

A HAR is what a user actually has: every request the page made, credentials included. These
tests drive the whole pipeline the way the README tells people to.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pagetrace.cli import EXIT_OK, EXIT_USAGE, EXIT_VIOLATIONS, main


def har_entry(url: str, status: int = 200, body: Any = None, link: str | None = None) -> Any:
    headers = [{"name": "Authorization", "value": "Bearer SUPERSECRET"}]
    response_headers = [{"name": "Set-Cookie", "value": "sid=SUPERSECRET"}]
    if link is not None:
        response_headers.append({"name": "Link", "value": link})
    return {
        "request": {"method": "GET", "url": url, "headers": headers},
        "response": {
            "status": status,
            "headers": response_headers,
            "content": {"mimeType": "application/json", "text": json.dumps(body or {})},
        },
    }


def write_har(tmp_path: Path, *entries: Any) -> Path:
    path = tmp_path / "capture.har"
    document = {"log": {"version": "1.2", "creator": {"name": "test"}, "entries": list(entries)}}
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_a_clean_cursor_capture_passes(tmp_path: Path) -> None:
    path = write_har(
        tmp_path,
        har_entry("https://cdn.example/app.js", body={"not": "an api"}),
        har_entry("https://api.example/items", body={"items": [{"id": 1}], "next_cursor": "c2"}),
        har_entry(
            "https://api.example/items?cursor=c2",
            body={"items": [{"id": 2}], "next_cursor": None},
        ),
    )
    assert main(["check", str(path), "--url-filter", "api.example/items"]) == EXIT_OK


def test_a_mismatch_in_a_capture_is_found(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_har(
        tmp_path,
        har_entry("https://api.example/items", body={"items": [], "next_cursor": "c2"}),
        har_entry(
            "https://api.example/items?cursor=WRONG",
            body={"items": [], "next_cursor": None},
        ),
    )
    assert main(["check", str(path), "--url-filter", "api.example"]) == EXIT_VIOLATIONS

    out = capsys.readouterr().out
    assert "CURSOR_CONTINUATION_MISMATCH" in out
    assert "SUPERSECRET" not in out


def test_page_numbers_in_the_evidence_refer_to_the_filtered_sequence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """After --url-filter drops the noise, page 0 must mean the first API call."""
    path = write_har(
        tmp_path,
        har_entry("https://cdn.example/a.png"),
        har_entry("https://cdn.example/b.png"),
        har_entry("https://api.example/items", body={"items": [], "next_cursor": "c2"}),
        har_entry("https://api.example/items?cursor=NO", body={"items": [], "next_cursor": None}),
    )
    main(["check", str(path), "--url-filter", "api.example"])

    out = capsys.readouterr().out
    assert "2 pages" in out
    assert "page[0].response.next_cursor" in out
    assert "page[1].request.cursor" in out


def test_the_link_preset_follows_rel_next(tmp_path: Path) -> None:
    path = write_har(
        tmp_path,
        har_entry(
            "https://api.example/items",
            body={"items": [{"id": 1}]},
            link='<https://api.example/items?page=2>; rel="next"',
        ),
        har_entry("https://api.example/items?page=2", body={"items": [{"id": 2}]}),
    )
    assert main(["check", str(path), "--preset", "link", "--url-filter", "api.example"]) == EXIT_OK


def test_the_link_preset_notices_a_request_that_ignored_the_header(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_har(
        tmp_path,
        har_entry(
            "https://api.example/items",
            body={"items": [{"id": 1}]},
            link='<https://api.example/items?page=2>; rel="next"',
        ),
        har_entry("https://api.example/items?page=9", body={"items": [{"id": 2}]}),
    )
    assert (
        main(["check", str(path), "--preset", "link", "--url-filter", "api.example"])
        == EXIT_VIOLATIONS
    )
    assert "CURSOR_CONTINUATION_MISMATCH" in capsys.readouterr().out


def test_a_link_url_differing_only_in_parameter_order_is_not_a_mismatch(tmp_path: Path) -> None:
    """Canonicalization keeps PageTrace from claiming a mismatch that is not one."""
    path = write_har(
        tmp_path,
        har_entry(
            "https://api.example/items",
            body={"items": []},
            link='<https://API.example/items?b=2&a=1>; rel="next"',
        ),
        har_entry("https://api.example/items?a=1&b=2", body={"items": []}),
    )
    assert main(["check", str(path), "--preset", "link", "--url-filter", "api.example"]) == EXIT_OK


def test_a_malformed_har_is_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "broken.har"
    path.write_text('{"log": {"entries": "nope"}}', encoding="utf-8")

    assert main(["check", str(path)]) == EXIT_USAGE
    assert "log.entries is missing" in capsys.readouterr().err


def test_the_json_report_names_the_input_format(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_har(tmp_path, har_entry("https://api.example/i", body={"items": []}))
    main(["check", str(path), "--format", "json"])

    report: Any = json.loads(capsys.readouterr().out)
    assert report["input"]["format"] == "har"


def preflight(url: str) -> Any:
    """A CORS preflight, as a browser records it: same URL, same query, 204, no body."""
    return {
        "request": {"method": "OPTIONS", "url": url, "headers": []},
        "response": {"status": 204, "headers": [], "content": {}},
    }


def test_cors_preflights_are_not_pages(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A preflight repeats the URL of the request after it, and used to read as a stall."""
    first = "https://api.example.com/v1/items"
    second = "https://api.example.com/v1/items?cursor=c2"
    path = write_har(
        tmp_path,
        preflight(first),
        har_entry(first, body={"items": [{"id": 1}], "next_cursor": "c2"}),
        preflight(second),
        har_entry(second, body={"items": [{"id": 2}], "next_cursor": None}),
    )

    assert main(["check", str(path), "--url-filter", "api.example.com"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "2 pages" in out
    assert "CURSOR_STALLED" not in out


def test_a_failed_request_is_reported_as_unchecked(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Silence about a page nobody could read used to look like a clean result."""
    path = write_har(
        tmp_path,
        har_entry("https://api.example.com/v1/items", body={"items": [], "next_cursor": "c2"}),
        har_entry("https://api.example.com/v1/items?cursor=c2", status=503),
        har_entry("https://api.example.com/v1/items?cursor=c9", body={"items": []}),
    )

    assert main(["check", str(path), "--url-filter", "api.example.com"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "REQUESTS_EXCLUDED_FROM_ANALYSIS" in out
    assert "1 of 3 requests" in out
