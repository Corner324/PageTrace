"""The JSON report is a public contract: it must always match the published schema."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from tests.factories import page, trace

from pagetrace.cli import EXIT_VIOLATIONS, main
from pagetrace.model import Certainty, Evidence, Finding, Severity
from pagetrace.render.json import SCHEMA_VERSION, build_report, render_json

SCHEMA_PATH = Path("specs/formats/report-json-v1.schema.json")


class Validator:
    """Thin typed wrapper: jsonschema ships no complete type information."""

    def __init__(self, schema_path: Path) -> None:
        schema: Any = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)  # pyright: ignore[reportUnknownMemberType]
        self._validator: Any = jsonschema.Draft202012Validator(schema)

    def validate(self, report: dict[str, Any]) -> None:
        self._validator.validate(report)


@pytest.fixture(scope="module")
def validator() -> Validator:
    return Validator(SCHEMA_PATH)


def finding(certainty: Certainty = Certainty.PROVEN, value: object = "abc") -> Finding:
    return Finding(
        code="CURSOR_CONTINUATION_MISMATCH",
        invariant="INV-CURSOR-001",
        certainty=certainty,
        severity=Severity.ERROR,
        message="Page 1 was requested with a continuation token that page 0 did not return.",
        affected_pages=(0, 1),
        evidence=(Evidence("page[0].response.next_cursor", value),),  # pyright: ignore[reportArgumentType]
    )


def test_empty_report_matches_the_schema(validator: Validator) -> None:
    validator.validate(build_report(trace(page(0)), []))


def test_populated_report_matches_the_schema(
    validator: Validator,
) -> None:
    findings = [
        finding(Certainty.PROVEN),
        finding(Certainty.SUSPICIOUS),
        finding(Certainty.INSUFFICIENT_EVIDENCE),
    ]
    validator.validate(build_report(trace(page(0), page(1)), findings))


@pytest.mark.parametrize("value", ["abc", 5, 5.5, True, None, "x" * 500, "a\x1bb"])
def test_every_evidence_value_shape_matches_the_schema(validator: Validator, value: object) -> None:
    validator.validate(build_report(trace(page(0)), [finding(value=value)]))


def test_summary_counts_and_exit_code() -> None:
    report = build_report(
        trace(page(0)),
        [finding(Certainty.PROVEN), finding(Certainty.SUSPICIOUS)],
    )
    assert report["summary"] == {
        "proven": 1,
        "suspicious": 1,
        "insufficient_evidence": 0,
        "exit_code": 1,
    }


def test_exit_code_zero_without_a_proven_finding() -> None:
    report = build_report(trace(page(0)), [finding(Certainty.SUSPICIOUS)])
    assert report["summary"]["exit_code"] == 0


def test_schema_version_is_declared() -> None:
    assert build_report(trace(page(0)), [])["schema_version"] == SCHEMA_VERSION


def test_input_block_describes_the_trace() -> None:
    report = build_report(trace(page(0), page(1), preset="offset"), [])
    assert report["input"] == {"format": "jsonl", "preset": "offset", "page_count": 2}


def test_long_values_are_truncated_and_the_true_length_reported() -> None:
    report = build_report(trace(page(0)), [finding(value="x" * 500)])
    evidence = report["findings"][0]["evidence"][0]
    assert evidence["truncated"] is True
    assert evidence["length"] == 500
    assert len(evidence["value"]) < 500


def test_short_values_carry_no_truncation_noise() -> None:
    evidence = build_report(trace(page(0)), [finding()])["findings"][0]["evidence"][0]
    assert set(evidence) == {"path", "value"}


def test_types_survive_the_round_trip() -> None:
    for value in (5, 5.5, True, None):
        report = build_report(trace(page(0)), [finding(value=value)])
        assert report["findings"][0]["evidence"][0]["value"] == value


def test_rendered_json_is_stable_and_parses() -> None:
    rendered = render_json(trace(page(0)), [finding()])
    assert rendered.endswith("\n")
    assert json.loads(rendered) == build_report(trace(page(0)), [finding()])
    assert rendered == render_json(trace(page(0)), [finding()])


def test_cli_json_output_validates(
    tmp_path: Path, validator: Validator, capsys: pytest.CaptureFixture[str]
) -> None:
    records: list[dict[str, Any]] = [
        {
            "v": 1,
            "request": {"url": "https://api.example/i"},
            "response": {"status": 200, "body": {"items": [], "next_cursor": "a"}},
        },
        {
            "v": 1,
            "request": {"url": "https://api.example/i?cursor=WRONG"},
            "response": {"status": 200, "body": {"items": [], "next_cursor": None}},
        },
    ]
    path = tmp_path / "trace.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")

    assert main(["check", str(path), "--format", "json"]) == EXIT_VIOLATIONS
    report: Any = json.loads(capsys.readouterr().out)
    validator.validate(report)
    assert report["findings"][0]["code"] == "CURSOR_CONTINUATION_MISMATCH"
    assert report["summary"]["exit_code"] == EXIT_VIOLATIONS
