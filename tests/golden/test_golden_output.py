"""Golden output for the three renderers.

Snapshots are kept for renderers only, and only over the two committed example traces. They
catch accidental changes to text a person or a CI parser reads. They are deliberately not used
for internal state: a snapshot of the whole model turns every refactor into a diff review.

Regenerate deliberately, never reflexively:

    PAGETRACE_UPDATE_GOLDEN=1 uv run pytest tests/golden
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from pagetrace import __version__
from pagetrace.cli import EXIT_OK, EXIT_VIOLATIONS, main

GOLDEN = Path("tests/golden")
EXAMPLES = Path("examples")
CASES = [
    ("clean-cursor", EXIT_OK),
    ("broken-cursor", EXIT_VIOLATIONS),
]
FORMATS = ["terminal", "json", "junit"]
SUFFIX = {"terminal": "txt", "json": "json", "junit": "xml"}


VERSION_PLACEHOLDER = "X.Y.Z"


def normalize(text: str) -> str:
    """A release number is not part of what these snapshots are for."""
    return text.replace(__version__, VERSION_PLACEHOLDER)


def compare(rendered: str, golden: Path) -> None:
    actual = normalize(rendered)
    if os.environ.get("PAGETRACE_UPDATE_GOLDEN"):
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_text(actual, encoding="utf-8")
        pytest.skip(f"updated {golden}")
    assert golden.exists(), f"{golden} is missing; run with PAGETRACE_UPDATE_GOLDEN=1"
    assert actual == golden.read_text(encoding="utf-8")


@pytest.mark.parametrize(("name", "expected_exit"), CASES)
@pytest.mark.parametrize("output_format", FORMATS)
def test_rendered_output_matches_the_golden_file(
    name: str,
    expected_exit: int,
    output_format: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        [
            "check",
            str(EXAMPLES / f"{name}.jsonl"),
            "--total",
            "$.total",
            "--format",
            output_format,
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == expected_exit
    assert captured.err == ""
    compare(captured.out, GOLDEN / f"{name}.{SUFFIX[output_format]}")


@pytest.mark.parametrize(("name", "expected_exit"), CASES)
def test_the_json_golden_file_is_still_valid_json(name: str, expected_exit: int) -> None:
    """A snapshot that stopped parsing would otherwise pass as "unchanged"."""
    report = json.loads((GOLDEN / f"{name}.json").read_text(encoding="utf-8"))
    assert report["schema_version"] == 1
    assert report["summary"]["exit_code"] == expected_exit


def test_the_readme_commands_still_work(capsys: pytest.CaptureFixture[str]) -> None:
    """The examples README tells people to run exactly this."""
    assert main(["check", str(EXAMPLES / "clean-cursor.jsonl"), "--total", "$.total"]) == EXIT_OK
    assert "No findings" in capsys.readouterr().out
