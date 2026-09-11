"""The CLI as a user meets it: exit codes, streams, no traceback, deterministic output."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from pagetrace import __version__
from pagetrace.cli import EXIT_OK, EXIT_USAGE, EXIT_VIOLATIONS, main


def record(seq: int, cursor: str | None, next_cursor: Any, items: list[int]) -> dict[str, Any]:
    query = f"?cursor={cursor}" if cursor is not None else ""
    return {
        "v": 1,
        "seq": seq,
        "request": {"method": "GET", "url": f"https://api.example/items{query}"},
        "response": {
            "status": 200,
            "body": {"items": [{"id": i} for i in items], "next_cursor": next_cursor},
        },
    }


def write_trace(tmp_path: Path, *records: dict[str, Any]) -> Path:
    path = tmp_path / "trace.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def clean_trace(tmp_path: Path) -> Path:
    return write_trace(
        tmp_path,
        record(0, None, "c1", [1, 2]),
        record(1, "c1", "c2", [3, 4]),
        record(2, "c2", None, [5]),
    )


@pytest.fixture
def broken_trace(tmp_path: Path) -> Path:
    return write_trace(
        tmp_path,
        record(0, None, "c1", [1, 2]),
        record(1, "WRONG", "c2", [3, 4]),
        record(2, "c2", None, [5]),
    )


def test_clean_trace_exits_zero(clean_trace: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check", str(clean_trace)]) == EXIT_OK
    out = capsys.readouterr().out
    assert "No findings" in out
    assert "0 proven" in out


def test_proven_violation_exits_one(broken_trace: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check", str(broken_trace)]) == EXIT_VIOLATIONS
    out = capsys.readouterr().out
    assert "CURSOR_CONTINUATION_MISMATCH" in out
    assert "INV-CURSOR-001" in out
    assert "1 proven" in out


def test_report_shows_the_evidence(broken_trace: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["check", str(broken_trace)])
    out = capsys.readouterr().out
    assert 'page[0].response.next_cursor = "c1"' in out
    assert 'page[1].request.cursor = "WRONG"' in out


def test_output_is_deterministic(broken_trace: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["check", str(broken_trace)])
    first = capsys.readouterr().out
    main(["check", str(broken_trace)])
    assert capsys.readouterr().out == first


def test_output_file(broken_trace: Path, tmp_path: Path) -> None:
    destination = tmp_path / "report.txt"
    assert main(["check", str(broken_trace), "--output", str(destination)]) == EXIT_VIOLATIONS
    assert "CURSOR_CONTINUATION_MISMATCH" in destination.read_text(encoding="utf-8")


def test_unwritable_output_is_a_usage_error(
    clean_trace: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    destination = tmp_path / "missing-dir" / "report.txt"
    assert main(["check", str(clean_trace), "--output", str(destination)]) == EXIT_USAGE
    assert "cannot write" in capsys.readouterr().err


def test_missing_file_is_a_usage_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check", str(tmp_path / "nope.jsonl")]) == EXIT_USAGE
    assert capsys.readouterr().err.startswith("pagetrace: ")


def test_bad_selector_is_a_usage_error(
    clean_trace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["check", str(clean_trace), "--next", "$.[[bad"]) == EXIT_USAGE
    assert "--next" in capsys.readouterr().err


def test_url_filter_selecting_nothing_is_a_usage_error(
    clean_trace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["check", str(clean_trace), "--url-filter", "nothing"]) == EXIT_USAGE
    assert "no requests left" in capsys.readouterr().err


def test_url_filter_keeps_matching_requests(
    clean_trace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["check", str(clean_trace), "--url-filter", "api.example"]) == EXIT_OK
    assert "3 pages" in capsys.readouterr().out


def test_selector_flags_override_the_preset(tmp_path: Path) -> None:
    path = write_trace(
        tmp_path,
        {
            "v": 1,
            "request": {"url": "https://api.example/i?after=a"},
            "response": {"status": 200, "body": {"paging": {"after": "b"}}},
        },
        {
            "v": 1,
            "request": {"url": "https://api.example/i?after=WRONG"},
            "response": {"status": 200, "body": {"paging": {"after": None}}},
        },
    )
    assert main(["check", str(path), "--cursor", "$.query.after"]) == EXIT_OK
    assert (
        main(["check", str(path), "--cursor", "$.query.after", "--next", "$.paging.after"])
        == EXIT_VIOLATIONS
    )


def test_secrets_never_reach_the_report(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = write_trace(
        tmp_path,
        {
            "v": 1,
            "request": {
                "url": "https://api.example/i",
                "headers": {"Authorization": "Bearer SUPERSECRET"},
            },
            "response": {
                "status": 200,
                "headers": {"Set-Cookie": "session=SUPERSECRET"},
                "body": {"items": [], "next_cursor": "a", "token": "SUPERSECRET"},
            },
        },
        {
            "v": 1,
            "request": {"url": "https://api.example/i?cursor=WRONG"},
            "response": {"status": 200, "body": {"items": [], "next_cursor": None}},
        },
    )
    main(["check", str(path)])
    captured = capsys.readouterr()
    assert "CURSOR_CONTINUATION_MISMATCH" in captured.out
    assert "SUPERSECRET" not in captured.out
    assert "SUPERSECRET" not in captured.err


def test_control_characters_in_a_cursor_are_escaped(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_trace(
        tmp_path,
        record(0, None, "esc[31mred", [1]),
        record(1, "WRONG", None, [2]),
    )
    main(["check", str(path)])
    out = capsys.readouterr().out
    assert "" not in out
    assert "\\x1b" in out


def test_module_entry_point_never_prints_a_traceback(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "pagetrace", "check", str(tmp_path / "nope.jsonl")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == EXIT_USAGE
    assert "Traceback" not in proc.stderr


def test_help_lists_preset_defaults(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["check", "--help"])
    out = capsys.readouterr().out
    assert "$.query.cursor" in out
    assert "--has-more" in out


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == EXIT_OK
    assert capsys.readouterr().out.strip() == f"pagetrace {__version__}"


def test_junit_output_reaches_ci(broken_trace: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check", str(broken_trace), "--format", "junit"]) == EXIT_VIOLATIONS
    out = capsys.readouterr().out

    assert out.startswith('<?xml version="1.0" encoding="utf-8"?>')
    assert '<testsuite name="pagetrace"' in out
    assert 'name="INV-CURSOR-001"' in out
    assert "<failure" in out


def test_junit_of_a_clean_trace_has_no_failures(
    clean_trace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["check", str(clean_trace), "--format", "junit"]) == EXIT_OK
    assert 'failures="0"' in capsys.readouterr().out
